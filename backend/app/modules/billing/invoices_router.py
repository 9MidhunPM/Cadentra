"""Staff invoice operations; portal routes reuse actor-aware service helpers."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_role
from app.db.session import get_session

from . import invoices
from .invoice_schemas import CancelInvoice, Input, PaymentWrite, SendInvoice

router = APIRouter(tags=["invoices"])
Database = Annotated[Session, Depends(get_session)]
Operator = Annotated[Actor, Depends(require_role("ADMIN", "STAFF"))]
_EMPTY_CONFIRM = Input()


@router.get("/invoices")
def invoice_list(
    actor: Operator,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    customer_id: UUID | None = None,
    status: Literal["DRAFT", "CONFIRMED", "PAID", "CANCELLED"] | None = None,
    overdue: bool | None = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
):
    return invoices.list_invoices(
        db,
        actor,
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        status=status,
        overdue=overdue,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/invoices/{invoice_id}")
def detail(invoice_id: UUID, actor: Operator, db: Database):
    return {"data": invoices.get_invoice_for_actor(db, actor, invoice_id)}


@router.post("/invoices/{invoice_id}/confirm")
def confirm(
    invoice_id: UUID,
    actor: Operator,
    db: Database,
    payload: Annotated[Input, Body()] = _EMPTY_CONFIRM,
):
    return {"data": invoices.confirm_invoice(db, actor, invoice_id)}


@router.post("/invoices/{invoice_id}/cancel")
def cancel(invoice_id: UUID, payload: CancelInvoice, actor: Operator, db: Database):
    return {"data": invoices.cancel_invoice(db, actor, invoice_id, payload.reason)}


@router.post("/invoices/{invoice_id}/payments", status_code=201)
def pay(invoice_id: UUID, payload: PaymentWrite, actor: Operator, db: Database, response: Response):
    result, replay = invoices.record_payment(db, actor, invoice_id, payload)
    if replay:
        response.status_code = 200
    return {"data": result}


@router.get("/invoices/{invoice_id}/payments")
def payments(
    invoice_id: UUID,
    actor: Operator,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    return invoices.list_invoice_payments(db, actor, invoice_id, page=page, page_size=page_size)


@router.post("/invoices/{invoice_id}/send", status_code=202)
def send(invoice_id: UUID, payload: SendInvoice, actor: Operator, db: Database):
    return {"data": invoices.send_invoice(db, actor, invoice_id, payload.request_key)}


@router.get("/invoices/{invoice_id}/print", response_class=HTMLResponse)
def printable(invoice_id: UUID, actor: Operator, db: Database):
    return HTMLResponse(
        invoices.render_invoice_for_actor(db, actor, invoice_id),
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )
