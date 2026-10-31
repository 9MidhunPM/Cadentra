"""Real invoice-service checks for the imported demo contact delivery policy."""

from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_invoices import seed_invoice

from app.core.demo_contacts import (
    DEMO_CONTACT_ACTION,
    DEMO_CONTACT_DOMAIN,
    DEMO_CONTACT_ENTITY_TYPE,
)
from app.core.errors import DomainError
from app.models import AuditEvent, Customer, EmailOutbox, Invoice, Payment
from app.modules.billing import invoices


@pytest.fixture
def demo_invoice_case(db_session, db_connection):
    invoice_id, actor, customer_id = seed_invoice(db_session)
    db_session.commit()

    def factory():
        return Session(
            bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return invoice_id, actor, customer_id, factory


def financial_state(db, invoice_id, actor_id):
    invoice = db.get(Invoice, invoice_id)
    return {
        "status": invoice.status,
        "total": invoice.total,
        "payments": db.scalar(
            select(func.count(Payment.id)).where(Payment.invoice_id == invoice_id)
        ),
        "emails": [
            {
                "id": row.id,
                "payload": deepcopy(row.payload),
                "recipient": row.recipient,
                "status": row.status,
                "attempts": row.attempts,
                "next_attempt_at": row.next_attempt_at,
                "last_error": row.last_error,
            }
            for row in db.scalars(
                select(EmailOutbox)
                .where(EmailOutbox.aggregate_id == invoice_id)
                .order_by(EmailOutbox.id)
            )
        ],
        "audits": db.scalar(
            select(func.count(AuditEvent.id)).where(AuditEvent.actor_user_id == actor_id)
        ),
    }


def assert_demo_email_rejected(factory, actor, invoice_id, key):
    with factory() as db, pytest.raises(DomainError) as error:
        invoices.send_invoice(db, actor, invoice_id, key)
    assert error.value.code == "DEMO_EMAIL_DISABLED"
    assert error.value.status_code == 409
    assert str(error.value) == "Email is disabled for imported demo contacts."


def test_reserved_demo_snapshot_never_enqueues_email(demo_invoice_case):
    iid, actor, _, factory = demo_invoice_case
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    with factory() as db, db.begin():
        db.get(Invoice, iid).customer_snapshot = {
            "display_name": "Fictional demo customer",
            "email": f"demo-contact@{DEMO_CONTACT_DOMAIN}",
        }
    with factory() as db:
        before = financial_state(db, iid, actor.id)
    assert before["emails"] == []
    assert_demo_email_rejected(factory, actor, iid, "never-enqueue")
    with factory() as db:
        assert financial_state(db, iid, actor.id) == before


def test_durable_marker_blocks_edited_contact_before_existing_key_replay(demo_invoice_case):
    iid, actor, customer_id, factory = demo_invoice_case
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    with factory() as db:
        original = invoices.send_invoice(db, actor, iid, "existing-key")
    with factory() as db, db.begin():
        db.add(
            AuditEvent(
                actor_user_id=actor.id,
                entity_type=DEMO_CONTACT_ENTITY_TYPE,
                entity_id=customer_id,
                action=DEMO_CONTACT_ACTION,
                redacted_details={"namespace": "billing-email-policy-test"},
            )
        )
        db.get(Customer, customer_id).email = "edited-contact@example.com"
        db.get(Invoice, iid).customer_snapshot = {
            "display_name": "Fictional imported customer",
            "email": "edited-snapshot@example.com",
        }
    with factory() as db:
        before = financial_state(db, iid, actor.id)
    assert len(before["emails"]) == 1
    assert before["emails"][0]["id"] == UUID(original["outbox_id"])
    assert_demo_email_rejected(factory, actor, iid, "existing-key")
    assert_demo_email_rejected(factory, actor, iid, "new-key")
    with factory() as db:
        assert financial_state(db, iid, actor.id) == before
