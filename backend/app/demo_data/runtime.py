"""Explicit historical date scope for the isolated fictional-demo importer."""

from contextlib import contextmanager
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.core.clock import Clock, use_clock
from app.core.config import get_settings


class ReplayClock(Clock):
    def __init__(self, day: date):
        self.day = day

    def now(self) -> datetime:
        local_noon = datetime.combine(
            self.day, time(12), tzinfo=ZoneInfo(get_settings().business_timezone)
        )
        return local_noon.astimezone(UTC)

    def today(self) -> date:
        return self.day


@contextmanager
def at_date(day: date):
    """Change only this CLI context; callers use normal domain transactions."""
    with use_clock(ReplayClock(day)):
        yield
