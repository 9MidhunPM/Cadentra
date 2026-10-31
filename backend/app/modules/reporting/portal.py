"""Read-only customer portal routes. Customer selection always comes from authentication."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import Actor, Role, require_role
from app.core.errors import DomainError
from app.db.session import get_session
from app.modules.reporting import portal_service


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
def get_subscription(subscription_id: UUID, actor: CustomerActor, db: Database):
    return {"data": portal_service.subscription_detail(db, actor, subscription_id)}


@router.get("/invoices")
def get_invoices(actor: CustomerActor, db: Database, page: Page = 1, page_size: PageSize = 25):
    return portal_service.invoices(db, actor, page, page_size)
