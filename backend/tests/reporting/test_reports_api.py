"""Report HTTP contracts with actual PostgreSQL users, login and cookie sessions."""

from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models import User
from app.modules.identity.rate_limit import reset_rate_limits

pytestmark = pytest.mark.integration
PASSWORD = "Reports-Fixture!"
ENDPOINTS = ("/api/v1/reports/summary", "/api/v1/reports/revenue-series")
RANGE = {"from": "2026-10-01", "to": "2026-11-01"}


@pytest.fixture(autouse=True)
def isolated_login_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


def login_role(client, db_session, reporting_case, role="STAFF"):
    email = f"report-{uuid4()}@example.com"
    user = User(
        display_name="Report API fixture",
        normalized_email=email,
        password_hash=hash_password(PASSWORD),
        role=role,
        customer_id=reporting_case["customers"]["A"].id if role == "CUSTOMER" else None,
    )
    db_session.add(user)
    db_session.commit()
    result = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert result.status_code == 200, result.text
    assert result.json()["data"]["actor"]["role"] == role
    assert client.get("/api/v1/auth/session").status_code == 200


@pytest.mark.parametrize("role", ["STAFF", "ADMIN"])
def test_report_endpoints_use_real_session_and_public_query_aliases(
    client, db_session, reporting_case, role
):
    login_role(client, db_session, reporting_case, role)
    result = client.get(ENDPOINTS[0], params=RANGE)
    assert result.status_code == 200
    payload = result.json()
    assert set(payload) == {"data"}
    expected = reporting_case["case"]["expectedSummary"]["combined"]["data"]
    assert {key: payload["data"][key] for key in expected} == expected
    assert payload["data"]["metric_basis"]["date_range"] == "[from,to)"
    assert isinstance(payload["data"]["invoiced_gross_in_range"], str)
    series = client.get(ENDPOINTS[1], params=RANGE)
    assert series.status_code == 200
    assert series.json() == reporting_case["case"]["expectedDailySeries"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_report_endpoint_requires_authentication(client, reporting_case, endpoint):
    result = client.get(endpoint, params=RANGE)
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "UNAUTHENTICATED"
    assert "data" not in result.json()
    assert result.json()["error"]["request_id"] == result.headers["X-Request-ID"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_customer_cannot_read_reports_even_for_their_own_customer(
    client, db_session, reporting_case, endpoint
):
    login_role(client, db_session, reporting_case, "CUSTOMER")
    result = client.get(
        endpoint,
        params={**RANGE, "customer_id": str(reporting_case["customers"]["A"].id)},
    )
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "FORBIDDEN"
    assert "data" not in result.json()


def test_default_range_is_business_month_through_today(client, db_session, reporting_case):
    login_role(client, db_session, reporting_case)
    summary = client.get(ENDPOINTS[0])
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["range_from"] == "2026-11-01"
    assert data["range_to"] == "2026-11-03"
    assert data["as_of"] == "2026-11-02"
    assert data["invoiced_gross_in_range"] == data["cash_received_in_range"] == "600.00"
    assert data["outstanding_now"] == "3570.16"
    series = client.get(ENDPOINTS[1])
    assert series.status_code == 200
    assert series.json()["data"]["buckets"] == [
        {
            "period_start": "2026-11-01",
            "period_end": "2026-11-02",
            "invoiced_gross": "600.00",
            "cash_received": "600.00",
        },
        {
            "period_start": "2026-11-02",
            "period_end": "2026-11-03",
            "invoiced_gross": "0.00",
            "cash_received": "0.00",
        },
    ]


def test_customer_filter_and_monthly_cadence_are_wired(client, db_session, reporting_case):
    login_role(client, db_session, reporting_case)
    params = {**RANGE, "customer_id": str(reporting_case["customers"]["A"].id)}
    summary = client.get(ENDPOINTS[0], params=params)
    assert summary.status_code == 200
    assert summary.json()["data"]["invoiced_gross_in_range"] == "5670.16"
    series = client.get(ENDPOINTS[1], params={**params, "cadence": "MONTHLY"})
    assert series.status_code == 200
    assert series.json()["data"]["cadence"] == "MONTHLY"
    assert series.json()["data"]["buckets"] == [
        {
            "period_start": "2026-10-01",
            "period_end": "2026-11-01",
            "invoiced_gross": "5670.16",
            "cash_received": "3050.00",
        }
    ]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize(
    "params",
    [
        {"from": "not-a-date", "to": "2026-11-01"},
        {"from": "2026-11-01", "to": "2026-10-01"},
        {"from": "2026-10-01", "to": "2026-10-01"},
        {"from": "2025-01-01", "to": "2027-01-01"},
        {**RANGE, "customer_id": "not-a-uuid"},
    ],
)
def test_invalid_report_query_uses_error_envelope(
    client, db_session, reporting_case, endpoint, params
):
    login_role(client, db_session, reporting_case)
    result = client.get(endpoint, params=params)
    assert result.status_code == 422
    assert set(result.json()) == {"error"}
    assert result.json()["error"]["code"] in ("VALIDATION_ERROR", "INVALID_REPORT_RANGE")
    assert result.json()["error"]["request_id"] == result.headers["X-Request-ID"]


def test_unsupported_cadence_rejected_at_http_boundary(client, db_session, reporting_case):
    login_role(client, db_session, reporting_case)
    result = client.get(ENDPOINTS[1], params={**RANGE, "cadence": "WEEKLY"})
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"
