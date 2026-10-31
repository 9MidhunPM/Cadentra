"""Bounded process-local limiter for the single-process MVP API.

Multi-process deployments require a shared limiter before horizontal scaling.
"""

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

from app.core.errors import DomainError

_events: OrderedDict[str, deque[float]] = OrderedDict()
_lock = Lock()


def check_rate_limit(key: str, *, limit: int = 30, window: int = 300) -> None:
    now = monotonic()
    with _lock:
        events = _events.setdefault(key, deque())
        while events and events[0] <= now - window:
            events.popleft()
        _events.move_to_end(key)
        if len(events) >= limit:
            raise DomainError("RATE_LIMITED", "Please wait before trying again.", status_code=429)
        events.append(now)
        while len(_events) > 10_000:
            _events.popitem(last=False)


def reset_rate_limits() -> None:
    """Reset process-local state for isolated tests."""
    with _lock:
        _events.clear()
