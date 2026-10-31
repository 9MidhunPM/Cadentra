"""Portal authorization against real PostgreSQL, actual cookies and request dependencies."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.auth import Actor, Role
from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import hash_token
from app.models import (
    BillingPeriod,
    Customer,
    Invoice,
    Payment,
    Plan,
    Product,
    SessionRecord,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    User,
)
from app.modules.reporting import portal_service

pytestmark = pytest.mark.integration


@pytest.fixture
def portal_records(db_session):
    customers = [
        Customer(
            display_name=name,
            email=f"{name.lower()}@portal.example",
            company_name="Demo",
            billing_address={
                "line1": "1 Test Street",
                "city": "Kochi",
                "internal_note": "SECRET_ADDRESS",
                "country": {"secret": "nested"},
            },
        )
        for name in ("Alice", "Bob")
    ]
    plan = Plan(name="Public plan", cadence="MONTHLY", available_from=date(2026, 1, 1))
    product = Product(name="Public product", product_type="SERVICE", cost_price=Decimal("17.00"))
    db_session.add_all([*customers, plan, product])
    db_session.flush()
    users = [
        User(
            display_name=customer.display_name,
            normalized_email=customer.email,
            role="CUSTOMER",
            customer_id=customer.id,
            password_hash="unused-by-session-read-test",
        )
        for customer in customers
    ]
    users.extend(
        User(
            display_name=role,
            normalized_email=f"{role.lower()}@portal.example",
            role=role,
            password_hash="unused-by-session-read-test",
        )
        for role in ("ADMIN", "STAFF")
    )
    db_session.add_all(users)
    db_session.flush()
    tokens = {}
    for user in users:
        token = f"portal-test-{uuid4()}"
        tokens[user.display_name] = token
        db_session.add(
            SessionRecord(
                user_id=user.id,
                token_hash=hash_token(token),
                csrf_token="portal-read-test",
                expires_at=get_clock().now() + timedelta(hours=1),
            )
        )
    subscriptions = []
    invoices = []
    for customer in [customers[0], customers[0], customers[1]]:
        subscription = Subscription(
            customer_id=customer.id,
            plan_id=plan.id,
            state="ACTIVE",
            start_date=date(2026, 10, 1),
            end_date=date(2027, 10, 1),
            created_at=datetime(2026, 10, 1, tzinfo=UTC),
            close_reason="SECRET_CLOSE",
            plan_snapshot={
                "name": "Original plan",
                "base_fee": "10.00",
                "cadence": "MONTHLY",
                "allow_pause": True,
                "cost_price": "SECRET_PLAN",
                "currency": {"secret": "nested"},
            },
        )
        db_session.add(subscription)
        db_session.flush()
        db_session.add(
            SubscriptionLine(
                subscription_id=subscription.id,
                product_id=product.id,
                description="Agreed line",
                quantity=3,
                unit_price=Decimal("1560.00"),
                price_snapshot={"cost_price": "SECRET_LINE", "staff_notes": "SECRET_NOTE"},
            )
        )
        db_session.add(
            SubscriptionPause(
                subscription_id=subscription.id,
                starts_on=date(2026, 11, 1),
                ends_on=date(2026, 12, 1),
            )
        )
        period = BillingPeriod(
            subscription_id=subscription.id,
            cycle_index=0,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 11, 1),
            disposition="INVOICED",
        )
        db_session.add(period)
        db_session.flush()
        invoice = Invoice(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_id=period.id,
            status="CONFIRMED",
            invoice_date=date(2026, 10, 1),
            due_date=date(2026, 10, 8),
            subtotal=Decimal("4680.00"),
            discount_total=Decimal("468.00"),
            tax_total=Decimal("758.16"),
            total=Decimal("4970.16"),
            customer_snapshot={"staff_notes": "SECRET_INVOICE"},
            seller_snapshot={},
            calculation_snapshot={"cost_price": "SECRET_CALCULATION"},
            created_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
        db_session.add(invoice)
        db_session.flush()
        subscriptions.append(subscription)
        invoices.append(invoice)
    # Two payments on one invoice exercise grouping without multiplying list rows.
    for amount in ("1200.00", "800.00"):
        db_session.add(
            Payment(
                invoice_id=invoices[0].id,
                method="MANUAL",
                amount=Decimal(amount),
                paid_on=date(2026, 10, 2),
                request_key=str(uuid4()),
                request_payload_hash="a" * 64,
                created_by=users[2].id,
                note="SECRET_PAYMENT_NOTE",
            )
        )
    db_session.commit()
    return {
        "customers": customers,
        "subscriptions": subscriptions,
        "invoices": invoices,
        "users": users,
        "tokens": tokens,
    }


def sign_in(client, records, name="Alice"):
    client.cookies.set(get_settings().session_cookie_name, records["tokens"][name])


def test_profile_projects_customer_fields_and_redacts_unknown_address_data(client, portal_records):
    sign_in(client, portal_records)
    response = client.get("/api/v1/portal/me")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": str(portal_records["customers"][0].id),
        "display_name": "Alice",
        "email": "alice@portal.example",
        "company_name": "Demo",
        "billing_address": {"line1": "1 Test Street", "city": "Kochi"},
    }


def test_subscription_pages_have_owner_scoped_counts_and_stable_order(client, portal_records):
    sign_in(client, portal_records)
    pages = [
        client.get(f"/api/v1/portal/subscriptions?page={page}&page_size=1").json()
        for page in (1, 2, 3)
    ]
    expected = sorted((str(row.id) for row in portal_records["subscriptions"][:2]), reverse=True)
    assert [pages[0]["items"][0]["id"], pages[1]["items"][0]["id"]] == expected
    assert all(page["total"] == 2 for page in pages)
    assert pages[2]["items"] == []
    assert pages[0]["page_size"] == 1


def test_subscription_details_are_snapshot_based_safe_and_isolated(
    client, portal_records, db_session
):
    sign_in(client, portal_records)
    owned, _, foreign = portal_records["subscriptions"]
    response = client.get(f"/api/v1/portal/subscriptions/{owned.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["plan_snapshot"] == {
        "name": "Original plan",
        "base_fee": "10.00",
        "cadence": "MONTHLY",
        "allow_pause": True,
    }
    assert data["lines"][0]["unit_price"] == "1560.00"
    assert data["pause_intervals"] == [{"starts_on": "2026-11-01", "ends_on": "2026-12-01"}]
    assert "allowed_actions" not in data and "next_billing_date" not in data
    assert "SECRET" not in response.text
    before = db_session.get(Subscription, foreign.id).revision
    for identifier in (foreign.id, uuid4()):
        denied = client.get(f"/api/v1/portal/subscriptions/{identifier}")
        assert denied.status_code == 404
        assert denied.json()["error"]["code"] == "NOT_FOUND"
        assert denied.json()["error"]["message"] == "Record not found."
    assert db_session.get(Subscription, foreign.id).revision == before


def test_invoice_list_is_owner_scoped_and_returns_stored_decimal_total(client, portal_records):
    sign_in(client, portal_records)
    response = client.get("/api/v1/portal/invoices?page_size=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2 and len(payload["items"]) == 1
    row = payload["items"][0]
    assert row["id"] in {str(invoice.id) for invoice in portal_records["invoices"][:2]}
    assert row["total"] == "4970.16"
    assert row["period_start"] == "2026-10-01" and row["period_end"] == "2026-11-01"
    assert "SECRET" not in response.text and "calculation_snapshot" not in row
    sign_in(client, portal_records, "Bob")
    other = client.get("/api/v1/portal/invoices").json()
    assert other["total"] == 1
    assert other["items"][0]["id"] == str(portal_records["invoices"][2].id)


def test_invoice_payment_aggregation_has_no_fanout_and_omits_private_notes(client, portal_records):
    sign_in(client, portal_records)
    response = client.get("/api/v1/portal/invoices")
    payload = response.json()
    assert payload["total"] == 2 and len(payload["items"]) == 2
    rows = {row["id"]: row for row in payload["items"]}
    partial = rows[str(portal_records["invoices"][0].id)]
    unpaid = rows[str(portal_records["invoices"][1].id)]
    assert partial["paid_amount"] == "2000.00" and partial["balance_due"] == "2970.16"
    assert partial["collection_status"] == "PARTIALLY_PAID"
    assert unpaid["paid_amount"] == "0.00" and unpaid["balance_due"] == "4970.16"
    assert unpaid["collection_status"] == "UNPAID"
    assert "SECRET" not in response.text


@pytest.mark.parametrize("route", ["me", "subscriptions", "invoices"])
def test_portal_rejects_customer_selection_even_for_own_id(client, portal_records, route):
    sign_in(client, portal_records)
    response = client.get(f"/api/v1/portal/{route}?customer_id={portal_records['customers'][0].id}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101", "page=no"])
@pytest.mark.parametrize("route", ["subscriptions", "invoices"])
def test_pagination_rejects_invalid_inputs(client, portal_records, route, query):
    sign_in(client, portal_records)
    assert client.get(f"/api/v1/portal/{route}?{query}").status_code == 422


@pytest.mark.parametrize("name", ["ADMIN", "STAFF"])
def test_staff_cannot_impersonate_customer_in_portal(client, portal_records, name):
    sign_in(client, portal_records, name)
    for route in ("me", "subscriptions", "invoices"):
        assert client.get(f"/api/v1/portal/{route}").status_code == 403
    assert (
        client.get(
            f"/api/v1/portal/subscriptions/{portal_records['subscriptions'][0].id}"
        ).status_code
        == 403
    )


def test_unauthenticated_requests_require_real_session(client):
    for route in ("me", "subscriptions", "invoices"):
        assert client.get(f"/api/v1/portal/{route}").status_code == 401


def test_services_defend_customer_scope_without_route_dependencies(db_session):
    for actor in (Actor(uuid4(), Role.STAFF), Actor(uuid4(), Role.CUSTOMER)):
        with pytest.raises(DomainError) as caught:
            portal_service.subscriptions(db_session, actor, 1, 25)
        assert caught.value.status_code == 403


def test_overdue_uses_business_date_and_excludes_draft_cancelled_paid(
    client, portal_records, db_session, monkeypatch
):
    class FixedClock:
        def today(self):
            return date(2026, 10, 8)

    monkeypatch.setattr(portal_service, "get_clock", lambda: FixedClock())
    sign_in(client, portal_records)
    invoice = portal_records["invoices"][1]

    def item():
        return next(
            row
            for row in client.get("/api/v1/portal/invoices").json()["items"]
            if row["id"] == str(invoice.id)
        )

    assert item()["overdue"] is False  # Due today is not overdue.
    invoice.due_date = date(2026, 10, 7)
    db_session.commit()
    assert item()["overdue"] is True
    for state in ("DRAFT", "CANCELLED", "PAID"):
        invoice.status = state
        db_session.commit()
        result = item()
        assert result["overdue"] is False
        assert result["collection_status"] == state


def test_subscription_detail_rejects_customer_selection(client, portal_records):
    sign_in(client, portal_records)
    identifier = portal_records["subscriptions"][2].id
    response = client.get(
        f"/api/v1/portal/subscriptions/{identifier}?customer_id={portal_records['customers'][1].id}"
    )
    assert response.status_code == 422


@pytest.mark.parametrize("route", ["subscriptions", "invoices"])
def test_oversized_page_returns_validation_error_instead_of_database_overflow(
    client, portal_records, route
):
    sign_in(client, portal_records)
    response = client.get(f"/api/v1/portal/{route}?page={10**30}&page_size=100")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "bigint" not in response.text
