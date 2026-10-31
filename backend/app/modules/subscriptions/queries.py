"""Permission-checked subscription projections without financial side effects."""

from datetime import date
from decimal import Context, Decimal, InvalidOperation, localcontext
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_customer_ownership
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.core.money import money_string
from app.models import (
    Customer,
    Invoice,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
)
from app.modules.billing.rules import get_applicable_taxes
from app.modules.catalog.service import get_product_tax_ids

from .calendar import CADENCES, CycleSnapshot, get_cycle_bounds


def _valid_uuid_string(value):
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def safe_plan_projection(snapshot) -> dict:
    """Copy only correctly typed public fields; never project nested legacy data."""
    if not isinstance(snapshot, dict):
        raise DomainError("INVALID_SNAPSHOT", "Subscription pricing snapshot is invalid.")
    result = {}
    value = snapshot.get("base_fee")
    try:
        if not isinstance(value, str):
            raise ValueError("Expected decimal string")
        amount = Decimal(value)
        if (
            not amount.is_finite()
            or amount < 0
            or amount > Decimal("9999999999999999.99")
            or amount.as_tuple().exponent < -2
        ):
            raise ValueError("Invalid monetary value")
    except (ValueError, InvalidOperation) as error:
        raise DomainError(
            "INVALID_SNAPSHOT", "Subscription pricing snapshot is invalid."
        ) from error
    result["base_fee"] = value
    for key in ("name", "currency"):
        if isinstance(snapshot.get(key), str):
            result[key] = snapshot[key]
    if isinstance(snapshot.get("cadence"), str) and snapshot["cadence"] in CADENCES:
        result["cadence"] = snapshot["cadence"]
    if _valid_uuid_string(snapshot.get("plan_id")):
        result["plan_id"] = snapshot["plan_id"]
    for key in ("available_from", "available_until"):
        value = snapshot.get(key)
        if key == "available_until" and key in snapshot and value is None:
            result[key] = None
        elif isinstance(value, str) and len(value) == 10:
            try:
                date.fromisoformat(value)
                result[key] = value
            except ValueError:
                pass
    for key in ("schema_version", "min_quantity"):
        if type(snapshot.get(key)) is int and snapshot[key] > 0:
            result[key] = snapshot[key]
    for key in ("allow_pause", "allow_early_close", "allow_renew", "auto_close"):
        if type(snapshot.get(key)) is bool:
            result[key] = snapshot[key]
    if isinstance(snapshot.get("tax_rule_ids"), list):
        result["tax_rule_ids"] = [
            value for value in snapshot["tax_rule_ids"] if _valid_uuid_string(value)
        ]
    return result


def _pagination(page, page_size):
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
        raise DomainError(
            "INVALID_PAGINATION", "Use page >= 1 and page_size between 1 and 100.", 422
        )


def _authorize(actor: Actor, row: Subscription) -> None:
    if actor.role not in {"ADMIN", "STAFF", "CUSTOMER"}:
        raise DomainError("FORBIDDEN", "Your role cannot read subscriptions.", 403)
    require_customer_ownership(actor, row.customer_id)


def _pause_data(pauses, today: date):
    current = next(
        (p for p in pauses if p.starts_on <= today and (p.ends_on is None or today < p.ends_on)),
        None,
    )
    upcoming = next((p for p in pauses if p.starts_on > today), None)
    interval = current or upcoming
    return {
        "paused": current is not None,
        "pause_interval": (
            {
                "starts_on": interval.starts_on.isoformat(),
                "ends_on": interval.ends_on.isoformat() if interval.ends_on else None,
            }
            if interval
            else None
        ),
        "pause_effective_on": upcoming.starts_on.isoformat() if upcoming else None,
        "resume_effective_on": current.ends_on.isoformat() if current and current.ends_on else None,
    }


def _summary(row, customer_name, gross, pauses, today):
    plan = safe_plan_projection(row.plan_snapshot)
    quotation_valid_days = row.plan_snapshot.get("quotation_valid_days", 7)
    if type(quotation_valid_days) is not int or quotation_valid_days <= 0:
        quotation_valid_days = 7
    bounds = None
    if row.state in {"CONFIRMED", "ACTIVE"} and "cadence" not in plan:
        raise DomainError("INVALID_SNAPSHOT", "Subscription scheduling snapshot is invalid.")
    if row.state in {"CONFIRMED", "ACTIVE"} and plan.get("cadence"):
        bounds = get_cycle_bounds(
            CycleSnapshot(row.start_date, row.end_date, plan["cadence"], row.close_effective_on),
            row.next_cycle_index,
        )
    with localcontext(Context(prec=50)):
        recurring = Decimal(plan["base_fee"]) + gross
    return {
        "id": str(row.id),
        "number": row.number,
        "customer_id": str(row.customer_id),
        "customer_name": customer_name,
        "plan_id": str(row.plan_id),
        "prior_subscription_id": str(row.prior_subscription_id)
        if row.prior_subscription_id
        else None,
        "state": row.state,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "payment_terms_days": row.payment_terms_days,
        "quotation_valid_until": row.quotation_valid_until.isoformat()
        if row.quotation_valid_until
        else None,
        "quotation_valid_days": quotation_valid_days,
        "currency": row.currency,
        "plan_snapshot": plan,
        "revision": row.revision,
        "next_cycle_index": row.next_cycle_index,
        "next_billing_date": bounds[0].isoformat() if bounds else None,
        "close_effective_on": row.close_effective_on.isoformat()
        if row.close_effective_on
        else None,
        "expired": today >= min(row.end_date, row.close_effective_on or row.end_date),
        "recurring_subtotal": money_string(recurring),
        "recurring_subtotal_basis": "before tax and discounts",
        **_pause_data(pauses, today),
    }


def template_data(db: Session, row: QuotationTemplate) -> dict:
    lines = db.scalars(
        select(QuotationTemplateLine)
        .where(QuotationTemplateLine.template_id == row.id)
        .order_by(QuotationTemplateLine.created_at, QuotationTemplateLine.id)
    ).all()
    return _template_data(row, lines)


def _template_data(row, lines):
    return {
        "id": str(row.id),
        "name": row.name,
        "plan_id": str(row.plan_id),
        "valid_days": row.valid_days,
        "active": row.active,
        "lines": [
            {
                "product_id": str(line.product_id),
                "variant_id": str(line.variant_id) if line.variant_id else None,
                "quantity": line.quantity,
            }
            for line in lines
        ],
    }


def _subscription_line_data(line: SubscriptionLine) -> dict:
    with localcontext(Context(prec=50)):
        line_total = line.unit_price * line.quantity
    return {
        "id": str(line.id),
        "product_id": str(line.product_id),
        "variant_id": str(line.variant_id) if line.variant_id else None,
        "description": line.description,
        "quantity": line.quantity,
        "unit_price": money_string(line.unit_price),
        "line_total": money_string(line_total),
    }


def _tax_metadata(db, stable_ids, period_start, cache):
    key = tuple(sorted({UUID(str(value)) for value in stable_ids}, key=str))
    if key not in cache:
        cache[key] = [
            {"id": str(tax.rule_id), "name": tax.name, "rate_percent": str(tax.rate_percent)}
            for tax in get_applicable_taxes(db, key, period_start)
        ]
    return cache[key]


def subscription_data(db: Session, actor: Actor, row: Subscription) -> dict:
    _authorize(actor, row)
    from .workflows import allowed_actions

    lines = db.scalars(
        select(SubscriptionLine)
        .where(SubscriptionLine.subscription_id == row.id)
        .order_by(SubscriptionLine.created_at, SubscriptionLine.id)
    ).all()
    pauses = db.scalars(
        select(SubscriptionPause)
        .where(SubscriptionPause.subscription_id == row.id)
        .order_by(SubscriptionPause.starts_on)
    ).all()
    with localcontext(Context(prec=50)):
        gross = sum((line.unit_price * line.quantity for line in lines), Decimal("0.00"))
    today = get_clock().today()
    customer = db.get(Customer, row.customer_id)
    result = _summary(row, customer.display_name if customer else None, gross, pauses, today)
    result["lines"] = [_subscription_line_data(line) for line in lines]
    preview_on = (
        date.fromisoformat(result["next_billing_date"])
        if result["next_billing_date"]
        else row.start_date
    )
    tax_cache = {}
    product_ids = {}
    result["base_fee_taxes"] = _tax_metadata(
        db, result["plan_snapshot"].get("tax_rule_ids", []), preview_on, tax_cache
    )
    for line, projection in zip(lines, result["lines"], strict=True):
        if line.product_id not in product_ids:
            product_ids[line.product_id] = get_product_tax_ids(db, line.product_id, preview_on)
        projection["taxes"] = _tax_metadata(db, product_ids[line.product_id], preview_on, tax_cache)
    result["tax_preview_on"] = preview_on.isoformat()
    result["tax_preview_basis"] = (
        "Applicable rules at this service-period start; invoice snapshots determine final taxes"
    )
    result["allowed_actions"] = allowed_actions(db, actor, row, today)
    result["invoice_references"] = [
        {"id": str(invoice.id), "number": invoice.number, "status": invoice.status}
        for invoice in db.scalars(
            select(Invoice)
            .where(Invoice.subscription_id == row.id)
            .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        )
    ]
    return result


def get_subscription_for_actor(db: Session, actor: Actor, subscription_id: UUID) -> dict:
    row = db.get(Subscription, subscription_id)
    if row is None:
        raise DomainError("NOT_FOUND", "Record not found.", 404)
    return subscription_data(db, actor, row)


def list_subscriptions(
    db: Session, actor: Actor, page=1, page_size=25, customer_id=None, state=None, q=None
) -> dict:
    _pagination(page, page_size)
    if actor.role not in {"ADMIN", "STAFF", "CUSTOMER"}:
        raise DomainError("FORBIDDEN", "Your role cannot read subscriptions.", 403)
    filters = []
    if actor.role == "CUSTOMER":
        if actor.customer_id is None or (
            customer_id is not None and customer_id != actor.customer_id
        ):
            raise DomainError("NOT_FOUND", "Customer not found.", 404)
        filters.append(Subscription.customer_id == actor.customer_id)
    elif customer_id is not None:
        filters.append(Subscription.customer_id == customer_id)
    if state:
        filters.append(Subscription.state == state)
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(Subscription.number.ilike(pattern), Customer.display_name.ilike(pattern))
        )
    base = (
        select(Subscription, Customer.display_name)
        .join(Customer, Customer.id == Subscription.customer_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.execute(
        base.order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    ids = [row.id for row, _ in rows]
    gross = (
        dict(
            db.execute(
                select(
                    SubscriptionLine.subscription_id,
                    func.sum(SubscriptionLine.unit_price * SubscriptionLine.quantity),
                )
                .where(SubscriptionLine.subscription_id.in_(ids))
                .group_by(SubscriptionLine.subscription_id)
            ).all()
        )
        if ids
        else {}
    )
    pauses = {}
    if ids:
        for pause in db.scalars(
            select(SubscriptionPause)
            .where(SubscriptionPause.subscription_id.in_(ids))
            .order_by(SubscriptionPause.starts_on)
        ):
            pauses.setdefault(pause.subscription_id, []).append(pause)
    today = get_clock().today()
    return {
        "items": [
            _summary(row, name, gross.get(row.id, Decimal("0.00")), pauses.get(row.id, []), today)
            for row, name in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_templates(db: Session, actor: Actor, page=1, page_size=25) -> dict:
    _pagination(page, page_size)
    if actor.role not in {"ADMIN", "STAFF"}:
        raise DomainError("FORBIDDEN", "Only operators can read quotation templates.", 403)
    rows = db.scalars(
        select(QuotationTemplate)
        .order_by(QuotationTemplate.created_at.desc(), QuotationTemplate.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    ids = [row.id for row in rows]
    grouped = {}
    if ids:
        for line in db.scalars(
            select(QuotationTemplateLine)
            .where(QuotationTemplateLine.template_id.in_(ids))
            .order_by(QuotationTemplateLine.created_at, QuotationTemplateLine.id)
        ):
            grouped.setdefault(line.template_id, []).append(line)
    return {
        "items": [_template_data(row, grouped.get(row.id, [])) for row in rows],
        "total": db.scalar(select(func.count()).select_from(QuotationTemplate)),
        "page": page,
        "page_size": page_size,
    }
