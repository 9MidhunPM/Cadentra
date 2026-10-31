from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.clock import get_clock
from app.core.security import hash_password
from app.models import Customer, EmailOutbox, PasswordResetToken, SessionRecord, User
from app.modules.identity.rate_limit import reset_rate_limits

pytestmark = pytest.mark.integration
PASSWORD = "Valid-Password!"


@pytest.fixture(autouse=True)
def clear_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


def signup(client, email="person@example.com", **extra):
    return client.post(
        "/api/v1/auth/signup",
        json={"name": "Customer", "email": email, "password": PASSWORD, **extra},
    )


def login(client, email="person@example.com", password=PASSWORD):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = response.json()["data"]["csrf_token"]
    return response


def reset_token(db_session):
    row = db_session.scalar(
        select(EmailOutbox).where(
            EmailOutbox.kind == "RESET", EmailOutbox.recipient == "person@example.com"
        )
    )
    return parse_qs(urlparse(row.payload["reset_url"]).query)["token"][0]


def test_signup_is_atomic_normalized_and_cannot_escalate(client, db_session):
    first = signup(client, "Person@EXAMPLE.COM")
    assert first.status_code == 201
    assert first.json()["data"]["role"] == "CUSTOMER"
    assert "password" not in str(first.json())
    assert signup(client, "person@example.com").status_code == 409
    assert signup(client, "other@example.com", role="ADMIN").status_code == 422
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.normalized_email.in_(("person@example.com", "other@example.com")))
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.email.in_(("person@example.com", "other@example.com")))
        )
        == 1
    )


@pytest.mark.parametrize("password", ["Abcdefg!", "abcdefgh!", "ABCDEFGH!", "Abcdefghi"])
def test_password_requirements_reject_invalid_without_partial_customer(
    client, db_session, password
):
    response = signup(client, password=password)
    assert response.status_code == 422
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.email.in_(("person@example.com", "other@example.com")))
        )
        == 0
    )


def test_password_nine_characters_without_digit_is_valid(client):
    assert signup(client, password="Abcdefgh!").status_code == 201


def test_signup_does_not_link_staff_customer_by_email(client, db_session):
    customer = Customer(display_name="Existing", email="person@example.com")
    db_session.add(customer)
    db_session.commit()
    response = signup(client)
    assert response.status_code == 201
    assert UUID(response.json()["data"]["customer_id"]) != customer.id


def test_login_session_logout_require_real_cookie_and_csrf(client, db_session):
    signup(client)
    assert client.get("/api/v1/auth/session").status_code == 401
    response = login(client)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Path=/api" in response.headers["set-cookie"]
    assert client.get("/api/v1/auth/session").json()["data"] == response.json()["data"]
    bad = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"})
    assert bad.status_code == 403
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/session").status_code == 401
    assert (
        db_session.scalar(
            select(SessionRecord)
            .join(User, User.id == SessionRecord.user_id)
            .where(User.normalized_email == "person@example.com")
        ).revoked_at
        is not None
    )


def test_login_rejects_wrong_password_and_missing_origin(client):
    signup(client)
    assert login(client, password="Incorrect!").status_code == 401
    client.headers.pop("Origin")
    assert login(client).status_code == 403


def test_expired_session_cannot_authenticate(client, db_session):
    signup(client)
    login(client)
    record = db_session.scalar(
        select(SessionRecord)
        .join(User, User.id == SessionRecord.user_id)
        .where(User.normalized_email == "person@example.com")
    )
    record.expires_at = get_clock().now() - timedelta(seconds=1)
    db_session.commit()
    assert client.get("/api/v1/auth/session").status_code == 401


def test_reset_is_generic_hashed_single_use_and_revokes_session(client, db_session):
    signup(client)
    login(client)
    known = client.post("/api/v1/auth/password-reset/request", json={"email": "person@example.com"})
    unknown = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "missing@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    raw = reset_token(db_session)
    record = db_session.scalar(
        select(PasswordResetToken)
        .join(User, User.id == PasswordResetToken.user_id)
        .where(User.normalized_email == "person@example.com")
    )
    assert raw != record.token_hash
    assert raw not in str(known.json())
    db_session.rollback()
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw, "new_password": "Replacement-Pass!"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/session").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/password-reset/confirm", json={"token": raw, "new_password": PASSWORD}
        ).status_code
        == 409
    )
    assert login(client, password=PASSWORD).status_code == 401
    assert login(client, password="Replacement-Pass!").status_code == 200


def test_expired_reset_cannot_change_password(client, db_session):
    signup(client)
    client.post("/api/v1/auth/password-reset/request", json={"email": "person@example.com"})
    raw = reset_token(db_session)
    db_session.scalar(
        select(PasswordResetToken)
        .join(User, User.id == PasswordResetToken.user_id)
        .where(User.normalized_email == "person@example.com")
    ).expires_at = get_clock().now() - timedelta(seconds=1)
    db_session.commit()
    assert (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw, "new_password": "New-Password!"},
        ).status_code
        == 409
    )
    assert login(client).status_code == 200


def test_admin_only_staff_and_operator_customer_crud(client, db_session):
    admin = User(
        display_name="Admin",
        normalized_email="admin@example.com",
        password_hash=hash_password(PASSWORD),
        role="ADMIN",
    )
    db_session.add(admin)
    db_session.commit()
    assert login(client, "admin@example.com").status_code == 200
    response = client.post(
        "/api/v1/staff",
        json={"name": "Staff", "email": "staff@example.com", "temporary_password": PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["data"]["role"] == "STAFF"
    assert login(client, "staff@example.com").status_code == 200
    assert (
        client.post(
            "/api/v1/staff",
            json={"name": "Other", "email": "other@example.com", "temporary_password": PASSWORD},
        ).status_code
        == 403
    )
    customer_email = f"billing-{uuid4()}@example.com"
    created = client.post(
        "/api/v1/customers", json={"display_name": "Billing Person", "email": customer_email}
    )
    assert created.status_code == 201
    identifier = created.json()["data"]["id"]
    assert (
        client.patch(
            f"/api/v1/customers/{identifier}", json={"company_name": "Brightloop"}
        ).status_code
        == 200
    )
    listing = client.get(f"/api/v1/customers?q={customer_email}").json()
    assert listing["total"] == 1
    assert listing["items"][0]["company_name"] == "Brightloop"
    assert client.get(f"/api/v1/customers/{identifier}").status_code == 200
    assert client.get("/api/v1/customers?page_size=101").status_code == 422
    signup(client)
    login(client)
    assert client.get("/api/v1/customers").status_code == 403
    assert client.get(f"/api/v1/customers/{identifier}").status_code == 403


def test_login_rate_limit_is_applied_even_to_unknown_accounts(client):
    for _ in range(10):
        assert login(client, "missing@example.com").status_code == 401
    assert login(client, "missing@example.com").status_code == 429
