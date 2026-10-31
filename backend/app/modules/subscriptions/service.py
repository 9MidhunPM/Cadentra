"""Subscription-owned billing inputs; callers own locking and transactions."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_customer_ownership
from app.core.errors import DomainError
from app.models import Subscription, SubscriptionLine, SubscriptionPause
from app.modules.catalog.service import get_product_tax_ids

from .calendar import CycleSnapshot, get_cycle_bounds


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def snapshot_to_json(value: Any) -> Any:
    """Materialize fresh JSON data from a frozen source snapshot for persistence."""
    if isinstance(value, Mapping):
        return {key: snapshot_to_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [snapshot_to_json(item) for item in value]
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class BillableLine:
    stable_line_key: str
    product_id: UUID | None
    variant_id: UUID | None
    description: str
    quantity: int
    unit_price: Decimal
    selected_tax_ids: tuple[UUID, ...]
    source_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_tax_ids", tuple(self.selected_tax_ids))
        object.__setattr__(self, "source_snapshot", _freeze(self.source_snapshot))


@dataclass(frozen=True, slots=True)
class BillableInputs:
    subscription_id: UUID
    customer_id: UUID
    revision: int
    plan_id: UUID
    currency: str
    payment_terms_days: int
    cycle_index: int
    period_start: date
    period_end: date
    effective_end: date
    paused: bool
    plan_snapshot: Mapping[str, Any]
    lines: tuple[BillableLine, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_snapshot", _freeze(self.plan_snapshot))
        object.__setattr__(self, "lines", tuple(self.lines))


def get_billable_inputs(db: Session, subscription_id: UUID, cycle_index: int) -> BillableInputs:
    """Read the next cycle without committing, advancing it or repricing sources.

    Billing must hold the subscription lock and reuse any durable period outcome
    before calling this function. Due-date filtering belongs to the worker.
    """
    if type(cycle_index) is not int or cycle_index < 0:
        raise DomainError("INVALID_CYCLE", "Cycle index must be a nonnegative integer.")
    subscription = db.get(Subscription, subscription_id)
    if subscription is None:
        raise DomainError("NOT_FOUND", "Subscription not found.", 404)
    if subscription.state != "ACTIVE":
        raise DomainError("INVALID_TRANSITION", "Only active subscriptions can be billed.")
    if cycle_index < subscription.next_cycle_index:
        raise DomainError("PERIOD_ALREADY_PROCESSED", "Reuse this cycle's persisted outcome.")
    if cycle_index > subscription.next_cycle_index:
        raise DomainError("INVALID_CYCLE", "Only the next unprocessed cycle can be billed.")

    plan = subscription.plan_snapshot
    schedule = CycleSnapshot(
        subscription.start_date,
        subscription.end_date,
        plan["cadence"],
        subscription.close_effective_on,
    )
    bounds = get_cycle_bounds(schedule, cycle_index)
    if bounds is None:
        raise DomainError("CYCLE_OUT_OF_RANGE", "No service period remains for this cycle.")
    start, end = bounds
    paused = (
        db.scalar(
            select(SubscriptionPause.id)
            .where(
                SubscriptionPause.subscription_id == subscription.id,
                SubscriptionPause.starts_on <= start,
                or_(SubscriptionPause.ends_on.is_(None), SubscriptionPause.ends_on > start),
            )
            .limit(1)
        )
        is not None
    )

    lines = [
        BillableLine(
            stable_line_key="BASE",
            product_id=None,
            variant_id=None,
            description=plan["name"],
            quantity=1,
            unit_price=Decimal(plan["base_fee"]),
            selected_tax_ids=tuple(UUID(value) for value in plan["tax_rule_ids"]),
            source_snapshot=plan,
        )
    ]
    product_taxes: dict[UUID, tuple[UUID, ...]] = {}
    for row in db.scalars(
        select(SubscriptionLine)
        .where(SubscriptionLine.subscription_id == subscription.id)
        .order_by(SubscriptionLine.created_at, SubscriptionLine.id)
    ):
        if row.product_id not in product_taxes:
            product_taxes[row.product_id] = tuple(
                UUID(value) for value in get_product_tax_ids(db, row.product_id, start)
            )
        lines.append(
            BillableLine(
                stable_line_key=str(row.id),
                product_id=row.product_id,
                variant_id=row.variant_id,
                description=row.description,
                quantity=row.quantity,
                unit_price=row.unit_price,
                selected_tax_ids=product_taxes[row.product_id],
                source_snapshot=row.price_snapshot,
            )
        )
    return BillableInputs(
        subscription_id=subscription.id,
        customer_id=subscription.customer_id,
        revision=subscription.revision,
        plan_id=subscription.plan_id,
        currency=subscription.currency,
        payment_terms_days=subscription.payment_terms_days,
        cycle_index=cycle_index,
        period_start=start,
        period_end=end,
        effective_end=min(
            subscription.end_date, subscription.close_effective_on or subscription.end_date
        ),
        paused=paused,
        plan_snapshot=plan,
        lines=tuple(lines),
    )


def get_subscription_for_actor(db: Session, actor: Actor, subscription_id: UUID) -> dict:
    """Shared safe detail projection for staff and customer portal callers."""
    from .queries import get_subscription_for_actor as project

    return project(db, actor, subscription_id)


def apply_action(
    db: Session,
    actor: Actor,
    subscription_id: UUID,
    action: str,
    payload: dict | None = None,
) -> dict:
    """Validate a portal/staff action and project its result; caller commits."""
    from . import queries, schemas, workflows

    subscription = db.get(Subscription, subscription_id)
    if subscription is None:
        raise DomainError("NOT_FOUND", "Subscription not found.", 404)
    require_customer_ownership(actor, subscription.customer_id)
    if actor.role not in {"ADMIN", "STAFF", "CUSTOMER"}:
        raise DomainError("FORBIDDEN", "Your role cannot act on subscriptions.", 403)
    if actor.role == "CUSTOMER" and action not in {"pause", "resume", "close", "renew"}:
        raise DomainError("FORBIDDEN", "Customers cannot perform staff lifecycle actions.", 403)
    if action not in {
        "issue-quotation",
        "revise",
        "confirm",
        "activate",
        "pause",
        "resume",
        "close",
        "renew",
    }:
        raise DomainError("INVALID_TRANSITION", "Unknown subscription action.")
    model = (
        schemas.QuoteIssue
        if action == "issue-quotation"
        else (schemas.Renew if action == "renew" else schemas.LifecycleAction)
    )
    try:
        values = model.model_validate({} if payload is None else payload).model_dump(
            exclude_unset=True
        )
    except ValidationError as error:
        fields = {
            ".".join(str(part) for part in item["loc"]) or "body": item["msg"]
            for item in error.errors()
        }
        raise DomainError("VALIDATION_ERROR", "Check the action fields.", 422, fields) from error
    row = workflows.apply_action_record(db, actor, subscription_id, action, values)
    return queries.subscription_data(db, actor, row)


def process_lifecycle(db: Session, as_of: date) -> dict:
    """Worker-facing lifecycle processing inside its caller-owned transaction."""
    from .workflows import process_lifecycle as process

    return process(db, as_of)
