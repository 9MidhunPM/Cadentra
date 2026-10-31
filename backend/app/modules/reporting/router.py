"""Foundation placeholder; the reporting owner replaces this in place."""

from fastapi import APIRouter

from app.core.errors import DomainError

router = APIRouter(tags=["reporting"])


@router.get("/reporting")
def not_implemented():
    raise DomainError("NOT_IMPLEMENTED", "Reporting is not implemented yet.", 501)
