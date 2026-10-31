"""Role-checked retained tax and discount administration."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_role
from app.db.session import get_session

from . import rule_schemas as schemas
from . import rules

router = APIRouter(tags=["billing rules"])
Database = Annotated[Session, Depends(get_session)]
Operator = Annotated[Actor, Depends(require_role("ADMIN", "STAFF"))]
Admin = Annotated[Actor, Depends(require_role("ADMIN"))]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/tax-rules")
def taxes(actor: Operator, db: Database, page: Page = 1, page_size: PageSize = 25):
    return rules.list_rules(db, actor, True, page, page_size)


@router.post("/tax-rules", status_code=201)
def create_tax(payload: schemas.TaxWrite, actor: Admin, db: Database):
    return {"data": rules.write_rule(db, actor, payload, True)}


@router.patch("/tax-rules/{rule_id}")
def revise_tax(rule_id: UUID, payload: schemas.TaxPatch, actor: Admin, db: Database):
    return {"data": rules.write_rule(db, actor, payload, True, rule_id)}


@router.get("/discount-rules")
def discounts(actor: Operator, db: Database, page: Page = 1, page_size: PageSize = 25):
    return rules.list_rules(db, actor, False, page, page_size)


@router.post("/discount-rules", status_code=201)
def create_discount(payload: schemas.DiscountWrite, actor: Admin, db: Database):
    return {"data": rules.write_rule(db, actor, payload, False)}


@router.patch("/discount-rules/{rule_id}")
def revise_discount(rule_id: UUID, payload: schemas.DiscountPatch, actor: Admin, db: Database):
    return {"data": rules.write_rule(db, actor, payload, False, rule_id)}
