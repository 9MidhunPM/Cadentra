"""Committed PostgreSQL issuance tests: snapshots, atomicity and actual lock races."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Lock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.errors import DomainError
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    DiscountRedemption,
    DiscountRevisionProduct,
    DiscountRule,
    DiscountRuleRevision,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    Plan,
    Product,
    ProductVariant,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
)
from app.modules.billing import issuance as service
from app.modules.catalog.service import get_plan_snapshot


class FixedClock:
    def __init__(self, day):
        self.day = day

    def today(self):
        return self.day

    def now(self):
        return datetime.combine(self.day, datetime.min.time(), UTC)


@pytest.fixture
def issuance_db(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL issuance tests")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not parsed.database.endswith("_test"):
        pytest.fail("Issuance requires a disposable PostgreSQL *_test database")
    schema = f"billing_race_{uuid4().hex}"
    base_engine = create_engine(parsed, poolclass=NullPool)
    scoped = parsed.update_query_dict(
        {"options": f"-csearch_path={schema} -clock_timeout=5000 -cstatement_timeout=10000"}
    )
    scoped_url = scoped.render_as_string(hide_password=False)
    with base_engine.begin() as db:
        db.execute(CreateSchema(schema))
    engine = create_engine(scoped, poolclass=NullPool)
    try:
        migration_env = dict(os.environ, DATABASE_URL=scoped_url)
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[2],
            env=migration_env,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except BaseException:
        engine.dispose()
        with base_engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        base_engine.dispose()
        raise
    # The restart regression must inherit the same isolated schema, not public.
    monkeypatch.setenv("TEST_DATABASE_URL", scoped_url)
    monkeypatch.setenv("DATABASE_URL", scoped_url)

    class IssuanceSession(Session):
        pass

    factory = sessionmaker(engine, class_=IssuanceSession, expire_on_commit=False)
    monkeypatch.setattr(service, "get_clock", lambda: FixedClock(date(2026, 10, 31)))

    def seed(
        *,
        start=date(2026, 10, 31),
        end=date(2026, 11, 30),
        cadence="MONTHLY",
        cap=None,
        discount=True,
        tax=True,
        shared=None,
    ):
        with factory.begin() as db:
            if shared is None:
                customer = Customer(
                    id=uuid4(), display_name="Issuance fixture", email=f"{uuid4()}@example.invalid"
                )
                product = Product(
                    id=uuid4(),
                    name="Frozen license",
                    product_type="SERVICE",
                    sales_price=Decimal("1000.00"),
                    cost_price=Decimal("50.00"),
                )
                plan = Plan(
                    id=uuid4(),
                    name="Fixture plan",
                    base_fee=Decimal("0.00"),
                    currency="INR",
                    cadence=cadence,
                    min_quantity=1,
                    available_from=date(2020, 1, 1),
                    allow_pause=True,
                    allow_early_close=True,
                    allow_renew=True,
                    auto_close=True,
                )
                db.add_all([customer, product, plan])
                db.flush()
                variant = ProductVariant(
                    id=uuid4(),
                    product_id=product.id,
                    attribute_name="Tier",
                    attribute_value="Premium",
                    price_delta=Decimal("560.00"),
                    active=True,
                )
                db.add(variant)
                db.flush()
                rule_id = None
                if tax:
                    tr = TaxRule(id=uuid4())
                    db.add(tr)
                    db.flush()
                    revision = TaxRuleRevision(
                        id=uuid4(),
                        tax_rule_id=tr.id,
                        effective_from=date(2020, 1, 1),
                        name="Illustrative 18 percent",
                        rate_percent=Decimal("18.0000"),
                        valid_from=date(2020, 1, 1),
                        active=True,
                    )
                    db.add(revision)
                    db.flush()
                    db.add(
                        TaxRevisionProduct(tax_rule_revision_id=revision.id, product_id=product.id)
                    )
                if discount:
                    rule = DiscountRule(id=uuid4(), uses_count=0)
                    db.add(rule)
                    db.flush()
                    revision = DiscountRuleRevision(
                        id=uuid4(),
                        discount_rule_id=rule.id,
                        effective_from=date(2020, 1, 1),
                        name="Fixture ten percent",
                        kind="PERCENT",
                        value=Decimal("10.0000"),
                        scope="PRODUCTS",
                        min_purchase=Decimal("0.00"),
                        min_quantity=1,
                        starts_on=date(2020, 1, 1),
                        usage_limit=cap,
                        active=True,
                    )
                    db.add(revision)
                    db.flush()
                    db.add(
                        DiscountRevisionProduct(
                            discount_rule_revision_id=revision.id, product_id=product.id
                        )
                    )
                    rule_id = rule.id
                db.flush()
            else:
                customer = db.get(Customer, shared["customer"])
                product = db.get(Product, shared["product"])
                variant = db.get(ProductVariant, shared["variant"])
                plan = db.get(Plan, shared["plan"])
                rule_id = shared["rule"]
            subscription = Subscription(
                id=uuid4(),
                customer_id=customer.id,
                plan_id=plan.id,
                state="ACTIVE",
                start_date=start,
                end_date=end,
                payment_terms_days=7,
                currency="INR",
                plan_snapshot=get_plan_snapshot(db, plan.id, start),
                next_cycle_index=0,
                revision=1,
            )
            db.add(subscription)
            db.flush()
            db.add(
                SubscriptionLine(
                    id=uuid4(),
                    subscription_id=subscription.id,
                    product_id=product.id,
                    variant_id=variant.id,
                    description="Quoted adjusted license",
                    quantity=3,
                    unit_price=Decimal("1560.00"),
                    price_snapshot={"sales_price": "1000.00", "variant_delta": "560.00"},
                    selected_tax_ids=[],
                )
            )
            data = {
                "subscription": subscription.id,
                "customer": customer.id,
                "product": product.id,
                "variant": variant.id,
                "plan": plan.id,
                "rule": rule_id,
            }
        return data

    try:
        yield factory, seed, engine
    finally:
        # Every contender is joined by its test before this fixture tears down.
        # Drop only this generated namespace; never touch public or another DB.
        engine.dispose()
        if not schema.startswith("billing_race_") or len(schema) != len("billing_race_") + 32:
            raise RuntimeError("Refusing to remove a non-generated test schema")
        with base_engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        base_engine.dispose()


def invoice_for(db, subscription_id):
    return db.scalar(select(Invoice).where(Invoice.subscription_id == subscription_id))


def test_actual_issue_snapshot_replay_and_creation_dates(issuance_db, monkeypatch):
    factory, seed, _ = issuance_db
    data = seed(start=date(2026, 10, 1), end=date(2026, 11, 1))
    result = service.issue_due_period(factory, data["subscription"], 0, date(2026, 10, 31))
    assert result.disposition == "INVOICED"
    with factory.begin() as db:
        invoice = invoice_for(db, data["subscription"])
        assert (
            invoice.subtotal,
            invoice.discount_total,
            invoice.tax_total,
            invoice.total,
        ) == tuple(Decimal(value) for value in ("4680.00", "468.00", "758.16", "4970.16"))
        assert invoice.invoice_date == date(2026, 10, 31) and invoice.due_date == date(2026, 11, 7)
        assert invoice.customer_snapshot["display_name"] == "Issuance fixture"
        assert (
            db.scalar(
                select(func.count())
                .select_from(InvoiceLine)
                .where(InvoiceLine.invoice_id == invoice.id)
            )
            == 2
        )
        line = db.scalar(
            select(InvoiceLine).where(
                InvoiceLine.invoice_id == invoice.id, InvoiceLine.product_id == data["product"]
            )
        )
        assert line.variant_id == data["variant"] and line.quantity == 3
        assert line.unit_price == Decimal("1560.00") and line.discount == Decimal("468.00")
        tax = db.scalar(select(InvoiceLineTax).where(InvoiceLineTax.invoice_line_id == line.id))
        assert tax.rate_snapshot == Decimal("18.0000") and tax.amount == Decimal("758.16")
        assert tax.tax_rule_id is not None and tax.tax_rule_revision_id is not None
        snapshot = invoice.calculation_snapshot
        db.get(Product, data["product"]).sales_price = Decimal("9999.00")
        db.get(Customer, data["customer"]).display_name = "Changed later"
    dto = service._inputs_service()

    def forbidden_getter(*args):
        raise AssertionError("Replay must reuse the persisted outcome before requesting inputs")

    monkeypatch.setattr(dto, "get_billable_inputs", forbidden_getter)
    replay = service.issue_due_period(factory, data["subscription"], 0, date(2026, 10, 31))
    assert replay.disposition == "EXISTING" and replay.invoice_id == result.invoice_id
    with factory() as db:
        invoice = invoice_for(db, data["subscription"])
        assert invoice.total == Decimal("4970.16") and invoice.calculation_snapshot == snapshot
        assert invoice.customer_snapshot["display_name"] == "Issuance fixture"
        assert db.get(Subscription, data["subscription"]).next_cycle_index == 1
        assert db.get(DiscountRule, data["rule"]).uses_count == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(DiscountRedemption)
                .where(DiscountRedemption.invoice_id == invoice.id)
            )
            == 1
        )


def test_shortened_final_period_has_full_cycle_charge(issuance_db):
    factory, seed, _ = issuance_db
    data = seed(end=date(2026, 11, 15))
    outcome = service.issue_due_period(factory, data["subscription"], 0, date(2026, 10, 31))
    with factory() as db:
        assert db.get(Invoice, outcome.invoice_id).total == Decimal("4970.16")
        period = db.get(BillingPeriod, outcome.period_id)
        assert period.period_end == date(2026, 11, 15)
    assert (
        service.issue_due_period(factory, data["subscription"], 1, date(2026, 12, 1)).disposition
        == "NOT_DUE"
    )


def test_before_commit_crash_rolls_back_all_financial_effects(issuance_db):
    factory, seed, _ = issuance_db
    data = seed(cap=1)

    def marked(session, context):
        if any(isinstance(row, Invoice) for row in session.new):
            session.info["invoice_flushed"] = True

    def crash(session):
        if session.info.get("invoice_flushed"):
            raise RuntimeError("simulated crash before financial commit")

    event.listen(factory.class_, "after_flush", marked)
    event.listen(factory.class_, "before_commit", crash)
    try:
        with pytest.raises(RuntimeError, match="simulated crash"):
            service.issue_due_period(factory, data["subscription"], 0, date(2026, 10, 31))
    finally:
        event.remove(factory.class_, "after_flush", marked)
        event.remove(factory.class_, "before_commit", crash)
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(BillingPeriod)
                .where(BillingPeriod.subscription_id == data["subscription"])
            )
            == 0
        )
        assert invoice_for(db, data["subscription"]) is None
        assert db.get(Subscription, data["subscription"]).next_cycle_index == 0
        assert db.get(DiscountRule, data["rule"]).uses_count == 0
    assert (
        service.issue_due_period(factory, data["subscription"], 0, date(2026, 10, 31)).disposition
        == "INVOICED"
    )


@pytest.mark.parametrize("kind", ["same_period", "last_discount_use"])
def test_actual_two_connection_issuance_races(issuance_db, monkeypatch, kind):
    factory, seed, _ = issuance_db
    first = seed(cap=1)
    second = first if kind == "same_period" else seed(shared=first)
    barrier = Barrier(2, timeout=5)
    lock = Lock()
    pids = set()
    target = "_lock_subscription" if kind == "same_period" else "choose_discount"
    original = getattr(service, target)

    def synchronized(db, *args, **kwargs):
        pid = db.scalar(select(func.pg_backend_pid()))
        with lock:
            is_first = pid not in pids
            pids.add(pid)
        if is_first:
            barrier.wait()
        return original(db, *args, **kwargs)

    monkeypatch.setattr(service, target, synchronized)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                service.issue_due_period, factory, data["subscription"], 0, date(2026, 10, 31)
            )
            for data in (first, second)
        ]
        outcomes = [future.result(timeout=15) for future in futures]
    assert len(pids) == 2
    with factory() as db:
        assert db.scalar(select(func.pg_backend_pid())) not in pids
        ids = {first["subscription"], second["subscription"]}
        invoices = db.scalars(select(Invoice).where(Invoice.subscription_id.in_(ids))).all()
        periods = db.scalars(
            select(BillingPeriod).where(BillingPeriod.subscription_id.in_(ids))
        ).all()
        assert len(invoices) == len(ids) == len(periods)
        assert db.get(DiscountRule, first["rule"]).uses_count == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(DiscountRedemption)
                .where(DiscountRedemption.discount_rule_id == first["rule"])
            )
            == 1
        )
        assert all(db.get(Subscription, sid).next_cycle_index == 1 for sid in ids)
        if kind == "same_period":
            assert sorted(outcome.disposition for outcome in outcomes) == ["EXISTING", "INVOICED"]
            assert outcomes[0].invoice_id == outcomes[1].invoice_id
        else:
            assert sorted(invoice.total for invoice in invoices) == [
                Decimal("4970.16"),
                Decimal("5522.40"),
            ]


def test_bounded_catchup_preserves_pause_outcomes_and_exclusive_expiry(issuance_db, monkeypatch):
    factory, seed, _ = issuance_db
    data = seed(
        start=date(2026, 10, 1), end=date(2026, 10, 6), cadence="DAILY", discount=False, tax=False
    )
    monkeypatch.setattr(service, "get_clock", lambda: FixedClock(date(2026, 10, 8)))
    with factory.begin() as db:
        db.add(
            SubscriptionPause(
                subscription_id=data["subscription"],
                starts_on=date(2026, 10, 2),
                ends_on=date(2026, 10, 4),
            )
        )
    results = [service.run_due(factory, date(2026, 10, 8), 2) for _ in range(3)]
    assert [result.processed_periods for result in results] == [2, 2, 1]
    assert [result.has_more_due for result in results] == [True, True, False]
    assert all(result.failed_subscription_count == 0 for result in results)
    with factory() as db:
        periods = db.scalars(
            select(BillingPeriod)
            .where(BillingPeriod.subscription_id == data["subscription"])
            .order_by(BillingPeriod.cycle_index)
        ).all()
        assert [row.disposition for row in periods] == [
            "INVOICED",
            "PAUSED",
            "PAUSED",
            "INVOICED",
            "INVOICED",
        ]
        assert all(row.period_start < date(2026, 10, 6) for row in periods)
        assert db.get(Subscription, data["subscription"]).next_cycle_index == 5
        invoices = db.scalars(
            select(Invoice).where(Invoice.subscription_id == data["subscription"])
        ).all()
        assert len(invoices) == 3
        assert all(
            row.invoice_date == date(2026, 10, 8) and row.due_date == date(2026, 10, 15)
            for row in invoices
        )
    assert service.run_due(factory, date(2026, 10, 8), 2).processed_periods == 0


def test_real_unique_conflict_rolls_back_before_reloading_outcome(issuance_db, monkeypatch):
    factory, seed, engine = issuance_db
    data = seed(discount=False, tax=False)
    with factory.begin() as db:
        period = BillingPeriod(
            id=uuid4(),
            subscription_id=data["subscription"],
            cycle_index=0,
            period_start=date(2026, 10, 31),
            period_end=date(2026, 11, 30),
            disposition="PAUSED",
            explanation="Existing durable pause",
        )
        db.add(period)
        existing_id = period.id
    original = service._existing_outcome
    first = True
    actual_errors = []

    def stale_first_read(db, subscription, index):
        nonlocal first
        if first:
            first = False
            return None
        return original(db, subscription, index)

    def observe_error(context):
        actual_errors.append(getattr(context.original_exception, "sqlstate", None))

    monkeypatch.setattr(service, "_existing_outcome", stale_first_read)
    event.listen(engine, "handle_error", observe_error)
    try:
        outcome = service.issue_due_period(factory, data["subscription"], 0, date(2026, 10, 31))
    finally:
        event.remove(engine, "handle_error", observe_error)
    assert "23505" in actual_errors  # A real PostgreSQL constraint violation, not a mocked error.
    assert outcome.disposition == "EXISTING" and outcome.period_id == existing_id
    with factory.begin() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(BillingPeriod)
                .where(BillingPeriod.subscription_id == data["subscription"])
            )
            == 1
        )
        assert invoice_for(db, data["subscription"]) is None
        assert db.get(Subscription, data["subscription"]).next_cycle_index == 1
        db.get(Customer, data["customer"]).company_name = "Recovered write succeeds"


def test_failed_period_attempts_count_toward_batch_limit(issuance_db, monkeypatch):
    factory, seed, _ = issuance_db
    for _ in range(3):
        seed(start=date(2026, 10, 1), end=date(2026, 10, 6), cadence="DAILY")
    calls = []

    def fail(factory, subscription_id, index, as_of, actor=None):
        calls.append(subscription_id)
        raise DomainError("INVALID_CONFIGURATION", "Review subscription configuration.")

    monkeypatch.setattr(service, "issue_due_period", fail)
    result = service.run_due(factory, date(2026, 10, 8), 1)
    assert len(calls) == 1
    assert result.processed_periods == 0
    assert result.failed_subscription_count == 1
    assert len(result.failures) == 1 and result.has_more_due


def test_failed_subscription_does_not_starve_later_bounded_batches(issuance_db, monkeypatch):
    factory, seed, _ = issuance_db
    records = [
        seed(start=date(2026, 10, 1), end=date(2026, 10, 2), cadence="DAILY") for _ in range(2)
    ]
    ids = {row["subscription"] for row in records}
    with factory.begin() as db:
        db.add(
            AuditEvent(
                entity_type="billing_batch",
                entity_id=service.BATCH_ENTITY,
                action="BATCH_COMPLETED",
                redacted_details={"continuation_after": str(UUID(int=0))},
            )
        )
    order = [
        row.id
        for row in service._candidates(factory, date(2026, 10, 8), service._read_cursor(factory))
        if row.id in ids
    ]
    failing, healthy = order
    original = service.issue_due_period

    def selective_failure(factory, subscription_id, index, as_of, actor=None):
        if subscription_id == failing:
            raise DomainError("INVALID_CONFIGURATION", "Operator review required.")
        return original(factory, subscription_id, index, as_of, actor)

    monkeypatch.setattr(service, "issue_due_period", selective_failure)
    first = service.run_due(factory, date(2026, 10, 8), 1)
    # A fresh interpreter has no in-memory traversal state or test monkeypatches.
    # It must resume after the failed prefix using only committed batch metadata.
    code = """
import json, os
from dataclasses import asdict
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.billing.issuance import run_due
engine = create_engine(os.environ['TEST_DATABASE_URL'])
factory = sessionmaker(engine, expire_on_commit=False)
print(json.dumps(asdict(run_due(factory, date(2026, 10, 8), 1))))
engine.dispose()
"""
    restarted = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=15
    )
    second = json.loads(restarted.stdout)
    assert first.failed_subscription_count == 1 and first.processed_periods == 0
    assert second["invoices_created"] == 1 and second["has_more_due"]
    with factory() as db:
        assert invoice_for(db, failing) is None
        assert invoice_for(db, healthy) is not None
        assert db.get(Subscription, failing).next_cycle_index == 0
