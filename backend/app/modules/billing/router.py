"""Staff billing routes, registered once by the application foundation."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, ConfigDict

from app.core.auth import Actor, require_role
from app.core.clock import get_clock
from app.core.config import get_settings
from app.db import session as database
from app.modules.billing.invoices_router import router as invoices_router
from app.modules.billing.rules_router import router as rules_router

from .issuance import run_due

router = APIRouter(tags=["billing"])
router.include_router(rules_router)
router.include_router(invoices_router)


class RunDueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


_EMPTY_RUN = RunDueRequest()


@router.post("/billing/run-due")
def run_due_now(
    actor: Annotated[Actor, Depends(require_role("ADMIN", "STAFF"))],
    payload: Annotated[RunDueRequest, Body()] = _EMPTY_RUN,
):
    result = run_due(
        database.SessionFactory, get_clock().today(), get_settings().worker_batch_size, actor=actor
    )
    return {"data": asdict(result)}
