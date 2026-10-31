"""Real PostgreSQL checks for durable billing keys and retained pricing history."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    BillingPeriod,
    Customer,
    Invoice,
    Plan,
    Product,
    Subscription,
    SubscriptionPause,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
)

pytestmark = pytest.mark.integration


def subscription(db):
    customer = Customer(display_name="Schema test", email=f"{uuid4()}@example.invalid")
    plan = Plan(name="Schema test", cadence="MONTHLY", available_from=date(2026, 1, 1))
    db.add_all([customer, plan])
    db.flush()
    result = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        state="ACTIVE",
        start_date=date(2026, 1, 1),
        end_date=date(2027, 1, 1),
        plan_snapshot={},
    )
    db.add(result)
    db.flush()
    return result


def period(db, owner, index=0):
    result = BillingPeriod(
        subscription_id=owner.id,
        cycle_index=index,
        period_start=date(2026, index + 1, 1),
        period_end=date(2026, index + 2, 1),
        disposition="INVOICED",
    )
    db.add(result)
    db.flush()
    return result


def revision(db, rule, **changes):
    values = {
        "tax_rule_id": rule.id,
        "name": "Historical tax",
        "rate_percent": Decimal("18"),
        "valid_from": date(2026, 1, 1),
        "effective_from": date(2026, 1, 1),
    }
    values.update(changes)
    result = TaxRuleRevision(**values)
    db.add(result)
    db.flush()
    return result


def test_subscription_and_invoice_numbers_are_allocated_uniquely(db_session):
    first = subscription(db_session)
    second = subscription(db_session)
    invoices = []
    for item in (first, second):
        billable = period(db_session, item)
        invoice = Invoice(
            subscription_id=item.id,
            customer_id=item.customer_id,
            billing_period_id=billable.id,
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            customer_snapshot={},
            seller_snapshot={},
            calculation_snapshot={},
        )
        db_session.add(invoice)
        db_session.flush()
        invoices.append(invoice)
    assert first.number and second.number and first.number != second.number
    assert invoices[0].number and invoices[1].number
    assert invoices[0].number != invoices[1].number


def test_duplicate_subscription_cycle_is_rejected_without_poisoning_transaction(db_session):
    owner = subscription(db_session)
    existing = period(db_session, owner)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        period(db_session, owner)
    assert (
        db_session.scalar(select(BillingPeriod.id).where(BillingPeriod.subscription_id == owner.id))
        == existing.id
    )
    assert period(db_session, owner, index=1).id != existing.id


def test_only_one_open_pause_is_allowed_and_closed_pause_retains_history(db_session):
    owner = subscription(db_session)
    existing = SubscriptionPause(subscription_id=owner.id, starts_on=date(2026, 2, 1))
    db_session.add(existing)
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(SubscriptionPause(subscription_id=owner.id, starts_on=date(2026, 3, 1)))
        db_session.flush()
    existing.ends_on = date(2026, 3, 1)
    db_session.flush()
    replacement = SubscriptionPause(subscription_id=owner.id, starts_on=date(2026, 4, 1))
    db_session.add(replacement)
    db_session.flush()
    records = db_session.scalars(
        select(SubscriptionPause).where(SubscriptionPause.subscription_id == owner.id)
    ).all()
    assert len(records) == 2
    assert sum(row.ends_on is None for row in records) == 1


def test_revision_overlap_and_payload_changes_are_rejected_but_boundary_can_close(db_session):
    rule = TaxRule()
    db_session.add(rule)
    db_session.flush()
    original = revision(db_session, rule)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        revision(db_session, rule, effective_from=date(2026, 2, 1))
    with pytest.raises(IntegrityError), db_session.begin_nested():
        original.rate_percent = Decimal("9")
        db_session.flush()
    db_session.refresh(original)
    assert original.rate_percent == Decimal("18")
    original.effective_until = date(2026, 2, 1)
    db_session.flush()
    successor = revision(db_session, rule, effective_from=date(2026, 2, 1))
    assert successor.id != original.id
    assert original.effective_until == successor.effective_from
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.delete(original)
        db_session.flush()
    assert db_session.get(TaxRuleRevision, successor.id) is not None


def test_revision_memberships_must_be_created_with_revision_and_remain_immutable(db_session):
    rule = TaxRule()
    product = Product(name="Schema product", product_type="SERVICE")
    another = Product(name="Another schema product", product_type="SERVICE")
    db_session.add_all([rule, product, another])
    db_session.flush()
    current = revision(db_session, rule)
    membership = TaxRevisionProduct(tax_rule_revision_id=current.id, product_id=product.id)
    db_session.add(membership)
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        membership.product_id = another.id
        db_session.flush()
    db_session.refresh(membership)
    assert membership.product_id == product.id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.delete(membership)
        db_session.flush()
    old_rule = TaxRule()
    db_session.add(old_rule)
    db_session.flush()
    older = revision(db_session, old_rule, created_at=datetime.now(UTC) - timedelta(days=1))
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(TaxRevisionProduct(tax_rule_revision_id=older.id, product_id=another.id))
        db_session.flush()
    assert db_session.get(TaxRuleRevision, older.id) is not None
