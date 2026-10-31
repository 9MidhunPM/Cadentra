"""Explicit, resumable commerce-demo import; never invoked by normal startup.

Run dry-run first. Production execution requires the exact database name and an
operator acknowledgement that the standalone worker has been paused externally.
Output contains aggregate evidence only; database exceptions are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select, text
from sqlalchemy.orm import sessionmaker

from app.core.auth import Actor
from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.money import money_string
from app.db.base import Base
from app.db.session import engine
from app.demo_data.foundation import ensure_foundation
from app.demo_data.profile import PROFILE_VERSION, catalog, customers, plans, record_id, templates
from app.demo_data.runtime import at_date
from app.demo_data.scenarios import cycle_intent, scenarios
from app.models import (
    AuditEvent,
    BillingPeriod,
    DiscountRuleRevision,
    EmailOutbox,
    Invoice,
    Payment,
    Subscription,
    SubscriptionPause,
    User,
)
from app.modules.billing.demo_import import DemoScope, replay_demo_cycle
from app.modules.subscriptions.calendar import CycleSnapshot, get_cycle_bounds
from app.modules.subscriptions.demo_import import apply_targeted_action, create_or_resume

RUN_ID = record_id("import", "commerce-v1")
LOCK_KEY = int.from_bytes(hashlib.sha256(str(RUN_ID).encode()).digest()[:8], "big", signed=True)
EXCLUDED_BASELINE = {"audit_events", "users", "sessions", "password_reset_tokens", "email_outbox"}


class ImportConflict(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical(value):
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


def manifest(anchor):
    return {
        "version": PROFILE_VERSION,
        "anchor": str(anchor),
        "customers": customers(),
        "catalog": catalog(),
        "plans": plans(anchor),
        "templates": templates(anchor),
        "scenarios": [asdict(item) for item in scenarios(anchor)],
        "cycles": [[asdict(intent) for intent in planned_cycles(item, index, anchor)]
                   for index, item in enumerate(scenarios(anchor))],
        "billing_policy": "deterministic-cycle-intent-v1",
    }


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def planned_cycles(item, index, anchor):
    if item.activated_on is None:
        return []
    by_plan = {row["id"]: row for row in plans(anchor)}
    snapshot = CycleSnapshot(item.start_date, item.end_date, by_plan[item.plan_id]["cadence"])
    result = []
    for cycle_index in range(24):
        bounds = get_cycle_bounds(snapshot, cycle_index)
        if bounds is None or bounds[0] > item.bill_through:
            return result
        intent = cycle_intent(record_id("scenario", item.key), index, cycle_index, bounds[0], anchor)
        if item.pause_on and bounds[0] > item.pause_on:
            intent = replace(intent, payment_mode="NONE", payment_dates=(),
                             invoice_state="CONFIRMED")
        result.append(intent)
    raise ImportConflict("CATCHUP_LIMIT_EXCEEDED")


def inventory(db):
    """Hash existing business rows without persisting their private contents."""
    result = {}
    for table in Base.metadata.sorted_tables:
        if table.name in EXCLUDED_BASELINE:
            continue
        rows = {}
        for row in db.execute(select(table)).mappings():
            key = canonical([row[column.name] for column in table.primary_key])
            rows[key] = digest(dict(row))
        result[table.name] = rows
    return result


def verify_preserved(db, baseline):
    current = inventory(db)
    for table, rows in baseline.items():
        if any(current.get(table, {}).get(key) != value for key, value in rows.items()):
            raise ImportConflict("PREEXISTING_RECORD_DRIFT")


def preflight(db, anchor):
    first = min(item.start_date for item in scenarios(anchor))
    unsafe = db.scalar(
        select(DiscountRuleRevision.id).where(
            DiscountRuleRevision.scope == "SUBSCRIPTION",
            DiscountRuleRevision.active.is_(True),
            DiscountRuleRevision.starts_on <= anchor,
            or_(DiscountRuleRevision.ends_on.is_(None), DiscountRuleRevision.ends_on > first),
            DiscountRuleRevision.effective_from <= anchor,
            or_(DiscountRuleRevision.effective_until.is_(None),
                DiscountRuleRevision.effective_until > first),
        ).limit(1)
    )
    if unsafe:
        raise ImportConflict("GLOBAL_DISCOUNT_CONFLICT")
    user = db.scalar(select(User).where(User.active.is_(True), User.role == "ADMIN")
                     .order_by(User.created_at, User.id).limit(1))
    if user is None:
        raise ImportConflict("ACTIVE_ADMIN_REQUIRED")
    return Actor(user.id, user.role, user.customer_id, user.display_name)


def replay(factory, actor, anchor):
    scheduled = scenarios(anchor)
    customer_ids = frozenset(item["id"] for item in customers())
    identifiers = []
    created = 0
    for item in scheduled:
        identifier, is_new = create_or_resume(
            factory, actor, item, created_on=item.draft_on, at_date=at_date
        )
        identifiers.append(identifier)
        created += is_new
    scope = DemoScope("commerce-v1", customer_ids, frozenset(identifiers))
    for index, (item, identifier) in enumerate(zip(scheduled, identifiers, strict=True)):
        def action(name, day, payload=None, scenario=item):
            return apply_targeted_action(
                factory, actor, scenario, name, payload or {}, event_key=name,
                on_date=day, at_date=at_date,
            )

        if item.quotation_on:
            action("issue-quotation", item.quotation_on, {"valid_days": item.quotation_valid_days})
        if item.confirmed_on:
            action("confirm", item.confirmed_on)
        if item.activated_on:
            action("activate", item.activated_on)
        if item.activated_on is None:
            continue
        paused = False
        for planned in planned_cycles(item, index, anchor):
            if item.pause_on and not paused and planned.as_of > item.pause_on:
                action("pause", item.pause_on, {"reason": "Fictional demo pause"})
                paused = True
            intent = replace(planned, subscription_id=identifier)
            replay_demo_cycle(factory, actor, scope, intent, at_date=at_date)
        if item.pause_on and not paused:
            action("pause", item.pause_on, {"reason": "Fictional demo pause"})
        if item.close_on:
            action("close", item.close_on, {"reason": "Fictional demo term completed"})
    return identifiers, created


def reconcile(db, identifiers, anchor):
    ids = set(identifiers)
    rows = db.scalars(select(Subscription).where(Subscription.id.in_(ids))).all()
    states = Counter(row.state for row in rows)
    if states != {"ACTIVE": 96, "DRAFT": 24, "QUOTATION": 24, "CONFIRMED": 24, "CLOSED": 24}:
        raise ValueError("Imported lifecycle state counts do not match manifest")
    pauses = db.scalars(select(SubscriptionPause).where(
        SubscriptionPause.subscription_id.in_(ids), SubscriptionPause.starts_on <= anchor,
        or_(SubscriptionPause.ends_on.is_(None), SubscriptionPause.ends_on > anchor),
    )).all()
    if len(pauses) != 12:
        raise ValueError("Imported pause count does not match manifest")
    invoices = db.scalars(select(Invoice).where(Invoice.subscription_id.in_(ids))).all()
    invoice_ids = {row.id for row in invoices}
    payments = db.scalars(select(Payment).where(Payment.invoice_id.in_(invoice_ids))).all()
    paid = {}
    for row in payments:
        paid[row.invoice_id] = paid.get(row.invoice_id, Decimal("0.00")) + row.amount
    for row in invoices:
        amount = paid.get(row.id, Decimal("0.00"))
        if amount > row.total or (row.status == "PAID" and amount != row.total):
            raise ValueError("Imported invoice/payment reconciliation failed")
    outbox_count = len(db.scalars(select(EmailOutbox.id).where(
        EmailOutbox.aggregate_id.in_(invoice_ids)
    )).all())
    if outbox_count:
        raise ValueError("Imported invoices unexpectedly have outbound email")
    periods = db.scalars(select(BillingPeriod).where(BillingPeriod.subscription_id.in_(ids))).all()
    expected_keys = {(row.subscription_id, row.cycle_index) for row in periods}
    if len(expected_keys) != len(periods):
        raise ValueError("Duplicate imported billing outcomes")
    return {
        "subscriptions": len(rows), "states": dict(states), "paused": len(pauses),
        "invoices": len(invoices), "invoice_states": dict(Counter(row.status for row in invoices)),
        "payments": len(payments), "billing_periods": len(periods), "outbound_emails": outbox_count,
        "cash_received": money_string(sum((row.amount for row in payments), Decimal("0.00"))),
        "invoiced_gross": money_string(sum((row.total for row in invoices
            if row.status in {"CONFIRMED", "PAID"}), Decimal("0.00"))),
        "outstanding": money_string(sum((row.total - paid.get(row.id, Decimal("0.00"))
            for row in invoices if row.status == "CONFIRMED"), Decimal("0.00"))),
    }


def run(args):
    settings = get_settings()
    database = engine.url.database
    if args.target == "local-test":
        if settings.app_env != "test" or not (database or "").endswith("_test"):
            raise ImportConflict("INVALID_LOCAL_TARGET")
    elif settings.app_env != "production" or settings.app_origin.rstrip("/") != "https://cadentra.midhunpm.in":
        raise ImportConflict("INVALID_PUBLIC_TARGET")
    if args.execute and (args.expected_database != database or not args.worker_paused):
        raise ImportConflict("EXECUTION_ACKNOWLEDGEMENT_REQUIRED")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with engine.connect() as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}):
            raise ImportConflict("IMPORT_ALREADY_RUNNING")
        lock.commit()
        try:
            if args.execute:
                # Keep rule edits from racing the read-only eligibility preflight.
                # The root operator additionally pauses public ingress and worker.
                lock.execute(text("SET LOCAL lock_timeout = '5s'"))
                lock.execute(text("LOCK TABLE discount_rules, discount_rule_revisions, "
                                  "discount_revision_products IN SHARE MODE"))
            with factory() as db:
                existing = db.get(AuditEvent, RUN_ID)
                anchor = args.anchor or (date.fromisoformat(existing.redacted_details["anchor"])
                                         if existing else get_clock().today())
                if anchor > get_clock().today():
                    raise ImportConflict("FUTURE_ANCHOR")
                data_hash = digest(manifest(anchor))
                if existing and existing.redacted_details["manifest_sha256"] != data_hash:
                    raise ImportConflict("MANIFEST_DRIFT")
                actor = preflight(db, anchor)
            if not args.execute:
                return {"status": "dry-run", "anchor": str(anchor), "manifest_sha256": data_hash,
                        "products": 80, "variants": 160, "customers": 96, "plans": 8,
                        "templates": 6, "subscriptions": 192, "resuming": existing is not None}
            with factory.begin() as db:
                marker = db.get(AuditEvent, RUN_ID)
                if marker is None:
                    marker = AuditEvent(id=RUN_ID, actor_user_id=actor.id, entity_type="DEMO_IMPORT",
                        entity_id=RUN_ID, action="DEMO_IMPORT_MANIFEST", redacted_details={
                            "anchor": str(anchor), "manifest_sha256": data_hash,
                            "baseline": inventory(db), "version": PROFILE_VERSION,
                        })
                    db.add(marker)
                baseline = marker.redacted_details["baseline"]
                verify_preserved(db, baseline)
                ensure_foundation(db, actor, anchor)
            identifiers, created = replay(factory, actor, anchor)
            with factory() as db:
                verify_preserved(db, baseline)
                evidence = reconcile(db, identifiers, anchor)
            return {"status": "complete", "anchor": str(anchor), "manifest_sha256": data_hash,
                    "subscriptions_created": created, "preserved_existing_records": True, **evidence}
        finally:
            lock.rollback()  # Release table locks before releasing the session lock.
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            lock.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=["local-test", "public-demo"])
    parser.add_argument("--anchor", type=date.fromisoformat)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-database")
    parser.add_argument("--worker-paused", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__,
                          "code": getattr(error, "code", "IMPORT_REQUIRES_REVIEW")}))
        return 1
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
