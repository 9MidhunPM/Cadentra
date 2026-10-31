import hmac
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import hash_token
from app.db import session as database
from app.models import SessionRecord, User


class Role(StrEnum):
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


@dataclass(frozen=True)
class Actor:
    id: UUID
    role: Role | str
    customer_id: UUID | None = None
    name: str = ""
    csrf_token: str = field(default="", repr=False)
    session_id: UUID | None = field(default=None, repr=False)


def require_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin or origin not in get_settings().allowed_origins:
        raise DomainError("FORBIDDEN_ORIGIN", "Request origin is not permitted.", 403)


def get_auth_session() -> Iterator[Session]:
    # Separate from the business session so auth reads cannot begin its transaction.
    with database.SessionFactory() as session:
        yield session


def require_actor(request: Request, db: Annotated[Session, Depends(get_auth_session)]) -> Actor:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise DomainError("UNAUTHENTICATED", "Sign in to continue.", 401)
    row = db.execute(
        select(SessionRecord, User)
        .join(User, User.id == SessionRecord.user_id)
        .where(SessionRecord.token_hash == hash_token(token))
    ).first()
    if row is None:
        raise DomainError("UNAUTHENTICATED", "Session is invalid or expired.", 401)
    session, user = row
    if not user.active or session.revoked_at is not None or session.expires_at <= get_clock().now():
        raise DomainError("UNAUTHENTICATED", "Session is invalid or expired.", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not hmac.compare_digest(
            csrf.encode("utf-8"), session.csrf_token.encode("utf-8")
        ):
            raise DomainError("INVALID_CSRF", "Refresh the session and try again.", 403)
    return Actor(
        user.id,
        Role(user.role),
        user.customer_id,
        user.display_name,
        session.csrf_token,
        session.id,
    )


def require_role(*roles: Role | str):
    allowed = frozenset(str(role) for role in roles)

    def dependency(actor: Annotated[Actor, Depends(require_actor)]) -> Actor:
        if actor.role not in allowed:
            raise DomainError("FORBIDDEN", "Your role cannot perform this action.", 403)
        return actor

    return dependency


def require_customer_ownership(actor: Actor, customer_id: UUID) -> None:
    if actor.role == Role.CUSTOMER and actor.customer_id != customer_id:
        raise DomainError("NOT_FOUND", "Record not found.", 404)
