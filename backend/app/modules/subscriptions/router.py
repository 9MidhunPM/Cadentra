"""Foundation placeholder; the subscriptions owner replaces this in place."""

from fastapi import APIRouter

from app.core.errors import DomainError

router = APIRouter(tags=["subscriptions"])


@router.get("/subscriptions")
def not_implemented():
    raise DomainError("NOT_IMPLEMENTED", "Subscriptions is not implemented yet.", 501)
