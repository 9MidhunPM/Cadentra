"""PostgreSQL integration checks for the targeted demo-import adapter."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.auth import Actor
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    Invoice,
    Plan,
    Product,
    Subscription,
    SubscriptionPause,
    User,
)
from app.modules.billing import issuance
from app.modules.subscriptions import workflows
from app.modules.subscriptions.demo_import import (
    DEMO_MARKER_ACTION,
    DemoScenario,
    apply_targeted_action,
    create_or_resume,
)


@pytest.fixture
def demo_import_setup(db_session, db_connection, monkeypatch):
    clock = SimpleNamespace(day=date(2026, 10, 1))
    clock.today = lambda: clock.day
    clock.now = lambda: datetime.combine(clock.day, datetime.min.time(), UTC)
    monkeypatch.setattr(workflows, "get_clock", lambda: clock)
    monkeypatch.setattr(issuance, "get_clock", lambda: clock)

    @contextmanager
    def at_date(day):
        previous = clock.day
        clock.day = day
        try:
            yield
        finally:
            clock.day = previous

    staff = User(
        display_name="Demo import staff",
        normalized_email=f"{uuid4()}@example.invalid",
        password_hash="test-only",
        role="STAFF",
    )
    customer = Customer(display_name="Fictional demo customer", email=f"{uuid4()}@example.invalid")
    plan = Plan(
        name="Demo monthly",
        base_fee=Decimal("25.00"),
        cadence="MONTHLY",
        min_quantity=1,
        available_from=date(2020, 1, 1),
        allow_pause=True,
        allow_early_close=True,
        allow_renew=True,
        auto_close=True,
    )
    products = [
        Product(name=f"Demo seat {index}", product_type="SERVICE", sales_price=Decimal("10.00"))
        for index in range(2)
    ]
    db_session.add_all([staff, customer, plan, *products])
    db_session.flush()
    factory = sessionmaker(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    lines = tuple(
        {"product_id": product.id, "quantity": index + 1} for index, product in enumerate(products)
    )
    return SimpleNamespace(
        actor=Actor(staff.id, "STAFF"),
        customer=customer,
        plan=plan,
        products=products,
        factory=factory,
        at_date=at_date,
        lines=lines,
    )


def active_scenario(setup, key="active-scenario"):
    return DemoScenario(
        key=key,
        customer_id=setup.customer.id,
        plan_id=setup.plan.id,
        start_date=date(2026, 10, 1),
        end_date=date(2027, 4, 1),
        payment_terms_days=14,
        lines=setup.lines,
        target="ACTIVE",
    )


def test_create_resume_compares_canonical_full_intent_without_mutating_rows(demo_import_setup):
    setup = demo_import_setup
    scenario = active_scenario(setup)
    identifier, created = create_or_resume(
        setup.factory, setup.actor, scenario, created_on=date(2026, 9, 30), at_date=setup.at_date
    )
    reordered = DemoScenario(**{**scenario.__dict__, "lines": tuple(reversed(scenario.lines))})
    resumed, created_again = create_or_resume(
        setup.factory, setup.actor, reordered, created_on=date(2026, 9, 30), at_date=setup.at_date
    )
    assert created and not created_again and resumed == identifier
    with setup.factory() as db:
        assert db.scalar(select(func.count()).select_from(Subscription)) == 1
        marker = db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == identifier, AuditEvent.action == DEMO_MARKER_ACTION
            )
        )
        assert len(marker.redacted_details["intent_sha256"]) == 64
    mismatched = DemoScenario(**{**scenario.__dict__, "payment_terms_days": 15})
    with pytest.raises(ValueError, match="intent changed"):
        create_or_resume(
            setup.factory,
            setup.actor,
            mismatched,
            created_on=date(2026, 9, 30),
            at_date=setup.at_date,
        )


def test_targeted_lifecycle_events_resume_idempotently(demo_import_setup):
    setup = demo_import_setup
    scenario = active_scenario(setup)
    identifier, _ = create_or_resume(
        setup.factory, setup.actor, scenario, created_on=date(2026, 9, 30), at_date=setup.at_date
    )
    quote = apply_targeted_action(
        setup.factory,
        setup.actor,
        scenario,
        "issue-quotation",
        {"valid_days": 14},
        event_key="quote",
        on_date=date(2026, 9, 30),
        at_date=setup.at_date,
    )
    replay = apply_targeted_action(
        setup.factory,
        setup.actor,
        scenario,
        "issue-quotation",
        {"valid_days": 14},
        event_key="quote",
        on_date=date(2026, 9, 30),
        at_date=setup.at_date,
    )
    assert quote.subscription_id == replay.subscription_id == identifier
    assert quote.state == "QUOTATION" and not quote.already_applied
    assert replay.state == "QUOTATION" and replay.already_applied
    confirmed = apply_targeted_action(
        setup.factory,
        setup.actor,
        scenario,
        "confirm",
        {},
        event_key="confirm",
        on_date=date(2026, 9, 30),
        at_date=setup.at_date,
    )
    active = apply_targeted_action(
        setup.factory,
        setup.actor,
        scenario,
        "activate",
        {},
        event_key="activate",
        on_date=date(2026, 10, 1),
        at_date=setup.at_date,
    )
    assert confirmed.state == "CONFIRMED" and active.state == "ACTIVE"
    assert active.subscription_id == identifier
    with pytest.raises(ValueError, match="event .* changed"):
        apply_targeted_action(
            setup.factory,
            setup.actor,
            scenario,
            "issue-quotation",
            {"valid_days": 7},
            event_key="quote",
            on_date=date(2026, 9, 30),
            at_date=setup.at_date,
        )


def test_renewal_creates_and_marks_only_its_linked_draft(demo_import_setup):
    setup = demo_import_setup
    scenario = active_scenario(setup)
    parent_id, _ = create_or_resume(
        setup.factory, setup.actor, scenario, created_on=date(2026, 9, 30), at_date=setup.at_date
    )
    for action, key, day, payload in (
        ("issue-quotation", "quote", date(2026, 9, 30), {"valid_days": 14}),
        ("confirm", "confirm", date(2026, 9, 30), {}),
        ("activate", "activate", date(2026, 10, 1), {}),
    ):
        apply_targeted_action(
            setup.factory,
            setup.actor,
            scenario,
            action,
            payload,
            event_key=key,
            on_date=day,
            at_date=setup.at_date,
        )
    renewal = DemoScenario(
        key="active-scenario:renewal",
        customer_id=setup.customer.id,
        plan_id=setup.plan.id,
        start_date=date(2027, 4, 1),
        end_date=date(2027, 10, 1),
        payment_terms_days=14,
        lines=setup.lines,
        target="DRAFT",
    )
    result = apply_targeted_action(
        setup.factory,
        setup.actor,
        scenario,
        "renew",
        {"start_date": renewal.start_date, "end_date": renewal.end_date},
        event_key="renewal",
        on_date=date(2026, 10, 1),
        at_date=setup.at_date,
        renewal_scenario=renewal,
    )
    replay = apply_targeted_action(
        setup.factory,
        setup.actor,
        scenario,
        "renew",
        {"start_date": renewal.start_date, "end_date": renewal.end_date},
        event_key="renewal",
        on_date=date(2026, 10, 1),
        at_date=setup.at_date,
        renewal_scenario=renewal,
    )
    assert result.renewal_id is not None and result.renewal_id == replay.renewal_id
    with setup.factory() as db:
        child = db.get(Subscription, result.renewal_id)
        assert child.prior_subscription_id == parent_id and child.state == "DRAFT"
        assert db.scalar(select(func.count()).select_from(Subscription)) == 2


def test_pause_and_expiry_close_use_actions_around_targeted_real_billing(demo_import_setup):
    setup = demo_import_setup

    def activate(scenario):
        identifier, _ = create_or_resume(
            setup.factory,
            setup.actor,
            scenario,
            created_on=date(2026, 9, 30),
            at_date=setup.at_date,
        )
        for action, key, day, payload in (
            ("issue-quotation", "quote", date(2026, 9, 30), {"valid_days": 14}),
            ("confirm", "confirm", date(2026, 9, 30), {}),
            ("activate", "activate", date(2026, 10, 1), {}),
        ):
            apply_targeted_action(
                setup.factory,
                setup.actor,
                scenario,
                action,
                payload,
                event_key=key,
                on_date=day,
                at_date=setup.at_date,
            )
        return identifier

    paused_scenario = active_scenario(setup, "pause-case")
    paused_id = activate(paused_scenario)
    issued = issuance.issue_due_period(setup.factory, paused_id, 0, date(2026, 10, 1), setup.actor)
    assert issued.disposition == "INVOICED"
    paused = apply_targeted_action(
        setup.factory,
        setup.actor,
        paused_scenario,
        "pause",
        {},
        event_key="pause",
        on_date=date(2026, 10, 1),
        at_date=setup.at_date,
    )
    assert paused.state == "ACTIVE"
    with setup.factory() as db:
        interval = db.scalar(
            select(SubscriptionPause).where(
                SubscriptionPause.subscription_id == paused_id,
                SubscriptionPause.ends_on.is_(None),
            )
        )
        assert interval.starts_on == date(2026, 11, 1)
    paused_outcome = issuance.issue_due_period(
        setup.factory, paused_id, 1, date(2026, 11, 1), setup.actor
    )
    assert paused_outcome.disposition == "PAUSED"

    closed_scenario = DemoScenario(
        key="close-case",
        customer_id=setup.customer.id,
        plan_id=setup.plan.id,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 11, 1),
        payment_terms_days=14,
        lines=setup.lines,
        target="CLOSED",
    )
    closed_id = activate(closed_scenario)
    closed_invoice = issuance.issue_due_period(
        setup.factory, closed_id, 0, date(2026, 10, 1), setup.actor
    )
    assert closed_invoice.disposition == "INVOICED"
    closed = apply_targeted_action(
        setup.factory,
        setup.actor,
        closed_scenario,
        "close",
        {},
        event_key="close",
        on_date=date(2026, 11, 1),
        at_date=setup.at_date,
    )
    assert closed.state == "CLOSED"
    with setup.factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 2
        assert (
            db.scalar(
                select(BillingPeriod.disposition).where(
                    BillingPeriod.subscription_id == paused_id,
                    BillingPeriod.cycle_index == 1,
                )
            )
            == "PAUSED"
        )
