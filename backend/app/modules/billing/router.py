"""Foundation placeholder; the billing owner replaces this in place."""

from fastapi import APIRouter

from app.core.errors import DomainError

router = APIRouter(tags=["billing"])


@router.get("/billing")
def not_implemented():
    raise DomainError("NOT_IMPLEMENTED", "Billing is not implemented yet.", 501)
