"""Original-anchor subscription periods; all service intervals are half-open."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

CADENCES = frozenset({"DAILY", "WEEKLY", "MONTHLY", "YEARLY"})


@dataclass(frozen=True, slots=True)
class CycleSnapshot:
    """Immutable scheduling inputs, independent of ORM models and the clock."""

    start_date: date
    end_date: date
    cadence: str
    close_effective_on: date | None = None

    def __post_init__(self) -> None:
        if type(self.start_date) is not date or type(self.end_date) is not date:
            raise ValueError("Service boundaries must be dates without time components")
        if not isinstance(self.cadence, str) or self.cadence not in CADENCES:
            raise ValueError("Unsupported subscription cadence")
        if self.end_date <= self.start_date:
            raise ValueError("Subscription end must be after its original start")
        if self.close_effective_on is not None:
            if type(self.close_effective_on) is not date:
                raise ValueError("Closure boundary must be a date without a time component")
            if self.close_effective_on < self.start_date:
                raise ValueError("Closure cannot precede the original subscription start")


def _boundary_before(anchor: date, cadence: str, index: int, limit: date) -> date | None:
    """Return an anchored boundary strictly before limit without date overflow."""
    if cadence in {"DAILY", "WEEKLY"}:
        offset = index * (1 if cadence == "DAILY" else 7)
        if offset >= (limit - anchor).days:
            return None
        boundary = anchor + timedelta(days=offset)
    elif cadence == "MONTHLY":
        month_index = anchor.year * 12 + anchor.month - 1 + index
        if month_index > limit.year * 12 + limit.month - 1:
            return None
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        boundary = date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))
    else:  # YEARLY; CycleSnapshot validates the cadence.
        year = anchor.year + index
        if year > limit.year:
            return None
        boundary = date(year, anchor.month, min(anchor.day, calendar.monthrange(year, anchor.month)[1]))
    return boundary if boundary < limit else None


def get_cycle_bounds(snapshot: CycleSnapshot, cycle_index: int) -> tuple[date, date] | None:
    """Return one capped period, or None after the effective end.

    The caller decides whether its start is due for a particular business date.
    Every boundary derives from start_date so short months never move the anchor.
    """
    if type(cycle_index) is not int or cycle_index < 0:
        raise ValueError("Cycle index must be a nonnegative integer")
    effective_end = min(snapshot.end_date, snapshot.close_effective_on or snapshot.end_date)
    start = _boundary_before(snapshot.start_date, snapshot.cadence, cycle_index, effective_end)
    if start is None:
        return None
    end = _boundary_before(snapshot.start_date, snapshot.cadence, cycle_index + 1, effective_end)
    return start, end or effective_end
