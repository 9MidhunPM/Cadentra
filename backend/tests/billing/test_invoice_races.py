"""Real two-connection payment and cancellation races on committed fixture rows."""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Lock

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from test_invoices import payload, seed_invoice

from app.core.errors import DomainError
from app.models import Invoice, Payment, Subscription
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
        # Preserve committed financial history, but prevent retained fake
        # subscriptions from becoming unrelated work for later due-run tests.
        with factory.begin() as db:
            invoice = db.get(Invoice, iid)
            db.get(Subscription, invoice.subscription_id).state = "CLOSED"
        engine.dispose()


@pytest.mark.parametrize("kind", ["capacity", "replay", "cancel"])
def test_real_invoice_lock_race(committed_invoice, kind):
    iid, actor, factory, engine = committed_invoice
    barrier = Barrier(2, timeout=5)
    pids = set()
    guard = Lock()

    def before_lock(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement and "invoices" in statement:
            pid = conn.connection.driver_connection.info.backend_pid
            with guard:
                first = pid not in pids
                pids.add(pid)
            if first:
                barrier.wait()

    event.listen(engine, "before_cursor_execute", before_lock)

    def contender(index):
        try:
            with factory() as db:
                if kind == "cancel" and index == 1:
                    return "cancel", invoices.cancel_invoice(db, actor, iid, "requested")
                amount = ("70.00" if index == 0 else "60.00") if kind == "capacity" else "100.00"
                key = "same-request" if kind == "replay" else f"contender-{index}"
                return "payment", invoices.record_payment(db, actor, iid, payload(amount, key))
        except DomainError as exc:
            return "conflict", exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(contender, i) for i in range(2)]
            results = [future.result(timeout=15) for future in futures]
    finally:
        event.remove(engine, "before_cursor_execute", before_lock)
    assert len(pids) == 2
    with factory() as observer:
        assert observer.connection().connection.driver_connection.info.backend_pid not in pids
        invoice = observer.get(Invoice, iid)
        payments = observer.scalars(select(Payment).where(Payment.invoice_id == iid)).all()
        paid = observer.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == iid)
        )
        if kind == "capacity":
            assert len(payments) == 1 and paid in (Decimal("60"), Decimal("70"))
            assert invoice.status == "CONFIRMED"
            assert sum(result[0] == "conflict" for result in results) == 1
        elif kind == "replay":
            assert len(payments) == 1 and paid == Decimal("100") and invoice.status == "PAID"
            assert all(result[0] == "payment" for result in results)
            assert results[0][1][0]["id"] == results[1][1][0]["id"]
            assert sorted(result[1][1] for result in results) == [False, True]
        elif invoice.status == "PAID":
            assert paid == Decimal("100") and len(payments) == 1
            assert ("conflict", "INVALID_TRANSITION") in results
        else:
            assert invoice.status == "CANCELLED" and not payments and paid == 0
            assert ("conflict", "INVALID_TRANSITION") in results
