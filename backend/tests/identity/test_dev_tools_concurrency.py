"""Two real connections serialize password reset against restoration of admin."""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import Request, Response
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.security import hash_password, hash_token
from app.db.base import Base
from app.models import Customer, DevAccessGrant, PasswordResetToken, SessionRecord, User
from app.modules.identity import dev_tools, service


@pytest.fixture
def race(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Disposable PostgreSQL URL required")
    owner = create_engine(url)
    assert owner.url.database.endswith("_test")
    schema = "dev_race_" + uuid4().hex
    with owner.begin() as db:
        db.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_tools_enabled", True)
    monkeypatch.setattr(settings, "demo_instance", True)
    monkeypatch.setattr(settings, "dev_password_hash", hash_password("Private-Dev-Password!"))
    monkeypatch.setattr(dev_tools, "CONFIGURATION_READY", True)
    with factory.begin() as db:
        c = Customer(display_name="Race customer", email="race@example.com")
        db.add(c)
        db.flush()
        admin = User(display_name="Race admin", normalized_email="admin@example.com",
            role="ADMIN", password_hash=hash_password("Private-User-Password!"))
        customer = User(display_name="Race customer", normalized_email="race@example.com",
            role="CUSTOMER", customer_id=c.id, password_hash=admin.password_hash)
        db.add_all([admin, customer])
        db.flush()
        original, _ = service.create_session(db, admin)
        grant = DevAccessGrant(token_hash=hash_token("private-grant"), operator_admin_id=admin.id,
            original_session_id=original.id, dev_csrf="private-dev-csrf",
            credential_fingerprint=hash_token(settings.dev_password_hash),
            expires_at=get_clock().now() + timedelta(minutes=30))
        db.add(grant)
        db.flush()
        target, raw = service.create_session(db, customer)
        target.dev_grant_id = grant.id
        db.add(PasswordResetToken(user_id=admin.id, token_hash=hash_token("private-reset"),
            expires_at=get_clock().now() + timedelta(minutes=30)))
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/dev-tools/end",
        "headers": [(b"origin", settings.allowed_origins[0].encode()),
            (b"x-dev-csrf-token", b"private-dev-csrf"), (b"cookie",
            f"{settings.session_cookie_name}={raw}; {settings.dev_grant_cookie_name}=private-grant".encode())]})
    try:
        yield factory, engine, admin.id, grant.id, request
    finally:
        engine.dispose()
        with owner.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        owner.dispose()


def wait_blocked(engine, identifier):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as db:
            if db.scalar(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": identifier}):
                return
        time.sleep(.01)
    raise AssertionError("Expected concurrent User lock was not observed")


@pytest.mark.parametrize("winner", ["reset", "end"])
def test_reset_and_end_cannot_leave_restored_admin_session_valid(race, monkeypatch, winner):
    factory, engine, admin_id, grant_id, request = race
    first_locked, release, second_started = threading.Event(), threading.Event(), threading.Event()
    pids = {}
    original_create = service.create_session
    def create(db, user):
        result = original_create(db, user)
        if winner == "end":
            first_locked.set()
            assert release.wait(5)
        return result
    monkeypatch.setattr(service, "create_session", create)
    def reset():
        with factory.begin() as db:
            pids["reset"] = db.scalar(text("SELECT pg_backend_pid()"))
            second_started.set()
            if winner == "reset":
                db.scalar(select(User).where(User.id == admin_id).with_for_update())
                first_locked.set()
                assert release.wait(5)
            service.consume_reset(db, "private-reset", "Changed-Private-Password!")
    def end():
        with engine.connect() as connection, Session(bind=connection, expire_on_commit=False) as db:
            # Pin the connection while leaving Session.begin ownership to end().
            pids["end"] = db.scalar(text("SELECT pg_backend_pid()"))
            db.commit()
            second_started.set()
            return dev_tools.end(request, Response(), db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(reset if winner == "reset" else end)
        assert first_locked.wait(5)
        second_started.clear()
        second = pool.submit(end if winner == "reset" else reset)
        assert second_started.wait(5)
        blocked = "end" if winner == "reset" else "reset"
        wait_blocked(engine, pids[blocked])
        release.set()
        first_result, second_result = first.result(timeout=10), second.result(timeout=10)
    ended = second_result if winner == "reset" else first_result
    if winner == "reset":
        assert ended.status_code == 401
    else:
        assert ended["data"]["actor"]["role"] == "ADMIN"
    with factory() as db:
        sessions = db.scalars(select(SessionRecord).where(SessionRecord.user_id == admin_id)).all()
        assert sessions and all(row.revoked_at is not None for row in sessions)
        assert db.get(DevAccessGrant, grant_id).revoked_at is not None
