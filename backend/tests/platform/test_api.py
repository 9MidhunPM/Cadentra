from uuid import uuid4

import pytest

from app.core.auth import Actor, Role, require_customer_ownership
from app.core.errors import DomainError


def test_health_and_unimplemented_feature(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ready"
    response = client.get("/api/v1/subscriptions")
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"
    assert response.json()["error"]["request_id"]
    response = client.get("/not-a-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_customer_ownership_hides_other_record():
    customer = uuid4()
    actor = Actor(uuid4(), Role.CUSTOMER, customer)
    require_customer_ownership(actor, customer)
    with pytest.raises(DomainError) as exc:
        require_customer_ownership(actor, uuid4())
    assert exc.value.status_code == 404


def test_malformed_csrf_is_forbidden_not_server_error(client):
    account = {"name": "CSRF test", "email": "csrf@example.com", "password": "ValidPass!"}
    assert client.post("/api/v1/auth/signup", json=account).status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login", json={k: account[k] for k in ("email", "password")}
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/auth/logout",
        headers=[(b"x-csrf-token", b"\xff"), (b"origin", b"http://localhost:5171")],
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_CSRF"
    assert client.get("/api/v1/auth/session").status_code == 200


def test_seeded_demo_admin_can_log_in(client, db_session):
    from app.core.config import get_settings
    from app.seed import seed_demo

    settings = get_settings()
    with db_session.begin():
        seed_demo(db_session, settings.demo_admin_email, "ValidDemo!Password")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.demo_admin_email, "password": "ValidDemo!Password"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["actor"]["role"] == "ADMIN"
