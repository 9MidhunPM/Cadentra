from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.auth import Actor
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.models import DiscountRule, DiscountRuleRevision, Product, TaxRuleRevision
from app.modules.billing import rules
from app.modules.billing.rule_schemas import DiscountPatch, DiscountWrite, TaxPatch, TaxWrite

ADMIN = Actor(uuid4(), "ADMIN")
STAFF = Actor(uuid4(), "STAFF")
TODAY = get_clock().today()


def tax(**changes):
    return TaxWrite(name="VAT", rate_percent="18.1250", valid_from=TODAY, **changes)


def discount(**changes):
    values = dict(
        name="Saving", kind="PERCENT", value="10.1250", scope="SUBSCRIPTION", starts_on=TODAY
    )
    values.update(changes)
    return DiscountWrite(**values)


def test_tax_revisions_preserve_history_and_windows(db_session):
    created = rules.write_rule(db_session, ADMIN, tax(), True)
    rule_id = UUID(created["id"])
    revised = rules.write_rule(
        db_session,
        ADMIN,
        TaxPatch(effective_from=TODAY + timedelta(days=1), rate_percent="20.0001"),
        True,
        rule_id,
    )
    assert revised["id"] == created["id"]
    assert revised["revision_id"] != created["revision_id"]
    assert revised["rate_percent"] == "20.0001"
    assert rules.get_applicable_taxes(db_session, (rule_id,), TODAY)[0].rate_percent == Decimal(
        "18.1250"
    )
    assert rules.get_applicable_taxes(db_session, (rule_id,), TODAY + timedelta(days=1))[
        0
    ].rate_percent == Decimal("20.0001")
    assert (
        len(
            db_session.scalars(
                select(TaxRuleRevision).where(TaxRuleRevision.tax_rule_id == rule_id)
            ).all()
        )
        == 2
    )


def test_rejected_patch_rolls_back_predecessor_closure(db_session):
    created = rules.write_rule(db_session, ADMIN, tax(), True)
    with pytest.raises(DomainError) as caught:
        rules.write_rule(
            db_session,
            ADMIN,
            TaxPatch(effective_from=TODAY + timedelta(days=1), product_ids=[uuid4()]),
            True,
            UUID(created["id"]),
        )
    assert caught.value.code == "INVALID_PRODUCT"
    row = db_session.get(TaxRuleRevision, UUID(created["revision_id"]))
    assert row.effective_until is None
    db_session.rollback()
    with pytest.raises(DomainError):
        rules.write_rule(
            db_session, ADMIN, TaxPatch(effective_from=TODAY), True, UUID(created["id"])
        )


def test_rule_roles_and_current_pagination(db_session):
    with pytest.raises(DomainError) as caught:
        rules.write_rule(db_session, STAFF, tax(), True)
    assert caught.value.status_code == 403
    rules.write_rule(db_session, ADMIN, tax(), True)
    result = rules.list_rules(db_session, STAFF, True, 1, 1)
    assert result["page_size"] == 1 and len(result["items"]) == 1
    assert result["total"] >= 1
    with pytest.raises(DomainError):
        rules.list_rules(db_session, Actor(uuid4(), "CUSTOMER", uuid4()), True)


@pytest.mark.parametrize(
    "payload",
    [
        {"rate_percent": 18.0},
        {"rate_percent": "18.00001"},
        {"rate_percent": "NaN"},
        {"rate_percent": "100.0001"},
        {"rate_percent": "-0.01"},
        {"active": "true"},
    ],
)
def test_tax_strict_validation(payload):
    values = dict(name="Tax", rate_percent="18.00", valid_from=TODAY)
    values.update(payload)
    with pytest.raises(ValidationError):
        TaxWrite(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "FIXED", "value": "1.001"},
        {"kind": "PERCENT", "value": "100.001"},
        {"value": 10.0},
        {"min_quantity": True},
        {"usage_limit": -1},
        {"scope": "PRODUCTS", "product_ids": []},
    ],
)
def test_discount_strict_validation(changes):
    with pytest.raises(ValidationError):
        discount(**changes)


def test_discount_scope_minimums_and_counter_not_consumed(db_session):
    product = Product(
        name="Scope", product_type="SERVICE", sales_price=Decimal("100"), cost_price=Decimal("0")
    )
    db_session.add(product)
    db_session.commit()
    created = rules.write_rule(
        db_session,
        ADMIN,
        discount(
            scope="PRODUCTS",
            product_ids=[product.id],
            min_purchase="100.00",
            min_quantity=2,
            usage_limit=1,
        ),
        False,
    )
    lines = (
        rules.DiscountLine("BASE", None, 1, Decimal("900")),
        rules.DiscountLine("L1", product.id, 1, Decimal("100")),
    )
    assert rules.choose_discount(db_session, TODAY, lines) is None
    db_session.rollback()
    lines = (lines[0], rules.DiscountLine("L1", product.id, 2, Decimal("100")))
    selected = rules.choose_discount(db_session, TODAY, lines)
    assert selected.rule_id == UUID(created["id"])
    assert selected.discount.eligible_line_keys == frozenset({"L1"})
    parent = db_session.get(DiscountRule, selected.rule_id)
    assert parent.uses_count == 0
    parent.uses_count = 1
    db_session.flush()
    assert rules.choose_discount(db_session, TODAY, lines) is None


def test_discount_patch_preserves_global_usage(db_session):
    created = rules.write_rule(db_session, ADMIN, discount(usage_limit=1), False)
    parent = db_session.get(DiscountRule, UUID(created["id"]))
    parent.uses_count = 1
    db_session.commit()
    rules.write_rule(
        db_session,
        ADMIN,
        DiscountPatch(effective_from=TODAY + timedelta(days=1), value="11.1250"),
        False,
        parent.id,
    )
    result = rules.choose_discount(
        db_session,
        TODAY + timedelta(days=1),
        (rules.DiscountLine("BASE", None, 1, Decimal("100")),),
    )
    assert result is None
    assert db_session.scalar(
        select(DiscountRuleRevision.value)
        .where(DiscountRuleRevision.discount_rule_id == parent.id)
        .order_by(DiscountRuleRevision.effective_from.desc())
    ) == Decimal("11.1250")


def test_discount_best_benefit_tie_is_stable(db_session):
    first = rules.write_rule(db_session, ADMIN, discount(kind="FIXED", value="15.00"), False)
    second = rules.write_rule(db_session, ADMIN, discount(kind="FIXED", value="15.00"), False)
    result = rules.choose_discount(
        db_session, TODAY, (rules.DiscountLine("BASE", None, 1, Decimal("100")),)
    )
    assert str(result.rule_id) == min(first["id"], second["id"])


def _login(client, db, role):
    from app.core.security import hash_password
    from app.models import User
    from app.modules.identity.rate_limit import reset_rate_limits

    reset_rate_limits()
    email = f"{uuid4()}@example.com"
    db.add(
        User(
            display_name="Rule operator",
            normalized_email=email,
            password_hash=hash_password("RulesTestAb!"),
            role=role,
        )
    )
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "RulesTestAb!"})
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["data"]["csrf_token"]}


def test_rules_api_admin_revision_and_validation(client, db_session):
    headers = _login(client, db_session, "ADMIN")
    payload = {"name": "Tax", "rate_percent": "18.1250", "valid_from": TODAY.isoformat()}
    invalid = client.post(
        "/api/v1/tax-rules", json={**payload, "rate_percent": 18.125}, headers=headers
    )
    assert invalid.status_code == 422
    response = client.post("/api/v1/tax-rules", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    response = client.patch(
        f"/api/v1/tax-rules/{created['id']}",
        json={
            "effective_from": (TODAY + timedelta(days=1)).isoformat(),
            "name": "Future tax",
            "rate_percent": "20.0001",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["rate_percent"] == "20.0001"
    current = client.get("/api/v1/tax-rules").json()
    record = next(row for row in current["items"] if row["id"] == created["id"])
    assert record["name"] == "Tax"
    assert client.get("/api/v1/discount-rules?page_size=101").status_code == 422
    assert client.post("/api/v1/tax-rules", json=payload).status_code == 403


def test_rules_api_staff_reads_but_cannot_write(client, db_session):
    headers = _login(client, db_session, "STAFF")
    assert client.get("/api/v1/tax-rules").status_code == 200
    assert client.get("/api/v1/discount-rules").status_code == 200
    payload = {"name": "Tax", "rate_percent": "18.00", "valid_from": TODAY.isoformat()}
    assert client.post("/api/v1/tax-rules", json=payload, headers=headers).status_code == 403
    assert (
        client.patch(
            f"/api/v1/discount-rules/{uuid4()}",
            json={"effective_from": (TODAY + timedelta(days=1)).isoformat()},
            headers=headers,
        ).status_code
        == 403
    )


def test_zero_benefit_never_consumes_or_selects_discount(db_session):
    created = rules.write_rule(
        db_session, ADMIN, discount(kind="FIXED", value="0.00", usage_limit=1), False
    )
    assert (
        rules.choose_discount(
            db_session, TODAY, (rules.DiscountLine("BASE", None, 1, Decimal("0.00")),)
        )
        is None
    )
    assert (
        rules.choose_discount(
            db_session, TODAY, (rules.DiscountLine("BASE", None, 1, Decimal("100.00")),)
        )
        is None
    )
    assert db_session.get(DiscountRule, UUID(created["id"])).uses_count == 0


def test_tax_validity_uses_period_start_and_exclusive_end(db_session):
    created = rules.write_rule(db_session, ADMIN, tax(valid_until=TODAY + timedelta(days=1)), True)
    rule_id = UUID(created["id"])
    assert rules.get_applicable_taxes(db_session, (rule_id,), TODAY)
    assert rules.get_applicable_taxes(db_session, (rule_id,), TODAY + timedelta(days=1)) == ()


@pytest.mark.parametrize(
    ("period_offset", "eligible"),
    [(1, False), (2, True), (3, True), (4, False), (5, False)],
    ids=["before-start", "inclusive-start", "inside-window", "exclusive-end", "expired"],
)
def test_discount_period_validity_boundaries_preserve_uses(db_session, period_offset, eligible):
    product = Product(
        name="Validity boundary",
        product_type="SERVICE",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("0.00"),
    )
    db_session.add(product)
    db_session.commit()
    created = rules.write_rule(
        db_session,
        ADMIN,
        discount(
            scope="PRODUCTS",
            product_ids=[product.id],
            starts_on=TODAY + timedelta(days=2),
            ends_on=TODAY + timedelta(days=4),
            usage_limit=3,
        ),
        False,
    )
    rule_id = UUID(created["id"])
    parent = db_session.get(DiscountRule, rule_id)
    parent.uses_count = 1
    db_session.commit()
    selected = rules.choose_discount(
        db_session,
        TODAY + timedelta(days=period_offset),
        (rules.DiscountLine("PRODUCT", product.id, 1, Decimal("100.00")),),
    )
    if eligible:
        assert selected is not None and selected.rule_id == rule_id
    else:
        assert selected is None or selected.rule_id != rule_id
    assert db_session.get(DiscountRule, rule_id).uses_count == 1


@pytest.mark.parametrize(
    ("gross", "eligible"),
    [("99.99", False), ("100.00", True), ("100.01", True)],
    ids=["below-minimum", "exact-minimum", "above-minimum"],
)
def test_discount_minimum_uses_eligible_product_gross(db_session, gross, eligible):
    product = Product(
        name="Purchase boundary",
        product_type="SERVICE",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("0.00"),
    )
    db_session.add(product)
    db_session.commit()
    created = rules.write_rule(
        db_session,
        ADMIN,
        discount(
            scope="PRODUCTS",
            product_ids=[product.id],
            min_purchase="100.00",
            min_quantity=1,
            usage_limit=3,
        ),
        False,
    )
    rule_id = UUID(created["id"])
    parent = db_session.get(DiscountRule, rule_id)
    parent.uses_count = 1
    db_session.commit()
    selected = rules.choose_discount(
        db_session,
        TODAY,
        (
            rules.DiscountLine("BASE", None, 1, Decimal("1000.00")),
            rules.DiscountLine("PRODUCT", product.id, 1, Decimal(gross)),
        ),
    )
    if eligible:
        assert selected is not None and selected.rule_id == rule_id
        assert selected.discount.eligible_line_keys == frozenset({"PRODUCT"})
    else:
        assert selected is None or selected.rule_id != rule_id
    assert db_session.get(DiscountRule, rule_id).uses_count == 1
