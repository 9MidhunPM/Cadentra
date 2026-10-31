"""Real PostgreSQL contract tests for the subscription-to-billing read boundary."""

import json
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.errors import DomainError
from app.models import (
    BillingPeriod,
    Customer,
    Invoice,
    Plan,
    PlanTax,
    Product,
    ProductVariant,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
)
from app.modules.catalog.service import get_plan_snapshot, get_product_snapshot
from app.modules.subscriptions.service import (
    BillableInputs,
    BillableLine,
    get_billable_inputs,
    snapshot_to_json,
)


@pytest.fixture
def records(db_session):
    customer = Customer(display_name="Calendar customer", email="calendar@example.invalid")
    product = Product(name="Desk", product_type="SERVICE", sales_price=Decimal("1000.00"))
    plan = Plan(
        name="Monthly seats",
        base_fee=Decimal("35.00"),
        cadence="MONTHLY",
        available_from=date(2027, 1, 1),
        min_quantity=3,
        allow_pause=True,
    )
    base_tax = TaxRule()
    db_session.add_all([customer, product, plan, base_tax])
    db_session.flush()
    variant = ProductVariant(
        product_id=product.id,
        attribute_name="Tier",
        attribute_value="Plus",
        price_delta=Decimal("560.00"),
    )
    db_session.add_all([variant, PlanTax(plan_id=plan.id, tax_rule_id=base_tax.id)])
    db_session.flush()
    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        state="ACTIVE",
        start_date=date(2027, 1, 31),
        end_date=date(2027, 5, 1),
        payment_terms_days=14,
        plan_snapshot=get_plan_snapshot(db_session, plan.id, date(2027, 1, 31)),
    )
    db_session.add(subscription)
    db_session.flush()
    snapshot = get_product_snapshot(db_session, product.id, variant.id, date(2027, 1, 31))
    line = SubscriptionLine(
        subscription_id=subscription.id,
        product_id=product.id,
        variant_id=variant.id,
        description=snapshot["description"],
        quantity=3,
        unit_price=Decimal(snapshot["unit_price"]),
        price_snapshot=snapshot["price_snapshot"],
        selected_tax_ids=snapshot["selected_tax_ids"],
    )
    db_session.add(line)
    db_session.flush()
    return SimpleNamespace(
        subscription=subscription,
        customer=customer,
        product=product,
        variant=variant,
        plan=plan,
        line=line,
        base_tax=base_tax,
    )


def rejected(code, call, status=409):
    with pytest.raises(DomainError) as caught:
        call()
    assert caught.value.code == code
    assert caught.value.status_code == status


def test_frozen_prices_and_exactly_one_base_line(db_session, records):
    records.product.sales_price = Decimal("9000.00")
    records.product.active = False
    records.variant.price_delta = Decimal("600.00")
    records.plan.base_fee = Decimal("500.00")
    db_session.flush()
    result = get_billable_inputs(db_session, records.subscription.id, 0)
    assert isinstance(result, BillableInputs)
    assert isinstance(result.lines, tuple)
    assert all(isinstance(line, BillableLine) for line in result.lines)
    assert len(result.lines) == 2
    base = next(line for line in result.lines if line.stable_line_key == "BASE")
    product = next(line for line in result.lines if line.product_id == records.product.id)
    assert (base.quantity, base.unit_price) == (1, Decimal("35.00"))
    assert base.product_id is None and base.variant_id is None
    assert base.selected_tax_ids == (records.base_tax.id,)
    assert (product.quantity, product.unit_price) == (3, Decimal("1560.00"))
    assert product.stable_line_key == str(records.line.id)
    assert product.variant_id == records.variant.id
    assert result.subscription_id == records.subscription.id
    assert result.customer_id == records.customer.id and result.plan_id == records.plan.id
    assert (result.currency, result.payment_terms_days, result.revision) == ("INR", 14, 1)
    assert (result.cycle_index, result.period_start, result.period_end) == (
        0,
        date(2027, 1, 31),
        date(2027, 2, 28),
    )
    assert result.effective_end == date(2027, 5, 1)


@pytest.mark.parametrize("index", [-1, True, False, 1.0, "1", None])
def test_invalid_index_precedes_missing_lookup(db_session, index):
    rejected("INVALID_CYCLE", lambda: get_billable_inputs(db_session, uuid4(), index))


def test_missing_subscription_is_not_found(db_session):
    rejected("NOT_FOUND", lambda: get_billable_inputs(db_session, uuid4(), 0), 404)


@pytest.mark.parametrize("state", ["DRAFT", "QUOTATION", "CONFIRMED", "CLOSED"])
def test_non_active_subscription_is_rejected(db_session, records, state):
    records.subscription.state = state
    db_session.flush()
    rejected(
        "INVALID_TRANSITION", lambda: get_billable_inputs(db_session, records.subscription.id, 0)
    )


def test_future_cycle_does_not_skip_cursor(db_session, records):
    rejected("INVALID_CYCLE", lambda: get_billable_inputs(db_session, records.subscription.id, 1))


def test_processed_cycle_is_not_repriced(db_session, records):
    records.subscription.next_cycle_index = 1
    db_session.flush()
    rejected(
        "PERIOD_ALREADY_PROCESSED",
        lambda: get_billable_inputs(db_session, records.subscription.id, 0),
    )


@pytest.mark.parametrize("close", [None, date(2027, 2, 28)])
def test_exhausted_current_cycle_is_rejected(db_session, records, close):
    records.subscription.end_date = date(2027, 2, 28)
    records.subscription.close_effective_on = close
    records.subscription.next_cycle_index = 1
    db_session.flush()
    rejected(
        "CYCLE_OUT_OF_RANGE", lambda: get_billable_inputs(db_session, records.subscription.id, 1)
    )


def test_period_end_respects_effective_close(db_session, records):
    records.subscription.close_effective_on = date(2027, 2, 15)
    db_session.flush()
    result = get_billable_inputs(db_session, records.subscription.id, 0)
    assert result.period_end == result.effective_end == date(2027, 2, 15)


@pytest.mark.parametrize(
    "starts,ends,paused",
    [
        (date(2027, 1, 31), None, True),
        (date(2027, 1, 31), date(2027, 2, 28), True),
        (date(2027, 1, 1), date(2027, 1, 31), False),
        (date(2027, 2, 28), None, False),
    ],
)
def test_pause_membership_is_start_inclusive_end_exclusive(
    db_session, records, starts, ends, paused
):
    db_session.add(
        SubscriptionPause(subscription_id=records.subscription.id, starts_on=starts, ends_on=ends)
    )
    db_session.flush()
    result = get_billable_inputs(db_session, records.subscription.id, 0)
    assert result.paused is paused
    assert records.subscription.state == "ACTIVE"


def test_getter_never_commits_advances_or_creates_outcomes(db_session, records, monkeypatch):
    def forbidden_commit():
        pytest.fail("Read-only getter committed the caller's transaction")

    monkeypatch.setattr(db_session, "commit", forbidden_commit)
    before = (records.subscription.next_cycle_index, records.subscription.revision)
    get_billable_inputs(db_session, records.subscription.id, 0)
    assert before == (records.subscription.next_cycle_index, records.subscription.revision)
    assert db_session.scalar(select(func.count()).select_from(BillingPeriod)) == 0
    assert db_session.scalar(select(func.count()).select_from(Invoice)) == 0


def test_dto_and_nested_snapshot_are_immutable_without_orm_aliases(db_session, records):
    result = get_billable_inputs(db_session, records.subscription.id, 0)
    product = next(line for line in result.lines if line.product_id == records.product.id)
    with pytest.raises(FrozenInstanceError):
        result.revision = 99
    with pytest.raises(FrozenInstanceError):
        product.quantity = 99
    with pytest.raises(TypeError):
        result.plan_snapshot["base_fee"] = "99.00"
    with pytest.raises(TypeError):
        result.plan_snapshot["tax_rule_ids"][0] = str(uuid4())
    with pytest.raises(TypeError):
        product.source_snapshot["sales_price"] = "99.00"
    records.line.price_snapshot["sales_price"] = "22.00"
    records.subscription.plan_snapshot["tax_rule_ids"].append(str(uuid4()))
    assert product.source_snapshot["sales_price"] == "1000.00"
    assert tuple(result.plan_snapshot["tax_rule_ids"]) == (str(records.base_tax.id),)


def test_frozen_snapshots_materialize_as_independent_json_data(db_session, records):
    result = get_billable_inputs(db_session, records.subscription.id, 0)
    materialized = snapshot_to_json(result.plan_snapshot)
    assert json.loads(json.dumps(materialized)) == records.subscription.plan_snapshot
    materialized["tax_rule_ids"].append(str(uuid4()))
    materialized["base_fee"] = "900.00"
    assert result.plan_snapshot["base_fee"] == "35.00"
    assert result.plan_snapshot["tax_rule_ids"] == (str(records.base_tax.id),)
    product = next(line for line in result.lines if line.product_id == records.product.id)
    assert (
        json.loads(json.dumps(snapshot_to_json(product.source_snapshot)))
        == records.line.price_snapshot
    )


def test_product_tax_membership_uses_period_start_not_frozen_quote_date(db_session, records):
    rule = TaxRule()
    db_session.add(rule)
    db_session.flush()
    revision = TaxRuleRevision(
        tax_rule_id=rule.id,
        effective_from=date(2027, 1, 1),
        name="Future product tax",
        rate_percent=Decimal("18.0000"),
        valid_from=date(2027, 3, 1),
        active=True,
    )
    db_session.add(revision)
    db_session.flush()
    db_session.add(
        TaxRevisionProduct(tax_rule_revision_id=revision.id, product_id=records.product.id)
    )
    # Seed cursor history; invoice generation itself is owned/tested by billing.
    db_session.add(
        BillingPeriod(
            subscription_id=records.subscription.id,
            cycle_index=0,
            period_start=date(2027, 1, 31),
            period_end=date(2027, 2, 28),
            disposition="INVOICED",
        )
    )
    records.subscription.next_cycle_index = 1
    db_session.flush()
    february = get_billable_inputs(db_session, records.subscription.id, 1)
    db_session.add(
        BillingPeriod(
            subscription_id=records.subscription.id,
            cycle_index=1,
            period_start=date(2027, 2, 28),
            period_end=date(2027, 3, 31),
            disposition="INVOICED",
        )
    )
    records.subscription.next_cycle_index = 2
    db_session.flush()
    march = get_billable_inputs(db_session, records.subscription.id, 2)
    for result, expected in ((february, ()), (march, (rule.id,))):
        product = next(line for line in result.lines if line.product_id == records.product.id)
        base = next(line for line in result.lines if line.stable_line_key == "BASE")
        assert product.selected_tax_ids == expected
        assert product.unit_price == Decimal("1560.00")
        assert base.selected_tax_ids == (records.base_tax.id,)
    assert records.line.selected_tax_ids == []
