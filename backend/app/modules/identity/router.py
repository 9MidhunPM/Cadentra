"""Account, session and staff/customer endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_actor, require_origin, require_role
from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.pagination import safe_offset
from app.core.security import hash_password, hash_token, normalize_email
from app.db.session import get_session
from app.models import Customer, SessionRecord, User

from . import schemas, service
from .rate_limit import check_rate_limit

router = APIRouter(tags=["identity"])
Database = Annotated[Session, Depends(get_session)]
Authenticated = Annotated[Actor, Depends(require_actor)]
Operator = Annotated[Actor, Depends(require_role("ADMIN", "STAFF"))]
Admin = Annotated[Actor, Depends(require_role("ADMIN"))]


def public_write(request: Request, category: str, account: str = "") -> None:
    require_origin(request)
    address = request.state.client_ip
    check_rate_limit(f"{category}:ip:{address}")
    if account:
        check_rate_limit(f"{category}:account:{hash_token(normalize_email(account))}", limit=10)


def email_conflict(exc: IntegrityError) -> None:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint == "uq_users_normalized_email":
        raise DomainError(
            "EMAIL_EXISTS", "An account with this email already exists.", status_code=409
        ) from exc
    raise exc


@router.post("/auth/signup", status_code=201)
def signup(payload: schemas.Signup, request: Request, db: Database):
    public_write(request, "signup", str(payload.email))
    try:
        with db.begin():
            user = service.create_customer_user(
                db, payload.name, str(payload.email), payload.password
            )
            result = service.actor_data(user)
    except IntegrityError as exc:
        email_conflict(exc)
    return {"data": result}


@router.post("/auth/login")
def login(payload: schemas.Login, request: Request, response: Response, db: Database):
    public_write(request, "login", str(payload.email))
    with db.begin():
        user = service.authenticate(db, str(payload.email), payload.password)
        session, raw = service.create_session(db, user)
        result = {"actor": service.actor_data(user), "csrf_token": session.csrf_token}
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        raw,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/api",
    )
    return {"data": result}


@router.get("/auth/session")
def session(actor: Authenticated):
    return {
        "data": {
            "actor": {
                "id": str(actor.id),
                "name": actor.name,
                "role": actor.role,
                "customer_id": str(actor.customer_id) if actor.customer_id else None,
            },
            "csrf_token": actor.csrf_token,
        }
    }


@router.post("/auth/logout")
def logout(response: Response, actor: Authenticated, db: Database):
    with db.begin():
        record = db.get(SessionRecord, actor.session_id)
        if record is not None:
            record.revoked_at = get_clock().now()
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/api",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return {"data": {"logged_out": True}}


@router.post("/auth/password-reset/request", status_code=202)
def request_reset(payload: schemas.ResetRequest, request: Request, db: Database):
    public_write(request, "reset-request", str(payload.email))
    with db.begin():
        service.request_reset(db, str(payload.email))
    # Same response whether the email exists or an outbox entry was queued.
    return {"data": {"message": "If this address is registered, a reset link will be sent."}}


@router.post("/auth/password-reset/confirm")
def confirm_reset(payload: schemas.ResetConfirm, request: Request, db: Database):
    public_write(request, "reset-confirm")
    with db.begin():
        service.consume_reset(db, payload.token, payload.new_password)
    return {"data": {"password_reset": True}}


@router.post("/staff", status_code=201)
def create_staff(payload: schemas.CreateStaff, actor: Admin, db: Database):
    try:
        with db.begin():
            user = User(
                display_name=payload.name,
                normalized_email=normalize_email(str(payload.email)),
                password_hash=hash_password(payload.temporary_password),
                role="STAFF",
            )
            db.add(user)
            db.flush()
            result = service.actor_data(user)
    except IntegrityError as exc:
        email_conflict(exc)
    return {"data": result}


@router.get("/customers")
def list_customers(
    actor: Operator,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    q: Annotated[str | None, Query(max_length=200)] = None,
):
    offset = safe_offset(page, page_size)
    filters = []
    if q:
        # Escape wildcard characters: search text cannot turn into an unbounded wildcard query.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters.append(
            or_(
                Customer.display_name.ilike(f"%{escaped}%", escape="\\"),
                Customer.email.ilike(f"%{escaped}%", escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(Customer).where(*filters))
    rows = db.scalars(
        select(Customer)
        .where(*filters)
        .order_by(Customer.created_at.desc(), Customer.id.desc())
        .offset(offset)
        .limit(page_size)
    ).all()
    return {
        "items": [service.customer_data(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/customers", status_code=201)
def create_customer(payload: schemas.CustomerWrite, actor: Operator, db: Database):
    with db.begin():
        customer = Customer(
            **payload.model_dump(exclude={"email"}), email=normalize_email(str(payload.email))
        )
        db.add(customer)
        db.flush()
        result = service.customer_data(customer)
    return {"data": result}


@router.get("/customers/{customer_id}")
def read_customer(customer_id: UUID, actor: Operator, db: Database):
    return {"data": service.customer_data(service.get_customer(db, customer_id))}


@router.patch("/customers/{customer_id}")
def edit_customer(customer_id: UUID, payload: schemas.CustomerPatch, actor: Operator, db: Database):
    changes = payload.model_dump(exclude_unset=True)
    if any(
        changes.get(field, "absent") is None
        for field in ("display_name", "email", "billing_address")
    ):
        raise DomainError(
            "INVALID_CUSTOMER", "Required customer fields cannot be null.", status_code=422
        )
    with db.begin():
        customer = service.get_customer(db, customer_id)
        for name, value in changes.items():
            setattr(customer, name, normalize_email(str(value)) if name == "email" else value)
        db.flush()
        result = service.customer_data(customer)
    return {"data": result}
