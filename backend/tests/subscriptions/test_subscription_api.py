"""Actual subscription HTTP contracts and customer-safe read projections."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.auth import Actor
from app.core.errors import DomainError
from app.core.security import hash_password
from app.models import (
    BillingPeriod,
    Customer,
    Plan,
    PlanTax,
    Product,
    Subscription,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
    User,
)
from app.modules.identity.rate_limit import reset_rate_limits
from app.modules.subscriptions import queries, schemas, workflows


@pytest.fixture
def api_setup(client, db_session, monkeypatch):
    reset_rate_limits()
    clock = SimpleNamespace(today=lambda: date(2027, 2, 10))
    monkeypatch.setattr(workflows, "get_clock", lambda: clock)
    monkeypatch.setattr(queries, "get_clock", lambda: clock)
    email = f"sub-api-{uuid4()}@example.com"
    staff = User(
        display_name="Subscription operator",
        normalized_email=email,
        password_hash=hash_password("SubscriptionAb!"),
        role="STAFF",
    )
    customer = Customer(display_name="API customer", email=f"{uuid4()}@example.com")
    plan = Plan(
        name="API monthly",
        base_fee=Decimal("25.00"),
        cadence="MONTHLY",
        min_quantity=3,
        available_from=date(2027, 1, 1),
        allow_pause=True,
        allow_early_close=True,
        allow_renew=True,
        auto_close=True,
    )
    product = Product(
        name="API seats",
        product_type="SERVICE",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("45.00"),
    )
    db_session.add_all([staff, customer, plan, product])
    db_session.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "SubscriptionAb!"})
    assert login.status_code == 200, login.text
    return SimpleNamespace(
        headers={"X-CSRF-Token": login.json()["data"]["csrf_token"]},
        staff=staff,
        customer=customer,
        plan=plan,
        product=product,
        clock=clock,
    )


def draft_payload(setup, **changes):
    return {
        "customer_id": str(setup.customer.id),
        "plan_id": str(setup.plan.id),
        "start_date": "2027-01-31",
        "end_date": "2027-05-01",
        "payment_terms_days": 14,
        "lines": [{"product_id": str(setup.product.id), "quantity": 3}],
        **changes,
    }


def create(client, setup, **changes):
    response = client.post(
        "/api/v1/subscriptions", headers=setup.headers, json=draft_payload(setup, **changes)
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_template_to_active_roundtrip_and_snapshot_isolation(client, db_session, api_setup):
    setup = api_setup
    template = client.post(
        "/api/v1/quotation-templates",
        headers=setup.headers,
        json={
            "name": "API template",
            "plan_id": str(setup.plan.id),
            "valid_days": 7,
            "lines": [{"product_id": str(setup.product.id), "quantity": 3}],
        },
    )
    assert template.status_code == 201, template.text
    payload = draft_payload(setup, template_id=template.json()["data"]["id"])
    del payload["lines"]
    response = client.post("/api/v1/subscriptions", headers=setup.headers, json=payload)
    assert response.status_code == 201, response.text
    identifier = response.json()["data"]["id"]
    base = f"/api/v1/subscriptions/{identifier}"
    quote = client.post(base + "/issue-quotation", headers=setup.headers, json={"valid_days": 7})
    assert quote.status_code == 200, quote.text
    assert quote.json()["data"]["quotation_valid_until"] == "2027-02-17"
    patched = client.patch(
        f"/api/v1/quotation-templates/{payload['template_id']}",
        headers=setup.headers,
        json={"lines": [{"product_id": str(setup.product.id), "quantity": 5}]},
    )
    assert patched.status_code == 200, patched.text
    for action in ("confirm", "activate"):
        result = client.post(base + "/" + action, headers=setup.headers, json={})
        assert result.status_code == 200, result.text
    detail = client.get(base).json()["data"]
    assert detail["state"] == "ACTIVE"
    assert detail["lines"][0]["quantity"] == 3
    assert detail["lines"][0]["line_total"] == "300.00"
    assert detail["recurring_subtotal"] == "325.00"
    assert detail["recurring_subtotal_basis"] == "before tax and discounts"
    assert detail["invoice_references"] == []
    assert "cost_price" not in str(detail)
    assert client.get("/api/v1/quotation-templates").json()["total"] == 1


def test_integer_storage_limits_reject_terms_and_validity_before_sql(client, api_setup):
    setup = api_setup
    response = client.post(
        "/api/v1/subscriptions",
        headers=setup.headers,
        json=draft_payload(setup, payment_terms_days=2**31),
    )
    assert response.status_code == 422

    row = create(client, setup)
    response = client.post(
        f"/api/v1/subscriptions/{row['id']}/issue-quotation",
        headers=setup.headers,
        json={"valid_days": 2**31},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/quotation-templates",
        headers=setup.headers,
        json={
            "name": "Oversized validity",
            "plan_id": str(setup.plan.id),
            "valid_days": 2**31,
            "lines": draft_payload(setup)["lines"],
        },
    )
    assert response.status_code == 422


def test_template_validity_default_is_persisted_and_explicit_issue_updates_it(client, api_setup):
    setup = api_setup
    response = client.post(
        "/api/v1/quotation-templates",
        headers=setup.headers,
        json={
            "name": "Two week quote",
            "plan_id": str(setup.plan.id),
            "valid_days": 14,
            "lines": draft_payload(setup)["lines"],
        },
    )
    assert response.status_code == 201, response.text
    template_id = response.json()["data"]["id"]
    payload = draft_payload(setup, template_id=template_id)
    del payload["lines"]
    response = client.post("/api/v1/subscriptions", headers=setup.headers, json=payload)
    assert response.status_code == 201, response.text
    identifier = response.json()["data"]["id"]
    url = f"/api/v1/subscriptions/{identifier}"
    assert response.json()["data"]["quotation_valid_days"] == 14
    assert client.get(url).json()["data"]["quotation_valid_days"] == 14
    response = client.patch(
        f"/api/v1/quotation-templates/{template_id}", headers=setup.headers, json={"valid_days": 30}
    )
    assert response.status_code == 200, response.text
    assert client.get(url).json()["data"]["quotation_valid_days"] == 14
    response = client.post(url + "/issue-quotation", headers=setup.headers, json={"valid_days": 21})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["quotation_valid_days"] == 21
    assert response.json()["data"]["quotation_valid_until"] == "2027-03-03"
    assert client.get(url).json()["data"]["quotation_valid_days"] == 21


def test_detail_tax_metadata_uses_period_rules_without_repricing(client, db_session, api_setup):
    setup = api_setup
    base_rule, product_rule = TaxRule(), TaxRule()
    db_session.add_all([base_rule, product_rule])
    db_session.flush()
    base_revision = TaxRuleRevision(
        tax_rule_id=base_rule.id,
        effective_from=date(2027, 1, 1),
        name="Base service tax",
        rate_percent=Decimal("5.0000"),
        valid_from=date(2027, 1, 1),
        active=True,
    )
    product_revision = TaxRuleRevision(
        tax_rule_id=product_rule.id,
        effective_from=date(2027, 1, 1),
        name="Product service tax",
        rate_percent=Decimal("18.0000"),
        valid_from=date(2027, 1, 1),
        active=True,
    )
    db_session.add_all([base_revision, product_revision])
    db_session.flush()
    db_session.add_all(
        [
            PlanTax(plan_id=setup.plan.id, tax_rule_id=base_rule.id),
            TaxRevisionProduct(
                tax_rule_revision_id=product_revision.id, product_id=setup.product.id
            ),
        ]
    )
    db_session.commit()
    draft = create(client, setup)
    url = f"/api/v1/subscriptions/{draft['id']}"
    assert (
        client.post(
            url + "/issue-quotation", headers=setup.headers, json={"valid_days": 7}
        ).status_code
        == 200
    )
    assert client.post(url + "/confirm", headers=setup.headers).status_code == 200
    assert client.post(url + "/activate", headers=setup.headers).status_code == 200
    subscription = db_session.get(Subscription, draft["id"])
    subscription.next_cycle_index = 1
    db_session.add(
        BillingPeriod(
            subscription_id=subscription.id,
            cycle_index=0,
            period_start=date(2027, 1, 31),
            period_end=date(2027, 2, 28),
            disposition="INVOICED",
        )
    )
    setup.product.sales_price = Decimal("999.00")
    db_session.commit()
    response = client.get(url)
    assert response.status_code == 200, response.text
    detail = response.json()["data"]
    assert detail["tax_preview_on"] == "2027-02-28"
    assert (
        detail["tax_preview_basis"]
        == "Applicable rules at this service-period start; invoice snapshots determine final taxes"
    )
    assert detail["base_fee_taxes"] == [
        {"id": str(base_rule.id), "name": "Base service tax", "rate_percent": "5.0000"}
    ]
    assert detail["lines"][0]["taxes"] == [
        {"id": str(product_rule.id), "name": "Product service tax", "rate_percent": "18.0000"}
    ]
    assert detail["lines"][0]["unit_price"] == "100.00"
    assert detail["lines"][0]["line_total"] == "300.00"
    assert "tax_total" not in detail and "cost_price" not in str(detail)


@pytest.mark.parametrize("patch", [{"start_date": None}, {"lines": None}, {"total": "1.00"}])
def test_strict_patch_schema_rejects_nulls_and_totals(client, api_setup, patch):
    row = create(client, api_setup)
    response = client.patch(
        f"/api/v1/subscriptions/{row['id']}", headers=api_setup.headers, json=patch
    )
    assert response.status_code == 422
    assert client.get(f"/api/v1/subscriptions/{row['id']}").json()["data"]["revision"] == 1


@pytest.mark.parametrize("quantity", [True, 1.0, 0, -1, 2**31])
def test_quantity_validation_is_strict(client, api_setup, quantity):
    response = client.post(
        "/api/v1/subscriptions",
        headers=api_setup.headers,
        json=draft_payload(
            api_setup, lines=[{"product_id": str(api_setup.product.id), "quantity": quantity}]
        ),
    )
    assert response.status_code == 422


def test_quotation_requires_revision_and_expiry_is_exclusive(client, api_setup):
    row = create(client, api_setup)
    base = f"/api/v1/subscriptions/{row['id']}"
    assert client.post(base + "/confirm", headers=api_setup.headers).status_code == 409
    assert (
        client.post(
            base + "/issue-quotation", headers=api_setup.headers, json={"valid_days": 1}
        ).status_code
        == 200
    )
    assert (
        client.patch(base, headers=api_setup.headers, json={"payment_terms_days": 7}).status_code
        == 409
    )
    api_setup.clock.today = lambda: date(2027, 2, 11)
    response = client.post(base + "/confirm", headers=api_setup.headers)
    assert response.status_code == 409
    assert client.get(base).json()["data"]["state"] == "QUOTATION"


def test_filters_pagination_and_customer_safe_detail(client, db_session, api_setup):
    setup = api_setup
    initial_total = client.get("/api/v1/subscriptions", params={"page_size": 1}).json()["total"]
    first = create(client, setup)
    second_customer = Customer(display_name="Other API customer", email=f"{uuid4()}@example.com")
    db_session.add(second_customer)
    db_session.commit()
    second = create(client, setup, customer_id=str(second_customer.id))
    page = client.get("/api/v1/subscriptions", params={"page_size": 1}).json()
    assert page["total"] == initial_total + 2 and len(page["items"]) == 1
    filtered = client.get(
        "/api/v1/subscriptions",
        params={"customer_id": str(setup.customer.id), "state": "DRAFT", "q": first["number"]},
    ).json()
    assert filtered["total"] == 1 and filtered["items"][0]["id"] == first["id"]
    assert client.get("/api/v1/subscriptions", params={"page_size": 101}).status_code == 422
    customer_actor = Actor(uuid4(), "CUSTOMER", setup.customer.id)
    owned = queries.get_subscription_for_actor(db_session, customer_actor, first["id"])
    assert "cost_price" not in str(owned) and owned["allowed_actions"] == []
    with pytest.raises(DomainError) as error:
        queries.get_subscription_for_actor(db_session, customer_actor, second["id"])
    assert error.value.status_code == 404
    own_page = queries.list_subscriptions(db_session, customer_actor)
    assert own_page["total"] == 1
    with pytest.raises(DomainError) as pagination_error:
        queries.list_subscriptions(db_session, customer_actor, page_size=101)
    assert pagination_error.value.status_code == 422


def test_mutation_requires_csrf_and_customer_has_no_staff_api_access(client, db_session, api_setup):
    assert client.post("/api/v1/subscriptions", json=draft_payload(api_setup)).status_code == 403
    customer_email = f"sub-customer-{uuid4()}@example.com"
    db_session.add(
        User(
            display_name="Portal customer",
            normalized_email=customer_email,
            password_hash=hash_password("CustomerAb!"),
            role="CUSTOMER",
            customer_id=api_setup.customer.id,
        )
    )
    db_session.commit()
    reset_rate_limits()
    response = client.post(
        "/api/v1/auth/login", json={"email": customer_email, "password": "CustomerAb!"}
    )
    assert response.status_code == 200
    assert client.get("/api/v1/subscriptions").status_code == 403
    assert client.get("/api/v1/quotation-templates").status_code == 403


@pytest.mark.parametrize("lines", [None, []])
def test_omission_is_distinct_from_invalid_explicit_lines(lines):
    payload = {
        "customer_id": uuid4(),
        "plan_id": uuid4(),
        "template_id": uuid4(),
        "start_date": "2027-01-31",
        "end_date": "2027-05-01",
        "payment_terms_days": 0,
    }
    assert "lines" not in schemas.SubscriptionCreate(**payload).model_fields_set
    if lines is None:
        with pytest.raises(ValidationError):
            schemas.SubscriptionCreate(**payload, lines=lines)
    else:
        assert schemas.SubscriptionCreate(**payload, lines=lines).lines == []


def test_customer_plan_projection_drops_nested_legacy_secrets(db_session, client, api_setup):
    import json

    draft = create(client, api_setup)
    row = db_session.get(Subscription, draft["id"])
    safe_tax_id = str(uuid4())
    snapshot = dict(row.plan_snapshot)
    snapshot.update(
        {
            "base_fee": "025.00",
            "name": {"internal_cost": "secret-cost-token"},
            "currency": {"staff_notes": "secret-staff-token"},
            "plan_id": {"staff_notes": "secret-id-token"},
            "schema_version": True,
            "min_quantity": {"internal_cost": "secret-minimum-token"},
            "allow_pause": {"staff_notes": "secret-policy-token"},
            "tax_rule_ids": [safe_tax_id, {"staff_notes": "secret-tax-token"}],
        }
    )
    row.plan_snapshot = snapshot
    db_session.commit()
    actor = Actor(uuid4(), "CUSTOMER", api_setup.customer.id)
    detail = queries.get_subscription_for_actor(db_session, actor, row.id)
    encoded = json.dumps(detail)
    assert (
        "secret-" not in encoded and "internal_cost" not in encoded and "staff_notes" not in encoded
    )
    projected = detail["plan_snapshot"]
    assert projected["base_fee"] == "025.00"
    assert detail["recurring_subtotal"] == "325.00"
    assert projected["tax_rule_ids"] == [safe_tax_id]
    assert all(
        key not in projected
        for key in ("name", "currency", "plan_id", "schema_version", "min_quantity", "allow_pause")
    )
    listed = queries.list_subscriptions(db_session, actor)
    assert "secret-" not in json.dumps(listed)


@pytest.mark.parametrize(
    "base_fee", [None, {"internal_cost": "private"}, "NaN", "-1.00", "1e100", True]
)
def test_invalid_financial_snapshot_is_rejected_not_replaced_with_zero(
    db_session, client, api_setup, base_fee
):
    draft = create(client, api_setup)
    row = db_session.get(Subscription, draft["id"])
    row.plan_snapshot = {**row.plan_snapshot, "base_fee": base_fee}
    db_session.commit()
    actor = Actor(uuid4(), "CUSTOMER", api_setup.customer.id)
    with pytest.raises(DomainError) as caught:
        queries.get_subscription_for_actor(db_session, actor, row.id)
    assert (caught.value.code, caught.value.status_code) == ("INVALID_SNAPSHOT", 409)
    assert "private" not in caught.value.message


def test_missing_and_foreign_customer_records_have_identical_not_found_errors(
    db_session, client, api_setup
):
    other = Customer(display_name="Private other customer", email=f"{uuid4()}@example.com")
    db_session.add(other)
    db_session.commit()
    draft = create(client, api_setup, customer_id=str(other.id))
    actor = Actor(uuid4(), "CUSTOMER", api_setup.customer.id)
    errors = []
    for identifier in (uuid4(), draft["id"]):
        with pytest.raises(DomainError) as caught:
            queries.get_subscription_for_actor(db_session, actor, identifier)
        errors.append((caught.value.code, caught.value.status_code, caught.value.message))
    assert errors == [("NOT_FOUND", 404, "Record not found.")] * 2


def test_malformed_active_schedule_returns_safe_snapshot_conflict(db_session, client, api_setup):
    draft = create(client, api_setup)
    row = db_session.get(Subscription, draft["id"])
    row.state = "ACTIVE"
    row.plan_snapshot = {**row.plan_snapshot, "cadence": {"staff_notes": "private-schedule"}}
    db_session.commit()
    actor = Actor(uuid4(), "CUSTOMER", api_setup.customer.id)
    with pytest.raises(DomainError) as caught:
        queries.get_subscription_for_actor(db_session, actor, row.id)
    assert (caught.value.code, caught.value.status_code) == ("INVALID_SNAPSHOT", 409)
    assert "private-schedule" not in caught.value.message


def test_empty_snapshot_rejects_detail_and_list_without_inventing_base_fee(
    db_session, client, api_setup
):
    draft = create(client, api_setup)
    row = db_session.get(Subscription, draft["id"])
    row.plan_snapshot = {}
    db_session.commit()
    for url in (f"/api/v1/subscriptions/{draft['id']}", "/api/v1/subscriptions"):
        response = client.get(url)
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "INVALID_SNAPSHOT"
        assert "recurring_subtotal" not in response.json()
