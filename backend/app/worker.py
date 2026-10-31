"""Standalone lifecycle/billing/outbox worker; never runs inside API startup."""
from __future__ import annotations

import argparse
import importlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


class WorkerNotReady(RuntimeError):
    """A required feature service has not been integrated yet."""


@dataclass(frozen=True)
class WorkerServices:
    lifecycle: Callable[..., Any]
    billing: Callable[..., Any]
    outbox: Callable[..., Any]


def _service(module_name: str, function_name: str) -> Callable[..., Any]:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name == module_name or module_name.startswith(f"{error.name}."):
            raise WorkerNotReady(f"Required service unavailable: {module_name}.{function_name}") from error
        raise  # A broken dependency inside a present feature is a genuine error.
    function = getattr(module, function_name, None)
    if not callable(function):
        raise WorkerNotReady(f"Required service unavailable: {module_name}.{function_name}")
    return function


def load_services() -> WorkerServices:
    return WorkerServices(
        lifecycle=_service("app.modules.subscriptions.service", "process_lifecycle"),
        billing=_service("app.modules.billing.service", "run_due"),
        outbox=_service("app.core.outbox", "dispatch_pending"),
    )


def run_tick(services: WorkerServices, session_factory: Any, as_of: date, limit: int) -> Any:
    """Lifecycle/outbox use caller-owned transactions; billing owns per-cycle ones."""
    with session_factory.begin() as db:
        services.lifecycle(db, as_of)
    result = services.billing(session_factory, as_of, limit)
    with session_factory.begin() as db:
        services.outbox(db)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one bounded tick then exit")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    # Resolve all services before performing any work. Foundation placeholders fail.
    try:
        services = load_services()
    except WorkerNotReady as error:
        parser.exit(2, f"Worker not ready: {error}\n")
    from app.core.clock import get_clock
    from app.core.config import get_settings
    from app.db.session import SessionFactory

    settings = get_settings()
    logging.basicConfig(level=logging.INFO)
    while True:
        run_tick(services, SessionFactory, get_clock().today(), args.limit)
        logger.info("Completed bounded worker tick")
        if args.once:
            return 0
        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
