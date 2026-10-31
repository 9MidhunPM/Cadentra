"""Customer-scoped read projections; lifecycle and invoice detail stay with their owners."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Actor, Role
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.core.money import money_string
from app.models import (
    BillingPeriod,
    Customer,
    Invoice,
    Payment,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
)


def customer_scope(actor: Actor) -> UUID:
    if actor.role != Role.CUSTOMER or actor.customer_id is None:
        raise DomainError("FORBIDDEN", "A customer account is required.", 403)
    return actor.customer_id


def _page(query, db: Session, page: int, page_size: int):
    offset = (page - 1) * page_size
    if page < 1 or page_size < 1 or page_size > 100 or offset > 2**63 - 1:
        raise DomainError("VALIDATION_ERROR", "Invalid pagination.", 422)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = db.execute(query.offset(offset).limit(page_size)).all()
    return rows, {"total": total, "page": page, "page_size": page_size}


def profile(db: Session, actor: Actor) -> dict:
    customer = db.scalar(select(Customer).where(Customer.id == customer_scope(actor)))
    if customer is None:
        raise DomainError("NOT_FOUND", "Record not found.", 404)
    address = customer.billing_address if isinstance(customer.billing_address, dict) else {}
    return {
        "id": str(customer.id),
        "display_name": customer.display_name,
        "email": customer.email,
        "company_name": customer.company_name,
        "billing_address": {
            key: address[key]
            for key in ("line1", "line2", "city", "state", "postal_code", "country")
            if isinstance(address.get(key), str)
        },
    }


def _subscription_summary(row: Subscription) -> dict:
    return {
        "id": str(row.id),
        "number": row.number,
        "plan_id": str(row.plan_id),
        "state": row.state,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "currency": row.currency,
        "close_effective_on": row.close_effective_on,
        "revision": row.revision,
    }


def subscriptions(db: Session, actor: Actor, page: int, page_size: int) -> dict:
    query = (
        select(Subscription)
        .where(Subscription.customer_id == customer_scope(actor))
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
    )
    rows, metadata = _page(query, db, page, page_size)
    return {"items": [_subscription_summary(row[0]) for row in rows], **metadata}


def _public_plan(snapshot: dict) -> dict:
    """Whitelist scalar values, never forwarding arbitrary nested pricing/audit payloads."""
    if not isinstance(snapshot, dict):
        return {}
    fields = {
        "name": str,
        "base_fee": str,
        "currency": str,
        "cadence": str,
        "min_quantity": int,
        "allow_pause": bool,
        "allow_early_close": bool,
        "allow_renew": bool,
        "auto_close": bool,
    }
    return {key: snapshot[key] for key, kind in fields.items() if type(snapshot.get(key)) is kind}


def subscription_detail(db: Session, actor: Actor, subscription_id: UUID) -> dict:
    scope = customer_scope(actor)
    row = db.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id, Subscription.customer_id == scope
        )
    )
    if row is None:
        raise DomainError("NOT_FOUND", "Record not found.", 404)
    lines = db.scalars(
        select(SubscriptionLine)
        .where(SubscriptionLine.subscription_id == row.id)
        .order_by(SubscriptionLine.created_at, SubscriptionLine.id)
    )
    pauses = db.scalars(
        select(SubscriptionPause)
        .where(SubscriptionPause.subscription_id == row.id)
        .order_by(SubscriptionPause.starts_on, SubscriptionPause.id)
    )
    invoices = db.execute(
        select(Invoice.id, Invoice.number)
        .where(Invoice.subscription_id == row.id, Invoice.customer_id == scope)
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
    )
    return {
        **_subscription_summary(row),
        "payment_terms_days": row.payment_terms_days,
        "quotation_valid_until": row.quotation_valid_until,
        "plan_snapshot": _public_plan(row.plan_snapshot),
        "lines": [
            {
                "id": str(line.id),
                "product_id": str(line.product_id),
                "variant_id": str(line.variant_id) if line.variant_id else None,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": money_string(line.unit_price),
            }
            for line in lines
        ],
        "pause_intervals": [
            {"starts_on": pause.starts_on, "ends_on": pause.ends_on} for pause in pauses
        ],
        "invoices": [{"id": str(invoice.id), "number": invoice.number} for invoice in invoices],
    }


def invoices(db: Session, actor: Actor, page: int, page_size: int) -> dict:
    # Aggregate payments once per invoice before joining, so payments never fan out
    # totals or pagination. Read committed amounts; never mutate financial state.
    scope = customer_scope(actor)
    payments = (
        select(Payment.invoice_id, func.sum(Payment.amount).label("paid_amount"))
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(Invoice.customer_id == scope)
        .group_by(Payment.invoice_id)
        .subquery()
    )
    query = (
        select(
            Invoice,
            BillingPeriod.period_start,
            BillingPeriod.period_end,
            func.coalesce(payments.c.paid_amount, Decimal("0.00")),
        )
        .join(BillingPeriod, BillingPeriod.id == Invoice.billing_period_id)
        .outerjoin(payments, payments.c.invoice_id == Invoice.id)
        .where(Invoice.customer_id == scope)
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
    )
    rows, metadata = _page(query, db, page, page_size)
    today = get_clock().today()
    return {
        "items": [
            {
                "id": str(row.id),
                "number": row.number,
                "subscription_id": str(row.subscription_id),
                "status": row.status,
                "currency": row.currency,
                "invoice_date": row.invoice_date,
                "due_date": row.due_date,
                "period_start": period_start,
                "period_end": period_end,
                "total": money_string(row.total),
                "paid_amount": money_string(paid_amount),
                "balance_due": money_string(row.total - paid_amount),
                "collection_status": (
                    row.status
                    if row.status != "CONFIRMED"
                    else "PARTIALLY_PAID"
                    if paid_amount > 0
                    else "UNPAID"
                ),
                "overdue": row.status == "CONFIRMED"
                and row.total > paid_amount
                and today > row.due_date,
            }
            for row, period_start, period_end, paid_amount in rows
        ],
        **metadata,
    }
