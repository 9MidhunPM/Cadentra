"""Identity operations. The caller owns each database transaction."""

from datetime import timedelta
from functools import lru_cache
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import hash_password, hash_token, new_token, normalize_email, verify_password
from app.models import Customer, EmailOutbox, PasswordResetToken, SessionRecord, User


def actor_data(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.display_name,
        "role": user.role,
        "customer_id": str(user.customer_id) if user.customer_id else None,
    }


def customer_data(customer: Customer) -> dict:
    return {
        "id": str(customer.id),
        "display_name": customer.display_name,
        "email": customer.email,
        "company_name": customer.company_name,
        "billing_address": customer.billing_address,
        "created_at": customer.created_at,
    }


def create_customer_user(db: Session, name: str, email: str, password: str) -> User:
    # Always create a new customer: matching an unverified email never grants ownership.
    encoded = hash_password(password)
    customer = Customer(display_name=name, email=normalize_email(email))
    db.add(customer)
    db.flush()
    user = User(
        display_name=name,
        normalized_email=normalize_email(email),
        password_hash=encoded,
        role="CUSTOMER",
        customer_id=customer.id,
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(
        select(User).where(User.normalized_email == normalize_email(email)).with_for_update()
    )
    if user is None:
        # Verify a fixed dummy hash to avoid a cheap user-existence timing distinction.
        verify_password(password, _cached_dummy_hash())
    if user is None or not verify_password(password, user.password_hash) or not user.active:
        raise DomainError("INVALID_CREDENTIALS", "Invalid email or password.", status_code=401)
    return user


@lru_cache(maxsize=1)
def _cached_dummy_hash() -> str:
    return hash_password("Unused-Dummy-Password-Aa!")


def create_session(db: Session, user: User) -> tuple[SessionRecord, str]:
    raw = new_token()
    record = SessionRecord(
        user_id=user.id,
        token_hash=hash_token(raw),
        csrf_token=new_token(),
        expires_at=get_clock().now() + timedelta(seconds=get_settings().session_ttl_seconds),
    )
    db.add(record)
    db.flush()
    return record, raw


def request_reset(db: Session, email: str) -> None:
    user = db.scalar(
        select(User)
        .where(User.normalized_email == normalize_email(email), User.active.is_(True))
        .with_for_update()
    )
    if user is None:
        return
    raw = new_token()
    now = get_clock().now()
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=now + timedelta(seconds=get_settings().reset_token_ttl_seconds),
    )
    db.add(reset)
    db.flush()
    db.add(
        EmailOutbox(
            kind="RESET",
            aggregate_id=user.id,
            recipient=user.normalized_email,
            subject="Reset your Cadentra password",
            dedupe_key=f"reset:{reset.id}",
            payload={
                "reset_url": f"{get_settings().app_origin.rstrip('/')}/reset-password?token={raw}"
            },
            next_attempt_at=now,
        )
    )


def consume_reset(db: Session, token: str, password: str) -> None:
    reset = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    if reset is None:
        raise DomainError(
            "INVALID_RESET_TOKEN", "This reset link is invalid or expired.", status_code=409
        )
    # Lock the user before any token so different reset tokens cannot deadlock each other.
    user = db.scalar(select(User).where(User.id == reset.user_id).with_for_update())
    reset = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.id == reset.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = get_clock().now()
    if user is None or not user.active or reset.used_at is not None or reset.expires_at <= now:
        raise DomainError(
            "INVALID_RESET_TOKEN", "This reset link is invalid or expired.", status_code=409
        )
    user.password_hash = hash_password(password)
    # Invalidate every outstanding reset link and every existing login session.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.execute(
        update(SessionRecord)
        .where(SessionRecord.user_id == user.id, SessionRecord.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def get_customer(db: Session, customer_id: UUID) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise DomainError("NOT_FOUND", "Customer not found.", status_code=404)
    return customer
