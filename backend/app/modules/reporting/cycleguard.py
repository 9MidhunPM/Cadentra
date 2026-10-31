"""Read-only operational alerts projected from committed billing records."""

from datetime import UTC, date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import Date, func, select
from sqlalchemy.orm import Session

from app.core.auth import Actor, Role
from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.money import money_string
from app.models import BillingPeriod, EmailOutbox, Invoice, Payment, Subscription, SubscriptionPause
from app.modules.subscriptions.calendar import CycleSnapshot, get_cycle_bounds

AlertKind = Literal["OVERDUE", "BILLING_DUE", "EMAIL_FAILED"]
_BATCH_SIZE = 500
_ERROR_CODES = {
    "InvalidPayload": "INVALID_CONTENT",
    "SMTPAuthenticationError": "SMTP_AUTH",
    "SMTPRecipientsRefused": "SMTP_RECIPIENT",
    "SMTPSenderRefused": "SMTP_SENDER",
    "SMTPConnectError": "SMTP_CONNECTION",
    "SMTPServerDisconnected": "SMTP_CONNECTION",
    "ConnectionRefusedError": "SMTP_CONNECTION",
    "TimeoutError": "SMTP_CONNECTION",
    "gaierror": "SMTP_CONNECTION",
    "SSLError": "SMTP_CONNECTION",
    "OSError": "SMTP_CONNECTION",
    "SMTPDataError": "SMTP_DELIVERY",
    "SMTPHeloError": "SMTP_DELIVERY",
    "SMTPNotSupportedError": "SMTP_DELIVERY",
    "SMTPResponseException": "SMTP_DELIVERY",
    "SMTPException": "SMTP_DELIVERY",
}


def _item(kind, source_id, record_id, record_type, label, reason, occurred_on, **extra):
    return {
        "id": f"{kind}:{source_id}",
        "kind": kind,
        "record_id": str(record_id),
        "record_type": record_type,
        "label": label,
        "reason": reason,
        "occurred_on": occurred_on.isoformat(),
        "amount": None,
        "currency": None,
        "attempts": None,
        "next_attempt_at": None,
        "error_code": None,
        **extra,
    }


def _overdue(db, today, customer_id, offset, page_size):
    payments = (
        select(Payment.invoice_id, func.sum(Payment.amount).label("paid"))
        .group_by(Payment.invoice_id)
        .subquery()
    )
    balance = Invoice.total - func.coalesce(payments.c.paid, Decimal("0.00"))
    query = (
        select(Invoice.id, Invoice.number, Invoice.due_date, balance.label("balance"))
        .outerjoin(payments, payments.c.invoice_id == Invoice.id)
        .where(Invoice.status == "CONFIRMED", Invoice.due_date < today, balance > 0)
    )
    if customer_id is not None:
        query = query.where(Invoice.customer_id == customer_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(Invoice.due_date, Invoice.id).offset(offset).limit(page_size))
    return [
        _item(
            "OVERDUE",
            row.id,
            row.id,
            "invoice",
            row.number,
            "Confirmed invoice has an unpaid balance after its due date.",
            row.due_date,
            amount=money_string(row.balance),
            currency="INR",
        )
        for row in rows
    ], total


def _billing_due(db, today, customer_id, offset, page_size):
    # Only the next original period is inspected. Durable outcomes, including
    # PAUSED ones, are not gaps even if a stale cursor still points at them.
    outcome = (
        select(BillingPeriod.id)
        .where(
            BillingPeriod.subscription_id == Subscription.id,
            BillingPeriod.cycle_index == Subscription.next_cycle_index,
        )
        .exists()
    )
    query = select(
        Subscription.id,
        Subscription.number,
        Subscription.start_date,
        Subscription.end_date,
        Subscription.close_effective_on,
        Subscription.next_cycle_index,
        Subscription.plan_snapshot["cadence"].as_string().label("cadence"),
    ).where(Subscription.state == "ACTIVE", Subscription.start_date <= today, ~outcome)
    if customer_id is not None:
        query = query.where(Subscription.customer_id == customer_id)
    alerts = []
    after = None
    while True:
        batch_query = query.where(Subscription.id > after) if after is not None else query
        rows = db.execute(batch_query.order_by(Subscription.id).limit(_BATCH_SIZE)).all()
        if not rows:
            break
        due = []
        for row in rows:
            try:
                bounds = get_cycle_bounds(
                    CycleSnapshot(
                        row.start_date, row.end_date, row.cadence, row.close_effective_on
                    ),
                    row.next_cycle_index,
                )
            except (TypeError, ValueError) as error:
                raise DomainError(
                    "INVALID_SCHEDULE", "Subscription schedule requires review.", 409
                ) from error
            if bounds is not None and bounds[0] <= today:
                due.append((row, bounds[0]))
        pauses = {}
        if due:
            for pause in db.execute(
                select(
                    SubscriptionPause.subscription_id,
                    SubscriptionPause.starts_on,
                    SubscriptionPause.ends_on,
                ).where(SubscriptionPause.subscription_id.in_([row.id for row, _ in due]))
            ):
                pauses.setdefault(pause.subscription_id, []).append(pause)
        for row, period_start in due:
            paused = any(
                pause.starts_on <= period_start
                and (pause.ends_on is None or period_start < pause.ends_on)
                for pause in pauses.get(row.id, ())
            )
            reason = (
                "Paused period awaits processing to record its outcome; no invoice is expected."
                if paused
                else "Scheduled billing period is due and has no recorded outcome."
            )
            alerts.append(
                _item(
                    "BILLING_DUE", row.id, row.id, "subscription", row.number, reason, period_start
                )
            )
        after = rows[-1].id
        if len(rows) < _BATCH_SIZE:
            break
    alerts.sort(key=lambda item: (item["occurred_on"], item["id"]))
    return alerts[offset : offset + page_size], len(alerts)


def _email_failed(db, customer_id, offset, page_size):
    # Never load recipient, subject or payload. In particular, reset messages
    # cannot reach this projection even when their aggregate ID matches an invoice.
    occurred_on = func.timezone(get_settings().business_timezone, EmailOutbox.created_at).cast(Date)
    query = (
        select(
            EmailOutbox.id,
            occurred_on.label("occurred_on"),
            EmailOutbox.attempts,
            EmailOutbox.next_attempt_at,
            EmailOutbox.last_error,
            Invoice.id.label("invoice_id"),
            Invoice.number,
        )
        .join(Invoice, Invoice.id == EmailOutbox.aggregate_id)
        .where(EmailOutbox.kind == "INVOICE", EmailOutbox.status == "FAILED")
    )
    if customer_id is not None:
        query = query.where(Invoice.customer_id == customer_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(occurred_on, EmailOutbox.id).offset(offset).limit(page_size))
    return [
        _item(
            "EMAIL_FAILED",
            row.id,
            row.invoice_id,
            "invoice",
            row.number,
            "Invoice email was not accepted by SMTP; its queued retry needs attention.",
            row.occurred_on,
            attempts=row.attempts,
            next_attempt_at=row.next_attempt_at.astimezone(UTC).isoformat(),
            error_code=_ERROR_CODES.get(row.last_error, "DELIVERY_FAILED"),
        )
        for row in rows
    ], total


def list_alerts(
    db: Session,
    actor: Actor,
    kind: AlertKind = "OVERDUE",
    customer_id: UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    if actor.role not in (Role.ADMIN, Role.STAFF):
        raise DomainError("FORBIDDEN", "Your role cannot view staff reports.", 403)
    if (
        type(page) is not int
        or page < 1
        or type(page_size) is not int
        or not 1 <= page_size <= 100
        or (page - 1) * page_size > 2**63 - 1
    ):
        raise DomainError("INVALID_PAGINATION", "Invalid pagination.", 422)
    if kind not in ("OVERDUE", "BILLING_DUE", "EMAIL_FAILED"):
        raise DomainError("INVALID_ALERT_KIND", "Choose a supported alert kind.", 422)
    today: date = get_clock().today()
    offset = (page - 1) * page_size
    # A reporting GET must never flush pending ORM objects as a side effect.
    with db.no_autoflush:
        if kind == "OVERDUE":
            items, total = _overdue(db, today, customer_id, offset, page_size)
        elif kind == "BILLING_DUE":
            items, total = _billing_due(db, today, customer_id, offset, page_size)
        else:
            items, total = _email_failed(db, customer_id, offset, page_size)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "as_of": today.isoformat(),
    }
