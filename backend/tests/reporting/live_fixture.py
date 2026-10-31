"""Explicit disposable-database fixture for real HTTP/browser reporting checks.

Run with APP_ENV=test and DATABASE_URL pointing to the assigned experience_test DB.
Credentials are random, local and mode0600; never print their contents. Cleanup
removes only records owned by the UUID customers/users created by this fixture.
"""

import argparse
import json
import os
import secrets
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fixture_database import checked_url
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    DiscountRedemption,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    PasswordResetToken,
    Payment,
    Plan,
    SessionRecord,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    User,
)


def checked_engine():
    return create_engine(checked_url(), pool_pre_ping=True)


def seed(path: Path):
    if path.exists() or path.parent != Path("/tmp"):
        raise RuntimeError("Use a new credentials filename directly under /tmp")
    from conftest import reporting_case

    engine = checked_engine()
    with (
        engine.begin() as connection,
        Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as db,
    ):
        if db.scalar(select(func.count()).select_from(Invoice)) or db.scalar(
            select(func.count()).select_from(Subscription)
        ):
            raise RuntimeError("Live reconciliation requires an empty disposable reporting dataset")
        with pytest.MonkeyPatch.context() as patch:
            fixture = reporting_case.__wrapped__(db, patch)
        actors = {}
        admin = db.get(User, fixture["actor"].id)
        for key, role, customer in [
            ("staff", "STAFF", None),
            ("customer_a", "CUSTOMER", "A"),
            ("customer_b", "CUSTOMER", "B"),
        ]:
            password = secrets.token_urlsafe(24) + "Aa!"
            user = User(
                display_name=f"Live fixture {key}",
                normalized_email=f"{uuid4()}@example.com",
                password_hash=hash_password(password),
                role=role,
                customer_id=fixture["customers"][customer].id if customer else None,
            )
            db.add(user)
            db.flush()
            actors[key] = {"email": user.normalized_email, "password": password, "id": str(user.id)}
        metadata = {
            "test_only": True,
            "database": checked_url().database,
            "actors": actors,
            "customers": {key: str(row.id) for key, row in fixture["customers"].items()},
            "subscriptions": {
                key: {"id": str(row.id), "number": row.number, "customer_id": str(row.customer_id)}
                for key, row in fixture["subscriptions"].items()
            },
            "invoices": {
                key: {"id": str(row.id), "number": row.number, "customer_id": str(row.customer_id)}
                for key, row in fixture["invoices"].items()
            },
            "fixture_admin_id": str(admin.id),
            "plan_id": str(next(iter(fixture["subscriptions"].values())).plan_id),
        }
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(metadata, output)
        db.commit()
    engine.dispose()
    print("Committed isolated live-browser fixture; credentials saved privately.")


def cleanup(path: Path):
    data = json.loads(path.read_text())
    if data.get("test_only") is not True or data.get("database") != checked_url().database:
        raise RuntimeError("Not a live-browser fixture manifest")
    customer_ids = [UUID(value) for value in data["customers"].values()]
    user_ids = [UUID(value["id"]) for value in data["actors"].values()] + [
        UUID(data["fixture_admin_id"])
    ]
    engine = checked_engine()
    with Session(engine) as db, db.begin():
        subscription_ids = list(
            db.scalars(select(Subscription.id).where(Subscription.customer_id.in_(customer_ids)))
        )
        invoice_ids = list(
            db.scalars(select(Invoice.id).where(Invoice.customer_id.in_(customer_ids)))
        )
        line_ids = list(
            db.scalars(select(InvoiceLine.id).where(InvoiceLine.invoice_id.in_(invoice_ids)))
        )
        entities = (
            customer_ids + user_ids + subscription_ids + invoice_ids + [UUID(data["plan_id"])]
        )
        db.execute(
            delete(AuditEvent).where(
                AuditEvent.actor_user_id.in_(user_ids) | AuditEvent.entity_id.in_(entities)
            )
        )
        db.execute(delete(EmailOutbox).where(EmailOutbox.aggregate_id.in_(entities)))
        db.execute(delete(SessionRecord).where(SessionRecord.user_id.in_(user_ids)))
        db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(user_ids)))
        db.execute(delete(Payment).where(Payment.invoice_id.in_(invoice_ids)))
        db.execute(delete(DiscountRedemption).where(DiscountRedemption.invoice_id.in_(invoice_ids)))
        db.execute(delete(InvoiceLineTax).where(InvoiceLineTax.invoice_line_id.in_(line_ids)))
        db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_ids)))
        db.execute(delete(Invoice).where(Invoice.id.in_(invoice_ids)))
        db.execute(delete(BillingPeriod).where(BillingPeriod.subscription_id.in_(subscription_ids)))
        db.execute(
            delete(SubscriptionPause).where(SubscriptionPause.subscription_id.in_(subscription_ids))
        )
        db.execute(
            delete(SubscriptionLine).where(SubscriptionLine.subscription_id.in_(subscription_ids))
        )
        db.execute(delete(Subscription).where(Subscription.id.in_(subscription_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        db.execute(delete(Plan).where(Plan.id == UUID(data["plan_id"])))
    engine.dispose()
    path.unlink()
    print("Removed only the recorded live fixture UUIDs and private credentials.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["seed", "cleanup"])
    parser.add_argument("credentials", type=Path)
    args = parser.parse_args()
    (seed if args.operation == "seed" else cleanup)(args.credentials)
