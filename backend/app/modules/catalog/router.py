"""Admin-managed products, variants and recurring plans."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import Actor, require_role
from app.core.errors import DomainError
from app.db.session import get_session
from app.models import Plan, PlanTax, Product, ProductVariant

from . import schemas, service

router = APIRouter(tags=["catalog"])
Database = Annotated[Session, Depends(get_session)]
Operator = Annotated[Actor, Depends(require_role("ADMIN", "STAFF"))]
Admin = Annotated[Actor, Depends(require_role("ADMIN"))]


def paginated(db, model, page, page_size, serialize, *, conditions=()):
    rows = db.scalars(
        select(model)
        .where(*conditions)
        .order_by(model.created_at.desc(), model.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [serialize(row) for row in rows],
        "total": db.scalar(select(func.count()).select_from(model).where(*conditions)),
        "page": page,
        "page_size": page_size,
    }


@router.get("/products")
def products(
    actor: Operator,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    q: Annotated[str | None, Query(max_length=200)] = None,
):
    search = q.strip() if q else ""
    conditions = (Product.name.icontains(search, autoescape=True),) if search else ()
    return paginated(db, Product, page, page_size, service.product_data, conditions=conditions)


@router.post("/products", status_code=201)
def create_product(payload: schemas.ProductWrite, actor: Admin, db: Database):
    with db.begin():
        product = Product(**payload.model_dump())
        db.add(product)
        db.flush()
        result = service.product_data(product)
    return {"data": result}


@router.get("/products/{product_id}")
def product_detail(product_id: UUID, actor: Operator, db: Database):
    product = service.product_data(service.get_product(db, product_id))
    product["variants"] = [
        service.variant_data(x)
        for x in db.scalars(
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id)
            .order_by(ProductVariant.created_at, ProductVariant.id)
        )
    ]
    return {"data": product}


@router.patch("/products/{product_id}")
def edit_product(product_id: UUID, payload: schemas.ProductPatch, actor: Admin, db: Database):
    changes = payload.model_dump(exclude_unset=True)
    service.reject_nulls(changes, nullable={"notes"})
    with db.begin():
        product = service.get_product(db, product_id, lock=True)
        if "sales_price" in changes:
            minimum = db.scalar(
                select(func.min(ProductVariant.price_delta)).where(
                    ProductVariant.product_id == product_id
                )
            )
            if minimum is not None and changes["sales_price"] + minimum < 0:
                raise DomainError(
                    "INVALID_PRICE", "The new base price would make a variant negative.", 422
                )
        for key, value in changes.items():
            setattr(product, key, value)
        db.flush()
        result = service.product_data(product)
    return {"data": result}


def write_variant(db, product_id, changes, variant_id=None):
    service.reject_nulls(changes)
    try:
        with db.begin():
            product = service.get_product(db, product_id, lock=True)
            if variant_id:
                variant = db.scalar(
                    select(ProductVariant)
                    .where(ProductVariant.id == variant_id, ProductVariant.product_id == product_id)
                    .with_for_update()
                )
                if variant is None:
                    raise DomainError("NOT_FOUND", "Variant not found for this product.", 404)
            else:
                variant = ProductVariant(product_id=product_id, **changes)
                db.add(variant)
            delta = changes.get("price_delta", variant.price_delta)
            if product.sales_price + delta < 0:
                raise DomainError("INVALID_PRICE", "Resulting unit price must be nonnegative.", 422)
            for key, value in changes.items():
                setattr(variant, key, value)
            db.flush()
            result = service.variant_data(variant)
    except IntegrityError as exc:
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "uq_product_variants_product_id"
        ):
            raise DomainError("VARIANT_EXISTS", "This variant already exists.", 409) from exc
        raise
    return {"data": result}


@router.post("/products/{product_id}/variants", status_code=201)
def create_variant(product_id: UUID, payload: schemas.VariantWrite, actor: Admin, db: Database):
    return write_variant(db, product_id, payload.model_dump())


@router.patch("/products/{product_id}/variants/{variant_id}")
def edit_variant(
    product_id: UUID, variant_id: UUID, payload: schemas.VariantPatch, actor: Admin, db: Database
):
    return write_variant(db, product_id, payload.model_dump(exclude_unset=True), variant_id)


@router.get("/plans")
def plans(
    actor: Operator,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    rows = db.scalars(
        select(Plan)
        .order_by(Plan.created_at.desc(), Plan.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    selected = {row.id: [] for row in rows}
    if rows:
        for plan_id, tax_id in db.execute(
            select(PlanTax.plan_id, PlanTax.tax_rule_id).where(PlanTax.plan_id.in_(selected))
        ):
            selected[plan_id].append(tax_id)
    return {
        "items": [service.plan_data(db, row, selected[row.id]) for row in rows],
        "total": db.scalar(select(func.count()).select_from(Plan)),
        "page": page,
        "page_size": page_size,
    }


@router.post("/plans", status_code=201)
def create_plan(payload: schemas.PlanWrite, actor: Admin, db: Database):
    values = payload.model_dump(exclude={"tax_rule_ids"})
    service.validate_plan_window(values["available_from"], values["available_until"])
    with db.begin():
        tax_ids = service.validate_tax_ids(db, payload.tax_rule_ids)
        plan = Plan(**values)
        db.add(plan)
        db.flush()
        db.add_all(PlanTax(plan_id=plan.id, tax_rule_id=tax_id) for tax_id in tax_ids)
        db.flush()
        result = service.plan_data(db, plan)
    return {"data": result}


@router.patch("/plans/{plan_id}")
def edit_plan(plan_id: UUID, payload: schemas.PlanPatch, actor: Admin, db: Database):
    changes = payload.model_dump(exclude_unset=True)
    service.reject_nulls(changes, nullable={"available_until"})
    with db.begin():
        plan = service.get_plan(db, plan_id, lock=True)
        service.validate_plan_window(
            changes.get("available_from", plan.available_from),
            changes.get("available_until", plan.available_until),
        )
        if "tax_rule_ids" in changes:
            tax_ids = service.validate_tax_ids(db, changes.pop("tax_rule_ids"))
            db.execute(delete(PlanTax).where(PlanTax.plan_id == plan.id))
            db.add_all(PlanTax(plan_id=plan.id, tax_rule_id=tax_id) for tax_id in tax_ids)
        for key, value in changes.items():
            setattr(plan, key, value)
        db.flush()
        result = service.plan_data(db, plan)
    return {"data": result}


@router.get("/plans/{plan_id}")
def plan_detail(plan_id: UUID, actor: Operator, db: Database):
    return {"data": service.plan_data(db, service.get_plan(db, plan_id))}
