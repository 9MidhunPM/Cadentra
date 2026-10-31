"""Actor-aware invoice reads and row-locked financial operations."""

import json
from hashlib import sha256
from html import escape
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_customer_ownership
from app.core.clock import get_clock
from app.core.errors import DomainError
from app.core.money import money, money_string
from app.models import (
    AuditEvent,
    BillingPeriod,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    Payment,
)

from .invoice_schemas import PaymentWrite


def _operator(actor: Actor) -> None:
    if actor.role not in {"ADMIN", "STAFF"}:
        raise DomainError("FORBIDDEN", "Your role cannot perform this action.", 403)


def _invoice(db: Session, actor: Actor, invoice_id: UUID, *, lock=False) -> Invoice:
    if actor.role not in {"ADMIN", "STAFF", "CUSTOMER"}:
        raise DomainError("FORBIDDEN", "Your role cannot read invoices.", 403)
    query = select(Invoice).where(Invoice.id == invoice_id)
    if actor.role == "CUSTOMER":
        query = query.where(Invoice.customer_id == actor.customer_id)
    if lock:
        query = query.with_for_update()
    invoice = db.scalar(query)
    if invoice is None:
        raise DomainError("NOT_FOUND", "Invoice not found.", 404)
    require_customer_ownership(actor, invoice.customer_id)
    return invoice


def _audit(db, actor, invoice, action, details=None):
    db.add(
        AuditEvent(
            actor_user_id=actor.id,
            entity_type="INVOICE",
            entity_id=invoice.id,
            action=action,
            redacted_details=details or {},
        )
    )


def _paid(db, invoice_id):
    return money(
        db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.invoice_id == invoice_id
            )
        )
    )


def _payment_data(row, *, staff=True):
    result = {
        "id": str(row.id),
        "invoice_id": str(row.invoice_id),
        "method": row.method,
        "amount": money_string(row.amount),
        "paid_on": row.paid_on.isoformat(),
    }
    if staff:
        result.update(
            note=row.note, external_reference=row.external_reference, request_key=row.request_key
        )
    return result


def _safe_snapshot(value):
    """Never expose imported internal cost or staff-note fields in explanations."""
    if isinstance(value, dict):
        return {
            key: _safe_snapshot(item)
            for key, item in value.items()
            if "cost" not in key.lower()
            and "note" not in key.lower()
            and not key.lower().startswith(("internal", "private", "staff"))
        }
    if isinstance(value, list):
        return [_safe_snapshot(item) for item in value]
    return value


def _summary(invoice, period, paid):
    balance = money(invoice.total - paid)
    overdue = (
        invoice.status == "CONFIRMED" and balance > 0 and get_clock().today() > invoice.due_date
    )
    collection = (
        "PARTIALLY_PAID"
        if invoice.status == "CONFIRMED" and paid > 0
        else "UNPAID"
        if invoice.status == "CONFIRMED"
        else invoice.status
    )
    return {
        "id": str(invoice.id),
        "number": invoice.number,
        "subscription_id": str(invoice.subscription_id),
        "customer_id": str(invoice.customer_id),
        "customer_snapshot": {"display_name": invoice.customer_snapshot.get("display_name", "")},
        "status": invoice.status,
        "collection_status": collection,
        "currency": invoice.currency,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "subtotal": money_string(invoice.subtotal),
        "discount_total": money_string(invoice.discount_total),
        "tax_total": money_string(invoice.tax_total),
        "total": money_string(invoice.total),
        "paid_amount": money_string(paid),
        "balance_due": money_string(balance),
        "overdue": overdue,
    }


def get_invoice_for_actor(db: Session, actor: Actor, invoice_id: UUID) -> dict:
    invoice = _invoice(db, actor, invoice_id)
    period = db.get(BillingPeriod, invoice.billing_period_id)
    result = _summary(invoice, period, _paid(db, invoice.id))
    result["customer_snapshot"] = {
        key: invoice.customer_snapshot[key]
        for key in ("display_name", "email", "company_name", "billing_address")
        if key in invoice.customer_snapshot
    }
    result["seller_snapshot"] = {
        key: invoice.seller_snapshot[key]
        for key in ("name", "address", "billing_address")
        if key in invoice.seller_snapshot
    }
    lines = db.scalars(
        select(InvoiceLine)
        .where(InvoiceLine.invoice_id == invoice.id)
        .order_by(InvoiceLine.stable_line_key)
    ).all()
    taxes = db.scalars(
        select(InvoiceLineTax)
        .join(InvoiceLine, InvoiceLine.id == InvoiceLineTax.invoice_line_id)
        .where(InvoiceLine.invoice_id == invoice.id)
        .order_by(InvoiceLineTax.id)
    ).all()
    grouped = {}
    for tax in taxes:
        grouped.setdefault(tax.invoice_line_id, []).append(
            {
                "name": tax.name_snapshot,
                "rate_percent": format(tax.rate_snapshot, ".4f"),
                "amount": money_string(tax.amount),
            }
        )
    result["lines"] = [
        {
            "id": str(line.id),
            "stable_line_key": line.stable_line_key,
            "description": line.description,
            "product_id": str(line.product_id) if line.product_id else None,
            "variant_id": str(line.variant_id) if line.variant_id else None,
            "quantity": line.quantity,
            **{
                field: money_string(getattr(line, field))
                for field in (
                    "unit_price",
                    "gross",
                    "discount",
                    "taxable_amount",
                    "tax_total",
                    "total",
                )
            },
            "taxes": grouped.get(line.id, []),
        }
        for line in lines
    ]
    payments = db.scalars(
        select(Payment)
        .where(Payment.invoice_id == invoice.id)
        .order_by(Payment.created_at, Payment.id)
    ).all()
    result["payments"] = [_payment_data(row, staff=actor.role != "CUSTOMER") for row in payments]
    outbox = db.scalar(
        select(EmailOutbox)
        .where(EmailOutbox.kind == "INVOICE", EmailOutbox.aggregate_id == invoice.id)
        .order_by(EmailOutbox.created_at.desc(), EmailOutbox.id.desc())
        .limit(1)
    )
    result["email_status"] = outbox.status if outbox else "NOT_REQUESTED"
    result["calculation_snapshot"] = _safe_snapshot(invoice.calculation_snapshot)
    if actor.role != "CUSTOMER":
        result["cancellation_reason"] = invoice.cancellation_reason
    return result


def list_invoices(
    db,
    actor,
    *,
    page=1,
    page_size=25,
    customer_id=None,
    status=None,
    overdue=None,
    from_date=None,
    to_date=None,
):
    if actor.role not in {"ADMIN", "STAFF", "CUSTOMER"}:
        raise DomainError("FORBIDDEN", "Your role cannot read invoices.", 403)
    if actor.role == "CUSTOMER" and customer_id is not None:
        raise DomainError("FORBIDDEN", "Customer filters are unavailable in the portal.", 403)
    if not 1 <= page_size <= 100 or page < 1 or (from_date and to_date and from_date >= to_date):
        raise DomainError("INVALID_FILTER", "Check pagination and date range.", 422)
    if status is not None and status not in {"DRAFT", "CONFIRMED", "PAID", "CANCELLED"}:
        raise DomainError("INVALID_FILTER", "Unknown invoice status.", 422)
    totals = (
        select(Payment.invoice_id, func.sum(Payment.amount).label("paid"))
        .group_by(Payment.invoice_id)
        .subquery()
    )
    paid = func.coalesce(totals.c.paid, 0)
    query = (
        select(Invoice, BillingPeriod, paid)
        .join(BillingPeriod, BillingPeriod.id == Invoice.billing_period_id)
        .outerjoin(totals, totals.c.invoice_id == Invoice.id)
    )
    if actor.role == "CUSTOMER":
        query = query.where(Invoice.customer_id == actor.customer_id)
    if customer_id is not None:
        query = query.where(Invoice.customer_id == customer_id)
    if status:
        query = query.where(Invoice.status == status)
    if from_date:
        query = query.where(Invoice.invoice_date >= from_date)
    if to_date:
        query = query.where(Invoice.invoice_date < to_date)
    overdue_clause = (
        (Invoice.status == "CONFIRMED")
        & (Invoice.due_date < get_clock().today())
        & (Invoice.total > paid)
    )
    if overdue is not None:
        query = query.where(overdue_clause if overdue else ~overdue_clause)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_summary(invoice, period, money(amount)) for invoice, period, amount in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_invoice_payments(db, actor, invoice_id, *, page=1, page_size=25):
    invoice = _invoice(db, actor, invoice_id)
    if page < 1 or not 1 <= page_size <= 100:
        raise DomainError("INVALID_FILTER", "Check pagination.", 422)
    query = select(Payment).where(Payment.invoice_id == invoice.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Payment.created_at.desc(), Payment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_payment_data(row, staff=actor.role != "CUSTOMER") for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def confirm_invoice(db, actor, invoice_id):
    _operator(actor)
    with db.begin():
        invoice = _invoice(db, actor, invoice_id, lock=True)
        if invoice.status == "DRAFT":
            invoice.status = "PAID" if invoice.total == 0 else "CONFIRMED"
            invoice.confirmed_at = get_clock().now()
            _audit(db, actor, invoice, "CONFIRMED")
            db.flush()
        elif invoice.status not in {"CONFIRMED", "PAID"}:
            raise DomainError("INVALID_TRANSITION", "Cancelled invoices cannot be confirmed.")
        return get_invoice_for_actor(db, actor, invoice_id)


def cancel_invoice(db, actor, invoice_id, reason):
    _operator(actor)
    if not isinstance(reason, str) or not reason.strip():
        raise DomainError("INVALID_REASON", "A cancellation reason is required.", 422)
    with db.begin():
        invoice = _invoice(db, actor, invoice_id, lock=True)
        if invoice.status not in {"DRAFT", "CONFIRMED"} or _paid(db, invoice.id) > 0:
            raise DomainError(
                "INVALID_TRANSITION", "Only unpaid draft or confirmed invoices may be cancelled."
            )
        invoice.status = "CANCELLED"
        invoice.cancelled_at = get_clock().now()
        invoice.cancellation_reason = reason.strip()
        _audit(db, actor, invoice, "CANCELLED")
        db.flush()
        return get_invoice_for_actor(db, actor, invoice_id)


def record_payment(db, actor, invoice_id, payload: PaymentWrite):
    _operator(actor)
    normalized = {
        "method": payload.method,
        "amount": money_string(payload.amount),
        "paid_on": payload.paid_on.isoformat(),
        "note": payload.note,
        "external_reference": payload.external_reference,
    }
    digest = sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with db.begin():
        invoice = _invoice(db, actor, invoice_id, lock=True)
        previous = db.scalar(
            select(Payment).where(
                Payment.invoice_id == invoice.id, Payment.request_key == payload.request_key
            )
        )
        if previous:
            if previous.request_payload_hash != digest:
                raise DomainError(
                    "IDEMPOTENCY_CONFLICT", "This request key was used for a different payment."
                )
            return _payment_data(previous), True
        if payload.paid_on > get_clock().today():
            raise DomainError("INVALID_PAYMENT_DATE", "Payment date cannot be in the future.", 422)
        if invoice.status != "CONFIRMED":
            raise DomainError("INVALID_TRANSITION", "Payments require a confirmed invoice.")
        remaining = money(invoice.total - _paid(db, invoice.id))
        if payload.amount > remaining:
            raise DomainError("OVERPAYMENT", "Payment exceeds the remaining balance.")
        payment = Payment(
            invoice_id=invoice.id,
            created_by=actor.id,
            request_payload_hash=digest,
            **payload.model_dump(),
        )
        db.add(payment)
        if payload.amount == remaining:
            invoice.status = "PAID"
        _audit(db, actor, invoice, "PAYMENT_RECORDED", {"amount": money_string(payload.amount)})
        db.flush()
        return _payment_data(payment), False


def _render(detail):
    def e(value):
        return escape(str(value), quote=True)

    rows = "".join(
        f"<tr><td>{e(line['description'])}</td><td>{line['quantity']}</td><td>{e(line['unit_price'])}</td><td>{e(line['discount'])}</td><td>{e(line['tax_total'])}</td><td>{e(line['total'])}</td></tr>"
        for line in detail["lines"]
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Invoice '
        + e(detail["number"])
        + "</title><style>body{font:16px sans-serif;max-width:960px;margin:32px auto;padding:16px;color:#111}table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #bbb;text-align:left}@media print{body{margin:0}}</style></head><body><h1>Invoice "
        + e(detail["number"])
        + "</h1><p>"
        + e(detail["seller_snapshot"].get("name", ""))
        + "</p><p>Customer: "
        + e(detail["customer_snapshot"].get("display_name", ""))
        + "</p><p>Issued "
        + e(detail["invoice_date"])
        + "; due "
        + e(detail["due_date"])
        + "</p><p>Service ["
        + e(detail["period_start"])
        + ", "
        + e(detail["period_end"])
        + ")</p><p>Status: "
        + e(detail["status"])
        + "</p><table><thead><tr><th>Description</th><th>Quantity</th><th>Unit price</th><th>Discount</th><th>Tax</th><th>Total</th></tr></thead><tbody>"
        + rows
        + "</tbody></table><p>"
        + e(detail["currency"])
        + " subtotal "
        + e(detail["subtotal"])
        + "; discount "
        + e(detail["discount_total"])
        + "; tax "
        + e(detail["tax_total"])
        + "</p><p>Total "
        + e(detail["total"])
        + "; paid "
        + e(detail["paid_amount"])
        + "; balance "
        + e(detail["balance_due"])
        + "</p></body></html>"
    )


def render_invoice_for_actor(db, actor, invoice_id):
    return _render(get_invoice_for_actor(db, actor, invoice_id))


def send_invoice(db, actor, invoice_id, request_key):
    _operator(actor)
    with db.begin():
        invoice = _invoice(db, actor, invoice_id, lock=True)
        dedupe = f"INVOICE:{invoice.id}:{request_key}"
        existing = db.scalar(select(EmailOutbox).where(EmailOutbox.dedupe_key == dedupe))
        if existing:
            return {
                "outbox_id": str(existing.id),
                "status": existing.status,
                "email_status": existing.status,
            }
        if invoice.status not in {"CONFIRMED", "PAID"}:
            raise DomainError("INVALID_TRANSITION", "Confirm the invoice before sending it.")
        detail = get_invoice_for_actor(db, actor, invoice_id)
        recipient = detail["customer_snapshot"].get("email")
        if not isinstance(recipient, str) or not recipient.strip():
            raise DomainError("INVALID_RECIPIENT", "Invoice has no customer email.", 422)
        outbox = EmailOutbox(
            kind="INVOICE",
            aggregate_id=invoice.id,
            recipient=recipient,
            subject=f"Invoice {invoice.number}",
            payload={
                "html": _render(detail),
                "text": f"Invoice {invoice.number}: {invoice.currency} {money_string(invoice.total)}; due {invoice.due_date.isoformat()}.",
            },
            dedupe_key=dedupe,
        )
        db.add(outbox)
        _audit(db, actor, invoice, "EMAIL_QUEUED")
        db.flush()
        return {"outbox_id": str(outbox.id), "status": outbox.status, "email_status": outbox.status}
