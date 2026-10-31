"""Portal authorization against real PostgreSQL, actual cookies and request dependencies."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from app.core.auth import Actor, Role
from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import hash_token
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
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
    client, portal_records, db_session, monkeypatch
):
    from app.modules.subscriptions import queries

    class FixedClock:
        def today(self):
            return date(2026, 10, 15)

    monkeypatch.setattr(queries, "get_clock", lambda: FixedClock())
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
    assert data["pause_interval"] == {"starts_on": "2026-11-01", "ends_on": "2026-12-01"}
    assert isinstance(data["allowed_actions"], list)
    assert data["next_billing_date"] == "2026-10-01"
    assert data["invoice_references"][0]["id"] == str(portal_records["invoices"][0].id)
    assert response.headers["cache-control"] == "private, no-store"
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


@pytest.fixture
def detailed_invoice(portal_records, db_session):
    invoice = portal_records["invoices"][0]
    invoice.customer_snapshot = {
        "display_name": '<img src=x onerror="alert(1)">',
        "email": "alice@portal.example",
        "billing_address": {"city": "Kochi"},
        "staff_notes": "SECRET_CUSTOMER_NOTES",
    }
    invoice.seller_snapshot = {"name": "<script>alert(2)</script>", "private_note": "SECRET_SELLER"}
    invoice.calculation_snapshot = {
        "subtotal": "4680.00",
        "tax_total": "758.16",
        "lines": [
            {"gross": "4680.00", "internal_cost": "SECRET_COST", "staff_notes": "SECRET_NESTED"}
        ],
    }
    invoice.cancellation_reason = "SECRET_CANCELLATION"
    line = InvoiceLine(
        invoice_id=invoice.id,
        stable_line_key="product:0",
        description='<svg onload="alert(3)">',
        quantity=3,
        unit_price=Decimal("1560.00"),
        gross=Decimal("4680.00"),
        discount=Decimal("468.00"),
        taxable_amount=Decimal("4212.00"),
        tax_total=Decimal("758.16"),
        total=Decimal("4970.16"),
        source_snapshot={"cost": "SECRET_LINE_COST"},
    )
    db_session.add(line)
    db_session.flush()
    db_session.add(
        InvoiceLineTax(
            invoice_line_id=line.id,
            name_snapshot="Illustrative tax",
            rate_snapshot=Decimal("18.00"),
            amount=Decimal("758.16"),
        )
    )
    db_session.commit()
    return invoice


def test_invoice_detail_delegates_real_billing_projection(client, portal_records, detailed_invoice):
    sign_in(client, portal_records)
    response = client.get(f"/api/v1/portal/invoices/{detailed_invoice.id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()["data"]
    assert data["total"] == "4970.16"
    assert data["paid_amount"] == "2000.00" and data["balance_due"] == "2970.16"
    assert data["collection_status"] == "PARTIALLY_PAID"
    assert data["lines"][0]["taxes"][0]["amount"] == "758.16"
    assert len(data["payments"]) == 2
    assert all(
        set(payment) == {"id", "invoice_id", "method", "amount", "paid_on"}
        for payment in data["payments"]
    )
    assert data["calculation_snapshot"]["lines"] == [{"gross": "4680.00"}]
    assert "cancellation_reason" not in data
    assert "SECRET" not in response.text


def test_invoice_print_escapes_dynamic_html_and_retains_owner_security_headers(
    client, portal_records, detailed_invoice
):
    sign_in(client, portal_records)
    response = client.get(f"/api/v1/portal/invoices/{detailed_invoice.id}/print")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
    )
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in response.text
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in response.text
    assert "&lt;svg onload=&quot;alert(3)&quot;&gt;" in response.text
    assert (
        "<script>" not in response.text
        and "<img " not in response.text
        and "<svg " not in response.text
    )
    assert "4970.16" in response.text and "2970.16" in response.text
    assert "SECRET" not in response.text


@pytest.mark.parametrize("suffix", ["", "/print"])
def test_invoice_foreign_and_missing_records_are_indistinguishable(client, portal_records, suffix):
    sign_in(client, portal_records)
    failures = []
    for identifier in (portal_records["invoices"][2].id, uuid4()):
        response = client.get(f"/api/v1/portal/invoices/{identifier}{suffix}")
        assert response.status_code == 404
        error = response.json()["error"]
        failures.append((error["code"], error["message"]))
    assert failures[0] == failures[1] == ("NOT_FOUND", "Invoice not found.")


@pytest.mark.parametrize("suffix", ["", "/print"])
@pytest.mark.parametrize("role", ["ADMIN", "STAFF"])
def test_portal_invoice_endpoints_reject_staff(client, portal_records, role, suffix):
    sign_in(client, portal_records, role)
    response = client.get(f"/api/v1/portal/invoices/{portal_records['invoices'][0].id}{suffix}")
    assert response.status_code == 403


@pytest.mark.parametrize("suffix", ["", "/print"])
def test_portal_invoice_endpoints_require_authentication(client, suffix):
    assert client.get(f"/api/v1/portal/invoices/{uuid4()}{suffix}").status_code == 401


@pytest.mark.parametrize("suffix", ["", "/print"])
def test_portal_invoice_endpoints_reject_customer_override(client, portal_records, suffix):
    sign_in(client, portal_records)
    response = client.get(
        f"/api/v1/portal/invoices/{portal_records['invoices'][0].id}{suffix}?customer_id={portal_records['customers'][0].id}"
    )
    assert response.status_code == 422


def test_invoice_reads_never_write_financial_outbox_or_audit_state(
    client, portal_records, detailed_invoice, db_session, db_connection
):
    sign_in(client, portal_records)
    counts_before = [
        db_session.scalar(select(func.count()).select_from(model))
        for model in (Invoice, Payment, EmailOutbox, AuditEvent)
    ]
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(db_connection, "before_cursor_execute", capture)
    try:
        for suffix in ("", "/print"):
            assert (
                client.get(f"/api/v1/portal/invoices/{detailed_invoice.id}{suffix}").status_code
                == 200
            )
    finally:
        event.remove(db_connection, "before_cursor_execute", capture)
    assert statements and set(statements) <= {"SELECT", "SAVEPOINT", "RELEASE", "ROLLBACK"}
    counts_after = [
        db_session.scalar(select(func.count()).select_from(model))
        for model in (Invoice, Payment, EmailOutbox, AuditEvent)
    ]
    assert counts_after == counts_before
    db_session.refresh(detailed_invoice)
    assert detailed_invoice.status == "CONFIRMED" and detailed_invoice.total == Decimal("4970.16")


def test_invoice_detail_omits_private_nested_address_fields(
    client, portal_records, detailed_invoice, db_session
):
    detailed_invoice.customer_snapshot = {
        **detailed_invoice.customer_snapshot,
        "billing_address": {"city": "Kochi", "staff_notes": "SECRET_CUSTOMER_ADDRESS"},
    }
    detailed_invoice.seller_snapshot = {
        **detailed_invoice.seller_snapshot,
        "address": {"city": "Kochi", "internal_cost": "SECRET_SELLER_ADDRESS"},
    }
    db_session.commit()
    sign_in(client, portal_records)
    response = client.get(f"/api/v1/portal/invoices/{detailed_invoice.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["customer_snapshot"]["billing_address"]["city"] == "Kochi"
    assert data["seller_snapshot"]["address"]["city"] == "Kochi"
    assert "SECRET" not in response.text


@pytest.fixture
def lifecycle_record(portal_records, db_session, monkeypatch):
    from app.core import clock
    from app.modules.catalog.service import get_plan_snapshot

    class FixedClock(clock.Clock):
        current_date = date(2026, 10, 15)

        def today(self):
            return self.current_date

    fixed = FixedClock()
    monkeypatch.setattr(clock, "_clock", fixed)
    row = portal_records["subscriptions"][0]
    plan = db_session.get(Plan, row.plan_id)
    plan.allow_pause = plan.allow_early_close = plan.allow_renew = True
    plan.base_fee = Decimal("10.00")
    line = db_session.scalar(
        select(SubscriptionLine).where(SubscriptionLine.subscription_id == row.id)
    )
    db_session.get(Product, line.product_id).sales_price = Decimal("1560.00")
    db_session.flush()
    row.plan_snapshot = get_plan_snapshot(db_session, plan.id, row.start_date)
    row.next_cycle_index = 1  # October's persisted invoice is the processed first cycle.
    for pause in db_session.scalars(
        select(SubscriptionPause).where(SubscriptionPause.subscription_id == row.id)
    ):
        db_session.delete(pause)
    db_session.commit()
    return row, fixed


def authorize_mutation(client, records, name="Alice"):
    sign_in(client, records, name)
    client.headers["X-CSRF-Token"] = "portal-read-test"


def portal_state(db):
    """Denial snapshots include mutable state and financial/audit record counts."""
    db.expire_all()
    return {
        "subscriptions": [
            (str(row.id), row.state, row.revision, row.close_effective_on)
            for row in db.scalars(select(Subscription).order_by(Subscription.id))
        ],
        "pauses": [
            (str(row.id), row.starts_on, row.ends_on)
            for row in db.scalars(select(SubscriptionPause).order_by(SubscriptionPause.id))
        ],
        "counts": [
            db.scalar(select(func.count()).select_from(model))
            for model in (Invoice, Payment, EmailOutbox, AuditEvent)
        ],
    }


def test_customer_pause_and_pending_resume_persist_owner_effective_dates(
    client, portal_records, lifecycle_record, db_session
):
    row, _ = lifecycle_record
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    initial = client.get(f"/api/v1/portal/subscriptions/{row.id}").json()["data"]
    assert set(initial["allowed_actions"]) == {"pause", "close", "renew"}
    paused = client.post(f"/api/v1/portal/subscriptions/{row.id}/pause", json={"reason": "Holiday"})
    assert paused.status_code == 200, paused.text
    data = paused.json()["data"]
    assert data["state"] == "ACTIVE" and data["paused"] is False
    assert data["pause_effective_on"] == "2026-11-01"
    assert data["pause_interval"] == {"starts_on": "2026-11-01", "ends_on": None}
    assert "resume" in data["allowed_actions"] and "pause" not in data["allowed_actions"]
    assert (
        client.get(f"/api/v1/portal/subscriptions/{row.id}").json()["data"]["pause_effective_on"]
        == "2026-11-01"
    )
    resumed = client.post(f"/api/v1/portal/subscriptions/{row.id}/resume", json={})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["pause_interval"] is None
    assert resumed.json()["data"]["pause_effective_on"] is None
    after = portal_state(db_session)
    assert after["counts"][:3] == before["counts"][:3]
    assert after["counts"][3] > before["counts"][3]
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(SubscriptionPause)
            .where(SubscriptionPause.subscription_id == row.id)
        )
        == 0
    )


def test_customer_resume_preserves_processed_pause_and_returns_next_boundary(
    client, portal_records, lifecycle_record, db_session
):
    row, clock = lifecycle_record
    clock.current_date = date(2026, 11, 15)
    row.next_cycle_index = 2
    db_session.add(SubscriptionPause(subscription_id=row.id, starts_on=date(2026, 11, 1)))
    db_session.add(
        BillingPeriod(
            subscription_id=row.id,
            cycle_index=1,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 12, 1),
            disposition="PAUSED",
        )
    )
    db_session.commit()
    authorize_mutation(client, portal_records)
    response = client.post(f"/api/v1/portal/subscriptions/{row.id}/resume", json={})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["paused"] is True and data["resume_effective_on"] == "2026-12-01"
    assert data["pause_interval"] == {"starts_on": "2026-11-01", "ends_on": "2026-12-01"}
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(BillingPeriod)
            .where(BillingPeriod.subscription_id == row.id, BillingPeriod.disposition == "PAUSED")
        )
        == 1
    )


def test_customer_close_schedules_boundary_without_creating_financial_records(
    client, portal_records, lifecycle_record, db_session
):
    row, _ = lifecycle_record
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    response = client.post(
        f"/api/v1/portal/subscriptions/{row.id}/close", json={"reason": "Ending service"}
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["state"] == "ACTIVE" and data["close_effective_on"] == "2026-11-01"
    reloaded = client.get(f"/api/v1/portal/subscriptions/{row.id}").json()["data"]
    assert reloaded["close_effective_on"] == "2026-11-01"
    assert "close_reason" not in reloaded
    assert portal_state(db_session)["counts"][:3] == before["counts"][:3]


def test_customer_renewal_creates_linked_draft_and_rejects_overlap(
    client, portal_records, lifecycle_record, db_session
):
    row, _ = lifecycle_record
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    payload = {"start_date": "2027-10-01", "end_date": "2028-10-01", "payment_terms_days": 14}
    response = client.post(f"/api/v1/portal/subscriptions/{row.id}/renew", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["id"] != str(row.id) and data["prior_subscription_id"] == str(row.id)
    assert data["state"] == "DRAFT" and data["allowed_actions"] == []
    assert data["customer_id"] == str(portal_records["customers"][0].id)
    assert data["payment_terms_days"] == 14
    assert (
        client.get(f"/api/v1/portal/subscriptions/{data['id']}").json()["data"]["state"] == "DRAFT"
    )
    after = portal_state(db_session)
    assert len(after["subscriptions"]) == len(before["subscriptions"]) + 1
    assert after["counts"][:3] == before["counts"][:3]
    replay = client.post(f"/api/v1/portal/subscriptions/{row.id}/renew", json=payload)
    assert replay.status_code == 409 and replay.json()["error"]["code"] == "RENEWAL_OVERLAP"
    assert portal_state(db_session) == after


@pytest.mark.parametrize("action", ["pause", "resume", "close", "renew"])
@pytest.mark.parametrize("payload", [{"reason": {"bad": "type"}}, ["invalid"], "invalid"])
def test_lifecycle_ownership_precedes_semantic_body_validation(
    client, portal_records, db_session, action, payload
):
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    failures = []
    for identifier in (portal_records["subscriptions"][2].id, uuid4()):
        response = client.post(f"/api/v1/portal/subscriptions/{identifier}/{action}", json=payload)
        assert response.status_code == 404
        error = response.json()["error"]
        failures.append((error["code"], error["message"]))
    assert failures[0] == failures[1] == ("NOT_FOUND", "Record not found.")
    assert portal_state(db_session) == before


@pytest.mark.parametrize(
    "guard", ["missing_csrf", "wrong_csrf", "missing_origin", "hostile_origin"]
)
def test_lifecycle_csrf_and_origin_denials_do_not_write(
    client, portal_records, lifecycle_record, db_session, guard
):
    row, _ = lifecycle_record
    authorize_mutation(client, portal_records)
    if guard == "missing_csrf":
        client.headers.pop("X-CSRF-Token")
    elif guard == "wrong_csrf":
        client.headers["X-CSRF-Token"] = "wrong"
    elif guard == "missing_origin":
        client.headers.pop("Origin")
    else:
        client.headers["Origin"] = "https://untrusted.example"
    before = portal_state(db_session)
    for action in ("pause", "resume", "close", "renew"):
        response = client.post(f"/api/v1/portal/subscriptions/{row.id}/{action}", json={})
        assert response.status_code == 403
        assert response.json()["error"]["code"] in {"INVALID_CSRF", "FORBIDDEN_ORIGIN"}
    assert portal_state(db_session) == before


@pytest.mark.parametrize("role", ["ADMIN", "STAFF", None])
def test_lifecycle_routes_require_customer_role(client, portal_records, db_session, role):
    if role:
        authorize_mutation(client, portal_records, role)
    before = portal_state(db_session)
    for action in ("pause", "resume", "close", "renew"):
        response = client.post(
            f"/api/v1/portal/subscriptions/{portal_records['subscriptions'][0].id}/{action}",
            json={},
        )
        assert response.status_code == (403 if role else 401)
    assert portal_state(db_session) == before


def test_lifecycle_rejects_customer_override_and_exposes_only_four_actions(
    client, portal_records, lifecycle_record, db_session
):
    row, _ = lifecycle_record
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    for action in ("pause", "resume", "close", "renew"):
        response = client.post(
            f"/api/v1/portal/subscriptions/{row.id}/{action}?customer_id={portal_records['customers'][0].id}",
            json={},
        )
        assert response.status_code == 422
    for action in ("activate", "confirm", "issue-quotation", "revise"):
        assert (
            client.post(f"/api/v1/portal/subscriptions/{row.id}/{action}", json={}).status_code
            == 404
        )
    assert portal_state(db_session) == before


@pytest.mark.parametrize("action", ["pause", "resume", "close", "renew"])
def test_lifecycle_own_payload_errors_do_not_mutate(
    client, portal_records, lifecycle_record, db_session, action
):
    row, _ = lifecycle_record
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    response = client.post(
        f"/api/v1/portal/subscriptions/{row.id}/{action}", json={"reason": {"bad": "type"}}
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert portal_state(db_session) == before


@pytest.mark.parametrize(
    "action,flag",
    [("pause", "allow_pause"), ("close", "allow_early_close"), ("renew", "allow_renew")],
)
def test_owner_policy_denials_roll_back_without_financial_side_effects(
    client, portal_records, lifecycle_record, db_session, action, flag
):
    row, _ = lifecycle_record
    row.plan_snapshot = {**row.plan_snapshot, flag: False}
    db_session.commit()
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    payload = {"start_date": "2027-10-01", "end_date": "2028-10-01"} if action == "renew" else {}
    response = client.post(f"/api/v1/portal/subscriptions/{row.id}/{action}", json=payload)
    assert response.status_code == 409 and response.json()["error"]["code"] == "POLICY_FORBIDDEN"
    assert portal_state(db_session) == before


def test_due_billing_blocks_pause_and_close_without_side_effects(
    client, portal_records, lifecycle_record, db_session
):
    row, clock = lifecycle_record
    clock.current_date = date(2026, 11, 1)
    authorize_mutation(client, portal_records)
    before = portal_state(db_session)
    for action in ("pause", "close"):
        response = client.post(f"/api/v1/portal/subscriptions/{row.id}/{action}", json={})
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "DUE_BILLING_PENDING"
        )
    assert portal_state(db_session) == before
