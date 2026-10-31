"""T33: actual billing and subscription actions serialize on the subscription row."""

import copy
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Event, Lock, local
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.auth import Actor
from app.core.errors import DomainError
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    Invoice,
    InvoiceLine,
    Plan,
    Product,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    User,
)
from app.modules.billing import issuance
from app.modules.subscriptions import workflows


@pytest.fixture
def action_race_db(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for real PostgreSQL action races")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Action races require an explicitly disposable PostgreSQL *_test database")
    # Only this newly created schema is removed; public and other fixtures are untouched.
    schema = f"subscription_action_race_{uuid4().hex}"
    base = create_engine(parsed, poolclass=NullPool)
    scoped = parsed.update_query_dict(
        {"options": f"-csearch_path={schema} -clock_timeout=5000 -cstatement_timeout=10000"}
    )
    engine = create_engine(scoped, poolclass=NullPool)
    with base.begin() as db:
        db.execute(CreateSchema(schema))
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[2],
            env=dict(os.environ, DATABASE_URL=scoped.render_as_string(hide_password=False)),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        class RaceSession(Session):
            pass

        factory = sessionmaker(engine, class_=RaceSession, expire_on_commit=False)
        clock = SimpleNamespace(today=lambda: date(2027, 2, 10))
        monkeypatch.setattr(workflows, "get_clock", lambda: clock)
        monkeypatch.setattr(issuance, "get_clock", lambda: clock)
        with factory.begin() as db:
            staff = User(
                normalized_email=f"{uuid4()}@example.invalid",
                display_name="Action race staff",
                password_hash="test-only",
                role="STAFF",
            )
            customer = Customer(
                display_name="Action race customer", email=f"{uuid4()}@example.invalid"
            )
            plan = Plan(
                name="Monthly action race",
                base_fee=Decimal("10.00"),
                cadence="MONTHLY",
                min_quantity=1,
                available_from=date(2027, 1, 1),
                allow_pause=True,
                allow_early_close=True,
                allow_renew=True,
                auto_close=True,
            )
            product = Product(
                name="Frozen action race seats",
                product_type="SERVICE",
                sales_price=Decimal("100.00"),
            )
            db.add_all([staff, customer, plan, product])
            db.flush()
            actor = Actor(staff.id, "STAFF")
            subscription = workflows.create_subscription(
                db,
                actor,
                {
                    "customer_id": customer.id,
                    "plan_id": plan.id,
                    "start_date": date(2027, 1, 31),
                    "end_date": date(2027, 5, 1),
                    "payment_terms_days": 14,
                    "lines": [{"product_id": product.id, "quantity": 2}],
                },
            )
            for action, payload in (
                ("issue-quotation", {"valid_days": 7}),
                ("confirm", {}),
                ("activate", {}),
            ):
                workflows.apply_action_record(db, actor, subscription.id, action, payload)
            data = SimpleNamespace(
                factory=factory,
                engine=engine,
                actor=actor,
                subscription=subscription.id,
                product=product.id,
                revision=subscription.revision,
                clock=clock,
            )
        yield data
    finally:
        engine.dispose()
        with base.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        base.dispose()


def _observe_database_wait(observer, waiter, blocker):
    """Observe PostgreSQL's actual lock wait, rather than infer it from elapsed time."""
    deadline = monotonic() + 4
    while monotonic() < deadline:
        observer.execute(text("SELECT pg_stat_clear_snapshot()"))
        row = observer.execute(
            text(
                "SELECT wait_event_type, pg_blocking_pids(pid) "
                "FROM pg_stat_activity WHERE pid = :pid"
            ),
            {"pid": waiter},
        ).one()
        if row.wait_event_type == "Lock" and blocker in row.pg_blocking_pids:
            return
    pytest.fail("The second contender never entered the expected PostgreSQL row-lock wait")


@pytest.mark.parametrize("action", ["edit", "pause", "close"])
@pytest.mark.parametrize("first", ["action", "issuer"])
def test_billing_and_subscription_action_both_lock_orders(
    action_race_db, monkeypatch, action, first
):
    data = action_race_db
    labels = local()
    pids = {}
    pid_lock = Lock()
    first_locked = Event()
    second_started = Event()
    release_first = Event()

    def record_connection(session, transaction, connection):
        label = getattr(labels, "name", None)
        if label not in {"action", "issuer"}:
            return
        pid = connection.scalar(select(text("pg_backend_pid()")))
        with pid_lock:
            pids[label] = pid
        if label != first:
            second_started.set()

    event.listen(data.factory.class_, "after_begin", record_connection)
    target = workflows if first == "action" else issuance
    name = "_subscription" if first == "action" else "_lock_subscription"
    original = getattr(target, name)

    def hold_after_actual_lock(*args, **kwargs):
        row = original(*args, **kwargs)
        if getattr(labels, "name", None) == first:
            first_locked.set()
            if not release_first.wait(timeout=10):
                raise AssertionError("First contender was not released within the race deadline")
        return row

    # The original service takes the real lock. This hook only pauses after it succeeds.
    monkeypatch.setattr(target, name, hold_after_actual_lock)

    def run_action():
        labels.name = "action"
        try:
            with data.factory.begin() as db:
                if action == "edit":
                    workflows.edit_subscription(
                        db,
                        data.actor,
                        data.subscription,
                        {"lines": [{"product_id": data.product, "quantity": 4}]},
                    )
                else:
                    workflows.apply_action_record(
                        db, data.actor, data.subscription, action, {"reason": "Race fixture"}
                    )
            return "accepted"
        except DomainError as error:
            assert error.status_code == 409
            return error.code

    def run_issuer():
        labels.name = "issuer"
        return issuance.issue_due_period(
            data.factory, data.subscription, 0, date(2027, 2, 10), data.actor
        )

    contenders = {"action": run_action, "issuer": run_issuer}
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        first_future = executor.submit(contenders[first])
        assert first_locked.wait(timeout=5), "First service did not acquire its real row lock"
        second = "issuer" if first == "action" else "action"
        second_future = executor.submit(contenders[second])
        assert second_started.wait(timeout=5), "Second service did not begin its transaction"
        with data.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
            observer_pid = observer.scalar(select(text("pg_backend_pid()")))
            assert len({pids["action"], pids["issuer"], observer_pid}) == 3
            _observe_database_wait(observer, pids[second], pids[first])
        release_first.set()
        results = {
            first: first_future.result(timeout=15),
            second: second_future.result(timeout=15),
        }
    finally:
        release_first.set()
        executor.shutdown(wait=True, cancel_futures=True)
        event.remove(data.factory.class_, "after_begin", record_connection)

    assert results["issuer"].disposition == "INVOICED"
    accepted = first == "issuer"
    assert results["action"] == ("accepted" if accepted else "DUE_BILLING_PENDING")
    with data.factory() as db:
        row = db.get(Subscription, data.subscription)
        periods = db.scalars(
            select(BillingPeriod).where(BillingPeriod.subscription_id == row.id)
        ).all()
        invoices = db.scalars(select(Invoice).where(Invoice.subscription_id == row.id)).all()
        assert len(periods) == len(invoices) == 1
        assert (periods[0].cycle_index, periods[0].period_start, periods[0].period_end) == (
            0,
            date(2027, 1, 31),
            date(2027, 2, 28),
        )
        assert periods[0].disposition == "INVOICED" and row.next_cycle_index == 1
        assert row.state == "ACTIVE" and row.revision == data.revision + accepted
        invoice = invoices[0]
        assert invoice.id == results["issuer"].invoice_id
        assert invoice.total == Decimal("210.00")
        historical_snapshot = copy.deepcopy(invoice.calculation_snapshot)
        original_dates = (invoice.invoice_date, invoice.due_date)
        original_invoice_id = invoice.id
        line = db.scalar(
            select(InvoiceLine).where(
                InvoiceLine.invoice_id == invoice.id, InvoiceLine.product_id == data.product
            )
        )
        assert (line.quantity, line.unit_price) == (2, Decimal("100.00"))
        current_line = db.scalar(
            select(SubscriptionLine).where(SubscriptionLine.subscription_id == row.id)
        )
        assert current_line.quantity == (4 if accepted and action == "edit" else 2)
        assert current_line.unit_price == Decimal("100.00")
        pauses = db.scalars(
            select(SubscriptionPause).where(SubscriptionPause.subscription_id == row.id)
        ).all()
        assert len(pauses) == (1 if accepted and action == "pause" else 0)
        if pauses:
            assert pauses[0].starts_on == date(2027, 2, 28) and pauses[0].ends_on is None
        assert row.close_effective_on == (
            date(2027, 2, 28) if accepted and action == "close" else None
        )
        audit_actions = list(
            db.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == row.id))
        )
        expected_audit = "subscription_edited" if action == "edit" else action
        assert (expected_audit in audit_actions) == accepted

    # Persist the next actual outcome: accepted changes affect only this future cycle.
    data.clock.today = lambda: date(2027, 2, 28)
    future = issuance.issue_due_period(
        data.factory, data.subscription, 1, date(2027, 2, 28), data.actor
    )
    expected_future = (
        "PAUSED"
        if accepted and action == "pause"
        else "NOT_DUE"
        if accepted and action == "close"
        else "INVOICED"
    )
    assert future.disposition == expected_future
    replay = issuance.issue_due_period(
        data.factory, data.subscription, 0, date(2027, 2, 28), data.actor
    )
    assert replay.disposition == "EXISTING" and replay.invoice_id == original_invoice_id
    with data.factory() as db:
        invoice = db.get(Invoice, original_invoice_id)
        assert invoice.total == Decimal("210.00")
        assert invoice.calculation_snapshot == historical_snapshot
        assert (invoice.invoice_date, invoice.due_date) == original_dates
        periods = db.scalars(
            select(BillingPeriod).where(BillingPeriod.subscription_id == data.subscription)
        ).all()
        invoices = db.scalars(
            select(Invoice).where(Invoice.subscription_id == data.subscription)
        ).all()
        assert len(periods) == (1 if expected_future == "NOT_DUE" else 2)
        assert len(invoices) == (2 if expected_future == "INVOICED" else 1)
        assert db.get(Subscription, data.subscription).next_cycle_index == (
            1 if expected_future == "NOT_DUE" else 2
        )
        if expected_future == "INVOICED":
            assert db.get(Invoice, future.invoice_id).total == (
                Decimal("410.00") if accepted and action == "edit" else Decimal("210.00")
            )
