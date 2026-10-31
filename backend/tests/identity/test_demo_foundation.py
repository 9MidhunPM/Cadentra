"""Static demo setup cannot overwrite data or lose its no-email provenance."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.auth import Actor
from app.core.demo_contacts import is_demo_contact
from app.demo_data import profile
from app.demo_data.foundation import FoundationConflict, ensure_foundation
from app.models import AuditEvent, Customer, Product, ProductVariant, User

pytestmark = pytest.mark.integration
ANCHOR = date(2026, 10, 31)


def admin(db):
    user = User(
        display_name="Foundation test administrator", role="ADMIN",
        normalized_email=f"{uuid4()}@example.com", password_hash="unused-test-only",
    )
    db.add(user)
    db.flush()
    return Actor(user.id, "ADMIN")


def test_foundation_replays_without_changes_and_preserves_unrelated_rows(db_session):
    actor = admin(db_session)
    original = Customer(display_name="Original customer", email="original@example.com")
    db_session.add(original)
    db_session.flush()
    first = ensure_foundation(db_session, actor, ANCHOR)
    assert first["counts"] == {
        "customers": 96, "products": 80, "variants": 160, "plans": 8,
        "templates": 6, "template_lines": 18, "contact_markers": 96,
    }
    before = db_session.scalar(select(func.count()).select_from(AuditEvent))
    second = ensure_foundation(db_session, actor, ANCHOR)
    assert not any(second["counts"].values())
    assert second["manifest_sha256"] == first["manifest_sha256"]
    assert second["references"] == first["references"]
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == before
    db_session.refresh(original)
    assert original.display_name == "Original customer"
    assert not is_demo_contact(db_session, customer_id=original.id)
    for customer_id in first["references"]["customer_ids"]:
        assert is_demo_contact(db_session, customer_id=customer_id)


def test_anchor_change_fails_without_touching_the_original_manifest(db_session):
    actor = admin(db_session)
    original = ensure_foundation(db_session, actor, ANCHOR)
    with pytest.raises(FoundationConflict, match="drift"):
        ensure_foundation(db_session, actor, ANCHOR + timedelta(days=1))
    again = ensure_foundation(db_session, actor, ANCHOR)
    assert original["manifest_sha256"] == again["manifest_sha256"]
    assert not any(again["counts"].values())


def test_edited_customer_keeps_suppression_and_importer_refuses_to_overwrite(db_session):
    actor = admin(db_session)
    result = ensure_foundation(db_session, actor, ANCHOR)
    customer = db_session.get(Customer, result["references"]["customer_ids"][0])
    customer.email = "operator-edited@example.com"
    db_session.flush()
    assert is_demo_contact(db_session, customer_id=customer.id, recipient=customer.email)
    with pytest.raises(FoundationConflict, match="drift"):
        ensure_foundation(db_session, actor, ANCHOR)
    assert customer.email == "operator-edited@example.com"


def test_unmarked_identity_collision_rolls_back_entire_foundation(db_session):
    actor = admin(db_session)
    product_id = profile.catalog()[0]["id"]
    db_session.add(Product(
        id=product_id, name="Unrelated retained product", product_type="GOODS",
    ))
    db_session.flush()
    with pytest.raises(FoundationConflict, match="Unmarked demo identity collision"):
        with db_session.begin_nested():
            ensure_foundation(db_session, actor, ANCHOR)
    assert db_session.scalar(select(func.count()).select_from(Customer)) == 0
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0
    assert db_session.get(Product, product_id).name == "Unrelated retained product"


def test_extra_nested_variant_is_drift_and_is_retained(db_session):
    actor = admin(db_session)
    result = ensure_foundation(db_session, actor, ANCHOR)
    extra = ProductVariant(
        product_id=result["references"]["product_ids"][0], attribute_name="Operator pack",
        attribute_value="Extra", price_delta=0,
    )
    db_session.add(extra)
    db_session.flush()
    with pytest.raises(FoundationConflict, match="Unexpected nested demo rows"):
        ensure_foundation(db_session, actor, ANCHOR)
    assert db_session.get(ProductVariant, extra.id) is extra


def test_foundation_requires_active_real_admin(db_session):
    actor = admin(db_session)
    user = db_session.get(User, actor.id)
    user.active = False
    db_session.flush()
    with pytest.raises(ValueError, match="active administrator"):
        ensure_foundation(db_session, actor, ANCHOR)
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0
