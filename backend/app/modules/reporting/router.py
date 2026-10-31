"""Read-only reports and the authenticated customer portal."""

from datetime import date, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import Actor, Role, require_role
from app.core.clock import get_clock
from app.db.session import get_session
from app.modules.reporting import service
from app.modules.reporting.portal import router as portal_router

router = APIRouter(tags=["reporting"])
Staff = Annotated[Actor, Depends(require_role(Role.ADMIN, Role.STAFF))]
Database = Annotated[Session, Depends(get_session)]


def report_range(range_from: date | None, range_to: date | None) -> tuple[date, date]:
    today = get_clock().today()
    return range_from or today.replace(day=1), range_to or today + timedelta(days=1)


@router.get("/reports/summary")
def summary(
    db: Database,
    actor: Staff,
    range_from: Annotated[date | None, Query(alias="from")] = None,
    range_to: Annotated[date | None, Query(alias="to")] = None,
    customer_id: UUID | None = None,
):
    start, end = report_range(range_from, range_to)
    return {"data": service.summary(db, actor, start, end, customer_id)}


@router.get("/reports/revenue-series")
def revenue_series(
    db: Database,
    actor: Staff,
    range_from: Annotated[date | None, Query(alias="from")] = None,
    range_to: Annotated[date | None, Query(alias="to")] = None,
    cadence: Literal["DAILY", "MONTHLY"] = "DAILY",
    customer_id: UUID | None = None,
):
    start, end = report_range(range_from, range_to)
    return {"data": service.revenue_series(db, actor, start, end, cadence, customer_id)}


router.include_router(portal_router)
