from datetime import date
from uuid import uuid4

import pytest

from app.core.errors import DomainError
from app.core.security import hash_password
from app.models import User
from app.modules.catalog.service import get_plan_snapshot, get_product_snapshot
from app.modules.identity.rate_limit import reset_rate_limits


@pytest.fixture(autouse=True)
def clear_limits():
    reset_rate_limits()


def login(client, db, role="ADMIN"):
    email = f"{uuid4()}@example.com"
    db.add(
        User(
            display_name="Catalog operator",
            normalized_email=email,
            password_hash=hash_password("CatalogAb!"),
            role=role,
        )
    )
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "CatalogAb!"})
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["data"]["csrf_token"]}


def product_payload(**changes):
    return {
        "name": "Cloud license",
        "product_type": "SERVICE",
        "sales_price": "1000.00",
        "cost_price": "100.00",
        **changes,
    }


def plan_payload(**changes):
    return {
        "name": "Monthly plan",
        "base_fee": "0.00",
        "currency": "INR",
        "cadence": "MONTHLY",
        "min_quantity": 1,
        "available_from": "2026-01-01",
        "available_until": "2027-01-01",
        "allow_pause": True,
        "allow_early_close": False,
        "allow_renew": True,
        "auto_close": True,
        **changes,
    }


def test_variant_prices_and_cross_product_ownership(client, db_session):
    headers = login(client, db_session)
    first = client.post("/api/v1/products", json=product_payload(), headers=headers).json()["data"]
    second = client.post(
        "/api/v1/products", json=product_payload(name="Other"), headers=headers
    ).json()["data"]
    response = client.post(
        f"/api/v1/products/{first['id']}/variants",
        headers=headers,
        json={"attribute_name": "Tier", "attribute_value": "Premium", "price_delta": "560.00"},
    )
    assert response.status_code == 201, response.text
    variant = response.json()["data"]
    snapshot = get_product_snapshot(db_session, first["id"], variant["id"])
    assert snapshot["unit_price"] == "1560.00"
    assert "cost_price" not in snapshot
    response = client.patch(
        f"/api/v1/products/{second['id']}/variants/{variant['id']}",
        json={"price_delta": "1.00"},
        headers=headers,
    )
    assert response.status_code == 404


def test_negative_variant_and_base_price_updates_cannot_break_price(client, db_session):
    headers = login(client, db_session)
    product = client.post("/api/v1/products", json=product_payload(), headers=headers).json()[
        "data"
    ]
    url = f"/api/v1/products/{product['id']}"
    bad = client.post(
        url + "/variants",
        headers=headers,
        json={"attribute_name": "Tier", "attribute_value": "Bad", "price_delta": "-1000.01"},
    )
    assert bad.status_code == 422
    valid = client.post(
        url + "/variants",
        headers=headers,
        json={"attribute_name": "Tier", "attribute_value": "Discount", "price_delta": "-500.00"},
    )
    assert valid.status_code == 201
    response = client.patch(url, json={"sales_price": "499.99"}, headers=headers)
    assert response.status_code == 422
    assert client.get(url).json()["data"]["sales_price"] == "1000.00"


def test_catalog_roles_and_money_boundary(client, db_session):
    headers = login(client, db_session, "STAFF")
    assert client.get("/api/v1/products").status_code == 200
    assert (
        client.post("/api/v1/products", json=product_payload(), headers=headers).status_code == 403
    )
    headers = login(client, db_session)
    for changes in [
        {"sales_price": 1000.5},
        {"sales_price": "NaN"},
        {"sales_price": "1.001"},
        {"sales_price": "-1.00"},
        {"role": "ADMIN"},
    ]:
        assert (
            client.post(
                "/api/v1/products", json=product_payload(**changes), headers=headers
            ).status_code
            == 422
        )
    assert client.get("/api/v1/products?page_size=101").status_code == 422


def test_customer_cannot_read_internal_catalog(client, db_session):
    email = f"{uuid4()}@example.com"
    assert (
        client.post(
            "/api/v1/auth/signup",
            json={"name": "Customer", "email": email, "password": "CatalogAb!"},
        ).status_code
        == 201
    )
    client.post("/api/v1/auth/login", json={"email": email, "password": "CatalogAb!"})
    assert client.get("/api/v1/products").status_code == 403
    assert client.get("/api/v1/plans").status_code == 403


@pytest.mark.parametrize("cadence", ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"])
def test_all_plan_cadences_and_snapshots_do_not_reprice(client, db_session, cadence):
    headers = login(client, db_session)
    response = client.post("/api/v1/plans", json=plan_payload(cadence=cadence), headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    snapshot = get_plan_snapshot(db_session, data["id"], date(2026, 1, 1))
    db_session.commit()
    changed = client.patch(
        f"/api/v1/plans/{data['id']}", json={"base_fee": "42.00"}, headers=headers
    )
    assert changed.status_code == 200, changed.text
    assert snapshot["base_fee"] == "0.00"
    assert snapshot["cadence"] == cadence
    assert snapshot["schema_version"] == 1
    assert isinstance(snapshot["min_quantity"], int)
    assert isinstance(snapshot["allow_pause"], bool)
    with pytest.raises(DomainError):
        get_plan_snapshot(db_session, data["id"], date(2027, 1, 1))


def test_invalid_plan_edits_are_atomic(client, db_session):
    headers = login(client, db_session)
    for changes in [
        {"min_quantity": 0},
        {"min_quantity": True},
        {"currency": "USD"},
        {"available_until": "2026-01-01"},
        {"tax_rule_ids": [str(uuid4())]},
    ]:
        response = client.post("/api/v1/plans", json=plan_payload(**changes), headers=headers)
        assert response.status_code == 422, response.text
    plan = client.post("/api/v1/plans", json=plan_payload(), headers=headers).json()["data"]
    assert (
        client.patch(
            f"/api/v1/plans/{plan['id']}", json={"name": None}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/plans/{plan['id']}", json={"available_until": "2025-01-01"}, headers=headers
        ).status_code
        == 422
    )
    assert client.get("/api/v1/plans").json()["items"][0]["available_until"] == "2027-01-01"


def test_archive_blocks_future_product_snapshot(client, db_session):
    headers = login(client, db_session)
    product = client.post("/api/v1/products", json=product_payload(), headers=headers).json()[
        "data"
    ]
    assert (
        client.patch(
            f"/api/v1/products/{product['id']}", json={"active": False}, headers=headers
        ).status_code
        == 200
    )
    with pytest.raises(DomainError):
        get_product_snapshot(db_session, product["id"])


def test_duplicate_variant_is_conflict_and_plan_detail_exists(client, db_session):
    headers = login(client, db_session)
    product = client.post("/api/v1/products", json=product_payload(), headers=headers).json()[
        "data"
    ]
    variant = {"attribute_name": "Tier", "attribute_value": "Unique", "price_delta": "0.00"}
    url = f"/api/v1/products/{product['id']}/variants"
    assert client.post(url, json=variant, headers=headers).status_code == 201
    assert client.post(url, json=variant, headers=headers).status_code == 409
    plan = client.post("/api/v1/plans", json=plan_payload(), headers=headers).json()["data"]
    response = client.get(f"/api/v1/plans/{plan['id']}")
    assert response.status_code == 200
    assert response.json()["data"] == plan


def test_period_tax_membership_changes_without_repricing_snapshot(db_session):
    from decimal import Decimal

    from app.models import Product, TaxRevisionProduct, TaxRule, TaxRuleRevision
    from app.modules.catalog.service import get_product_tax_ids

    product = Product(
        name="Fixed price",
        product_type="SERVICE",
        sales_price=Decimal("1000.00"),
        cost_price=Decimal("50.00"),
    )
    rule = TaxRule()
    db_session.add_all([product, rule])
    db_session.flush()
    revision = TaxRuleRevision(
        tax_rule_id=rule.id,
        effective_from=date(2026, 1, 1),
        name="Future tax",
        rate_percent=Decimal("18.00"),
        valid_from=date(2026, 2, 1),
        active=True,
    )
    db_session.add(revision)
    db_session.flush()
    db_session.add(TaxRevisionProduct(tax_rule_revision_id=revision.id, product_id=product.id))
    db_session.flush()
    snapshot = get_product_snapshot(db_session, product.id, effective_date=date(2026, 1, 1))
    assert snapshot["selected_tax_ids"] == []
    product.sales_price = Decimal("2000.00")
    db_session.flush()
    assert get_product_tax_ids(db_session, product.id, date(2026, 2, 1)) == [str(rule.id)]
    assert snapshot["unit_price"] == "1000.00"
    assert snapshot["selected_tax_ids"] == []
