"""Explicit demo-instance impersonation with revocable server-side authority."""
import hmac
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_actor, require_origin
from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.pagination import safe_offset
from app.core.security import hash_token, new_token, normalize_email, verify_password
from app.db.session import get_session
from app.models import AuditEvent, DevAccessGrant, SessionRecord, User

from . import service
from .rate_limit import check_rate_limit

router = APIRouter(prefix="/dev-tools", tags=["demo role testing"])
Database = Annotated[Session, Depends(get_session)]
GRANT_SECONDS = 1800
CONFIGURATION_READY = False


class Unlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=1024, repr=False)


class Switch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID


def enabled():
    s = get_settings()
    return CONFIGURATION_READY and s.dev_tools_enabled and s.demo_instance and s.dev_password_hash.startswith("$argon2")


def deny():
    raise DomainError("DEV_ACCESS_DENIED", "Unlock role testing with your administrator account.", 403)


def available():
    if not enabled():
        raise DomainError("NOT_FOUND", "Record not found.", 404)


def audit(db, grant, action, target=None, **details):
    db.add(AuditEvent(actor_user_id=grant.operator_admin_id, entity_type="DEV_ACCESS_GRANT",
        entity_id=grant.id, action=action, redacted_details={
            "operator_id": str(grant.operator_admin_id),
            "target_user_id": str(target) if target else None,
            **details,
        }))


def lock_users(db, identifiers):
    """Global identity lock order: sorted Users -> Grant -> source/linked Sessions."""
    identifiers = set(identifiers)
    if identifiers:
        db.scalars(select(User).where(User.id.in_(identifiers)).order_by(User.id)
            .with_for_update().execution_options(populate_existing=True)).all()


def lock_request_users(db, request, *, additional=(), login_email=None):
    identifiers = set(additional)
    raw = request.cookies.get(get_settings().dev_grant_cookie_name, "")
    operator_id = db.scalar(select(DevAccessGrant.operator_admin_id).where(
        DevAccessGrant.token_hash == hash_token(raw))) if raw else None
    if operator_id:
        identifiers.add(operator_id)
    current = db.execute(select(SessionRecord.user_id, SessionRecord.dev_grant_id).where(
        SessionRecord.token_hash == hash_token(request.cookies.get(
            get_settings().session_cookie_name, "")))).first()
    if current:
        identifiers.add(current.user_id)
        if current.dev_grant_id:
            linked_operator = db.scalar(select(DevAccessGrant.operator_admin_id).where(
                DevAccessGrant.id == current.dev_grant_id))
            if linked_operator:
                identifiers.add(linked_operator)
    if login_email:
        target_id = db.scalar(select(User.id).where(User.normalized_email == normalize_email(login_email)))
        if target_id:
            identifiers.add(target_id)
    lock_users(db, identifiers)


def lock_active_operators(db):
    candidates = db.execute(select(DevAccessGrant.id, DevAccessGrant.operator_admin_id).where(
        DevAccessGrant.revoked_at.is_(None))).all()
    lock_users(db, (operator_id for _, operator_id in candidates))
    return [identifier for identifier, _ in candidates]


def authority(db, grant, *, locked=False):
    now = get_clock().now()
    source_query = select(SessionRecord).where(SessionRecord.id == grant.original_session_id)
    if locked:
        source_query = source_query.with_for_update()
    original = db.scalar(source_query.execution_options(populate_existing=True))
    operator = db.scalar(select(User).where(User.id == grant.operator_admin_id)
                         .execution_options(populate_existing=True))
    if (not enabled() or grant.revoked_at is not None or grant.expires_at <= now
        or not hmac.compare_digest(grant.credential_fingerprint, hash_token(get_settings().dev_password_hash))
        or original is None or original.dev_grant_id is not None
        or original.user_id != grant.operator_admin_id or original.revoked_at is not None
        or original.expires_at <= now or operator is None or not operator.active or operator.role != "ADMIN"):
        deny()
    return operator, original


def grant_context(db, request, *, lock=False, write=False, additional_users=()):
    available()
    if lock:
        lock_request_users(db, request, additional=additional_users)
    raw = request.cookies.get(get_settings().dev_grant_cookie_name, "")
    statement = select(DevAccessGrant).where(DevAccessGrant.token_hash == hash_token(raw))
    grant = db.scalar((statement.with_for_update() if lock else statement)
                      .execution_options(populate_existing=True))
    if not raw or grant is None:
        deny()
    authority(db, grant, locked=lock)
    current = db.scalar(select(SessionRecord).where(SessionRecord.token_hash == hash_token(
        request.cookies.get(get_settings().session_cookie_name, ""))))
    user = db.get(User, current.user_id) if current else None
    if (current is None or current.revoked_at is not None or current.expires_at <= get_clock().now()
        or user is None or not user.active
        or (current.id != grant.original_session_id and current.dev_grant_id != grant.id)):
        deny()
    if write:
        require_origin(request)
        csrf = request.headers.get("x-dev-csrf-token", "")
        if not csrf or not hmac.compare_digest(csrf, grant.dev_csrf):
            raise DomainError("INVALID_DEV_CSRF", "Refresh role testing and try again.", 403)
    return grant, current, user


def validate_linked(db, request, session):
    try:
        grant, current, _ = grant_context(db, request)
        if current.id != session.id or grant.id != session.dev_grant_id:
            deny()
    except DomainError as error:
        operator_id = db.scalar(select(DevAccessGrant.operator_admin_id).where(
            DevAccessGrant.id == session.dev_grant_id))
        lock_request_users(db, request, additional=(operator_id,) if operator_id else ())
        grant = db.scalar(select(DevAccessGrant).where(DevAccessGrant.id == session.dev_grant_id)
            .with_for_update().execution_options(populate_existing=True))
        if grant is not None and grant.revoked_at is None:
            revoke(db, grant)
            audit(db, grant, "DEV_AUTHORITY_INVALIDATED", session.user_id)
            db.commit()
        raise DomainError("DEV_SESSION_EXPIRED", "Role testing ended. Sign in again.", 401) from error
    request.state.dev_audit = {"grant_id": grant.id, "operator_id": grant.operator_admin_id,
                               "target_id": session.user_id}


def status_data(db, request):
    if not enabled():
        return {"enabled": False, "unlocked": False}
    try:
        grant, _, target = grant_context(db, request)
    except DomainError:
        return {"enabled": True, "unlocked": False}
    operator = db.get(User, grant.operator_admin_id)
    return {"enabled": True, "unlocked": True, "dev_csrf_token": grant.dev_csrf,
            "expires_at": grant.expires_at.isoformat(),
            "operator": {"id": str(operator.id), "name": operator.display_name},
            "target": service.actor_data(target)}


def revoke(db, grant):
    grant.revoked_at = get_clock().now()
    db.execute(update(SessionRecord).where(SessionRecord.dev_grant_id == grant.id,
        SessionRecord.revoked_at.is_(None)).values(revoked_at=grant.revoked_at))


def terminate_request_grant(db, request, *, revoke_original=True):
    lock_request_users(db, request)
    raw = request.cookies.get(get_settings().dev_grant_cookie_name, "")
    linked_id = db.scalar(select(SessionRecord.dev_grant_id).where(
        SessionRecord.token_hash == hash_token(request.cookies.get(
            get_settings().session_cookie_name, ""))))
    filters = [DevAccessGrant.token_hash == hash_token(raw)] if raw else []
    if linked_id:
        filters.append(DevAccessGrant.id == linked_id)
    if not filters:
        return
    grants = db.scalars(select(DevAccessGrant).where(or_(*filters)).order_by(DevAccessGrant.id)
        .with_for_update().execution_options(populate_existing=True)).all()
    if revoke_original:
        db.scalars(select(SessionRecord).where(SessionRecord.id.in_(
            [grant.original_session_id for grant in grants])).order_by(SessionRecord.id)
            .with_for_update().execution_options(populate_existing=True)).all()
    for grant in grants:
        if grant.revoked_at is None:
            revoke(db, grant)
            audit(db, grant, "DEV_CONTEXT_TERMINATED")
        if revoke_original:
            db.execute(update(SessionRecord).where(SessionRecord.id == grant.original_session_id,
                SessionRecord.revoked_at.is_(None)).values(revoked_at=get_clock().now()))


def set_session_cookie(response, raw, seconds):
    s = get_settings()
    response.set_cookie(s.session_cookie_name, raw, max_age=max(0, seconds),
        httponly=True, secure=s.session_cookie_secure, samesite="lax", path="/api")


def clear_grant_cookie(response):
    response.delete_cookie(get_settings().dev_grant_cookie_name, path="/api",
        httponly=True, secure=get_settings().session_cookie_secure, samesite="lax")


@router.get("/status")
def status(request: Request, db: Database):
    return {"data": status_data(db, request)}


@router.post("/unlock")
def unlock(payload: Unlock, request: Request, response: Response, db: Database,
           actor: Annotated[Actor, Depends(require_actor)]):
    available()
    if actor.role != "ADMIN":
        deny()
    check_rate_limit(f"dev-unlock:ip:{request.state.client_ip}", limit=10)
    check_rate_limit(f"dev-unlock:admin:{actor.id}", limit=5)
    if not verify_password(payload.password, get_settings().dev_password_hash):
        with db.begin():
            db.add(AuditEvent(actor_user_id=actor.id, entity_type="DEV_TOOLS",
                entity_id=actor.id, action="DEV_UNLOCK_DENIED", redacted_details={}))
        deny()
    with db.begin():
        lock_request_users(db, request, additional=(actor.id,))
        terminate_request_grant(db, request, revoke_original=False)
        original = db.scalar(select(SessionRecord).where(SessionRecord.id == actor.session_id)
            .with_for_update().execution_options(populate_existing=True))
        operator = db.get(User, actor.id)
        if (original is None or original.dev_grant_id is not None
            or original.revoked_at is not None or original.expires_at <= get_clock().now()
            or original.user_id != actor.id or not operator.active or operator.role != "ADMIN"):
            deny()
        raw = new_token()
        grant = DevAccessGrant(token_hash=hash_token(raw), operator_admin_id=actor.id,
            original_session_id=actor.session_id, dev_csrf=new_token(),
            expires_at=min(get_clock().now() + timedelta(seconds=GRANT_SECONDS), original.expires_at),
            credential_fingerprint=hash_token(get_settings().dev_password_hash))
        db.add(grant)
        db.flush()
        audit(db, grant, "DEV_UNLOCKED", actor.id)
        data = {"enabled": True, "unlocked": True, "dev_csrf_token": grant.dev_csrf,
                "expires_at": grant.expires_at.isoformat(),
                "operator": {"id": str(actor.id), "name": actor.name},
                "target": service.actor_data(db.get(User, actor.id))}
    response.set_cookie(get_settings().dev_grant_cookie_name, raw, max_age=GRANT_SECONDS,
        httponly=True, secure=get_settings().session_cookie_secure, samesite="lax", path="/api")
    return {"data": data}


@router.get("/accounts")
def accounts(request: Request, db: Database,
             page: Annotated[int, Query(ge=1)] = 1,
             page_size: Annotated[int, Query(ge=1, le=100)] = 25,
             q: Annotated[str, Query(max_length=200)] = ""):
    grant_context(db, request)
    filters = [User.active.is_(True)]
    if q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters.append(or_(User.display_name.ilike(f"%{escaped}%", escape="\\"),
                           User.normalized_email.ilike(f"%{escaped}%", escape="\\")))
    total = db.scalar(select(func.count()).select_from(User).where(*filters))
    users = db.scalars(select(User).where(*filters).order_by(User.display_name, User.id)
        .offset(safe_offset(page, page_size)).limit(page_size))
    return {"items": [service.actor_data(u) | {"email": u.normalized_email} for u in users],
            "total": total, "page": page, "page_size": page_size}


@router.post("/switch")
def switch(payload: Switch, request: Request, response: Response, db: Database):
    with db.begin():
        grant, _, _ = grant_context(db, request, lock=True, write=True,
                                    additional_users=(payload.user_id,))
        user = db.get(User, payload.user_id)
        if user is None or not user.active:
            raise DomainError("NOT_FOUND", "Account not found.", 404)
        now = get_clock().now()
        db.execute(update(SessionRecord).where(SessionRecord.dev_grant_id == grant.id,
            SessionRecord.revoked_at.is_(None)).values(revoked_at=now))
        session, raw = service.create_session(db, user)
        session.dev_grant_id = grant.id
        session.expires_at = min(session.expires_at, grant.expires_at)
        audit(db, grant, "DEV_SWITCHED", user.id, target_role=user.role)
        data = {"actor": service.actor_data(user), "csrf_token": session.csrf_token}
    set_session_cookie(response, raw, int((session.expires_at - get_clock().now()).total_seconds()))
    # Request still contains the previous cookie. Target is explicitly overridden.
    data["dev_tools"] = {"enabled": True, "unlocked": True,
        "dev_csrf_token": grant.dev_csrf, "expires_at": grant.expires_at.isoformat(),
        "operator": {"id": str(grant.operator_admin_id), "name": db.get(User, grant.operator_admin_id).display_name},
        "target": data["actor"]}
    return {"data": data}


@router.post("/end")
def end(request: Request, response: Response, db: Database):
    require_origin(request)
    try:
        with db.begin():
            grant, _, _ = grant_context(db, request, lock=True, write=True)
            operator, original = authority(db, grant, locked=True)
            revoke(db, grant)
            original.revoked_at = get_clock().now()
            session, raw = service.create_session(db, operator)
            audit(db, grant, "DEV_ENDED", operator.id)
            data = {"actor": service.actor_data(operator), "csrf_token": session.csrf_token,
                    "dev_tools": {"enabled": enabled(), "unlocked": False}}
    except DomainError as error:
        if error.code not in {"DEV_ACCESS_DENIED", "NOT_FOUND"}:
            raise
        # Expired/disabled authority cannot restore an ordinary admin session.
        with db.begin():
            terminate_request_grant(db, request)
        result = JSONResponse(status_code=401, content={"error": {
            "code": "DEV_SESSION_EXPIRED", "message": "Role testing ended. Sign in again.",
            "fields": {}, "request_id": getattr(request.state, "request_id", ""),
        }})
        result.delete_cookie(get_settings().session_cookie_name, path="/api", httponly=True,
            secure=get_settings().session_cookie_secure, samesite="lax")
        clear_grant_cookie(result)
        return result
    set_session_cookie(response, raw, get_settings().session_ttl_seconds)
    clear_grant_cookie(response)
    return {"data": data}


def revoke_all():
    """Private operator action before toggling flags or rotating credentials."""
    from app.db import session as database
    with database.SessionFactory() as db, db.begin():
        candidate_ids = lock_active_operators(db)
        grants = db.scalars(select(DevAccessGrant).where(
            DevAccessGrant.id.in_(candidate_ids), DevAccessGrant.revoked_at.is_(None)).order_by(DevAccessGrant.id).with_for_update()).all()
        for grant in grants:
            revoke(db, grant)
            audit(db, grant, "DEV_OPERATOR_REVOKED")
        return len(grants)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Revoke every demo role-testing grant.")
    parser.add_argument("--revoke-all", action="store_true", required=True)
    parser.parse_args()
    print({"revoked_grants": revoke_all()})


def reconcile_configuration():
    """Reconcile persisted authority before any demo grants are usable at boot.

    An unavailable/unmigrated database leaves demo tools disabled; normal API
    readiness continues to report its own migration/database failure safely.
    """
    global CONFIGURATION_READY
    CONFIGURATION_READY = False
    from app.db import session as database
    try:
        with database.SessionFactory() as db, db.begin():
            versions = db.scalars(text("SELECT version_num FROM alembic_version")).all()
            if versions != ["0003"]:
                return
            s = get_settings()
            configured = s.dev_tools_enabled and s.demo_instance and s.dev_password_hash.startswith("$argon2")
            fingerprint = hash_token(s.dev_password_hash)
            candidate_ids = lock_active_operators(db)
            for grant in db.scalars(select(DevAccessGrant).where(
                DevAccessGrant.id.in_(candidate_ids), DevAccessGrant.revoked_at.is_(None)).order_by(DevAccessGrant.id).with_for_update()):
                if not configured or grant.credential_fingerprint != fingerprint:
                    revoke(db, grant)
                    audit(db, grant, "DEV_CONFIGURATION_REVOKED")
    except SQLAlchemyError:
        # Fail closed for developer tools; never log SQL/URLs/credential material.
        return
    CONFIGURATION_READY = True
