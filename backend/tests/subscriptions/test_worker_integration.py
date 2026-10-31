"""Real lifecycle/billing worker behavior over committed PostgreSQL records."""

import os
import subprocess
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core import outbox
from app.core.auth import Actor
from app.models import (
    BillingPeriod,
    Customer,
    Invoice,
    InvoiceLine,
    Plan,
    Product,
    Subscription,
    SubscriptionPause,
    User,
)
from app.modules.billing import invoices, issuance
from app.modules.subscriptions import workflows
from app.worker import load_services, run_tick


class FixedClock:
    def __init__(self, day):
        self.day = day

    def today(self):
        return self.day

    def now(self):
        return datetime.combine(self.day, datetime.min.time(), UTC)


@pytest.fixture
def worker_db(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL worker tests")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Worker integration requires a disposable PostgreSQL *_test database")
    schema = f"subscription_worker_{uuid4().hex}"
    base_engine = create_engine(parsed, poolclass=NullPool)
    scoped = parsed.update_query_dict(
        {"options": f"-csearch_path={schema} -clock_timeout=5000 -cstatement_timeout=10000"}
    )
    scoped_url = scoped.render_as_string(hide_password=False)
    with base_engine.begin() as db:
        db.execute(CreateSchema(schema))
    engine = create_engine(scoped, poolclass=NullPool)
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[2],
            env=dict(os.environ, DATABASE_URL=scoped_url),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        factory = sessionmaker(engine, expire_on_commit=False)
        clock = FixedClock(date(2027, 1, 31))
        for module in (workflows, issuance, invoices, outbox):
            monkeypatch.setattr(module, "get_clock", lambda: clock)
        services = load_services()

        def create(*, start, end, cadence="MONTHLY", auto_close=True):
            clock.day = start
            with factory.begin() as db:
                staff = User(
                    display_name="Worker acceptance staff",
                    normalized_email=f"{uuid4()}@example.invalid",
                    password_hash="test-only",
                    role="STAFF",
                )
                customer = Customer(
                    display_name="Worker acceptance customer", email="worker@example.invalid"
                )
                plan = Plan(
                    name="Worker acceptance plan",
                    cadence=cadence,
                    base_fee=Decimal("5.00"),
                    currency="INR",
                    min_quantity=3,
                    available_from=date(2020, 1, 1),
                    allow_pause=True,
                    allow_early_close=True,
                    allow_renew=True,
                    auto_close=auto_close,
                )
                product = Product(
                    name="Worker acceptance seats",
                    product_type="SERVICE",
                    sales_price=Decimal("100.00"),
                )
                db.add_all([staff, customer, plan, product])
                db.flush()
                actor = Actor(staff.id, "STAFF")
                row = workflows.create_subscription(
                    db,
                    actor,
                    dict(
                        customer_id=customer.id,
                        plan_id=plan.id,
                        start_date=start,
                        end_date=end,
                        payment_terms_days=7,
                        lines=[dict(product_id=product.id, quantity=3)],
                    ),
                )
                for action, payload in (
                    ("issue-quotation", {"valid_days": 7}),
                    ("confirm", {}),
                    ("activate", {}),
                ):
                    workflows.apply_action_record(db, actor, row.id, action, payload)
                return SimpleNamespace(id=row.id, actor=actor)

        def tick(day, limit=1):
            clock.day = day
            result = run_tick(services, factory, day, limit)
            assert result.failed_subscription_count == 0
            assert result.failures == ()
            return result

        yield SimpleNamespace(factory=factory, clock=clock, create=create, tick=tick)
    finally:
        engine.dispose()
        # Only this fixture's freshly created UUID schema is removed. Public and
        # other workstreams' committed financial fixture graphs are untouched.
        with base_engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        base_engine.dispose()


def state(env, identifier):
    with env.factory() as db:
        row = db.get(Subscription, identifier)
        return row.state, row.next_cycle_index


def periods(env, identifier):
    with env.factory() as db:
        return [
            (row.cycle_index, row.period_start, row.period_end, row.disposition)
            for row in db.scalars(
                select(BillingPeriod)
                .where(BillingPeriod.subscription_id == identifier)
                .order_by(BillingPeriod.cycle_index)
            )
        ]


def test_worker_downtime_drains_bounded_backlog_before_expiry_closure(worker_db):
    env = worker_db
    row = env.create(start=date(2026, 10, 1), end=date(2026, 10, 4), cadence="DAILY")
    for index in range(3):
        result = env.tick(date(2026, 10, 8))
        assert (result.processed_periods, result.invoices_created, result.paused_periods) == (
            1,
            1,
            0,
        )
        assert result.has_more_due is (index < 2)
        # Lifecycle runs first and must leave unresolved history discoverable.
        assert state(env, row.id) == ("ACTIVE", index + 1)
    assert periods(env, row.id) == [
        (0, date(2026, 10, 1), date(2026, 10, 2), "INVOICED"),
        (1, date(2026, 10, 2), date(2026, 10, 3), "INVOICED"),
        (2, date(2026, 10, 3), date(2026, 10, 4), "INVOICED"),
    ]
    for _ in range(2):
        result = env.tick(date(2026, 10, 8))
        assert (result.processed_periods, result.invoices_created, result.has_more_due) == (
            0,
            0,
            False,
        )
        assert state(env, row.id) == ("CLOSED", 3)
    with env.factory() as db:
        stored = db.scalars(select(Invoice).where(Invoice.subscription_id == row.id)).all()
        assert len(stored) == 3
        assert {(invoice.invoice_date, invoice.due_date, invoice.total) for invoice in stored} == {
            (date(2026, 10, 8), date(2026, 10, 15), Decimal("305.00"))
        }


def test_worker_pause_resume_keeps_anchor_and_bills_short_final_period_in_full(worker_db):
    env = worker_db
    row = env.create(start=date(2027, 1, 31), end=date(2027, 5, 1))
    assert env.tick(date(2027, 1, 31)).invoices_created == 1
    env.clock.day = date(2027, 2, 10)
    with env.factory.begin() as db:
        workflows.apply_action_record(db, row.actor, row.id, "pause", {})
    result = env.tick(date(2027, 2, 28))
    assert (result.processed_periods, result.invoices_created, result.paused_periods) == (1, 0, 1)
    assert state(env, row.id) == ("ACTIVE", 2)
    env.clock.day = date(2027, 3, 10)
    with env.factory.begin() as db:
        workflows.apply_action_record(db, row.actor, row.id, "resume", {})
    with env.factory() as db:
        pause = db.scalar(
            select(SubscriptionPause).where(SubscriptionPause.subscription_id == row.id)
        )
        assert (pause.starts_on, pause.ends_on) == (date(2027, 2, 28), date(2027, 3, 31))
    assert env.tick(date(2027, 3, 30)).processed_periods == 0
    for cursor, more in ((3, True), (4, False)):
        result = env.tick(date(2027, 5, 10))
        assert (result.invoices_created, result.paused_periods, result.has_more_due) == (1, 0, more)
        assert state(env, row.id) == ("ACTIVE", cursor)
    assert periods(env, row.id) == [
        (0, date(2027, 1, 31), date(2027, 2, 28), "INVOICED"),
        (1, date(2027, 2, 28), date(2027, 3, 31), "PAUSED"),
        (2, date(2027, 3, 31), date(2027, 4, 30), "INVOICED"),
        (3, date(2027, 4, 30), date(2027, 5, 1), "INVOICED"),
    ]
    assert env.tick(date(2027, 5, 10)).processed_periods == 0
    assert state(env, row.id) == ("CLOSED", 4)
    with env.factory() as db:
        stored = db.scalars(select(Invoice).where(Invoice.subscription_id == row.id)).all()
        assert len(stored) == 3
        assert all(invoice.total == Decimal("305.00") for invoice in stored)
        final = db.scalar(
            select(Invoice)
            .join(BillingPeriod, BillingPeriod.id == Invoice.billing_period_id)
            .where(BillingPeriod.subscription_id == row.id, BillingPeriod.cycle_index == 3)
        )
        assert (final.invoice_date, final.due_date) == (date(2027, 5, 10), date(2027, 5, 17))
        lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == final.id)).all()
        assert sorted((line.quantity, line.unit_price) for line in lines) == [
            (1, Decimal("5.00")),
            (3, Decimal("100.00")),
        ]
    replay = env.tick(date(2027, 6, 30))
    assert (replay.processed_periods, replay.invoices_created, replay.has_more_due) == (0, 0, False)


def test_worker_catches_up_unprocessed_pause_history_before_terminal_closure(worker_db):
    env = worker_db
    row = env.create(start=date(2026, 10, 1), end=date(2026, 10, 6), cadence="DAILY")
    assert env.tick(date(2026, 10, 1)).invoices_created == 1
    with env.factory.begin() as db:
        workflows.apply_action_record(db, row.actor, row.id, "pause", {})
    # No worker runs during the pause. Resume retains the already-started
    # interval even though its durable PAUSED outcomes have not been written.
    env.clock.day = date(2026, 10, 4)
    with env.factory.begin() as db:
        workflows.apply_action_record(db, row.actor, row.id, "resume", {})
    result = env.tick(date(2026, 10, 8), limit=2)
    assert (result.processed_periods, result.invoices_created, result.paused_periods) == (2, 0, 2)
    assert result.has_more_due is True
    assert state(env, row.id) == ("ACTIVE", 3)
    result = env.tick(date(2026, 10, 8), limit=2)
    assert (result.processed_periods, result.invoices_created, result.paused_periods) == (2, 2, 0)
    assert result.has_more_due is False
    assert state(env, row.id) == ("ACTIVE", 5)
    assert periods(env, row.id) == [
        (0, date(2026, 10, 1), date(2026, 10, 2), "INVOICED"),
        (1, date(2026, 10, 2), date(2026, 10, 3), "PAUSED"),
        (2, date(2026, 10, 3), date(2026, 10, 4), "PAUSED"),
        (3, date(2026, 10, 4), date(2026, 10, 5), "INVOICED"),
        (4, date(2026, 10, 5), date(2026, 10, 6), "INVOICED"),
    ]
    assert env.tick(date(2026, 10, 8), limit=2).processed_periods == 0
    assert state(env, row.id) == ("CLOSED", 5)
    with env.factory() as db:
        invoice_periods = db.scalars(
            select(BillingPeriod.cycle_index)
            .join(Invoice, Invoice.billing_period_id == BillingPeriod.id)
            .where(BillingPeriod.subscription_id == row.id)
            .order_by(BillingPeriod.cycle_index)
        ).all()
        assert invoice_periods == [0, 3, 4]
    assert env.tick(date(2026, 10, 9), limit=2).processed_periods == 0


def test_scheduled_early_close_preserves_debt_and_prevents_later_billing(worker_db):
    env = worker_db
    row = env.create(start=date(2027, 1, 31), end=date(2027, 5, 1), auto_close=False)
    assert env.tick(date(2027, 1, 31)).invoices_created == 1
    with env.factory() as db:
        invoice = db.scalar(select(Invoice).where(Invoice.subscription_id == row.id))
        original = (invoice.id, invoice.number, invoice.total, dict(invoice.calculation_snapshot))
    # Financial operations own their transaction; use a fresh, unbegun session.
    with env.factory() as db:
        invoices.confirm_invoice(db, row.actor, original[0])
    env.clock.day = date(2027, 2, 10)
    with env.factory.begin() as db:
        closed = workflows.apply_action_record(
            db, row.actor, row.id, "close", {"reason": "Acceptance early close"}
        )
        assert (closed.state, closed.close_effective_on) == ("ACTIVE", date(2027, 2, 28))
    for day in (date(2027, 2, 28), date(2027, 6, 1)):
        result = env.tick(day)
        assert (result.processed_periods, result.invoices_created, result.has_more_due) == (
            0,
            0,
            False,
        )
        assert state(env, row.id) == ("CLOSED", 1)
    assert periods(env, row.id) == [(0, date(2027, 1, 31), date(2027, 2, 28), "INVOICED")]
    with env.factory() as db:
        stored = db.scalars(select(Invoice).where(Invoice.subscription_id == row.id)).all()
        assert len(stored) == 1
        invoice = stored[0]
        assert (invoice.id, invoice.number, invoice.total, invoice.calculation_snapshot) == original
        detail = invoices.get_invoice_for_actor(db, row.actor, invoice.id)
        assert (detail["status"], detail["balance_due"], detail["paid_amount"]) == (
            "CONFIRMED",
            "305.00",
            "0.00",
        )
