"""HTTP authorization/clock boundary; actual issuance/races are tested separately."""

from uuid import uuid4

from test_rules import _login

from app.core.clock import get_clock
from app.core.config import get_settings
from app.modules.billing import router
from app.modules.billing.issuance import BillingRunResult


def test_due_action_uses_server_clock_and_rejects_extra_inputs(client, db_session, monkeypatch):
    calls = []

    def run(factory, cutoff, limit, *, actor):
        calls.append((cutoff, limit, actor.role))
        return BillingRunResult(0, 0, 0, 0, 0, False, ())

    monkeypatch.setattr(router, "run_due", run)
    assert client.post("/api/v1/billing/run-due", json={}).status_code == 401
    headers = _login(client, db_session, "STAFF")
    assert client.post("/api/v1/billing/run-due", json={}).status_code == 403
    assert (
        client.post(
            "/api/v1/billing/run-due", json={"as_of": "2000-01-01"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v1/billing/run-due", json={"limit": 9999}, headers=headers).status_code
        == 422
    )
    assert not calls
    response = client.post("/api/v1/billing/run-due", json={}, headers=headers)
    assert response.status_code == 200, response.text
    assert calls == [(get_clock().today(), get_settings().worker_batch_size, "STAFF")]
    assert response.json()["data"]["has_more_due"] is False


def test_customer_cannot_run_billing(client):
    from app.modules.identity.rate_limit import reset_rate_limits

    reset_rate_limits()
    email = f"{uuid4()}@example.com"
    signup = {"name": "Customer", "email": email, "password": "BillingCustomer!"}
    assert client.post("/api/v1/auth/signup", json=signup).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": signup["password"]})
    headers = {"X-CSRF-Token": login.json()["data"]["csrf_token"]}
    assert client.post("/api/v1/billing/run-due", json={}, headers=headers).status_code == 403
