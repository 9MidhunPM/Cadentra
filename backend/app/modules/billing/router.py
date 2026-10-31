"""Staff billing routes, registered once by the application foundation."""

from fastapi import APIRouter

from app.modules.billing.invoices_router import router as invoices_router
from app.modules.billing.rules_router import router as rules_router

router = APIRouter(tags=["billing"])
router.include_router(rules_router)
router.include_router(invoices_router)
