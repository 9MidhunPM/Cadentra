"""Real-service fictional billing imports; no SMTP dispatch or broad suite runs."""

from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_issuance import issuance_db  # noqa: F401

from app.core.auth import Actor
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.demo_data.runtime import at_date
from app.models import (
    AuditEvent,
    BillingPeriod,
    DiscountRedemption,
    DiscountRule,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    Payment,
    Subscription,
    SubscriptionLine,
    User,
)
from app.modules.billing import demo_import, invoices, issuance


@pytest.fixture
def import_case(issuance_db, monkeypatch):  # noqa: F811
    factory, seed, _ = issuance_db
    # issuance_db's fixed provider predates shared historical contexts. Restore
    # the real provider so the actual issuer/confirm/payment see the same clock.
    monkeypatch.setattr(issuance, "get_clock", get_clock)
    monkeypatch.setattr(invoices, "get_clock", get_clock)
    data = seed(start=date(2026, 8, 1), end=date(2026, 9, 1))
    namespace = f"demo-import-test-{uuid4().hex}"
    operator_id = uuid4()
    with factory.begin() as db:
        db.add(
            User(
                id=operator_id,
                display_name="Fictional import operator",
                normalized_email=f"{operator_id}@example.invalid",
                password_hash="unused",
                role="ADMIN",
            )
        )
        db.flush()
        marker = AuditEvent(
            actor_user_id=operator_id,
            entity_type="CUSTOMER",
            entity_id=data["customer"],
            action="DEMO_CONTACT_NO_EMAIL",
            redacted_details={"namespace": namespace},
        )
        db.add(marker)
        db.flush()
        marker_id = marker.id
    actor = Actor(operator_id, "ADMIN")
    scope = demo_import.DemoScope(
        namespace, frozenset({data["customer"]}), frozenset({data["subscription"]})
    )
    intent = demo_import.DemoCycleIntent(
        subscription_id=data["subscription"],
        cycle_index=0,
        issue_date=date(2026, 9, 5),
        as_of=date(2026, 8, 31),
        payment_mode="PAID",
        invoice_state="CONFIRMED",
        payment_dates=(date(2026, 9, 10), date(2026, 9, 20)),
    )
    return factory, data, actor, scope, intent, marker_id


def financial_state(factory):
    """Fresh persisted snapshots detect mutations as well as duplicate counts."""
    models = (
        Subscription,
        BillingPeriod,
        Invoice,
        InvoiceLine,
        InvoiceLineTax,
        DiscountRule,
        DiscountRedemption,
        Payment,
        EmailOutbox,
        AuditEvent,
    )
    with factory() as db:
        return {
            model.__tablename__: [
                {
                    column.name: deepcopy(getattr(row, column.name))
                    for column in model.__table__.columns
                }
                for row in db.scalars(select(model).order_by(model.id))
            ]
            for model in models
        }


def replay(case, intent=None):
    factory, _, actor, scope, initial, _ = case
    return demo_import.replay_demo_cycle(factory, actor, scope, intent or initial, at_date=at_date)


@pytest.mark.parametrize("checkpoint", ["issue_due_period", "record_payment"])
def test_import_resumes_after_real_financial_commit_lost_ack(import_case, monkeypatch, checkpoint):
    factory, data, _, _, intent, _ = import_case
    original = getattr(demo_import, checkpoint)
    tripped = False

    def committed_then_lost_ack(*args, **kwargs):
        nonlocal tripped
        result = original(*args, **kwargs)
        if not tripped:
            tripped = True
            raise RuntimeError("simulated lost acknowledgement after committed operation")
        return result

    monkeypatch.setattr(demo_import, checkpoint, committed_then_lost_ack)
    normal_clock = get_clock()
    with pytest.raises(RuntimeError, match="lost acknowledgement"):
        replay(import_case)
    assert get_clock() is normal_clock
    interrupted = financial_state(factory)
    assert tripped
    assert len(interrupted["billing_periods"]) == len(interrupted["invoices"]) == 1
    assert len(interrupted["payments"]) == (1 if checkpoint == "record_payment" else 0)
    invoice_id = interrupted["invoices"][0]["id"]
    committed_payment_ids = {row["id"] for row in interrupted["payments"]}
    receipt = replay(import_case)
    assert receipt.invoice_id == invoice_id and receipt.status == "PAID"
    assert (receipt.total, receipt.paid, receipt.balance) == ("4970.16", "4970.16", "0.00")
    complete = financial_state(factory)
    assert len(complete["billing_periods"]) == len(complete["invoices"]) == 1
    payments = complete["payments"]
    assert len(payments) == 2 and committed_payment_ids <= {row["id"] for row in payments}
    assert sum((row["amount"] for row in payments), Decimal("0")) == Decimal("4970.16")
    assert sorted(row["paid_on"] for row in payments) == list(intent.payment_dates)
    invoice = complete["invoices"][0]
    assert invoice["invoice_date"] == intent.issue_date
    assert invoice["due_date"] == intent.issue_date + timedelta(days=7)
    assert invoice["confirmed_at"].date() == intent.issue_date
    period = complete["billing_periods"][0]
    assert (period["period_start"], period["period_end"]) == (date(2026, 8, 1), date(2026, 9, 1))
    assert period["subscription_id"] == data["subscription"]
    assert not complete["email_outbox"]
    assert replay(import_case) == receipt
    assert financial_state(factory) == complete and get_clock() is normal_clock


@pytest.mark.parametrize(
    "mode,state,expected,payment_count",
    [
        ("PARTIAL", "CONFIRMED", "CONFIRMED", 1),
        ("NONE", "CONFIRMED", "CONFIRMED", 0),
        ("NONE", "DRAFT", "DRAFT", 0),
        ("NONE", "CANCELLED", "CANCELLED", 0),
    ],
)
def test_import_supported_nonsettled_states(import_case, mode, state, expected, payment_count):
    factory, _, _, _, initial, _ = import_case
    dates = initial.payment_dates[:1] if mode == "PARTIAL" else ()
    intent = replace(initial, payment_mode=mode, invoice_state=state, payment_dates=dates)
    receipt = replay(import_case, intent)
    snapshot = financial_state(factory)
    assert receipt.status == expected
    assert len(snapshot["billing_periods"]) == len(snapshot["invoices"]) == 1
    assert len(snapshot["payments"]) == payment_count and not snapshot["email_outbox"]
    if mode == "PARTIAL":
        assert Decimal("0.00") < Decimal(receipt.paid) < Decimal(receipt.total)
        assert Decimal(receipt.balance) == Decimal(receipt.total) - Decimal(receipt.paid)
    else:
        assert receipt.paid == "0.00"
    assert replay(import_case, intent) == receipt
    assert financial_state(factory) == snapshot


def test_zero_import_confirms_paid_without_fabricated_payment(import_case):
    factory, data, _, _, initial, _ = import_case
    with factory.begin() as db:
        line = db.scalar(
            select(SubscriptionLine).where(SubscriptionLine.subscription_id == data["subscription"])
        )
        line.unit_price = Decimal("0.00")
        line.price_snapshot = {"sales_price": "0.00", "variant_delta": "0.00"}
    intent = replace(initial, payment_mode="NONE", payment_dates=())
    receipt = replay(import_case, intent)
    assert (receipt.status, receipt.total, receipt.paid, receipt.balance) == (
        "PAID",
        "0.00",
        "0.00",
        "0.00",
    )
    state = financial_state(factory)
    assert not state["payments"] and not state["email_outbox"]
    assert len(state["invoices"]) == len(state["billing_periods"]) == 1


def test_unmarked_customer_is_rejected_without_financial_mutation(import_case):
    factory, _, _, _, _, marker_id = import_case
    with factory.begin() as db:
        db.execute(delete(AuditEvent).where(AuditEvent.id == marker_id))
    before = financial_state(factory)
    with pytest.raises(DomainError) as error:
        replay(import_case)
    assert error.value.code == "DEMO_SCOPE_VIOLATION"
    assert financial_state(factory) == before


def test_existing_period_without_import_declaration_is_not_adopted(import_case):
    factory, data, _, _, intent, _ = import_case
    with at_date(intent.issue_date):
        issuance.issue_due_period(factory, data["subscription"], 0, intent.as_of)
    before = financial_state(factory)
    assert len(before["billing_periods"]) == len(before["invoices"]) == 1
    with pytest.raises(DomainError) as error:
        replay(import_case)
    assert error.value.status_code == 409
    assert error.value.code in {"DEMO_INTENT_CONFLICT", "DEMO_IMPORT_RECONCILIATION"}
    assert financial_state(factory) == before


def test_changed_intent_is_rejected_before_existing_records_are_touched(import_case):
    factory, _, _, _, initial, _ = import_case
    unpaid = replace(initial, payment_mode="NONE", payment_dates=())
    replay(import_case, unpaid)
    before = financial_state(factory)
    with pytest.raises(DomainError) as error:
        replay(import_case, initial)
    assert error.value.code == "DEMO_INTENT_CONFLICT"
    assert financial_state(factory) == before
