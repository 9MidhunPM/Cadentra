"""Persisted subscription workflows. Every mutation uses the caller's transaction."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_customer_ownership
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
)
from app.modules.catalog.service import get_plan, get_plan_snapshot, get_product_snapshot

from .calendar import CycleSnapshot, get_cycle_bounds


def _operator(actor: Actor) -> None:
    if actor.role not in {"ADMIN", "STAFF"}:
        raise DomainError("FORBIDDEN", "Staff access is required.", 403)


def _audit(db, actor, row, action, details=None):
    db.add(
        AuditEvent(
            actor_user_id=actor.id if actor else None,
            entity_type="subscription" if isinstance(row, Subscription) else "quotation_template",
            entity_id=row.id,
            action=action,
            redacted_details=details or {},
        )
    )


def _subscription(db, actor, identifier, *, lock=True):
    query = select(Subscription).where(Subscription.id == identifier)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise DomainError("NOT_FOUND", "Record not found.", 404)
    require_customer_ownership(actor, row.customer_id)
    if actor.role not in {"ADMIN", "STAFF", "CUSTOMER"}:
        raise DomainError("FORBIDDEN", "Subscription access is forbidden.", 403)
    return row


def _template(db, identifier, *, lock=False):
    query = select(QuotationTemplate).where(QuotationTemplate.id == identifier)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise DomainError("NOT_FOUND", "Quotation template not found.", 404)
    return row


def _window(start, end, terms):
    if type(start) is not date or type(end) is not date or end <= start:
        raise DomainError("INVALID_SERVICE_WINDOW", "End date must follow start date.", 422)
    if type(terms) is not int or terms < 0:
        raise DomainError("INVALID_TERMS", "Payment terms must be nonnegative days.", 422)


def _line_payloads(lines):
    if not isinstance(lines, list) or not lines:
        raise DomainError("INVALID_LINES", "At least one product line is required.", 422)
    for line in lines:
        if (
            not isinstance(line, dict)
            or type(line.get("quantity")) is not int
            or line["quantity"] <= 0
        ):
            raise DomainError("INVALID_LINES", "Product quantities must be positive integers.", 422)
    return lines


def _minimum(lines, snapshot):
    _line_payloads(lines)
    if sum(line["quantity"] for line in lines) < snapshot["min_quantity"]:
        raise DomainError("MINIMUM_QUANTITY", "Product quantity is below the plan minimum.", 422)


def _lines(db, row):
    return list(
        db.scalars(
            select(SubscriptionLine)
            .where(SubscriptionLine.subscription_id == row.id)
            .order_by(SubscriptionLine.created_at, SubscriptionLine.id)
        )
    )


def _replace_lines(db, row, lines, *, preserve=False):
    _minimum(lines, row.plan_snapshot)
    old = _lines(db, row)
    remaining = list(old)
    for data in lines:
        matched = next(
            (
                item
                for item in remaining
                if item.product_id == data["product_id"]
                and item.variant_id == data.get("variant_id")
            ),
            None,
        )
        if matched is not None:
            remaining.remove(matched)
        if preserve and matched is not None:
            matched.quantity = data["quantity"]
            continue
        snap = get_product_snapshot(db, data["product_id"], data.get("variant_id"), row.start_date)
        values = dict(
            product_id=data["product_id"],
            variant_id=data.get("variant_id"),
            description=snap["description"],
            quantity=data["quantity"],
            unit_price=Decimal(snap["unit_price"]),
            price_snapshot=snap["price_snapshot"],
            selected_tax_ids=snap["selected_tax_ids"],
        )
        if matched is None:
            db.add(SubscriptionLine(subscription_id=row.id, **values))
        else:
            for key, value in values.items():
                setattr(matched, key, value)
    for item in remaining:
        db.delete(item)


def _template_lines(db, row, lines):
    _line_payloads(lines)
    plan = get_plan(db, row.plan_id)
    _minimum(lines, {"min_quantity": plan.min_quantity})
    for line in lines:
        get_product_snapshot(db, line["product_id"], line.get("variant_id"))
    db.execute(delete(QuotationTemplateLine).where(QuotationTemplateLine.template_id == row.id))
    for line in lines:
        db.add(QuotationTemplateLine(template_id=row.id, **line))


def create_template(db: Session, actor: Actor, payload: dict) -> QuotationTemplate:
    _operator(actor)
    if type(payload.get("valid_days")) is not int or payload["valid_days"] <= 0:
        raise DomainError("INVALID_VALIDITY", "Quotation validity must be positive days.", 422)
    get_plan(db, payload["plan_id"])
    row = QuotationTemplate(
        name=payload["name"], plan_id=payload["plan_id"], valid_days=payload["valid_days"]
    )
    db.add(row)
    db.flush()
    _template_lines(db, row, payload["lines"])
    _audit(db, actor, row, "template_created")
    db.flush()
    return row


def edit_template(db: Session, actor: Actor, identifier: UUID, payload: dict) -> QuotationTemplate:
    _operator(actor)
    row = _template(db, identifier, lock=True)
    if "valid_days" in payload and (
        type(payload["valid_days"]) is not int or payload["valid_days"] <= 0
    ):
        raise DomainError("INVALID_VALIDITY", "Quotation validity must be positive days.", 422)
    if "plan_id" in payload:
        get_plan(db, payload["plan_id"])
    for key in ("name", "plan_id", "valid_days", "active"):
        if key in payload:
            setattr(row, key, payload[key])
    lines = payload.get("lines")
    if lines is None:
        lines = [
            dict(product_id=x.product_id, variant_id=x.variant_id, quantity=x.quantity)
            for x in db.scalars(
                select(QuotationTemplateLine).where(QuotationTemplateLine.template_id == row.id)
            )
        ]
    _template_lines(db, row, lines)
    _audit(db, actor, row, "template_edited")
    db.flush()
    return row


def _create_draft(db: Session, actor: Actor, payload: dict) -> Subscription:
    if db.get(Customer, payload["customer_id"]) is None:
        raise DomainError("NOT_FOUND", "Customer not found.", 404)
    _window(payload["start_date"], payload["end_date"], payload["payment_terms_days"])
    plan = get_plan_snapshot(db, payload["plan_id"], payload["start_date"])
    lines = payload.get("lines")
    quotation_valid_days = 7
    if payload.get("template_id") is not None:
        template = _template(db, payload["template_id"], lock=True)
        if not template.active or template.plan_id != payload["plan_id"]:
            raise DomainError(
                "INVALID_TEMPLATE", "Select an active template matching the plan.", 422
            )
        quotation_valid_days = template.valid_days
        if "lines" not in payload:
            lines = [
                dict(product_id=x.product_id, variant_id=x.variant_id, quantity=x.quantity)
                for x in db.scalars(
                    select(QuotationTemplateLine).where(
                        QuotationTemplateLine.template_id == template.id
                    )
                )
            ]
    _minimum(lines, plan)
    plan["quotation_valid_days"] = quotation_valid_days
    row = Subscription(
        customer_id=payload["customer_id"],
        plan_id=payload["plan_id"],
        state="DRAFT",
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        payment_terms_days=payload["payment_terms_days"],
        currency=plan["currency"],
        plan_snapshot=plan,
    )
    db.add(row)
    db.flush()
    _replace_lines(db, row, lines)
    _audit(db, actor, row, "draft_created")
    db.flush()
    return row


def create_subscription(db: Session, actor: Actor, payload: dict) -> Subscription:
    _operator(actor)
    return _create_draft(db, actor, payload)


def _schedule(row):
    return CycleSnapshot(
        row.start_date, row.end_date, row.plan_snapshot["cadence"], row.close_effective_on
    )


def _due_guard(row, today):
    bounds = get_cycle_bounds(_schedule(row), row.next_cycle_index)
    if bounds is not None and bounds[0] <= today:
        raise DomainError(
            "DUE_BILLING_PENDING", "Process due billing before changing this subscription."
        )


def edit_subscription(db: Session, actor: Actor, identifier: UUID, payload: dict) -> Subscription:
    _operator(actor)
    row = _subscription(db, actor, identifier)
    if row.state not in {"DRAFT", "ACTIVE"}:
        raise DomainError(
            "INVALID_TRANSITION",
            "Revise a quotation before editing; confirmed and closed records cannot be edited.",
        )
    if row.state == "ACTIVE":
        if set(payload) - {"lines"}:
            raise DomainError(
                "INVALID_TRANSITION", "Only next-cycle lines may change on an active subscription."
            )
        if get_cycle_bounds(_schedule(row), row.next_cycle_index) is None:
            raise DomainError(
                "CYCLE_OUT_OF_RANGE", "No unprocessed service cycle remains for an edit."
            )
        _due_guard(row, get_clock().today())
    else:
        start = payload.get("start_date", row.start_date)
        end = payload.get("end_date", row.end_date)
        terms = payload.get("payment_terms_days", row.payment_terms_days)
        _window(start, end, terms)
        snapshot = get_plan_snapshot(db, row.plan_id, start)
        snapshot["quotation_valid_days"] = row.plan_snapshot.get("quotation_valid_days", 7)
        row.plan_snapshot = snapshot
        row.start_date, row.end_date, row.payment_terms_days = start, end, terms
        row.currency = row.plan_snapshot["currency"]
    if "lines" in payload:
        _replace_lines(db, row, payload["lines"], preserve=row.state == "ACTIVE")
    row.revision += 1
    _audit(
        db,
        actor,
        row,
        "subscription_edited",
        {"fields": sorted(payload), "effective_cycle_index": row.next_cycle_index},
    )
    db.flush()
    return row


def _first_boundary(row, today):
    """Binary search the original schedule, never walk a downtime day-by-day."""
    schedule = _schedule(row)
    low = row.next_cycle_index
    bounds = get_cycle_bounds(schedule, low)
    if bounds is None or bounds[0] >= today:
        return bounds[0] if bounds else min(row.end_date, row.close_effective_on or row.end_date)
    high = max(low + 1, 1)
    while True:
        bounds = get_cycle_bounds(schedule, high)
        if bounds is None or bounds[0] >= today:
            break
        high *= 2
    while low < high:
        mid = (low + high) // 2
        bounds = get_cycle_bounds(schedule, mid)
        if bounds is not None and bounds[0] < today:
            low = mid + 1
        else:
            high = mid
    bounds = get_cycle_bounds(schedule, low)
    return bounds[0] if bounds else min(row.end_date, row.close_effective_on or row.end_date)


def _require_state(row, *states):
    if row.state not in states:
        raise DomainError(
            "INVALID_TRANSITION", "This action is not available in the current state."
        )


def _renew(db, actor, row, payload, today):
    _require_state(row, "ACTIVE", "CLOSED")
    if not row.plan_snapshot.get("allow_renew"):
        raise DomainError("POLICY_FORBIDDEN", "Renewal is disabled by this subscription's plan.")
    start, end = payload["start_date"], payload["end_date"]
    effective_end = min(row.end_date, row.close_effective_on or row.end_date)
    if start < (effective_end if today < effective_end else today):
        raise DomainError(
            "INVALID_RENEWAL", "Renewal cannot overlap the existing term or backdate a gap."
        )
    if db.scalar(
        select(Subscription.id)
        .where(
            Subscription.prior_subscription_id == row.id,
            Subscription.start_date < end,
            Subscription.end_date > start,
        )
        .limit(1)
    ):
        raise DomainError("RENEWAL_OVERLAP", "An overlapping renewal already exists.")
    lines = _lines(db, row)
    new = _create_draft(
        db,
        actor,
        dict(
            customer_id=row.customer_id,
            plan_id=row.plan_id,
            start_date=start,
            end_date=end,
            payment_terms_days=payload.get("payment_terms_days", row.payment_terms_days),
            lines=[
                dict(product_id=x.product_id, variant_id=x.variant_id, quantity=x.quantity)
                for x in lines
            ],
        ),
    )
    new.prior_subscription_id = row.id
    _audit(db, actor, row, "renewal_requested", {"new_subscription_id": str(new.id)})
    return new


def apply_action_record(
    db: Session, actor: Actor, identifier: UUID, action: str, payload: dict
) -> Subscription:
    row = _subscription(db, actor, identifier)
    if actor.role == "CUSTOMER" and action not in {"pause", "resume", "close", "renew"}:
        raise DomainError("FORBIDDEN", "Customers cannot perform staff lifecycle actions.", 403)
    today = get_clock().today()
    if action == "renew":
        result = _renew(db, actor, row, payload, today)
        db.flush()
        return result
    if action == "issue-quotation":
        _require_state(row, "DRAFT")
        days = payload.get("valid_days")
        if type(days) is not int or days <= 0:
            raise DomainError("INVALID_VALIDITY", "Quotation validity must be positive days.", 422)
        try:
            deadline = today + timedelta(days=days)
        except OverflowError as error:
            raise DomainError(
                "INVALID_VALIDITY", "Quotation deadline exceeds supported dates.", 422
            ) from error
        snapshot = get_plan_snapshot(db, row.plan_id, row.start_date)
        snapshot["quotation_valid_days"] = days
        row.plan_snapshot = snapshot
        _replace_lines(
            db,
            row,
            [
                dict(product_id=x.product_id, variant_id=x.variant_id, quantity=x.quantity)
                for x in _lines(db, row)
            ],
        )
        row.quotation_valid_until = deadline
        row.state = "QUOTATION"
    elif action == "revise":
        _require_state(row, "QUOTATION")
        row.state, row.quotation_valid_until = "DRAFT", None
    elif action == "confirm":
        _require_state(row, "QUOTATION")
        if row.quotation_valid_until is None or today >= row.quotation_valid_until:
            raise DomainError("QUOTATION_EXPIRED", "Revise and reissue the expired quotation.")
        get_plan(db, row.plan_id, lock=True)
        snapshot = get_plan_snapshot(db, row.plan_id, row.start_date)
        contractual_fields = (
            "base_fee",
            "currency",
            "cadence",
            "min_quantity",
            "allow_pause",
            "allow_early_close",
            "allow_renew",
            "auto_close",
        )
        if any(snapshot[field] != row.plan_snapshot.get(field) for field in contractual_fields) or (
            set(snapshot["tax_rule_ids"]) != set(row.plan_snapshot.get("tax_rule_ids", []))
        ):
            raise DomainError(
                "QUOTATION_PLAN_CHANGED",
                "Plan terms changed after quotation. Revise and reissue before confirming.",
            )
        snapshot["quotation_valid_days"] = row.plan_snapshot.get("quotation_valid_days", 7)
        _minimum([dict(quantity=x.quantity) for x in _lines(db, row)], snapshot)
        row.plan_snapshot, row.currency, row.state = snapshot, snapshot["currency"], "CONFIRMED"
    elif action == "activate":
        _require_state(row, "CONFIRMED")
        if today < row.start_date:
            raise DomainError("INVALID_TRANSITION", "Activation requires an eligible service date.")
        row.state = "ACTIVE"
    elif action in {"pause", "resume", "close"}:
        _require_state(row, "ACTIVE")
        effective_end = min(row.end_date, row.close_effective_on or row.end_date)
        if action == "close" and today >= effective_end:
            if actor.role == "CUSTOMER" and not row.plan_snapshot.get("allow_early_close"):
                raise DomainError("POLICY_FORBIDDEN", "Closure requires staff review.")
            _due_guard(row, today)
            row.state = "CLOSED"
        elif action == "resume":
            if not row.plan_snapshot.get("allow_pause"):
                raise DomainError("POLICY_FORBIDDEN", "Pause and resume are disabled.")
            pause = db.scalar(
                select(SubscriptionPause).where(
                    SubscriptionPause.subscription_id == row.id, SubscriptionPause.ends_on.is_(None)
                )
            )
            if pause is None:
                raise DomainError("INVALID_TRANSITION", "There is no open pause to resume.")
            applied = db.scalar(
                select(BillingPeriod.id)
                .where(
                    BillingPeriod.subscription_id == row.id,
                    BillingPeriod.disposition == "PAUSED",
                    BillingPeriod.period_start >= pause.starts_on,
                )
                .limit(1)
            )
            if applied is None and pause.starts_on >= today:
                db.delete(pause)
                _audit(
                    db,
                    actor,
                    row,
                    "pending_pause_cancelled",
                    {"starts_on": pause.starts_on.isoformat()},
                )
            else:
                boundary = _first_boundary(row, today)
                if boundary >= effective_end:
                    raise DomainError(
                        "CYCLE_OUT_OF_RANGE", "No eligible original resume boundary remains."
                    )
                if boundary <= pause.starts_on:
                    raise DomainError("INVALID_TRANSITION", "No later resume boundary remains.")
                pause.ends_on = boundary
        else:
            if today >= effective_end:
                raise DomainError("SUBSCRIPTION_EXPIRED", "The service term has expired.")
            policy = "allow_pause" if action == "pause" else "allow_early_close"
            if not row.plan_snapshot.get(policy):
                raise DomainError(
                    "POLICY_FORBIDDEN", "This action is disabled by the confirmed plan."
                )
            _due_guard(row, today)
            bounds = get_cycle_bounds(_schedule(row), row.next_cycle_index)
            boundary = bounds[0] if bounds else effective_end
            if action == "pause":
                if boundary >= effective_end or db.scalar(
                    select(SubscriptionPause.id)
                    .where(
                        SubscriptionPause.subscription_id == row.id,
                        SubscriptionPause.ends_on.is_(None),
                    )
                    .limit(1)
                ):
                    raise DomainError("INVALID_TRANSITION", "No new pause can be scheduled.")
                db.add(SubscriptionPause(subscription_id=row.id, starts_on=boundary))
            else:
                row.close_effective_on = boundary
                row.close_reason = payload.get("reason")
                if boundary <= today:
                    row.state = "CLOSED"
    else:
        raise DomainError("INVALID_TRANSITION", "Unknown subscription action.")
    row.revision += 1
    _audit(
        db,
        actor,
        row,
        action,
        {
            "state": row.state,
            "effective_on": row.close_effective_on.isoformat() if row.close_effective_on else None,
        },
    )
    db.flush()
    return row


def process_lifecycle(db: Session, as_of: date) -> dict:
    counts = {"activated": 0, "closed": 0, "deferred": 0}
    rows = db.scalars(
        select(Subscription)
        .where(
            or_(
                and_(Subscription.state == "CONFIRMED", Subscription.start_date <= as_of),
                and_(
                    Subscription.state == "ACTIVE",
                    or_(
                        Subscription.close_effective_on <= as_of,
                        and_(
                            Subscription.end_date <= as_of,
                            Subscription.plan_snapshot["auto_close"].as_boolean().is_(True),
                        ),
                    ),
                ),
            )
        )
        .order_by(Subscription.id)
        .with_for_update()
    )
    for row in rows:
        action = None
        if row.state == "CONFIRMED" and row.start_date <= as_of:
            row.state, action = "ACTIVE", "automatic_activation"
            counts["activated"] += 1
        effective_end = min(row.end_date, row.close_effective_on or row.end_date)
        if as_of >= effective_end and (
            row.plan_snapshot.get("auto_close") or row.close_effective_on is not None
        ):
            if get_cycle_bounds(_schedule(row), row.next_cycle_index) is None:
                row.state, action = "CLOSED", "automatic_closure"
                counts["closed"] += 1
            else:
                counts["deferred"] += 1
        if action:
            row.revision += 1
            _audit(db, None, row, action)
    db.flush()
    return counts


def allowed_actions(
    db: Session, actor: Actor, subscription: Subscription, as_of: date
) -> list[str]:
    require_customer_ownership(actor, subscription.customer_id)
    if actor.role not in {"ADMIN", "STAFF", "CUSTOMER"}:
        return []
    row = subscription
    staff = actor.role in {"ADMIN", "STAFF"}
    if row.state == "DRAFT":
        return ["issue-quotation"] if staff else []
    if row.state == "QUOTATION":
        result = ["revise"] if staff else []
        if staff and row.quotation_valid_until and as_of < row.quotation_valid_until:
            result.append("confirm")
        return result
    if row.state == "CONFIRMED":
        return ["activate"] if staff and row.start_date <= as_of else []
    result = ["renew"] if row.plan_snapshot.get("allow_renew") else []
    if row.state != "ACTIVE":
        return result if row.state == "CLOSED" else []
    effective_end = min(row.end_date, row.close_effective_on or row.end_date)
    bounds = get_cycle_bounds(_schedule(row), row.next_cycle_index)
    due = bounds is not None and bounds[0] <= as_of
    if as_of >= effective_end:
        if staff and not due:
            result.append("close")
        return result
    pause = db.scalar(
        select(SubscriptionPause).where(
            SubscriptionPause.subscription_id == row.id, SubscriptionPause.ends_on.is_(None)
        )
    )
    if pause and row.plan_snapshot.get("allow_pause"):
        applied = db.scalar(
            select(BillingPeriod.id)
            .where(
                BillingPeriod.subscription_id == row.id,
                BillingPeriod.disposition == "PAUSED",
                BillingPeriod.period_start >= pause.starts_on,
            )
            .limit(1)
        )
        pending_cancel = applied is None and pause.starts_on >= as_of
        boundary = _first_boundary(row, as_of)
        if pending_cancel or pause.starts_on < boundary < effective_end:
            result.append("resume")
    elif not due and bounds and row.plan_snapshot.get("allow_pause"):
        result.append("pause")
    if not due and row.plan_snapshot.get("allow_early_close"):
        result.append("close")
    return result
