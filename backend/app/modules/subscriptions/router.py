"""Staff subscription routes using shared authentication and explicit transactions."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_role
from app.db.session import get_session

from . import queries, schemas, workflows

router = APIRouter(tags=["subscriptions"])
Database = Annotated[Session, Depends(get_session)]
Operator = Annotated[Actor, Depends(require_role("ADMIN", "STAFF"))]
State = Literal["DRAFT", "QUOTATION", "CONFIRMED", "ACTIVE", "CLOSED"]


@router.get("/quotation-templates")
def templates(
    actor: Operator,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    return queries.list_templates(db, actor, page, page_size)


@router.post("/quotation-templates", status_code=201)
def create_template(payload: schemas.TemplateWrite, actor: Operator, db: Database):
    with db.begin():
        row = workflows.create_template(db, actor, payload.model_dump(exclude_unset=True))
        result = queries.template_data(db, row)
    return {"data": result}


@router.patch("/quotation-templates/{template_id}")
def edit_template(template_id: UUID, payload: schemas.TemplatePatch, actor: Operator, db: Database):
    with db.begin():
        row = workflows.edit_template(
            db, actor, template_id, payload.model_dump(exclude_unset=True)
        )
        result = queries.template_data(db, row)
    return {"data": result}


@router.get("/subscriptions")
def subscriptions(
    actor: Operator,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    customer_id: UUID | None = None,
    state: State | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
):
    return queries.list_subscriptions(db, actor, page, page_size, customer_id, state, q)


@router.post("/subscriptions", status_code=201)
def create_subscription(payload: schemas.SubscriptionCreate, actor: Operator, db: Database):
    with db.begin():
        row = workflows.create_subscription(db, actor, payload.model_dump(exclude_unset=True))
        result = queries.subscription_data(db, actor, row)
    return {"data": result}


@router.get("/subscriptions/{subscription_id}")
def subscription_detail(subscription_id: UUID, actor: Operator, db: Database):
    return {"data": queries.get_subscription_for_actor(db, actor, subscription_id)}


@router.patch("/subscriptions/{subscription_id}")
def edit_subscription(
    subscription_id: UUID, payload: schemas.SubscriptionEdit, actor: Operator, db: Database
):
    with db.begin():
        row = workflows.edit_subscription(
            db, actor, subscription_id, payload.model_dump(exclude_unset=True)
        )
        result = queries.subscription_data(db, actor, row)
    return {"data": result}


@router.post("/subscriptions/{subscription_id}/issue-quotation")
def issue_quotation(
    subscription_id: UUID, payload: schemas.QuoteIssue, actor: Operator, db: Database
):
    with db.begin():
        row = workflows.apply_action_record(
            db, actor, subscription_id, "issue-quotation", payload.model_dump()
        )
        result = queries.subscription_data(db, actor, row)
    return {"data": result}


@router.post("/subscriptions/{subscription_id}/renew")
def renew(subscription_id: UUID, payload: schemas.Renew, actor: Operator, db: Database):
    with db.begin():
        row = workflows.apply_action_record(
            db, actor, subscription_id, "renew", payload.model_dump(exclude_unset=True)
        )
        result = queries.subscription_data(db, actor, row)
    return {"data": result}


def _lifecycle_endpoint(action):
    def endpoint(
        subscription_id: UUID,
        actor: Operator,
        db: Database,
        payload: schemas.LifecycleAction | None = None,
    ):
        with db.begin():
            row = workflows.apply_action_record(
                db,
                actor,
                subscription_id,
                action,
                payload.model_dump(exclude_unset=True) if payload else {},
            )
            result = queries.subscription_data(db, actor, row)
        return {"data": result}

    endpoint.__name__ = f"subscription_{action}"
    return endpoint


for _action in ("revise", "confirm", "activate", "pause", "resume", "close"):
    router.add_api_route(
        f"/subscriptions/{{subscription_id}}/{_action}",
        _lifecycle_endpoint(_action),
        methods=["POST"],
    )
