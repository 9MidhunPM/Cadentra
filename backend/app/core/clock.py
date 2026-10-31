from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().astimezone(ZoneInfo(get_settings().business_timezone)).date()


_clock = Clock()


def get_clock() -> Clock:
    """Override this provider in tests; there is no public clock-setting endpoint."""
    return _clock
