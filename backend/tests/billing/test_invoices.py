"""Actual PostgreSQL invoice operations; fixture setup is rolled back after tests."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Actor
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    Payment,
    Plan,
    Subscription,
    User,
)
from app.modules.billing import invoices
from app.modules.billing.invoice_schemas import PaymentWrite


def seed_invoice(db_session, total=Decimal("4970.16")):
    now = get_clock().today()
    customer = Customer(
        id=uuid4(), display_name="<script>bad()</script>", email="invoice@example.invalid"
    )
    user = User(
        id=uuid4(),
        display_name="Operator",
        normalized_email=f"{uuid4()}@example.invalid",
        password_hash="unused",
        role="STAFF",
    )
    plan = Plan(
        id=uuid4(),
        name="Monthly",
        base_fee=Decimal("0"),
        cadence="MONTHLY",
        min_quantity=1,
        available_from=now,
    )
    db_session.add_all([customer, user, plan])
    db_session.flush()
    subscription = Subscription(
        id=uuid4(),
        customer_id=customer.id,
        plan_id=plan.id,
        state="ACTIVE",
        start_date=now,
        end_date=now + timedelta(days=60),
    )
    db_session.add(subscription)
    db_session.flush()
    period = BillingPeriod(
        id=uuid4(),
        subscription_id=subscription.id,
        cycle_index=0,
        period_start=now,
        period_end=now + timedelta(days=30),
        disposition="INVOICED",
    )
    db_session.add(period)
    db_session.flush()
    invoice = Invoice(
        id=uuid4(),
        subscription_id=subscription.id,
        billing_period_id=period.id,
        customer_id=customer.id,
        invoice_date=now,
        due_date=now + timedelta(days=7),
        customer_snapshot={"display_name": customer.display_name, "email": customer.email},
        seller_snapshot={"name": "Brightloop"},
        subtotal=total,
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=total,
        calculation_snapshot={
            "rounding": "ROUND_HALF_UP",
            "cost_price": "secret",
            "nested": {"staff_note": "secret"},
        },
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        InvoiceLine(
            id=uuid4(),
            invoice_id=invoice.id,
            stable_line_key="BASE",
            description="<img src=x onerror=alert(1)>",
            quantity=1,
            unit_price=invoice.total,
            gross=invoice.total,
            discount=Decimal("0"),
            taxable_amount=invoice.total,
            tax_total=Decimal("0"),
            total=invoice.total,
            source_snapshot={"cost_price": "secret"},
        )
    )
    db_session.flush()
    return invoice.id, Actor(user.id, "STAFF"), customer.id


@pytest.fixture
def invoice_case(db_session, db_connection):
    iid, actor, cid = seed_invoice(db_session)
    db_session.commit()

    def factory():
        return Session(
            bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return iid, actor, cid, factory


def payload(amount, key, **kwargs):
    return PaymentWrite(
        method="BANK_TRANSFER",
        amount=amount,
        paid_on=get_clock().today(),
        note="staff-only private note",
        request_key=key,
        **kwargs,
    )


def test_customer_projection_excludes_nested_private_address_fields(invoice_case):
    iid, _, customer_id, factory = invoice_case
    with factory() as db, db.begin():
        row = db.get(Invoice, iid)
        row.customer_snapshot = {
            "display_name": "Customer",
            "email": "customer@example.invalid",
            "billing_address": {
                "city": "Kochi",
                "line1": "Example Street",
                "staff_notes": "SECRET_CUSTOMER_ADDRESS",
                "country": {"name": "India", "private": "NESTED_SECRET"},
            },
        }
        row.seller_snapshot = {
            "name": "Brightloop",
            "address": {"city": "Kochi", "internal_cost": "SECRET_SELLER_ADDRESS"},
        }
    actor = Actor(uuid4(), "CUSTOMER", customer_id)
    with factory() as db:
        detail = invoices.get_invoice_for_actor(db, actor, iid)
        printable = invoices.render_invoice_for_actor(db, actor, iid)
    assert detail["customer_snapshot"]["billing_address"] == {
        "city": "Kochi",
        "line1": "Example Street",
    }
    assert detail["seller_snapshot"]["address"] == {"city": "Kochi"}
    assert "SECRET_" not in printable and "NESTED_SECRET" not in printable


def test_partial_full_and_matching_replay_after_paid(invoice_case):
    iid, actor, _, factory = invoice_case
    with factory() as db:
        detail = invoices.confirm_invoice(db, actor, iid)
    original_dates = (detail["invoice_date"], detail["due_date"])
    with factory() as db:
        first, replay = invoices.record_payment(db, actor, iid, payload("2000.00", "first"))
        assert first["amount"] == "2000.00" and not replay
    with factory() as db:
        detail = invoices.get_invoice_for_actor(db, actor, iid)
        assert detail["balance_due"] == "2970.16" and detail["status"] == "CONFIRMED"
    with factory() as db:
        second, replay = invoices.record_payment(db, actor, iid, payload("2970.16", "final"))
    with factory() as db:
        repeated, replay = invoices.record_payment(db, actor, iid, payload("2970.16", "final"))
        assert replay and repeated["id"] == second["id"]
    with factory() as db:
        detail = invoices.get_invoice_for_actor(db, actor, iid)
        assert detail["status"] == "PAID" and detail["balance_due"] == "0.00"
        assert len(detail["payments"]) == 2
        assert (detail["invoice_date"], detail["due_date"]) == original_dates
    with factory() as db, pytest.raises(DomainError, match="different payment"):
        invoices.record_payment(db, actor, iid, payload("2970.15", "final"))


def test_reject_overpayment_future_date_and_partial_cancellation(invoice_case):
    iid, actor, _, factory = invoice_case
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    with factory() as db, pytest.raises(DomainError) as error:
        invoices.record_payment(db, actor, iid, payload("5000.00", "too-much"))
    assert error.value.code == "OVERPAYMENT"
    future = payload("1.00", "future").model_copy(
        update={"paid_on": get_clock().today() + timedelta(days=1)}
    )
    with factory() as db, pytest.raises(DomainError):
        invoices.record_payment(db, actor, iid, future)
    with factory() as db:
        invoices.record_payment(db, actor, iid, payload("2000.00", "partial"))
    with factory() as db, pytest.raises(DomainError):
        invoices.cancel_invoice(db, actor, iid, "requested")
    with factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_id == iid))
            == 1
        )


def test_cancel_preserves_history(invoice_case):
    iid, actor, _, factory = invoice_case
    with factory() as db:
        result = invoices.cancel_invoice(db, actor, iid, "duplicate")
        assert result["status"] == "CANCELLED"
    with factory() as db, pytest.raises(DomainError):
        invoices.record_payment(db, actor, iid, payload("1.00", "cancelled"))
    with factory() as db:
        assert db.get(Invoice, iid).billing_period_id is not None
        with pytest.raises(DomainError):
            invoices.get_invoice_for_actor(db, Actor(uuid4(), "CUSTOMER", uuid4()), iid)


def test_safe_customer_projection_print_and_send_dedupe(invoice_case):
    iid, actor, cid, factory = invoice_case
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    with factory() as db:
        invoices.record_payment(db, actor, iid, payload("1.00", "partial"))
    with factory() as db:
        own = Actor(uuid4(), "CUSTOMER", cid)
        detail = invoices.get_invoice_for_actor(db, own, iid)
        assert "note" not in detail["payments"][0]
        assert "cost_price" not in str(detail) and "staff_note" not in str(detail)
        html = invoices.render_invoice_for_actor(db, own, iid)
        assert "<script>" not in html and "<img" not in html
        assert "&lt;script&gt;" in html and "&lt;img" in html
        assert "private note" not in html
    with factory() as db:
        queued = invoices.send_invoice(db, actor, iid, "send-once")
    with factory() as db:
        replay = invoices.send_invoice(db, actor, iid, "send-once")
        assert replay == queued and queued["status"] == "PENDING"
    with factory() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(EmailOutbox).where(EmailOutbox.aggregate_id == iid)
            )
            == 1
        )
        assert (
            db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_id == iid))
            == 1
        )


def test_invoice_filters(invoice_case):
    iid, actor, cid, factory = invoice_case
    with factory() as db:
        result = invoices.list_invoices(db, actor, customer_id=cid, status="DRAFT", overdue=False)
        assert result["total"] == 1 and result["items"][0]["id"] == str(iid)
        assert invoices.list_invoices(db, Actor(uuid4(), "CUSTOMER", uuid4()))["total"] == 0


def test_strict_payment_inputs():
    for amount in (1.5, "NaN", "0.00", "-1.00", "1.001"):
        with pytest.raises(ValidationError):
            payload(amount, "invalid")
    with pytest.raises(ValidationError):
        PaymentWrite(
            method="CASH",
            amount="1.00",
            paid_on=date.today(),
            note="",
            request_key="x",
            total="1.00",
        )


def test_zero_total_confirmation_without_fabricated_payment(db_session, db_connection):
    iid, actor, _ = seed_invoice(db_session, Decimal("0.00"))
    db_session.commit()
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db:
        detail = invoices.confirm_invoice(db, actor, iid)
        assert detail["status"] == "PAID" and detail["balance_due"] == "0.00"
        assert detail["payments"] == []


def test_payment_failure_rolls_back_flushed_changes(invoice_case, monkeypatch):
    iid, actor, _, factory = invoice_case
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    original = invoices._payment_data

    def fail_after_flush(*args, **kwargs):
        raise RuntimeError("intentional precommit failure")

    monkeypatch.setattr(invoices, "_payment_data", fail_after_flush)
    with factory() as db, pytest.raises(RuntimeError):
        invoices.record_payment(db, actor, iid, payload("4970.16", "rollback"))
    monkeypatch.setattr(invoices, "_payment_data", original)
    with factory() as db:
        detail = invoices.get_invoice_for_actor(db, actor, iid)
        assert detail["status"] == "CONFIRMED" and detail["payments"] == []
    with factory() as db:
        row, replay = invoices.record_payment(db, actor, iid, payload("4970.16", "rollback"))
        assert row["amount"] == "4970.16" and not replay


def test_overdue_is_separate_from_partial_collection(invoice_case):
    iid, actor, cid, factory = invoice_case
    with factory() as db, db.begin():
        invoice = db.get(Invoice, iid)
        invoice.invoice_date = get_clock().today() - timedelta(days=10)
        invoice.due_date = get_clock().today() - timedelta(days=1)
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    with factory() as db:
        invoices.record_payment(db, actor, iid, payload("1.00", "partial"))
    with factory() as db:
        detail = invoices.get_invoice_for_actor(db, actor, iid)
        assert detail["collection_status"] == "PARTIALLY_PAID" and detail["overdue"]
        with pytest.raises(DomainError):
            invoices.list_invoices(db, Actor(uuid4(), "CUSTOMER", cid), customer_id=cid)


def test_staff_http_auth_csrf_and_customer_restrictions(invoice_case, client):
    from app.core.config import get_settings
    from app.core.security import hash_token
    from app.models import SessionRecord

    iid, actor, cid, factory = invoice_case
    url = f"/api/v1/invoices/{iid}"
    assert client.get(url).status_code == 401
    with factory() as db, db.begin():
        db.add(
            SessionRecord(
                user_id=actor.id,
                token_hash=hash_token("invoice-fixture-token"),
                csrf_token="invoice-fixture-csrf",
                expires_at=get_clock().now() + timedelta(hours=1),
            )
        )
    client.cookies.set(get_settings().session_cookie_name, "invoice-fixture-token")
    assert client.get(url).status_code == 200
    assert client.post(url + "/confirm").status_code == 403
    assert (
        client.post(
            url + "/confirm",
            json={"total": "0.00"},
            headers={"X-CSRF-Token": "invoice-fixture-csrf"},
        ).status_code
        == 422
    )
    assert (
        client.post(url + "/confirm", headers={"X-CSRF-Token": "invoice-fixture-csrf"}).status_code
        == 200
    )
    request = {
        "method": "CASH",
        "amount": "1.00",
        "paid_on": get_clock().today().isoformat(),
        "note": "paid",
        "request_key": "http-key",
    }
    first = client.post(
        url + "/payments", json=request, headers={"X-CSRF-Token": "invoice-fixture-csrf"}
    )
    assert first.status_code == 201
    assert (
        client.post(
            url + "/payments", json=request, headers={"X-CSRF-Token": "invoice-fixture-csrf"}
        ).status_code
        == 200
    )
    assert client.get(url + "/payments").json()["total"] == 1
    response = client.get(url + "/print")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"

    with factory() as db, db.begin():
        user = db.get(User, actor.id)
        user.role = "CUSTOMER"
        user.customer_id = cid
    assert client.get(url).status_code == 403
    assert client.get(url + "/print").status_code == 403
    assert (
        client.post(url + "/confirm", headers={"X-CSRF-Token": "invoice-fixture-csrf"}).status_code
        == 403
    )


def _persisted_columns(record):
    return {
        column.name: deepcopy(getattr(record, column.name)) for column in record.__table__.columns
    }


def _send_contract_state(db, invoice_id, actor_id):
    """Capture real persisted rows, including the original queued envelope."""
    return {
        "invoices": [
            _persisted_columns(row)
            for row in db.scalars(
                select(Invoice).where(Invoice.id == invoice_id).order_by(Invoice.id)
            )
        ],
        "payments": [
            _persisted_columns(row)
            for row in db.scalars(
                select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.id)
            )
        ],
        "outbox": [
            _persisted_columns(row)
            for row in db.scalars(
                select(EmailOutbox)
                .where(EmailOutbox.aggregate_id == invoice_id)
                .order_by(EmailOutbox.id)
            )
        ],
        "queue_audit": [
            _persisted_columns(row)
            for row in db.scalars(
                select(AuditEvent)
                .where(AuditEvent.entity_id == invoice_id, AuditEvent.action == "EMAIL_QUEUED")
                .order_by(AuditEvent.id)
            )
        ],
        "audit": [
            _persisted_columns(row)
            for row in db.scalars(
                select(AuditEvent)
                .where(AuditEvent.actor_user_id == actor_id)
                .order_by(AuditEvent.id)
            )
        ],
    }


@pytest.mark.parametrize("status", ["SENDING", "SENT", "FAILED"])
def test_send_replay_preserves_envelope_and_transport_state_after_payment(invoice_case, status):
    iid, actor, _, factory = invoice_case
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    with factory() as db:
        queued = invoices.send_invoice(db, actor, iid, "retained-send")
    assert queued["status"] == "PENDING"
    outbox_id = UUID(queued["outbox_id"])
    with factory() as db:
        original = _persisted_columns(db.get(EmailOutbox, outbox_id))
    # Represent observable dispatcher states without invoking SMTP. Persisting
    # SENDING here verifies billing's read/replay contract, not crash recovery.
    next_attempt = get_clock().now() + timedelta(minutes=7)
    with factory() as db, db.begin():
        outbox = db.get(EmailOutbox, outbox_id)
        outbox.status = status
        outbox.attempts = 3
        outbox.next_attempt_at = next_attempt
        outbox.last_error = "SMTPServerDisconnected" if status == "FAILED" else None
    with factory() as db:
        payment, replay = invoices.record_payment(db, actor, iid, payload("100.00", "after-send"))
    assert not replay and payment["amount"] == "100.00"
    with factory() as db:
        current = invoices.get_invoice_for_actor(db, actor, iid)
        current_html = invoices.render_invoice_for_actor(db, actor, iid)
        before = _send_contract_state(db, iid, actor.id)
    assert current["balance_due"] == "4870.16"
    assert "4870.16" in current_html and current_html != original["payload"]["html"]
    assert len(before["queue_audit"]) == 1
    assert len(before["invoices"]) == len(before["payments"]) == len(before["outbox"]) == 1
    envelope = before["outbox"][0]
    for field in (
        "id",
        "kind",
        "aggregate_id",
        "recipient",
        "subject",
        "payload",
        "dedupe_key",
        "created_at",
    ):
        assert envelope[field] == original[field]
    assert envelope["attempts"] == 3
    assert envelope["next_attempt_at"] == next_attempt
    assert envelope["last_error"] == ("SMTPServerDisconnected" if status == "FAILED" else None)
    with factory() as db:
        repeated = invoices.send_invoice(db, actor, iid, "retained-send")
    assert repeated == {"outbox_id": queued["outbox_id"], "status": status, "email_status": status}
    with factory() as db:
        after = _send_contract_state(db, iid, actor.id)
    assert after == before, (
        "Replay must not rebuild email from the changed balance or reset retries"
    )


@pytest.fixture
def staff_send_client(invoice_case, client):
    from app.core.config import get_settings
    from app.core.security import hash_token
    from app.models import SessionRecord

    iid, actor, _, factory = invoice_case
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    with factory() as db, db.begin():
        db.add(
            SessionRecord(
                user_id=actor.id,
                token_hash=hash_token("send-contract-fixture-token"),
                csrf_token="send-contract-fixture-csrf",
                expires_at=get_clock().now() + timedelta(hours=1),
            )
        )
    client.cookies.set(get_settings().session_cookie_name, "send-contract-fixture-token")
    return iid, actor, factory, client, {"X-CSRF-Token": "send-contract-fixture-csrf"}


@pytest.mark.parametrize("key", ["normalized-key", "k" * 128])
def test_http_send_normalizes_key_and_accepts_128_character_boundary(staff_send_client, key):
    iid, actor, factory, client, headers = staff_send_client
    endpoint = f"/api/v1/invoices/{iid}/send"
    first = client.post(endpoint, json={"request_key": f"  {key}  "}, headers=headers)
    assert first.status_code == 202
    queued = first.json()["data"]
    assert queued["status"] == "PENDING"
    with factory() as db:
        before = _send_contract_state(db, iid, actor.id)
    assert len(before["outbox"]) == len(before["queue_audit"]) == 1
    assert before["outbox"][0]["dedupe_key"] == f"INVOICE:{iid}:{key}"
    assert len(before["outbox"][0]["dedupe_key"]) <= 200
    second = client.post(endpoint, json={"request_key": key}, headers=headers)
    assert second.status_code == 202 and second.json()["data"] == queued
    with factory() as db:
        assert _send_contract_state(db, iid, actor.id) == before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"request_key": ""},
        {"request_key": "   "},
        {"request_key": "k" * 129},
        {"request_key": 17},
        {"request_key": True},
        {"request_key": None},
        {"request_key": ["key"]},
        {"request_key": "valid", "total": "0.00"},
    ],
    ids=[
        "missing",
        "empty",
        "whitespace",
        "overlength",
        "integer",
        "boolean",
        "null",
        "array",
        "extra",
    ],
)
def test_http_send_rejects_invalid_keys_without_financial_or_queue_side_effects(
    staff_send_client, body
):
    iid, actor, factory, client, headers = staff_send_client
    with factory() as db:
        before = _send_contract_state(db, iid, actor.id)
    assert len(before["invoices"]) == 1 and not before["payments"] and not before["outbox"]
    assert not before["queue_audit"]
    response = client.post(f"/api/v1/invoices/{iid}/send", json=body, headers=headers)
    assert response.status_code == 422
    with factory() as db:
        assert _send_contract_state(db, iid, actor.id) == before
