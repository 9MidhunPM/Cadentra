"""Worker wiring behavior independent of future financial services."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import Mock

import pytest

from app.worker import WorkerNotReady, WorkerServices, _service, run_tick


def test_missing_worker_service_is_explicit():
    with pytest.raises(WorkerNotReady, match="Required service unavailable"):
        _service("app.modules.nonexistent.service", "run")


def test_worker_transactions_and_order():
    events = []

    class Factory:
        @contextmanager
        def begin(self):
            events.append("begin")
            yield "db"
            events.append("commit")

    factory = Factory()
    today = date(2026, 10, 31)
    services = WorkerServices(
        lifecycle=lambda db, as_of: events.append(("lifecycle", db, as_of)),
        billing=lambda sf, as_of, limit: events.append(("billing", sf, as_of, limit)),
        outbox=lambda db: events.append(("outbox", db)),
    )
    run_tick(services, factory, today, 10)
    assert events == [
        "begin",
        ("lifecycle", "db", today),
        "commit",
        ("billing", factory, today, 10),
        "begin",
        ("outbox", "db"),
        "commit",
    ]


def test_worker_stops_after_lifecycle_failure():
    @contextmanager
    def begin():
        yield "db"

    lifecycle = Mock(side_effect=RuntimeError("database failure"))
    billing, outbox = Mock(), Mock()
    factory = Mock()
    factory.begin = begin
    with pytest.raises(RuntimeError, match="database failure"):
        run_tick(WorkerServices(lifecycle, billing, outbox), factory, date(2026, 10, 31), 10)
    billing.assert_not_called()
    outbox.assert_not_called()


@pytest.fixture
def seed_db():
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL seed verification")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail(
            "Seed integration tests require an explicitly disposable PostgreSQL *_test database"
        )
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection) as db:
            yield db
        transaction.rollback()
    engine.dispose()


@pytest.mark.integration
def test_demo_seed_is_idempotent_and_preserves_password(seed_db):
    from app.core.security import hash_password
    from app.models import User
    from app.seed import demo_id, seed_demo

    first = seed_demo(seed_db, "Demo.Admin@example.invalid", "ValidDemo!Password")
    assert first == {"users": 1, "products": 1, "variants": 1, "plans": 1}
    user = seed_db.get(User, demo_id("admin"))
    existing_hash = hash_password("ChangedLocally!Password")
    user.password_hash = existing_hash
    seed_db.flush()
    second = seed_demo(seed_db, "demo.admin@example.invalid", "DifferentDemo!Password")
    assert second == {"users": 0, "products": 0, "variants": 0, "plans": 0}
    assert user.password_hash == existing_hash


@pytest.mark.integration
def test_demo_seed_does_not_promote_existing_staff(seed_db):
    from uuid import uuid4

    from app.models import User
    from app.seed import seed_demo

    user = User(
        id=uuid4(),
        display_name="Existing staff",
        normalized_email="existing@example.invalid",
        password_hash="unused-test-hash",
        role="STAFF",
        active=True,
    )
    seed_db.add(user)
    seed_db.flush()
    with pytest.raises(ValueError, match="non-admin account"):
        seed_demo(seed_db, "existing@example.invalid", "ValidDemo!Password")
    assert user.role == "STAFF"
