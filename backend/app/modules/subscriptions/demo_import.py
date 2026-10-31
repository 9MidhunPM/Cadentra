"""Targeted, resumable fictional subscription-history import adapter."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.auth import Actor
from app.models import AuditEvent, Subscription, SubscriptionLine
from app.modules.subscriptions.workflows import apply_action_record, create_subscription

DEMO_DATASET_VERSION = "uci-retail-fictional-v1"
DEMO_MARKER_ACTION = "DEMO_SEED_SCENARIO"
ClockScope = Callable[[date], AbstractContextManager[Any]]
SessionFactory = Callable[[], Session]
ScenarioState = Literal["DRAFT", "QUOTATION", "CONFIRMED", "ACTIVE", "PAUSED", "CLOSED"]
SUPPORTED_ACTIONS = frozenset(
    {"issue-quotation", "revise", "confirm", "activate", "pause", "resume", "close", "renew"}
)


@dataclass(frozen=True)
class DemoScenario:
    """Immutable identity and full intent for one seeded subscription."""

    key: str
    customer_id: UUID
    plan_id: UUID
    start_date: date
    end_date: date
    payment_terms_days: int
    lines: Sequence[Mapping[str, Any]]
    target: ScenarioState

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,119}", self.key):
            raise ValueError("Demo scenario keys must be stable lowercase identifiers")
        if self.end_date <= self.start_date or not self.lines:
            raise ValueError("A demo scenario needs a nonempty line set and service window")
        if type(self.payment_terms_days) is not int or self.payment_terms_days < 0:
            raise ValueError("Payment terms must be nonnegative integer days")


@dataclass(frozen=True)
class DemoActionResult:
    subscription_id: UUID
    state: str
    already_applied: bool
    renewal_id: UUID | None = None


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported demo intent value: {type(value).__name__}")


def canonical_intent(scenario: DemoScenario) -> dict[str, Any]:
    """Canonical, order-independent intent persisted by the ownership marker."""
    lines = [
        {
            "product_id": str(line["product_id"]),
            "variant_id": str(line["variant_id"]) if line.get("variant_id") else None,
            "quantity": line["quantity"],
        }
        for line in scenario.lines
    ]
    lines.sort(key=lambda line: (line["product_id"], line["variant_id"] or "", line["quantity"]))
    return {
        "dataset": DEMO_DATASET_VERSION,
        "scenario_key": scenario.key,
        "customer_id": str(scenario.customer_id),
        "plan_id": str(scenario.plan_id),
        "start_date": scenario.start_date.isoformat(),
        "end_date": scenario.end_date.isoformat(),
        "payment_terms_days": scenario.payment_terms_days,
        "lines": lines,
        "target": scenario.target,
    }


def _intent_hash(scenario: DemoScenario) -> str:
    encoded = json.dumps(canonical_intent(scenario), sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def _lock_key(key: str) -> int:
    return int.from_bytes(
        sha256(f"{DEMO_DATASET_VERSION}:{key}".encode()).digest()[:8],
        byteorder="big",
        signed=True,
    )


def _marker_query(key: str):
    return select(AuditEvent).where(
        AuditEvent.entity_type == "subscription",
        AuditEvent.action == DEMO_MARKER_ACTION,
        AuditEvent.redacted_details["dataset"].as_string() == DEMO_DATASET_VERSION,
        AuditEvent.redacted_details["scenario_key"].as_string() == key,
    )


def _marker(db: Session, key: str) -> AuditEvent | None:
    rows = db.scalars(_marker_query(key).with_for_update()).all()
    if len(rows) > 1:
        raise ValueError(f"Duplicate demo markers for scenario {key!r}; refusing to choose")
    return rows[0] if rows else None


def _line_intent(db: Session, subscription_id: UUID) -> list[dict[str, Any]]:
    lines = db.scalars(
        select(SubscriptionLine).where(SubscriptionLine.subscription_id == subscription_id)
    )
    result = [
        {
            "product_id": str(line.product_id),
            "variant_id": str(line.variant_id) if line.variant_id else None,
            "quantity": line.quantity,
        }
        for line in lines
    ]
    result.sort(key=lambda line: (line["product_id"], line["variant_id"] or "", line["quantity"]))
    return result


def _check_subscription(db: Session, row: Subscription, scenario: DemoScenario, marker: AuditEvent):
    expected = canonical_intent(scenario)
    if marker.redacted_details.get("intent_sha256") != _intent_hash(scenario):
        raise ValueError(f"Demo scenario {scenario.key!r} intent changed between runs")
    if (
        row.customer_id != scenario.customer_id
        or row.plan_id != scenario.plan_id
        or row.start_date != scenario.start_date
        or row.end_date != scenario.end_date
        or row.payment_terms_days != scenario.payment_terms_days
        or _line_intent(db, row.id) != expected["lines"]
    ):
        raise ValueError(f"Marked demo scenario {scenario.key!r} no longer matches its intent")


def _get_owned(db: Session, scenario: DemoScenario) -> tuple[Subscription, AuditEvent] | None:
    marker = _marker(db, scenario.key)
    if marker is None:
        return None
    row = db.scalar(
        select(Subscription).where(Subscription.id == marker.entity_id).with_for_update()
    )
    if row is None:
        raise ValueError(f"Demo marker {scenario.key!r} points to a missing subscription")
    _check_subscription(db, row, scenario, marker)
    return row, marker


def create_or_resume(
    factory: SessionFactory,
    actor: Actor,
    scenario: DemoScenario,
    *,
    created_on: date,
    at_date: ClockScope,
) -> tuple[UUID, bool]:
    """Create a marked DRAFT or return its matching row without rewriting it."""
    intent = canonical_intent(scenario)
    digest = _intent_hash(scenario)
    with factory.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _lock_key(scenario.key)})
        existing = _get_owned(db, scenario)
        if existing is not None:
            return existing[0].id, False
        with at_date(created_on):
            row = create_subscription(
                db,
                actor,
                {
                    "customer_id": scenario.customer_id,
                    "plan_id": scenario.plan_id,
                    "start_date": scenario.start_date,
                    "end_date": scenario.end_date,
                    "payment_terms_days": scenario.payment_terms_days,
                    "lines": [dict(line) for line in scenario.lines],
                },
            )
        db.add(
            AuditEvent(
                actor_user_id=actor.id,
                entity_type="subscription",
                entity_id=row.id,
                action=DEMO_MARKER_ACTION,
                redacted_details={
                    "dataset": DEMO_DATASET_VERSION,
                    "scenario_key": scenario.key,
                    "intent": intent,
                    "intent_sha256": digest,
                    "events": {},
                },
            )
        )
        db.flush()
        return row.id, True


def apply_targeted_action(
    factory: SessionFactory,
    actor: Actor,
    scenario: DemoScenario,
    action: str,
    payload: Mapping[str, Any],
    *,
    event_key: str,
    on_date: date,
    at_date: ClockScope,
    renewal_scenario: DemoScenario | None = None,
) -> DemoActionResult:
    """Apply one idempotent historical action to the subscription marked by key.

    The root importer sequences dates and invokes billing for this subscription
    separately. A renewal can be atomically marked as a second scenario.
    """
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unsupported demo lifecycle action: {action}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,119}", event_key):
        raise ValueError("Demo action event keys must be stable lowercase identifiers")
    if (action == "renew") != (renewal_scenario is not None):
        raise ValueError("Renewal actions require a linked renewal scenario intent")

    event = {
        "action": action,
        "payload": _json_value(payload),
        "on_date": on_date.isoformat(),
        "renewal_intent_sha256": _intent_hash(renewal_scenario)
        if renewal_scenario is not None
        else None,
    }
    event_digest = sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with at_date(on_date):
        with factory.begin() as db:
            db.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": _lock_key(scenario.key)},
            )
            owned = _get_owned(db, scenario)
            if owned is None:
                raise ValueError(f"Demo scenario {scenario.key!r} has not been created")
            row, marker = owned
            details = dict(marker.redacted_details)
            events = dict(details.get("events", {}))
            previous = events.get(event_key)
            if previous is not None and previous != event_digest:
                raise ValueError(f"Demo event {event_key!r} changed between runs")
            if previous == event_digest:
                renewal_id = None
                if renewal_scenario is not None:
                    child = _get_owned(db, renewal_scenario)
                    if child is None or child[0].prior_subscription_id != row.id:
                        raise ValueError("Renewal event marker does not match its linked draft")
                    renewal_id = child[0].id
                return DemoActionResult(row.id, row.state, True, renewal_id)

            result = apply_action_record(db, actor, row.id, action, dict(payload))
            renewal_id = None
            if renewal_scenario is not None:
                db.flush()
                child_marker = _marker(db, renewal_scenario.key)
                if child_marker is not None:
                    child = db.get(Subscription, child_marker.entity_id)
                    if (
                        child is None
                        or child_marker.redacted_details.get("intent_sha256")
                        != _intent_hash(renewal_scenario)
                        or child.prior_subscription_id != row.id
                    ):
                        raise ValueError("Existing renewal marker conflicts with this parent")
                else:
                    _check_subscription_shape(db, result, renewal_scenario)
                    child_marker = AuditEvent(
                        actor_user_id=actor.id,
                        entity_type="subscription",
                        entity_id=result.id,
                        action=DEMO_MARKER_ACTION,
                        redacted_details={
                            "dataset": DEMO_DATASET_VERSION,
                            "scenario_key": renewal_scenario.key,
                            "intent": canonical_intent(renewal_scenario),
                            "intent_sha256": _intent_hash(renewal_scenario),
                            "events": {},
                        },
                    )
                    db.add(child_marker)
                renewal_id = result.id
            events[event_key] = event_digest
            details["events"] = events
            marker.redacted_details = details
            db.flush()
            return DemoActionResult(row.id, result.state, False, renewal_id)


def _check_subscription_shape(db: Session, row: Subscription, scenario: DemoScenario) -> None:
    expected = canonical_intent(scenario)
    if (
        row.customer_id != scenario.customer_id
        or row.plan_id != scenario.plan_id
        or row.start_date != scenario.start_date
        or row.end_date != scenario.end_date
        or row.payment_terms_days != scenario.payment_terms_days
        or _line_intent(db, row.id) != expected["lines"]
    ):
        raise ValueError(f"New subscription does not match intent {scenario.key!r}")
