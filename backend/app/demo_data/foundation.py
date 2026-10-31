"""Atomic, attributable static setup for the explicitly invoked commerce demo.

The caller owns the transaction. This module never commits, sends mail or creates
subscriptions/financial records. Replays verify owned rows rather than repairing
them, so an operator's edits can never be silently overwritten.
"""

import hashlib
import json
from datetime import date
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.auth import Actor
from app.core.demo_contacts import (
    DEMO_CONTACT_ACTION,
    DEMO_CONTACT_ENTITY_TYPE,
)
from app.models import (
    AuditEvent,
    Customer,
    Plan,
    Product,
    ProductVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    User,
)
from app.modules.catalog.schemas import PlanWrite, ProductWrite, VariantWrite
from app.modules.catalog.service import validate_plan_window
from app.modules.identity.schemas import CustomerWrite
from app.modules.subscriptions.schemas import TemplateWrite

from . import profile

FOUNDATION_ACTION = "DEMO_FOUNDATION_INTENT"
FOUNDATION_ENTITY = "DEMO_IMPORT"


class FoundationConflict(ValueError):
    """The requested cohort is inconsistent with an existing durable record."""


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _ensure(db: Session, model, spec: dict, *, owned: bool) -> bool:
    row = db.get(model, spec["id"])
    if row is None:
        if owned:
            raise FoundationConflict(f"Missing owned demo row: {model.__tablename__}")
        db.add(model(**spec))
        return True
    if not owned:
        raise FoundationConflict(f"Unmarked demo identity collision: {model.__tablename__}")
    if any(getattr(row, key) != value for key, value in spec.items()):
        raise FoundationConflict(f"Demo foundation drift: {model.__tablename__}")
    return False


def ensure_foundation(db: Session, actor: Actor, anchor: date) -> dict:
    """Validate and persist fixed-ID foundation rows inside one caller transaction.

    Returns created counts, reference UUID lists and the complete static manifest
    digest. Calling again with the same input is read-only apart from row locks.
    A changed anchor/profile or owned-row drift fails instead of mutating history.
    The caller must roll back its transaction after any exception.
    """
    operator = db.get(User, actor.id)
    if actor.role != "ADMIN" or operator is None or not operator.active or operator.role != "ADMIN":
        raise ValueError("An active administrator is required for the demo foundation")
    if not isinstance(anchor, date):
        raise ValueError("An explicit foundation anchor date is required")
    lock_key = int.from_bytes(profile.PROFILE_NAMESPACE.bytes[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})

    customers = profile.customers()
    products = profile.catalog()
    plans = profile.plans(anchor)
    templates = profile.templates(anchor)
    manifest = {
        "version": profile.PROFILE_VERSION, "anchor": anchor.isoformat(),
        "customers": customers, "products": products, "plans": plans, "templates": templates,
    }
    digest = _digest(manifest)
    marker_id = profile.record_id("foundation-intent", "v1")
    marker_details = {
        "namespace": str(profile.PROFILE_NAMESPACE), "version": profile.PROFILE_VERSION,
        "anchor": anchor.isoformat(), "manifest_sha256": digest,
    }
    marker_spec = {
        "id": marker_id, "entity_type": FOUNDATION_ENTITY,
        "entity_id": profile.PROFILE_NAMESPACE, "action": FOUNDATION_ACTION,
        "redacted_details": marker_details,
    }
    marker = db.get(AuditEvent, marker_id)
    owned = marker is not None
    if owned:
        _ensure(db, AuditEvent, marker_spec, owned=True)
    else:
        db.add(AuditEvent(**marker_spec, actor_user_id=actor.id))
    counts = dict.fromkeys((
        "customers", "products", "variants", "plans", "templates", "template_lines",
        "contact_markers",
    ), 0)
    references: dict[str, list[UUID]] = {
        key: [] for key in ("customer_ids", "product_ids", "variant_ids", "plan_ids", "template_ids")
    }

    for spec in customers:
        CustomerWrite.model_validate({k: v for k, v in spec.items() if k != "id"})
        counts["customers"] += _ensure(db, Customer, spec, owned=owned)
        references["customer_ids"].append(spec["id"])
        db.flush()  # Contact and its durable no-email marker share this transaction.
        policy_spec = {
            "id": profile.record_id("contact-no-email", str(spec["id"])),
            "entity_type": DEMO_CONTACT_ENTITY_TYPE, "entity_id": spec["id"],
            "action": DEMO_CONTACT_ACTION,
            "redacted_details": {"namespace": str(profile.PROFILE_NAMESPACE)},
        }
        if db.get(AuditEvent, policy_spec["id"]) is None:
            if owned:
                raise FoundationConflict("A durable demo no-email marker is missing")
            db.add(AuditEvent(**policy_spec, actor_user_id=actor.id))
            counts["contact_markers"] += 1
        else:
            _ensure(db, AuditEvent, policy_spec, owned=owned)
    for spec in products:
        fields = {k: v for k, v in spec.items() if k not in {"stock_code", "original_description", "variants"}}
        ProductWrite.model_validate({
            k: str(v) if k in {"sales_price", "cost_price"} else v
            for k, v in fields.items() if k != "id"
        })
        counts["products"] += _ensure(db, Product, fields, owned=owned)
        references["product_ids"].append(spec["id"])
    db.flush()
    for spec in products:
        for variant in spec["variants"]:
            VariantWrite.model_validate({
                k: str(v) if k == "price_delta" else v
                for k, v in variant.items() if k not in {"id", "product_id"}
            })
            if spec["sales_price"] + variant["price_delta"] < 0:
                raise ValueError("A demo variant would have a negative unit price")
            counts["variants"] += _ensure(db, ProductVariant, variant, owned=owned)
            references["variant_ids"].append(variant["id"])
    for spec in plans:
        PlanWrite.model_validate({
            k: str(v) if k == "base_fee" else v for k, v in spec.items() if k != "id"
        })
        validate_plan_window(spec["available_from"], spec["available_until"])
        counts["plans"] += _ensure(db, Plan, spec, owned=owned)
        references["plan_ids"].append(spec["id"])
    db.flush()
    for spec in templates:
        TemplateWrite.model_validate({
            k: [{lk: lv for lk, lv in line.items() if lk != "id"} for line in v]
            if k == "lines" else v for k, v in spec.items() if k not in {"id", "active"}
        })
        fields = {k: v for k, v in spec.items() if k != "lines"}
        counts["templates"] += _ensure(db, QuotationTemplate, fields, owned=owned)
        references["template_ids"].append(spec["id"])
    db.flush()
    for spec in templates:
        for line in spec["lines"]:
            counts["template_lines"] += _ensure(
                db, QuotationTemplateLine, line | {"template_id": spec["id"]}, owned=owned
            )
    db.flush()
    # Detect added nested rows too; matching deterministic IDs alone is insufficient.
    for model, parent_column, parent_ids, expected_ids in (
        (ProductVariant, ProductVariant.product_id, references["product_ids"], references["variant_ids"]),
        (QuotationTemplateLine, QuotationTemplateLine.template_id, references["template_ids"],
         [line["id"] for spec in templates for line in spec["lines"]]),
    ):
        actual = set(db.scalars(select(model.id).where(parent_column.in_(parent_ids))))
        if actual != set(expected_ids):
            raise FoundationConflict(f"Unexpected nested demo rows: {model.__tablename__}")
    return {"counts": counts, "references": references, "manifest_sha256": digest}
