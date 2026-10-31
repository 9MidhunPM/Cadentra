"""PostgreSQL proofs that imported demo contacts cannot enqueue or send email."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core import outbox
from app.core.clock import get_clock
from app.core.demo_contacts import (
    DEMO_CONTACT_ACTION,
    DEMO_CONTACT_DOMAIN,
    DEMO_CONTACT_ENTITY_TYPE,
    is_demo_contact,
)
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    EmailOutbox,
    Invoice,
    PasswordResetToken,
    Plan,
    Subscription,
    User,
)
from app.modules.identity.service import request_reset

pytestmark = pytest.mark.integration


def contact(db, *, marked=False):
    row = Customer(display_name="Fictional demo contact", email=f"{uuid4()}@{DEMO_CONTACT_DOMAIN}")
    db.add(row)
    db.flush()
    if marked:
        db.add(AuditEvent(
            entity_type=DEMO_CONTACT_ENTITY_TYPE,
            entity_id=row.id,
            action=DEMO_CONTACT_ACTION,
            redacted_details={"dataset": "demo-policy-test"},
        ))
        db.flush()
    return row


def linked_user(db, customer):
    row = User(
        display_name="Fictional demo user", normalized_email=customer.email,
        password_hash="unused-in-service-policy-test", role="CUSTOMER", customer_id=customer.id,
    )
    db.add(row)
    db.flush()
    return row


def invoice_for_contact(db, customer):
    today = get_clock().today()
    plan = Plan(name="Policy test plan", cadence="MONTHLY", min_quantity=1, available_from=today)
    db.add(plan)
    db.flush()
    subscription = Subscription(
        customer_id=customer.id, plan_id=plan.id, start_date=today,
        end_date=today + timedelta(days=60),
    )
    db.add(subscription)
    db.flush()
    period = BillingPeriod(
        subscription_id=subscription.id, cycle_index=0, period_start=today,
        period_end=today + timedelta(days=30), disposition="INVOICED",
    )
    db.add(period)
    db.flush()
    row = Invoice(
        subscription_id=subscription.id, billing_period_id=period.id, customer_id=customer.id,
        invoice_date=today, due_date=today,
        customer_snapshot={"display_name": customer.display_name, "email": customer.email},
        seller_snapshot={"name": "Policy test"}, calculation_snapshot={},
    )
    db.add(row)
    db.flush()
    return row


def test_marker_survives_email_edit_and_domain_matching_is_specific(db_session):
    customer = contact(db_session, marked=True)
    customer.email = f"{uuid4()}@example.com"
    db_session.flush()
    db_session.expire_all()

    assert is_demo_contact(db_session, customer_id=customer.id, recipient=customer.email)
    assert is_demo_contact(db_session, recipient=f"demo@{DEMO_CONTACT_DOMAIN.upper()}")
    assert is_demo_contact(db_session, recipient=f"demo@sub.{DEMO_CONTACT_DOMAIN}")
    assert not is_demo_contact(db_session, customer_id=uuid4(), recipient="normal@example.com")
    assert not is_demo_contact(db_session, recipient=f"normal@{DEMO_CONTACT_DOMAIN}.other.com")


@pytest.mark.parametrize("edited", [False, True], ids=["reserved-domain", "edited-marked-contact"])
def test_reset_suppression_creates_no_token_or_outbox(db_session, edited):
    customer = contact(db_session, marked=edited)
    if edited:
        customer.email = f"{uuid4()}@example.com"
        db_session.flush()
    user = linked_user(db_session, customer)

    assert request_reset(db_session, user.normalized_email) is None

    assert db_session.scalar(select(func.count()).select_from(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id
    )) == 0
    assert db_session.scalar(select(func.count()).select_from(EmailOutbox).where(
        EmailOutbox.kind == "RESET", EmailOutbox.aggregate_id == user.id
    )) == 0


@pytest.mark.parametrize("kind", ["RESET", "INVOICE"])
def test_dispatch_blocks_marked_contact_before_composition_or_smtp(db_session, monkeypatch, kind):
    customer = contact(db_session, marked=True)
    customer.email = f"{uuid4()}@example.com"
    db_session.flush()
    aggregate = linked_user(db_session, customer) if kind == "RESET" else invoice_for_contact(
        db_session, customer
    )
    row = EmailOutbox(
        kind=kind, aggregate_id=aggregate.id, recipient=customer.email,
        subject="Demo policy test", payload={}, dedupe_key=str(uuid4()),
        next_attempt_at=get_clock().now() - timedelta(seconds=1),
    )
    db_session.add(row)
    db_session.flush()

    def forbidden(*args, **kwargs):
        pytest.fail("Suppressed demo contacts must not reach message composition or SMTP")

    monkeypatch.setattr(outbox, "build_message", forbidden)
    monkeypatch.setattr(outbox, "send_message", forbidden)
    result = outbox.dispatch_pending(db_session, limit=1)

    assert result == {"processed": 1, "accepted_by_smtp": 0, "failed": 1}
    assert row.status == "FAILED"
    assert row.last_error == "DemoContactSuppressed"
    assert row.attempts == 1
    assert row.next_attempt_at > get_clock().now()
