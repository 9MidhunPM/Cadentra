"""Read-only reporting of stored invoices, payments and present service state."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.core.auth import Actor, Role
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.core.money import money_string
from app.models import Invoice, Payment, Subscription, SubscriptionPause

ZERO = Decimal("0.00")


def _validate(actor: Actor, range_from: date, range_to: date) -> None:
    if actor.role not in (Role.ADMIN, Role.STAFF):
        raise DomainError("FORBIDDEN", "Your role cannot view staff reports.", 403)
    if range_from >= range_to or (range_to - range_from).days > 366:
        raise DomainError(
            "INVALID_REPORT_RANGE", "Choose a nonempty date range of at most 366 days.", 422
        )


def summary(
    db: Session,
    actor: Actor,
    range_from: date,
    range_to: date,
    customer_id: UUID | None = None,
) -> dict:
    _validate(actor, range_from, range_to)
    today = get_clock().today()
    invoice_filter = [Invoice.customer_id == customer_id] if customer_id else []
    subscription_filter = [Subscription.customer_id == customer_id] if customer_id else []
    paused = (
        select(SubscriptionPause.id)
        .where(
            SubscriptionPause.subscription_id == Subscription.id,
            SubscriptionPause.starts_on <= today,
            SubscriptionPause.ends_on.is_(None) | (SubscriptionPause.ends_on > today),
        )
        .exists()
    )
    active = select(func.count(Subscription.id)).where(
        *subscription_filter,
        Subscription.state == "ACTIVE",
        Subscription.start_date <= today,
        Subscription.end_date > today,
        Subscription.close_effective_on.is_(None) | (Subscription.close_effective_on > today),
        ~paused,
    )
    invoiced = select(func.coalesce(func.sum(Invoice.total), ZERO)).where(
        *invoice_filter,
        Invoice.status.in_(("CONFIRMED", "PAID")),
        Invoice.invoice_date >= range_from,
        Invoice.invoice_date < range_to,
    )
    cash = (
        select(func.coalesce(func.sum(Payment.amount), ZERO))
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(*invoice_filter, Payment.paid_on >= range_from, Payment.paid_on < range_to)
    )
    paid = (
        select(Payment.invoice_id, func.sum(Payment.amount).label("paid"))
        .group_by(Payment.invoice_id)
        .subquery()
    )
    balance = Invoice.total - func.coalesce(paid.c.paid, ZERO)
    debt = (
        select(
            func.coalesce(func.sum(balance), ZERO).label("outstanding"),
            func.coalesce(func.sum(balance).filter(Invoice.due_date < today), ZERO).label(
                "overdue"
            ),
            func.count(Invoice.id).filter(Invoice.due_date < today).label("overdue_count"),
        )
        .outerjoin(paid, paid.c.invoice_id == Invoice.id)
        .where(*invoice_filter, Invoice.status == "CONFIRMED", balance > ZERO)
        .subquery()
    )
    # One PostgreSQL statement gives all metrics the same committed snapshot.
    row = db.execute(
        select(
            active.scalar_subquery().label("active"),
            invoiced.scalar_subquery().label("invoiced"),
            cash.scalar_subquery().label("cash"),
            debt.c.outstanding,
            debt.c.overdue,
            debt.c.overdue_count,
        )
    ).one()
    return {
        "as_of": today.isoformat(),
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "currency": "INR",
        "active_subscriptions": row.active,
        "invoiced_gross_in_range": money_string(row.invoiced),
        "cash_received_in_range": money_string(row.cash),
        "outstanding_now": money_string(row.outstanding),
        "overdue_now": money_string(row.overdue),
        "overdue_invoice_count": row.overdue_count,
        "metric_basis": {
            "date_range": "[from,to)",
            "invoiced": "confirmed/paid, tax-inclusive by invoice_date",
            "cash": "recorded payments by paid_on",
            "outstanding": "present confirmed unpaid balances",
            "active": "present active, in-term and unpaused",
        },
    }


def revenue_series(
    db: Session,
    actor: Actor,
    range_from: date,
    range_to: date,
    cadence: str = "DAILY",
    customer_id: UUID | None = None,
) -> dict:
    _validate(actor, range_from, range_to)
    if cadence not in ("DAILY", "MONTHLY"):
        raise DomainError("INVALID_REPORT_CADENCE", "Choose DAILY or MONTHLY reporting.", 422)
    invoice_filter = [Invoice.customer_id == customer_id] if customer_id else []
    # Independent aggregates prevent invoice totals multiplying across payment rows.
    invoiced = (
        select(
            Invoice.invoice_date.label("day"),
            func.sum(Invoice.total).label("invoiced"),
            literal(ZERO, type_=Invoice.total.type).label("cash"),
        )
        .where(
            *invoice_filter,
            Invoice.status.in_(("CONFIRMED", "PAID")),
            Invoice.invoice_date >= range_from,
            Invoice.invoice_date < range_to,
        )
        .group_by(Invoice.invoice_date)
    )
    cash = (
        select(
            Payment.paid_on.label("day"),
            literal(ZERO, type_=Invoice.total.type).label("invoiced"),
            func.sum(Payment.amount).label("cash"),
        )
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(*invoice_filter, Payment.paid_on >= range_from, Payment.paid_on < range_to)
        .group_by(Payment.paid_on)
    )
    combined = invoiced.union_all(cash).subquery()
    rows = db.execute(
        select(combined.c.day, func.sum(combined.c.invoiced), func.sum(combined.c.cash)).group_by(
            combined.c.day
        )
    )
    by_day = {day: (gross, received) for day, gross, received in rows}
    buckets = []
    current = range_from
    while current < range_to:
        days = (
            1
            if cadence == "DAILY"
            else monthrange(current.year, current.month)[1] - current.day + 1
        )
        end = current + timedelta(days=min(days, (range_to - current).days))
        gross = received = ZERO
        day = current
        while day < end:
            daily_gross, daily_received = by_day.get(day, (ZERO, ZERO))
            gross += daily_gross
            received += daily_received
            day += timedelta(days=1)
        buckets.append(
            {
                "period_start": current.isoformat(),
                "period_end": end.isoformat(),
                "invoiced_gross": money_string(gross),
                "cash_received": money_string(received),
            }
        )
        current = end
    return {
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "currency": "INR",
        "cadence": cadence,
        "buckets": buckets,
    }
