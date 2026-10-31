"""Real two-connection payment and cancellation races on committed fixture rows."""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event, Lock, local
from time import monotonic

import pytest
from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from test_invoices import payload, seed_invoice

from app.core.errors import DomainError
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    DiscountRedemption,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    Payment,
    Plan,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    User,
)
from app.modules.billing import invoices


@pytest.fixture
def committed_invoice():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for actual PostgreSQL races")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not parsed.database.endswith("_test"):
        pytest.fail("Race tests require an isolated PostgreSQL *_test database")
    engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args={"options": "-c lock_timeout=5000 -c statement_timeout=10000"},
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as db:
        iid, actor, _ = seed_invoice(db, Decimal("100.00"))
    with factory() as db:
        invoices.confirm_invoice(db, actor, iid)
    try:
        yield iid, actor, factory, engine
    finally:
        # Only this fixture's fake UUID graph in an explicitly disposable test DB
        # is removed. Application services never delete financial history.
        with factory.begin() as db:
            invoice = db.get(Invoice, iid)
            subscription = db.get(Subscription, invoice.subscription_id)
            sid, cid, plan_id, period_id = (
                subscription.id,
                invoice.customer_id,
                subscription.plan_id,
                invoice.billing_period_id,
            )
            line_ids = select(InvoiceLine.id).where(InvoiceLine.invoice_id == iid)
            db.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == actor.id))
            db.execute(delete(EmailOutbox).where(EmailOutbox.aggregate_id == iid))
            db.execute(delete(Payment).where(Payment.invoice_id == iid))
            db.execute(delete(DiscountRedemption).where(DiscountRedemption.invoice_id == iid))
            db.execute(delete(InvoiceLineTax).where(InvoiceLineTax.invoice_line_id.in_(line_ids)))
            db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == iid))
            db.execute(delete(Invoice).where(Invoice.id == iid))
            db.execute(delete(BillingPeriod).where(BillingPeriod.id == period_id))
            db.execute(delete(SubscriptionLine).where(SubscriptionLine.subscription_id == sid))
            db.execute(delete(SubscriptionPause).where(SubscriptionPause.subscription_id == sid))
            db.execute(delete(Subscription).where(Subscription.id == sid))
            db.execute(delete(Plan).where(Plan.id == plan_id))
            db.execute(delete(User).where(User.id == actor.id))
            db.execute(delete(Customer).where(Customer.id == cid))
        engine.dispose()


@pytest.mark.parametrize("kind", ["capacity", "replay", "cancel", "send"])
@pytest.mark.parametrize("winner", [0, 1])
def test_real_invoice_lock_race(committed_invoice, kind, winner):
    iid, actor, factory, engine = committed_invoice
    barrier = Barrier(2, timeout=5)
    winner_locked, release_winner = Event(), Event()
    pids, seen = {}, set()
    guard = Lock()
    worker = local()

    def before_lock(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" not in statement or "invoices" not in statement:
            return
        pid = conn.connection.driver_connection.info.backend_pid
        with guard:
            first = pid not in seen
            seen.add(pid)
            pids[worker.index] = pid
        context.billing_race_first_lock = first
        if first:
            barrier.wait()
            if worker.index != winner:
                assert winner_locked.wait(5), "Winner never acquired its actual invoice lock"

    def after_lock(conn, cursor, statement, parameters, context, executemany):
        if getattr(context, "billing_race_first_lock", False) and worker.index == winner:
            # SELECT FOR UPDATE completed: this contender holds the real row lock.
            # Only the main observer releases it; never wait for the loser to acquire it.
            winner_locked.set()
            assert release_winner.wait(8), "Observer did not release the winning transaction"

    event.listen(engine, "before_cursor_execute", before_lock)
    event.listen(engine, "after_cursor_execute", after_lock)

    def contender(index):
        worker.index = index
        try:
            with factory() as db:
                if kind == "send":
                    return "send", invoices.send_invoice(db, actor, iid, "concurrent-send")
                if kind == "cancel" and index == 1:
                    return "cancel", invoices.cancel_invoice(db, actor, iid, "requested")
                amount = ("70.00" if index == 0 else "60.00") if kind == "capacity" else "100.00"
                key = "same-request" if kind == "replay" else f"contender-{index}"
                return "payment", invoices.record_payment(db, actor, iid, payload(amount, key))
        except DomainError as exc:
            return "conflict", exc.code

    executor = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [executor.submit(contender, i) for i in range(2)]
        try:
            assert winner_locked.wait(5), "Winner did not reach the acquired-lock hook"
            assert len(set(pids.values())) == 2
            with factory() as observer:
                assert (
                    observer.connection().connection.driver_connection.info.backend_pid
                    not in pids.values()
                )
                deadline = monotonic() + 4
                waiting = False
                # Bounded database polling, rather than sleeps, proves that the loser
                # is actually blocked on the winner's lock before release.
                while monotonic() < deadline:
                    observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                    waiting = observer.scalar(
                        text(
                            "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"
                        ),
                        {"pid": pids[1 - winner]},
                    )
                    if waiting:
                        break
                assert waiting, "Losing connection never entered a PostgreSQL lock wait"
        finally:
            release_winner.set()
        results = [future.result(timeout=15) for future in futures]
    finally:
        release_winner.set()
        barrier.abort()
        executor.shutdown(wait=True, cancel_futures=True)
        event.remove(engine, "before_cursor_execute", before_lock)
        event.remove(engine, "after_cursor_execute", after_lock)

    with factory() as observer:
        assert (
            observer.connection().connection.driver_connection.info.backend_pid not in pids.values()
        )
        invoice = observer.get(Invoice, iid)
        payments = observer.scalars(select(Payment).where(Payment.invoice_id == iid)).all()
        paid = observer.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == iid)
        )
        if kind == "capacity":
            expected = Decimal("70") if winner == 0 else Decimal("60")
            assert len(payments) == 1 and paid == expected
            assert invoice.status == "CONFIRMED"
            assert results[winner][0] == "payment"
            assert results[1 - winner] == ("conflict", "OVERPAYMENT")
        elif kind == "replay":
            assert len(payments) == 1 and paid == Decimal("100") and invoice.status == "PAID"
            assert all(result[0] == "payment" for result in results)
            assert results[0][1][0]["id"] == results[1][1][0]["id"]
            assert results[winner][1][1] is False and results[1 - winner][1][1] is True
        elif kind == "send":
            assert not payments and paid == 0 and invoice.status == "CONFIRMED"
            assert all(result[0] == "send" for result in results)
            assert results[0][1]["outbox_id"] == results[1][1]["outbox_id"]
            assert (
                observer.scalar(
                    select(func.count())
                    .select_from(EmailOutbox)
                    .where(EmailOutbox.aggregate_id == iid, EmailOutbox.kind == "INVOICE")
                )
                == 1
            )
            assert (
                observer.scalar(select(func.count()).select_from(Invoice).where(Invoice.id == iid))
                == 1
            )
        elif winner == 0:
            assert invoice.status == "PAID" and paid == Decimal("100") and len(payments) == 1
            assert results[1] == ("conflict", "INVALID_TRANSITION")
        else:
            assert invoice.status == "CANCELLED" and not payments and paid == 0
            assert results[0] == ("conflict", "INVALID_TRANSITION")
