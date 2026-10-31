"""Real HTTP/database grant boundaries, role enforcement and revocation."""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import AuditEvent, Customer, DevAccessGrant, SessionRecord, User
from app.modules.identity.rate_limit import reset_rate_limits

PASSWORD = "Private-User-Password!"
DEV_PASSWORD = "Private-Dev-Password!"


@pytest.fixture
def people(db_session, monkeypatch):
    reset_rate_limits()
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_tools_enabled", True)
    monkeypatch.setattr(settings, "demo_instance", True)
    monkeypatch.setattr(settings, "dev_password_hash", hash_password(DEV_PASSWORD))
    encoded = hash_password(PASSWORD)
    c = Customer(display_name="First customer", email=f"{uuid4()}@example.com")
    db_session.add(c)
    db_session.flush()
    users = {}
    for role in ("ADMIN", "STAFF", "CUSTOMER"):
        u = User(display_name=role, normalized_email=f"{uuid4()}@example.com", password_hash=encoded,
                 role=role, customer_id=c.id if role == "CUSTOMER" else None)
        db_session.add(u)
        db_session.flush()
        users[role] = u
    return users


def login(client, user):
    result = client.post("/api/v1/auth/login", json={"email": user.normalized_email, "password": PASSWORD})
    assert result.status_code == 200
    return result.json()["data"]


def unlock(client, user):
    signed = login(client, user)
    result = client.post("/api/v1/dev-tools/unlock", json={"password": DEV_PASSWORD},
                         headers={"X-CSRF-Token": signed["csrf_token"]})
    assert result.status_code == 200, result.text
    return result.json()["data"]


def switch(client, grant, user):
    result = client.post("/api/v1/dev-tools/switch", json={"user_id": str(user.id)},
                         headers={"X-Dev-CSRF-Token": grant["dev_csrf_token"]})
    assert result.status_code == 200, result.text
    return result.json()["data"]


def test_requires_real_admin_and_both_separate_csrf_tokens(client, people):
    signed = login(client, people["ADMIN"])
    denied = client.post("/api/v1/dev-tools/unlock", json={"password": DEV_PASSWORD})
    assert denied.status_code == 403
    denied = client.post("/api/v1/dev-tools/unlock", json={"password": "wrong"},
                         headers={"X-CSRF-Token": signed["csrf_token"]})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "DEV_ACCESS_DENIED"
    assert client.get("/api/v1/auth/session").status_code == 200
    for role in ("STAFF", "CUSTOMER"):
        signed = login(client, people[role])
        denied = client.post("/api/v1/dev-tools/unlock", json={"password": DEV_PASSWORD},
                             headers={"X-CSRF-Token": signed["csrf_token"]})
        assert denied.status_code == 403


def test_actual_role_customer_isolation_audit_switch_revocation_and_restore(client, people, db_session):
    grant = unlock(client, people["ADMIN"])
    denied = client.post("/api/v1/dev-tools/switch", json={"user_id": str(people["CUSTOMER"].id)})
    assert denied.status_code == 403
    target = switch(client, grant, people["CUSTOMER"])
    old_cookie = client.cookies.get(get_settings().session_cookie_name)
    assert target["actor"]["customer_id"] == str(people["CUSTOMER"].customer_id)
    assert client.get("/api/v1/products").status_code == 403
    assert client.get(f"/api/v1/portal/invoices/{uuid4()}").status_code == 404
    result = client.post("/api/v1/products", json={"name": "Forbidden"},
                         headers={"X-CSRF-Token": target["csrf_token"]})
    assert result.status_code == 403
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.action == "DEV_BUSINESS_WRITE_ATTEMPT"))
    switched = switch(client, grant, people["STAFF"])
    assert switched["actor"]["role"] == "STAFF"
    assert client.get("/api/v1/auth/session", headers={"Cookie": f"cadentra_session={old_cookie}; cadentra_dev_grant={client.cookies.get('cadentra_dev_grant')}"}).status_code == 401
    ended = client.post("/api/v1/dev-tools/end", headers={"X-Dev-CSRF-Token": grant["dev_csrf_token"]})
    assert ended.status_code == 200 and ended.json()["data"]["actor"]["role"] == "ADMIN"
    assert client.get("/api/v1/dev-tools/status").json()["data"]["unlocked"] is False
    assert people["CUSTOMER"].role == "CUSTOMER"


@pytest.mark.parametrize("invalidation", ["expiry", "disable", "rotation", "operator", "original_session"])
def test_linked_sessions_lose_authority_on_every_request(client, people, db_session, monkeypatch, invalidation):
    grant = unlock(client, people["ADMIN"])
    switch(client, grant, people["CUSTOMER"])
    row = db_session.scalar(select(DevAccessGrant))
    if invalidation == "expiry":
        row.expires_at = get_clock().now() - timedelta(seconds=1)
    elif invalidation == "disable":
        monkeypatch.setattr(get_settings(), "dev_tools_enabled", False)
    elif invalidation == "rotation":
        monkeypatch.setattr(get_settings(), "dev_password_hash", hash_password("Changed-Private-Password!"))
    elif invalidation == "operator":
        people["ADMIN"].active = False
    else:
        db_session.get(SessionRecord, row.original_session_id).revoked_at = get_clock().now()
    db_session.flush()
    assert client.get("/api/v1/auth/session").status_code == 401
    assert client.get("/api/v1/dev-tools/accounts").status_code in {403,404}


def test_normal_login_terminates_grant_and_disabled_routes_are_hidden(client, people, db_session, monkeypatch):
    grant = unlock(client, people["ADMIN"])
    switch(client, grant, people["CUSTOMER"])
    login(client, people["STAFF"])
    assert db_session.scalar(select(DevAccessGrant.revoked_at)) is not None
    assert client.get("/api/v1/dev-tools/status").json()["data"]["unlocked"] is False
    monkeypatch.setattr(get_settings(), "dev_tools_enabled", False)
    assert client.get("/api/v1/dev-tools/status").json()["data"] == {"enabled": False,"unlocked": False}
    assert client.get("/api/v1/dev-tools/accounts").status_code == 404


def test_grant_alone_is_insufficient_and_account_listing_is_bounded(client, people):
    assert client.get("/api/v1/dev-tools/accounts").status_code == 403
    grant = unlock(client, people["ADMIN"])
    result = client.get("/api/v1/dev-tools/accounts?page=1&page_size=1&q=CUSTOMER")
    assert result.status_code == 200
    data = result.json()
    assert data["total"] == 1 and data["items"][0]["id"] == str(people["CUSTOMER"].id)
    assert set(data["items"][0]) == {"id", "name", "role", "customer_id", "email"}
    raw = client.cookies.get(get_settings().dev_grant_cookie_name)
    assert client.get("/api/v1/dev-tools/accounts", headers={"Cookie": f"cadentra_dev_grant={raw}"}).status_code == 403
    target = switch(client, grant, people["CUSTOMER"])
    session = client.cookies.get(get_settings().session_cookie_name)
    assert client.get("/api/v1/auth/session", headers={"Cookie": f"cadentra_session={session}"}).status_code == 401
    assert target["actor"]["role"] == "CUSTOMER"


def test_impersonated_admin_cannot_unlock_and_logout_revokes_grant(client, people, db_session):
    grant = unlock(client, people["ADMIN"])
    target = switch(client, grant, people["ADMIN"])
    denied = client.post("/api/v1/dev-tools/unlock", json={"password": DEV_PASSWORD},
                         headers={"X-CSRF-Token": target["csrf_token"]})
    assert denied.status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": target["csrf_token"]}).status_code == 200
    assert db_session.scalar(select(DevAccessGrant.revoked_at)) is not None
    assert client.get("/api/v1/dev-tools/accounts").status_code == 403


def test_startup_disable_then_reenable_cannot_revive_unseen_grants(client, people, db_session, monkeypatch):
    from app.db import session as database
    from app.modules.identity import dev_tools
    grant = unlock(client, people["ADMIN"])
    switch(client, grant, people["CUSTOMER"])
    monkeypatch.setattr(get_settings(), "dev_tools_enabled", False)
    # Use the same transaction-backed factory as the real HTTP test server.
    dev_tools.reconcile_configuration()
    assert db_session.scalar(select(DevAccessGrant.revoked_at)) is not None
    monkeypatch.setattr(get_settings(), "dev_tools_enabled", True)
    dev_tools.reconcile_configuration()
    assert client.get("/api/v1/auth/session").status_code == 401
    assert database.SessionFactory is not None



def test_write_attempt_failure_prevents_mutation(client, people, db_session, monkeypatch, caplog):
    from sqlalchemy.exc import SQLAlchemyError

    from app.models import Product
    from app.modules.identity import dev_audit
    grant = unlock(client, people["ADMIN"])
    target = switch(client, grant, people["ADMIN"])
    def unavailable(*args, **kwargs):
        raise SQLAlchemyError("sensitive-audit-storage-detail")
    monkeypatch.setattr(dev_audit, "store_event", unavailable)
    name = f"must-not-exist-{uuid4()}"
    result = client.post("/api/v1/products", json={"name": name, "product_type": "SERVICE",
        "sales_price": "10.00", "cost_price": "5.00"},
        headers={"X-CSRF-Token": target["csrf_token"]})
    assert result.status_code == 503 and result.json()["error"]["code"] == "DEV_AUDIT_UNAVAILABLE"
    assert db_session.scalar(select(Product.id).where(Product.name == name)) is None
    assert "sensitive-audit-storage-detail" not in caplog.text


def test_outcome_failure_preserves_committed_success_and_pending_attempt(client, people, db_session, monkeypatch, caplog):
    from sqlalchemy.exc import SQLAlchemyError

    from app.models import Product
    from app.modules.identity import dev_audit
    grant = unlock(client, people["ADMIN"])
    target = switch(client, grant, people["ADMIN"])
    original = dev_audit.store_event
    def unavailable(context, action, details, event_id):
        if action == "DEV_BUSINESS_WRITE_OUTCOME":
            raise SQLAlchemyError("sensitive-audit-storage-detail")
        return original(context, action, details, event_id)
    monkeypatch.setattr(dev_audit, "store_event", unavailable)
    name = f"durable-business-success-{uuid4()}"
    result = client.post("/api/v1/products", json={"name": name, "product_type": "SERVICE",
        "sales_price": "10.00", "cost_price": "5.00"},
        headers={"X-CSRF-Token": target["csrf_token"]})
    assert result.status_code == 201, result.text
    assert db_session.scalar(select(Product.id).where(Product.name == name)) is not None
    request_id = result.headers["x-request-id"]
    events = db_session.scalars(select(AuditEvent).where(
        AuditEvent.redacted_details["request_id"].as_string() == request_id)).all()
    assert len(events) == 1 and events[0].action == "DEV_BUSINESS_WRITE_ATTEMPT"
    assert events[0].redacted_details["state"] == "PENDING"
    assert "sensitive-audit-storage-detail" not in caplog.text


def test_unhandled_failure_retains_attempt_and_failure_outcome(client, people, db_session):
    from fastapi.testclient import TestClient
    grant = unlock(client, people["ADMIN"])
    target = switch(client, grant, people["ADMIN"])
    @client.app.post("/api/v1/audit-unhandled-probe")
    def fail():
        raise RuntimeError("private-unhandled-detail")
    probe = TestClient(client.app, cookies=client.cookies,
        headers={"Origin": get_settings().allowed_origins[0]}, raise_server_exceptions=False)
    result = probe.post("/api/v1/audit-unhandled-probe", headers={"X-CSRF-Token": target["csrf_token"]})
    assert result.status_code == 500
    assert "private-unhandled-detail" not in result.text
    events = db_session.scalars(select(AuditEvent).where(
        AuditEvent.redacted_details["path"].as_string() == "/api/v1/audit-unhandled-probe")).all()
    assert len(events) == 1 and events[0].action == "DEV_BUSINESS_WRITE_ATTEMPT"
    outcome = db_session.scalar(select(AuditEvent).where(
        AuditEvent.action == "DEV_BUSINESS_WRITE_OUTCOME",
        AuditEvent.redacted_details["attempt_id"].as_string() == str(events[0].id)))
    assert outcome.redacted_details["http_status"] == 500
    assert outcome.redacted_details["error_type"] == "RuntimeError"


def test_normal_logout_and_login_revoke_original_admin_source(client, people, db_session):
    grant = unlock(client, people["ADMIN"])
    row = db_session.scalar(select(DevAccessGrant))
    original_id = row.original_session_id
    target = switch(client, grant, people["CUSTOMER"])
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": target["csrf_token"]}).status_code == 200
    db_session.expire_all()
    assert db_session.get(SessionRecord, original_id).revoked_at is not None
    grant = unlock(client, people["ADMIN"])
    row = db_session.scalar(select(DevAccessGrant).where(DevAccessGrant.revoked_at.is_(None)))
    original_id = row.original_session_id
    switch(client, grant, people["CUSTOMER"])
    login(client, people["STAFF"])
    db_session.expire_all()
    assert db_session.get(SessionRecord, original_id).revoked_at is not None


def test_terminal_end_clears_cookies_without_restoring_admin_but_bad_csrf_preserves_context(client, people, db_session):
    grant = unlock(client, people["ADMIN"])
    switch(client, grant, people["CUSTOMER"])
    rejected = client.post("/api/v1/dev-tools/end", headers={"X-Dev-CSRF-Token": "wrong"})
    assert rejected.status_code == 403
    assert client.get("/api/v1/auth/session").json()["data"]["actor"]["role"] == "CUSTOMER"
    row = db_session.scalar(select(DevAccessGrant))
    row.expires_at = get_clock().now() - timedelta(seconds=1)
    db_session.flush()
    ended = client.post("/api/v1/dev-tools/end", headers={"X-Dev-CSRF-Token": grant["dev_csrf_token"]})
    assert ended.status_code == 401 and ended.json()["error"]["code"] == "DEV_SESSION_EXPIRED"
    assert not client.cookies.get(get_settings().session_cookie_name)
    assert not client.cookies.get(get_settings().dev_grant_cookie_name)
    db_session.expire_all()
    assert db_session.get(DevAccessGrant, row.id).revoked_at is not None
    assert db_session.get(SessionRecord, row.original_session_id).revoked_at is not None


def test_logout_with_missing_grant_cookie_revokes_actual_context(client, people, db_session):
    grant = unlock(client, people["ADMIN"])
    row = db_session.scalar(select(DevAccessGrant))
    original_id = row.original_session_id
    target = switch(client, grant, people["CUSTOMER"])
    client.cookies.delete(get_settings().dev_grant_cookie_name)
    rejected = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"})
    assert rejected.status_code == 403
    result = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": target["csrf_token"]})
    assert result.status_code == 200
    assert not client.cookies.get(get_settings().session_cookie_name)
    assert not client.cookies.get(get_settings().dev_grant_cookie_name)
    db_session.expire_all()
    assert db_session.get(SessionRecord, original_id).revoked_at is not None
    assert db_session.get(DevAccessGrant, row.id).revoked_at is not None
    linked = db_session.scalars(select(SessionRecord).where(SessionRecord.dev_grant_id == row.id)).all()
    assert linked and all(session.revoked_at is not None for session in linked)
