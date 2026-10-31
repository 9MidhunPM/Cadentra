"""Catalog reads and snapshots. Caller owns the database transaction."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.errors import DomainError
from app.core.money import money_string
from app.models import (
    Plan,
    PlanTax,
    Product,
    ProductVariant,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
)


def get_product(db: Session, product_id: UUID, *, lock=False) -> Product:
    query = select(Product).where(Product.id == product_id)
    if lock:
        query = query.with_for_update()
    product = db.scalar(query)
    if product is None:
        raise DomainError("NOT_FOUND", "Product not found.", 404)
    return product


def get_plan(db: Session, plan_id: UUID, *, lock=False) -> Plan:
    query = select(Plan).where(Plan.id == plan_id)
    if lock:
        query = query.with_for_update()
    plan = db.scalar(query)
    if plan is None:
        raise DomainError("NOT_FOUND", "Plan not found.", 404)
    return plan


def validate_plan_window(start: date, end: date | None) -> None:
    if end is not None and end <= start:
        raise DomainError("INVALID_AVAILABILITY", "Availability end must follow its start.", 422)


def validate_tax_ids(db: Session, ids: list[UUID]) -> list[UUID]:
    if len(ids) != len(set(ids)):
        raise DomainError("INVALID_TAX_RULE", "Tax selections must be unique.", 422)
    if ids and set(db.scalars(select(TaxRule.id).where(TaxRule.id.in_(ids)))) != set(ids):
        raise DomainError("INVALID_TAX_RULE", "A selected tax rule does not exist.", 422)
    return ids


def reject_nulls(changes: dict, nullable=()) -> None:
    if any(value is None and key not in nullable for key, value in changes.items()):
        raise DomainError("INVALID_CATALOG", "Required catalog fields cannot be null.", 422)


def variant_data(row: ProductVariant) -> dict:
    return {
        "id": str(row.id),
        "product_id": str(row.product_id),
        "attribute_name": row.attribute_name,
        "attribute_value": row.attribute_value,
        "price_delta": money_string(row.price_delta),
        "active": row.active,
    }


def product_data(row: Product) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "product_type": row.product_type,
        "sales_price": money_string(row.sales_price),
        "cost_price": money_string(row.cost_price),
        "notes": row.notes,
        "active": row.active,
    }


def plan_data(db: Session, row: Plan, tax_rule_ids=None) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "base_fee": money_string(row.base_fee),
        "currency": row.currency,
        "cadence": row.cadence,
        "min_quantity": row.min_quantity,
        "available_from": row.available_from.isoformat(),
        "available_until": row.available_until.isoformat() if row.available_until else None,
        "allow_pause": row.allow_pause,
        "allow_early_close": row.allow_early_close,
        "allow_renew": row.allow_renew,
        "auto_close": row.auto_close,
        "tax_rule_ids": sorted(
            str(x)
            for x in (
                tax_rule_ids
                if tax_rule_ids is not None
                else db.scalars(select(PlanTax.tax_rule_id).where(PlanTax.plan_id == row.id))
            )
        ),
    }


def get_plan_snapshot(db: Session, plan_id: UUID, effective_date: date) -> dict:
    plan = get_plan(db, plan_id)
    if effective_date < plan.available_from or (
        plan.available_until is not None and effective_date >= plan.available_until
    ):
        raise DomainError(
            "PLAN_UNAVAILABLE", "Plan is unavailable on the requested service date.", 409
        )
    snapshot = plan_data(db, plan)
    snapshot["plan_id"] = snapshot.pop("id")
    snapshot["schema_version"] = 1
    return snapshot


def get_product_tax_ids(db: Session, product_id: UUID, effective_date: date) -> list[str]:
    """Resolve period-effective tax membership without reading or repricing catalog prices."""
    selected_tax_ids = list(
        db.scalars(
            select(TaxRuleRevision.tax_rule_id)
            .join(
                TaxRevisionProduct,
                TaxRevisionProduct.tax_rule_revision_id == TaxRuleRevision.id,
            )
            .where(
                TaxRevisionProduct.product_id == product_id,
                TaxRuleRevision.effective_from <= effective_date,
                (
                    TaxRuleRevision.effective_until.is_(None)
                    | (TaxRuleRevision.effective_until > effective_date)
                ),
                TaxRuleRevision.active.is_(True),
                TaxRuleRevision.valid_from <= effective_date,
                (
                    TaxRuleRevision.valid_until.is_(None)
                    | (TaxRuleRevision.valid_until > effective_date)
                ),
            )
        )
    )
    return sorted(str(value) for value in selected_tax_ids)


def get_product_snapshot(
    db: Session,
    product_id: UUID,
    variant_id: UUID | None = None,
    effective_date: date | None = None,
) -> dict:
    product = get_product(db, product_id)
    if not product.active:
        raise DomainError("PRODUCT_UNAVAILABLE", "Product is archived.", 409)
    variant = None
    if variant_id is not None:
        variant = db.scalar(
            select(ProductVariant).where(
                ProductVariant.id == variant_id, ProductVariant.product_id == product_id
            )
        )
        if variant is None:
            raise DomainError("NOT_FOUND", "Variant not found for this product.", 404)
        if not variant.active:
            raise DomainError("PRODUCT_UNAVAILABLE", "Variant is archived.", 409)
    unit_price = product.sales_price + (variant.price_delta if variant else 0)
    if unit_price < 0:
        raise DomainError("INVALID_PRICE", "Variant price cannot be negative.", 409)
    selected_tax_ids = get_product_tax_ids(db, product_id, effective_date or get_clock().today())
    return {
        "product_id": str(product.id),
        "variant_id": str(variant.id) if variant else None,
        "description": product.name
        + (f" ({variant.attribute_name}: {variant.attribute_value})" if variant else ""),
        "unit_price": money_string(unit_price),
        "selected_tax_ids": selected_tax_ids,
        "price_snapshot": {
            "sales_price": money_string(product.sales_price),
            "variant_delta": money_string(variant.price_delta if variant else "0.00"),
        },
    }
