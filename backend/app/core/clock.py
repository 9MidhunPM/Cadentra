from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().astimezone(ZoneInfo(get_settings().business_timezone)).date()


_clock = Clock()
_context_clock: ContextVar[Clock | None] = ContextVar("cadentra_clock", default=None)


def get_clock() -> Clock:
    """Override this provider in tests; there is no public clock-setting endpoint."""
    return _context_clock.get() or _clock


@contextmanager
def use_clock(clock: Clock) -> Iterator[None]:
    """Scope an explicit clock to an isolated administrative/demo replay context.

    Normal HTTP/worker processes keep system time. This is never an HTTP input
    and does not change the host clock or another task's context.
    """
    token = _context_clock.set(clock)
    try:
        yield
    finally:
        _context_clock.reset(token)
