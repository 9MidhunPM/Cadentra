"""Retained rule administration and transaction-scoped billing selection."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.auth import Actor
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.core.money import money, money_string
from app.core.pagination import safe_offset
from app.models import (
    DiscountRevisionProduct,
    DiscountRule,
    DiscountRuleRevision,
    Product,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
)

from .pricing import SelectedDiscount
from .rule_schemas import DiscountWrite, TaxWrite


@dataclass(frozen=True)
class TaxSelection:
    rule_id: UUID
    revision_id: UUID
    name: str
    rate_percent: Decimal


@dataclass(frozen=True)
class DiscountLine:
    stable_line_key: str
    product_id: UUID | None
    quantity: int
    gross: Decimal


@dataclass(frozen=True)
class DiscountSelection:
    rule_id: UUID
    revision_id: UUID
    name: str
    discount: SelectedDiscount


def _effective(model, day):
    return (
        model.effective_from <= day,
        or_(model.effective_until.is_(None), model.effective_until > day),
    )


def get_applicable_taxes(db: Session, stable_ids, period_start: date) -> tuple[TaxSelection, ...]:
    ids = tuple(UUID(str(value)) for value in stable_ids)
    if not ids:
        return ()
    rows = db.scalars(
        select(TaxRuleRevision)
        .where(
            TaxRuleRevision.tax_rule_id.in_(ids),
            *_effective(TaxRuleRevision, period_start),
            TaxRuleRevision.active.is_(True),
            TaxRuleRevision.valid_from <= period_start,
            or_(TaxRuleRevision.valid_until.is_(None), TaxRuleRevision.valid_until > period_start),
        )
        .order_by(TaxRuleRevision.tax_rule_id)
    ).all()
    return tuple(TaxSelection(row.tax_rule_id, row.id, row.name, row.rate_percent) for row in rows)


def choose_discount(
    db: Session, period_start: date, lines: tuple[DiscountLine, ...]
) -> DiscountSelection | None:
    # Parent locks precede the eligibility/counter reread. Caller retains them until
    # invoice, redemption and counter commit together; this helper never consumes a use.
    parents = db.scalars(
        select(DiscountRule)
        .order_by(DiscountRule.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if not parents:
        return None
    revisions = db.scalars(
        select(DiscountRuleRevision).where(
            DiscountRuleRevision.discount_rule_id.in_([parent.id for parent in parents]),
            *_effective(DiscountRuleRevision, period_start),
            DiscountRuleRevision.active.is_(True),
            DiscountRuleRevision.starts_on <= period_start,
            or_(
                DiscountRuleRevision.ends_on.is_(None), DiscountRuleRevision.ends_on > period_start
            ),
        )
    ).all()
    counts = {parent.id: parent.uses_count for parent in parents}
    memberships: dict[UUID, set[UUID]] = {}
    for revision_id, product_id in db.execute(
        select(
            DiscountRevisionProduct.discount_rule_revision_id, DiscountRevisionProduct.product_id
        ).where(
            DiscountRevisionProduct.discount_rule_revision_id.in_([row.id for row in revisions])
        )
    ):
        memberships.setdefault(revision_id, set()).add(product_id)
    winner = None
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        for row in revisions:
            if row.usage_limit is not None and counts[row.discount_rule_id] >= row.usage_limit:
                continue
            eligible = tuple(
                line
                for line in lines
                if row.scope == "SUBSCRIPTION" or line.product_id in memberships.get(row.id, set())
            )
            gross = sum((line.gross for line in eligible), Decimal("0.00"))
            quantity = sum(line.quantity for line in eligible if line.product_id is not None)
            if gross <= 0 or gross < row.min_purchase or quantity < row.min_quantity:
                continue
            benefit = money(
                min(gross, gross * row.value / 100 if row.kind == "PERCENT" else row.value)
            )
            if benefit <= 0:
                continue
            candidate = (benefit, str(row.discount_rule_id))
            if (
                winner is None
                or benefit > winner[0]
                or (benefit == winner[0] and candidate[1] < winner[1])
            ):
                winner = (
                    benefit,
                    candidate[1],
                    DiscountSelection(
                        row.discount_rule_id,
                        row.id,
                        row.name,
                        SelectedDiscount(
                            row.kind,
                            row.value,
                            frozenset(line.stable_line_key for line in eligible),
                        ),
                    ),
                )
    return winner[2] if winner else None


def _admin(actor):
    if actor.role != "ADMIN":
        raise DomainError("FORBIDDEN", "Only administrators may change rules.", 403)


def _products(db, ids):
    found = set(db.scalars(select(Product.id).where(Product.id.in_(ids)))) if ids else set()
    if found != set(ids):
        raise DomainError("INVALID_PRODUCT", "One or more products are unavailable.", 422)


def _configuration(db, row, tax):
    model = TaxRevisionProduct if tax else DiscountRevisionProduct
    revision_column = model.tax_rule_revision_id if tax else model.discount_rule_revision_id
    ids = list(
        db.scalars(
            select(model.product_id).where(revision_column == row.id).order_by(model.product_id)
        )
    )
    fields = (
        ("name", "rate_percent", "valid_from", "valid_until", "active")
        if tax
        else (
            "name",
            "kind",
            "value",
            "scope",
            "min_purchase",
            "min_quantity",
            "starts_on",
            "ends_on",
            "usage_limit",
            "active",
        )
    )
    data = {field: getattr(row, field) for field in fields}
    for field in ("rate_percent", "value", "min_purchase"):
        if field in data:
            data[field] = format(data[field], "f")
    data["product_ids"] = [str(value) for value in ids]
    return data


def rule_data(db, parent, revision, tax):
    data = _configuration(db, revision, tax)
    if "min_purchase" in data:
        data["min_purchase"] = money_string(data["min_purchase"])
        if revision.kind == "FIXED":
            data["value"] = money_string(data["value"])
    data.update(
        id=str(parent.id),
        revision_id=str(revision.id),
        effective_from=revision.effective_from.isoformat(),
        effective_until=revision.effective_until.isoformat() if revision.effective_until else None,
    )
    for field in ("valid_from", "valid_until", "starts_on", "ends_on"):
        if field in data and data[field] is not None:
            data[field] = data[field].isoformat()
    if not tax:
        data["uses_count"] = parent.uses_count
    return data


def list_rules(db, actor, tax, page=1, page_size=25):
    if actor.role not in ("ADMIN", "STAFF"):
        raise DomainError("FORBIDDEN", "Staff access is required.", 403)
    offset = safe_offset(page, page_size)
    parent_model, revision_model = (
        (TaxRule, TaxRuleRevision) if tax else (DiscountRule, DiscountRuleRevision)
    )
    parent_key = revision_model.tax_rule_id if tax else revision_model.discount_rule_id
    today = get_clock().today()
    query = (
        select(parent_model, revision_model)
        .join(revision_model, parent_key == parent_model.id)
        .where(*_effective(revision_model, today))
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(parent_model.created_at.desc(), parent_model.id.desc())
        .offset(offset)
        .limit(page_size)
    ).all()
    return {
        "items": [rule_data(db, parent, revision, tax) for parent, revision in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def write_rule(db, actor: Actor, payload, tax: bool, rule_id: UUID | None = None):
    _admin(actor)
    parent_model, revision_model = (
        (TaxRule, TaxRuleRevision) if tax else (DiscountRule, DiscountRuleRevision)
    )
    parent_field = "tax_rule_id" if tax else "discount_rule_id"
    membership_model = TaxRevisionProduct if tax else DiscountRevisionProduct
    membership_field = "tax_rule_revision_id" if tax else "discount_rule_revision_id"
    schema = TaxWrite if tax else DiscountWrite
    with db.begin():
        if rule_id is None:
            effective = get_clock().today()
            parent = parent_model()
            db.add(parent)
            db.flush()
            configuration = payload
        else:
            parent = db.scalar(
                select(parent_model).where(parent_model.id == rule_id).with_for_update()
            )
            if parent is None:
                raise DomainError("NOT_FOUND", "Rule not found.", 404)
            effective = payload.effective_from
            if effective <= get_clock().today():
                raise DomainError(
                    "INVALID_EFFECTIVE_DATE",
                    "Revision must begin at least the next business day.",
                    422,
                )
            predecessor = db.scalar(
                select(revision_model)
                .where(getattr(revision_model, parent_field) == parent.id)
                .order_by(revision_model.effective_from.desc())
                .limit(1)
            )
            if (
                predecessor is None
                or effective <= predecessor.effective_from
                or predecessor.effective_until is not None
            ):
                raise DomainError(
                    "RULE_REVISION_CONFLICT", "Append a revision after the latest revision start."
                )
            merged = _configuration(db, predecessor, tax)
            merged.update(
                payload.model_dump(mode="json", exclude_unset=True, exclude={"effective_from"})
            )
            try:
                configuration = schema.model_validate(merged)
            except ValidationError as error:
                raise DomainError(
                    "INVALID_RULE", "Check the rule fields and validity window.", 422
                ) from error
            predecessor.effective_until = effective
            db.flush()
        _products(db, configuration.product_ids)
        values = configuration.model_dump(exclude={"product_ids"})
        row = revision_model(**{parent_field: parent.id}, effective_from=effective, **values)
        db.add(row)
        db.flush()
        for product_id in configuration.product_ids:
            db.add(membership_model(**{membership_field: row.id}, product_id=product_id))
        db.flush()
        result = rule_data(db, parent, row, tax)
    return result
