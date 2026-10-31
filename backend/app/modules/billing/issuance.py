"""Atomic recurring issuance; each subscription period owns one transaction."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Context, localcontext
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import Actor, Role
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.core.money import money, money_string
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    DiscountRedemption,
    DiscountRule,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    Subscription,
)
from app.modules.subscriptions.calendar import CycleSnapshot, get_cycle_bounds

from .pricing import PricingLine, calculate_invoice
from .rules import DiscountLine, choose_discount, get_applicable_taxes

logger = logging.getLogger(__name__)
BATCH_ENTITY = UUID("c8f1a9d0-7a19-4daa-9084-a3cf86cb661c")
__all__ = [
    "BillingRunResult",
    "issue_due_period",
    "run_due",
]


@dataclass(frozen=True)
class PeriodOutcome:
    disposition: str
    period_id: UUID | None = None
    invoice_id: UUID | None = None


@dataclass(frozen=True)
class BillingFailure:
    subscription_id: str
    code: str


@dataclass(frozen=True)
class BillingRunResult:
    processed_periods: int
    invoices_created: int
    paused_periods: int
    existing_periods: int
    failed_subscription_count: int
    has_more_due: bool
    failures: tuple[BillingFailure, ...]


def _inputs_service():
    target = "app.modules.subscriptions.service"
    try:
        module = importlib.import_module(target)
    except ModuleNotFoundError as error:
        if error.name != target:
            raise
        raise DomainError(
            "SERVICE_NOT_READY", "Subscription pricing inputs are not integrated yet.", 503
        ) from error
    if not callable(getattr(module, "get_billable_inputs", None)):
        raise DomainError("SERVICE_NOT_READY", "Subscription pricing inputs are unavailable.", 503)
    return module


def _bounds(subscription: Subscription, cycle_index: int):
    try:
        return get_cycle_bounds(
            CycleSnapshot(
                start_date=subscription.start_date,
                end_date=subscription.end_date,
                cadence=subscription.plan_snapshot["cadence"],
                close_effective_on=subscription.close_effective_on,
            ),
            cycle_index,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise DomainError("INVALID_SCHEDULE", "Subscription schedule requires review.") from error


def _lock_subscription(db: Session, subscription_id: UUID) -> Subscription:
    row = db.scalar(
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise DomainError("NOT_FOUND", "Subscription not found.", 404)
    return row


def _existing_outcome(db: Session, subscription: Subscription, index: int):
    period = db.scalar(
        select(BillingPeriod).where(
            BillingPeriod.subscription_id == subscription.id, BillingPeriod.cycle_index == index
        )
    )
    if period is None:
        return None
    invoice_id = db.scalar(select(Invoice.id).where(Invoice.billing_period_id == period.id))
    if period.disposition == "INVOICED" and invoice_id is None:
        raise DomainError("INCOMPLETE_PERIOD", "A billing period needs operator review.")
    if subscription.next_cycle_index == index:
        subscription.next_cycle_index = index + 1
    return PeriodOutcome("EXISTING", period.id, invoice_id)


def _persist_invoice(db: Session, subscription: Subscription, period: BillingPeriod, inputs, dto):
    lines = tuple(inputs.lines)
    if sum(line.stable_line_key == "BASE" for line in lines) != 1 or any(
        line.quantity != 1 or line.product_id is not None
        for line in lines
        if line.stable_line_key == "BASE"
    ):
        raise DomainError("INVALID_BILLABLE_INPUTS", "Exactly one base-fee line is required.")
    taxes = {
        line.stable_line_key: get_applicable_taxes(db, line.selected_tax_ids, inputs.period_start)
        for line in lines
    }
    pricing_lines = tuple(
        PricingLine(
            line.stable_line_key,
            line.quantity,
            line.unit_price,
            tuple(tax.rate_percent for tax in taxes[line.stable_line_key]),
        )
        for line in lines
    )
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        selected = choose_discount(
            db,
            inputs.period_start,
            tuple(
                DiscountLine(
                    line.stable_line_key,
                    line.product_id,
                    line.quantity,
                    money(line.unit_price * line.quantity),
                )
                for line in lines
            ),
        )
        result = calculate_invoice(pricing_lines, selected.discount if selected else None)
    today = get_clock().today()
    if inputs.payment_terms_days > (date.max - today).days:
        raise DomainError("INVALID_PAYMENT_TERMS", "Payment terms exceed supported dates.", 422)
    customer = db.get(Customer, subscription.customer_id)
    if customer is None:
        raise DomainError("INVALID_CUSTOMER", "Subscription customer is unavailable.")
    invoice = Invoice(
        id=uuid4(),
        subscription_id=subscription.id,
        billing_period_id=period.id,
        customer_id=subscription.customer_id,
        status="DRAFT",
        currency=inputs.currency,
        invoice_date=today,
        due_date=today + timedelta(days=inputs.payment_terms_days),
        customer_snapshot={
            "display_name": customer.display_name,
            "email": customer.email,
            "company_name": customer.company_name,
            "billing_address": dict(customer.billing_address),
        },
        seller_snapshot={"name": "Brightloop Software"},
        subtotal=result.subtotal,
        discount_total=result.discount_total,
        tax_total=result.tax_total,
        total=result.total,
        discount_rule_id=selected.rule_id if selected else None,
        discount_rule_revision_id=selected.revision_id if selected else None,
        calculation_snapshot={
            "schema_version": 1,
            "rounding": "ROUND_HALF_UP",
            "tax_policy": "after_discount_noncompounding",
            "subscription_revision": inputs.revision,
            "discount_kind": selected.discount.kind if selected else None,
            "discount_value": format(selected.discount.value, "f") if selected else "0.00",
            "discount_reason": selected.name if selected else "No eligible positive discount",
            "line_keys": [line.stable_line_key for line in lines],
            "lines": [
                {
                    "stable_line_key": source.stable_line_key,
                    "quantity": source.quantity,
                    "unit_price": money_string(source.unit_price),
                    "gross": money_string(item.gross),
                    "discount": money_string(item.discount),
                    "taxable_amount": money_string(item.taxable_amount),
                    "tax_total": money_string(item.tax_total),
                    "total": money_string(item.total),
                    "price_components": {
                        key: dto.snapshot_to_json(source.source_snapshot[key])
                        for key in ("sales_price", "variant_delta", "base_fee")
                        if key in source.source_snapshot
                    },
                    "taxes": [
                        {
                            "rule_id": str(tax.rule_id),
                            "revision_id": str(tax.revision_id),
                            "name": tax.name,
                            "rate_percent": format(tax.rate_percent, ".4f"),
                            "amount": money_string(amount),
                        }
                        for tax, amount in zip(
                            taxes[source.stable_line_key], item.tax_amounts, strict=True
                        )
                    ],
                }
                for source, item in zip(lines, result.lines, strict=True)
            ],
        },
    )
    db.add(invoice)
    db.flush()
    persisted = []
    for source, calculated in zip(lines, result.lines, strict=True):
        row = InvoiceLine(
            id=uuid4(),
            invoice_id=invoice.id,
            stable_line_key=source.stable_line_key,
            description=source.description,
            product_id=source.product_id,
            variant_id=source.variant_id,
            quantity=source.quantity,
            unit_price=source.unit_price,
            gross=calculated.gross,
            discount=calculated.discount,
            taxable_amount=calculated.taxable_amount,
            tax_total=calculated.tax_total,
            total=calculated.total,
            source_snapshot=dto.snapshot_to_json(source.source_snapshot),
        )
        db.add(row)
        persisted.append((row, calculated))
    db.flush()
    for row, calculated in persisted:
        for tax, amount in zip(taxes[row.stable_line_key], calculated.tax_amounts, strict=True):
            db.add(
                InvoiceLineTax(
                    invoice_line_id=row.id,
                    tax_rule_id=tax.rule_id,
                    tax_rule_revision_id=tax.revision_id,
                    name_snapshot=tax.name,
                    rate_snapshot=tax.rate_percent,
                    amount=amount,
                )
            )
    if selected:
        parent = db.get(DiscountRule, selected.rule_id)
        parent.uses_count += 1  # choose_discount retains this parent lock until commit.
        db.add(
            DiscountRedemption(
                discount_rule_id=selected.rule_id,
                invoice_id=invoice.id,
                amount=result.discount_total,
            )
        )
    return invoice


def _issue_transaction(db_factory, subscription_id, cycle_index, as_of, actor):
    with db_factory() as db, db.begin():
        subscription = _lock_subscription(db, subscription_id)
        existing = _existing_outcome(db, subscription, cycle_index)
        if existing is not None:
            return existing
        if cycle_index < subscription.next_cycle_index:
            raise DomainError("PERIOD_OUTCOME_MISSING", "A prior billing period needs review.")
        if cycle_index > subscription.next_cycle_index:
            raise DomainError("INVALID_CYCLE", "Only the next unprocessed cycle can be billed.")
        bounds = _bounds(subscription, cycle_index)
        if subscription.state != "ACTIVE" or bounds is None or bounds[0] > as_of:
            return PeriodOutcome("NOT_DUE")
        dto = _inputs_service()
        inputs = dto.get_billable_inputs(db, subscription_id, cycle_index)
        if (inputs.period_start, inputs.period_end) != bounds:
            raise DomainError("INVALID_BILLABLE_INPUTS", "Billing period bounds do not agree.")
        period = BillingPeriod(
            id=uuid4(),
            subscription_id=subscription_id,
            cycle_index=cycle_index,
            period_start=inputs.period_start,
            period_end=inputs.period_end,
            disposition="PAUSED" if inputs.paused else "INVOICED",
            explanation="Scheduled pause" if inputs.paused else "Recurring invoice",
        )
        db.add(period)
        db.flush()
        invoice = None if inputs.paused else _persist_invoice(db, subscription, period, inputs, dto)
        subscription.next_cycle_index = cycle_index + 1
        db.add(
            AuditEvent(
                actor_user_id=actor.id if actor else None,
                entity_type="billing_period",
                entity_id=period.id,
                action=period.disposition,
                redacted_details={
                    "subscription_id": str(subscription_id),
                    "cycle_index": cycle_index,
                },
            )
        )
        db.flush()
        return PeriodOutcome(period.disposition, period.id, invoice.id if invoice else None)


def issue_due_period(db_factory, subscription_id: UUID, cycle_index: int, as_of: date, actor=None):
    """Issue or replay one period; any failed insert rolls back before recovery."""
    if type(cycle_index) is not int or cycle_index < 0 or type(as_of) is not date:
        raise ValueError("A nonnegative cycle index and service date are required")
    if actor is not None and actor.role not in (Role.ADMIN, Role.STAFF):
        raise DomainError("FORBIDDEN", "Your role cannot run billing.", 403)
    try:
        return _issue_transaction(db_factory, subscription_id, cycle_index, as_of, actor)
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) != "23505":
            raise
        # Context managers have rolled back and closed the failed transaction.
        with db_factory() as db, db.begin():
            subscription = _lock_subscription(db, subscription_id)
            existing = _existing_outcome(db, subscription, cycle_index)
            if existing is None:
                raise
            return existing


def _read_cursor(db_factory):
    with db_factory() as db:
        details = db.scalar(
            select(AuditEvent.redacted_details)
            .where(AuditEvent.entity_id == BATCH_ENTITY, AuditEvent.action == "BATCH_COMPLETED")
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )
    if not isinstance(details, dict) or not details.get("continuation_after"):
        return None
    try:
        return UUID(details["continuation_after"])
    except (TypeError, ValueError):
        logger.warning("Ignoring malformed billing batch continuation metadata")
        return None


def _candidates(db_factory, as_of, cursor=None):
    # Resume after the previous bounded batch, then wrap once. A broken low-ID
    # subscription cannot consume every later tick's entire attempt budget.
    ranges = ((cursor, None), (None, cursor)) if cursor is not None else ((None, None),)
    for lower, upper in ranges:
        after = lower
        while True:
            with db_factory() as db:
                query = (
                    select(Subscription)
                    .where(Subscription.state == "ACTIVE", Subscription.start_date <= as_of)
                    .order_by(Subscription.id)
                    .limit(200)
                )
                if after is not None:
                    query = query.where(Subscription.id > after)
                if upper is not None:
                    query = query.where(Subscription.id <= upper)
                rows = db.scalars(query).all()
                for row in rows:
                    db.expunge(row)
            if not rows:
                break
            yield from rows
            after = rows[-1].id


def run_due(db_factory, as_of: date, limit: int, *, actor: Actor | None = None) -> BillingRunResult:
    """Bounded catch-up over original schedules, with safe per-subscription failures."""
    if type(as_of) is not date or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Billing requires a service date and a limit between 1 and 1000")
    if actor is not None and actor.role not in (Role.ADMIN, Role.STAFF):
        raise DomainError("FORBIDDEN", "Your role cannot run billing.", 403)
    _inputs_service()  # Do not return fake zero-work success before the getter is integrated.
    processed = created = paused = existing = attempts = 0
    failures = []
    failed_ids = set()
    last_attempted = None
    for subscription in _candidates(db_factory, as_of, _read_cursor(db_factory)):
        index = subscription.next_cycle_index
        try:
            while attempts < limit:
                bounds = _bounds(subscription, index)
                if bounds is None or bounds[0] > as_of:
                    break
                last_attempted = subscription.id
                outcome = issue_due_period(db_factory, subscription.id, index, as_of, actor)
                attempts += 1
                if outcome.disposition == "NOT_DUE":
                    break
                processed += 1
                created += outcome.disposition == "INVOICED"
                paused += outcome.disposition == "PAUSED"
                existing += outcome.disposition == "EXISTING"
                index += 1
        except (DomainError, ValueError, SQLAlchemyError) as error:
            attempts += 1
            last_attempted = subscription.id
            code = error.code if isinstance(error, DomainError) else "BILLING_FAILED"
            failures.append(BillingFailure(str(subscription.id), code))
            failed_ids.add(subscription.id)
            logger.warning("Billing failed for subscription %s (%s)", subscription.id, code)
        if attempts >= limit:
            break
    has_more = False
    for subscription in _candidates(db_factory, as_of):
        if subscription.id in failed_ids:
            has_more = True
            break
        try:
            bounds = _bounds(subscription, subscription.next_cycle_index)
            if bounds is not None and bounds[0] <= as_of:
                has_more = True
                break
        except DomainError:
            has_more = True
            break
    result = BillingRunResult(
        processed, created, paused, existing, len(failures), has_more, tuple(failures)
    )
    if last_attempted is not None:
        with db_factory() as db, db.begin():
            db.add(
                AuditEvent(
                    actor_user_id=actor.id if actor else None,
                    entity_type="billing_batch",
                    entity_id=BATCH_ENTITY,
                    action="BATCH_COMPLETED",
                    redacted_details={
                        "continuation_after": str(last_attempted),
                        "attempted_periods": attempts,
                        "processed_periods": processed,
                        "failed_subscription_count": len(failures),
                        "has_more_due": has_more,
                    },
                )
            )
    return result
