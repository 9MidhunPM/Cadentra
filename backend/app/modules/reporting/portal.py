"""Customer-scoped portal reads and delegated lifecycle actions."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.auth import Actor, Role, require_role
from app.core.errors import DomainError
from app.db.session import get_session
from app.modules.billing.service import get_invoice_for_actor, render_invoice_for_actor
from app.modules.reporting import portal_service
from app.modules.subscriptions.service import apply_action, get_subscription_for_actor


def reject_customer_selection(request: Request) -> None:
    if "customer_id" in request.query_params:
        raise DomainError(
            "VALIDATION_ERROR",
            "Customer selection is not supported in the portal.",
            422,
            {"query.customer_id": "Customer identity comes from your session."},
        )


router = APIRouter(
    prefix="/portal", tags=["portal"], dependencies=[Depends(reject_customer_selection)]
)
CustomerActor = Annotated[Actor, Depends(require_role(Role.CUSTOMER))]
Database = Annotated[Session, Depends(get_session)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/me")
def get_profile(actor: CustomerActor, db: Database):
    return {"data": portal_service.profile(db, actor)}


@router.get("/subscriptions")
def get_subscriptions(actor: CustomerActor, db: Database, page: Page = 1, page_size: PageSize = 25):
    return portal_service.subscriptions(db, actor, page, page_size)


@router.get("/subscriptions/{subscription_id}")
def get_subscription(subscription_id: UUID, actor: CustomerActor, db: Database, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return {"data": get_subscription_for_actor(db, actor, subscription_id)}


@router.get("/invoices")
def get_invoices(actor: CustomerActor, db: Database, page: Page = 1, page_size: PageSize = 25):
    return portal_service.invoices(db, actor, page, page_size)


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: UUID, actor: CustomerActor, db: Database, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return {"data": get_invoice_for_actor(db, actor, invoice_id)}


@router.get("/invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_invoice(invoice_id: UUID, actor: CustomerActor, db: Database):
    return HTMLResponse(
        render_invoice_for_actor(db, actor, invoice_id),
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _subscription_action(
    db: Session, actor: Actor, subscription_id: UUID, action: str, payload: Any
):
    # The owner validates ownership before payload semantics and acquires the row
    # lock. Begin before calling it: its first lookup starts the transaction.
    with db.begin():
        result = apply_action(db, actor, subscription_id, action, payload)
    return {"data": result}


@router.post("/subscriptions/{subscription_id}/pause")
def pause_subscription(
    subscription_id: UUID,
    actor: CustomerActor,
    db: Database,
    payload: Annotated[Any, Body()] = None,
):
    return _subscription_action(db, actor, subscription_id, "pause", payload)


@router.post("/subscriptions/{subscription_id}/resume")
def resume_subscription(
    subscription_id: UUID,
    actor: CustomerActor,
    db: Database,
    payload: Annotated[Any, Body()] = None,
):
    return _subscription_action(db, actor, subscription_id, "resume", payload)


@router.post("/subscriptions/{subscription_id}/close")
def close_subscription(
    subscription_id: UUID,
    actor: CustomerActor,
    db: Database,
    payload: Annotated[Any, Body()] = None,
):
    return _subscription_action(db, actor, subscription_id, "close", payload)


@router.post("/subscriptions/{subscription_id}/renew")
def renew_subscription(
    subscription_id: UUID,
    actor: CustomerActor,
    db: Database,
    payload: Annotated[Any, Body()] = None,
):
    return _subscription_action(db, actor, subscription_id, "renew", payload)
