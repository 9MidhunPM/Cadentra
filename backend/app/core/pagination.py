"""Validate bounded page sizes and PostgreSQL-compatible offsets before SQL."""

from app.core.errors import DomainError

MAX_OFFSET = 2**63 - 1


def safe_offset(page: int, page_size: int, *, code: str = "INVALID_PAGINATION") -> int:
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
        raise DomainError(code, "Use page >= 1 and page_size between 1 and 100.", 422)
    offset = (page - 1) * page_size
    if offset > MAX_OFFSET:
        raise DomainError(code, "The requested page offset is unsupported.", 422)
    return offset
