"""Fail closed on schema mismatch and reject offsets PostgreSQL cannot represent."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import Actor
from app.core.errors import DomainError
from app.core.pagination import MAX_OFFSET, safe_offset
from app.core.security import hash_password
from app.db.session import get_session
from app.main import create_app
from app.models import User
from app.modules.billing.invoices import list_invoice_payments
from app.modules.identity.rate_limit import reset_rate_limits


@pytest.mark.parametrize(
    "revisions,status",
    [
        (["0003"], 200),
        (["0001"], 503),
        (["unknown-revision"], 503),
        ([], 503),
        (["0003", "unknown-revision"], 503),
    ],
)
def test_readiness_requires_exactly_the_current_migration(revisions, status):
    class Database:
        def execute(self, statement):
            return None

        def scalars(self, statement):
            return SimpleNamespace(all=lambda: revisions)

    application = create_app()
    application.dependency_overrides[get_session] = lambda: Database()
    with TestClient(application) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == status
    if status == 200:
        assert response.json()["data"] == {"status": "ready", "migration": "0003"}
    else:
        assert response.json()["error"]["code"] == "NOT_READY"
        assert "unknown-revision" not in response.text
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_readiness_database_failure_is_generic():
    class Database:
        def execute(self, statement):
            raise SQLAlchemyError("private connection diagnostic must not reach the response")

    application = create_app()
    application.dependency_overrides[get_session] = lambda: Database()
    with TestClient(application) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    assert "private connection diagnostic" not in response.text


@pytest.mark.parametrize("page,page_size", [(1, 1), (1, 100), (7, 25), (MAX_OFFSET + 1, 1)])
def test_safe_offset_preserves_valid_pagination(page, page_size):
    assert safe_offset(page, page_size) == (page - 1) * page_size


@pytest.mark.parametrize(
    "page,page_size",
    [
        (0, 25),
        (-1, 25),
        (1, 0),
        (1, 101),
        (True, 25),
        (1, True),
        (1.5, 25),
        (1, 1.5),
        (MAX_OFFSET + 2, 1),
        (10**30, 100),
    ],
)
def test_unsupported_pagination_returns_validation_error(page, page_size):
    with pytest.raises(DomainError) as error:
        safe_offset(page, page_size)
    assert error.value.status_code == 422
    assert error.value.code == "INVALID_PAGINATION"


@pytest.fixture
def admin_client(client, db_session):
    reset_rate_limits()
    email = f"pagination-{uuid4()}@example.com"
    password = "Pagination-Valid!Password"
    with db_session.begin():
        db_session.add(
            User(
                display_name="Pagination admin",
                normalized_email=email,
                password_hash=hash_password(password),
                role="ADMIN",
            )
        )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    try:
        yield client
    finally:
        reset_rate_limits()


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    [
        "customers",
        "products",
        "plans",
        "subscriptions",
        "quotation-templates",
        "invoices",
        "tax-rules",
        "discount-rules",
    ],
)
def test_staff_list_offset_overflow_is_422_and_normal_page_still_works(admin_client, path):
    response = admin_client.get(f"/api/v1/{path}?page={10**30}&page_size=100")
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"INVALID_PAGINATION", "INVALID_FILTER"}
    response = admin_client.get(f"/api/v1/{path}?page=1&page_size=25")
    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["page_size"] == 25


def test_payment_history_rejects_impossible_offset_before_list_query(monkeypatch):
    from app.modules.billing import invoices

    # Ownership lookup remains first; an invalid offset never reaches list SQL.
    monkeypatch.setattr(invoices, "_invoice", lambda *args: SimpleNamespace(id=uuid4()))
    with pytest.raises(DomainError) as error:
        list_invoice_payments(None, Actor(uuid4(), "ADMIN"), uuid4(), page=10**30)
    assert error.value.status_code == 422
    assert error.value.code == "INVALID_FILTER"
