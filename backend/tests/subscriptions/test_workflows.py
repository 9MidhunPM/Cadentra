"""PostgreSQL lifecycle behavior, without a billing or authorization mock repository."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.auth import Actor
from app.core.errors import DomainError
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    Plan,
    Product,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    User,
)
from app.modules.subscriptions import workflows as w


@pytest.fixture
def setup(db_session, monkeypatch):
    clock = SimpleNamespace(today=lambda: date(2027, 2, 10))
    monkeypatch.setattr(w, "get_clock", lambda: clock)
    customer = Customer(display_name="Test customer", email="lifecycle@example.invalid")
    staff = User(
        display_name="Test staff",
        normalized_email=f"{uuid4()}@example.invalid",
        password_hash="test-only",
        role="STAFF",
    )
    plan = Plan(
        name="Monthly",
        base_fee=Decimal("0.00"),
        cadence="MONTHLY",
        min_quantity=3,
        available_from=date(2027, 1, 1),
        allow_pause=True,
        allow_early_close=True,
        allow_renew=True,
        auto_close=True,
    )
    product = Product(name="Seats", product_type="SERVICE", sales_price=Decimal("100.00"))
    db_session.add_all([customer, staff, plan, product])
    db_session.flush()
    actor = Actor(staff.id, "STAFF")
    payload = dict(
        customer_id=customer.id,
        plan_id=plan.id,
        start_date=date(2027, 1, 31),
        end_date=date(2027, 5, 1),
        payment_terms_days=14,
        lines=[dict(product_id=product.id, quantity=3)],
    )
    return SimpleNamespace(
        clock=clock, actor=actor, customer=customer, plan=plan, product=product, payload=payload
    )


def active(db, setup):
    row = w.create_subscription(db, setup.actor, setup.payload)
    for action, payload in (
        ("issue-quotation", {"valid_days": 7}),
        ("confirm", {}),
        ("activate", {}),
    ):
        w.apply_action_record(db, setup.actor, row.id, action, payload)
    return row


def outcome(db, row, index, start, end, disposition="INVOICED"):
    db.add(
        BillingPeriod(
            subscription_id=row.id,
            cycle_index=index,
            period_start=start,
            period_end=end,
            disposition=disposition,
        )
    )
    row.next_cycle_index = index + 1
    db.flush()


def reject(code, call):
    with pytest.raises(DomainError) as caught:
        call()
    assert caught.value.code == code


def test_template_copy_and_quote_price_isolation(db_session, setup):
    template = w.create_template(
        db_session,
        setup.actor,
        dict(name="Three seats", plan_id=setup.plan.id, valid_days=7, lines=setup.payload["lines"]),
    )
    payload = {key: value for key, value in setup.payload.items() if key != "lines"}
    row = w.create_subscription(db_session, setup.actor, {**payload, "template_id": template.id})
    w.apply_action_record(db_session, setup.actor, row.id, "issue-quotation", {"valid_days": 7})
    w.edit_template(
        db_session,
        setup.actor,
        template.id,
        {"lines": [dict(product_id=setup.product.id, quantity=9)]},
    )
    setup.product.sales_price = Decimal("900.00")
    setup.plan.base_fee = Decimal("20.00")
    db_session.flush()
    reject(
        "QUOTATION_PLAN_CHANGED",
        lambda: w.apply_action_record(db_session, setup.actor, row.id, "confirm", {}),
    )
    assert row.state == "QUOTATION"
    line = db_session.scalar(
        select(SubscriptionLine).where(SubscriptionLine.subscription_id == row.id)
    )
    assert (line.quantity, line.unit_price) == (3, Decimal("100.00"))
    assert row.plan_snapshot["base_fee"] == "0.00"
    w.apply_action_record(db_session, setup.actor, row.id, "revise", {})
    w.apply_action_record(db_session, setup.actor, row.id, "issue-quotation", {"valid_days": 7})
    w.apply_action_record(db_session, setup.actor, row.id, "confirm", {})
    assert row.plan_snapshot["base_fee"] == "20.00"
    assert line.unit_price == Decimal("900.00")
    assert row.state == "CONFIRMED"


def test_required_states_and_exclusive_quote_expiry(db_session, setup):
    row = w.create_subscription(db_session, setup.actor, setup.payload)
    reject(
        "INVALID_TRANSITION",
        lambda: w.apply_action_record(db_session, setup.actor, row.id, "activate", {}),
    )
    w.apply_action_record(db_session, setup.actor, row.id, "issue-quotation", {"valid_days": 1})
    setup.clock.today = lambda: date(2027, 2, 11)
    reject(
        "QUOTATION_EXPIRED",
        lambda: w.apply_action_record(db_session, setup.actor, row.id, "confirm", {}),
    )
    assert row.state == "QUOTATION"
    w.apply_action_record(db_session, setup.actor, row.id, "revise", {})
    assert row.state == "DRAFT"


def test_due_guard_then_frozen_next_cycle_quantity_edit(db_session, setup):
    row = active(db_session, setup)
    reject(
        "DUE_BILLING_PENDING",
        lambda: w.edit_subscription(
            db_session, setup.actor, row.id, {"lines": setup.payload["lines"]}
        ),
    )
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 28))
    setup.product.sales_price = Decimal("900.00")
    db_session.flush()
    w.edit_subscription(
        db_session, setup.actor, row.id, {"lines": [dict(product_id=setup.product.id, quantity=4)]}
    )
    line = db_session.scalar(
        select(SubscriptionLine).where(SubscriptionLine.subscription_id == row.id)
    )
    assert (line.quantity, line.unit_price) == (4, Decimal("100.00"))
    reject(
        "INVALID_TRANSITION",
        lambda: w.edit_subscription(
            db_session, setup.actor, row.id, {"end_date": date(2028, 1, 1)}
        ),
    )


def test_pending_pause_cancellation_and_processed_resume(db_session, setup):
    row = active(db_session, setup)
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 28))
    w.apply_action_record(db_session, setup.actor, row.id, "pause", {})
    w.apply_action_record(db_session, setup.actor, row.id, "resume", {})
    assert (
        db_session.scalar(
            select(SubscriptionPause).where(SubscriptionPause.subscription_id == row.id)
        )
        is None
    )
    assert (
        db_session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == row.id, AuditEvent.action == "pending_pause_cancelled"
            )
        )
        is not None
    )
    w.apply_action_record(db_session, setup.actor, row.id, "pause", {})
    outcome(db_session, row, 1, date(2027, 2, 28), date(2027, 3, 31), "PAUSED")
    setup.clock.today = lambda: date(2027, 2, 28)
    w.apply_action_record(db_session, setup.actor, row.id, "resume", {})
    pause = db_session.scalar(
        select(SubscriptionPause).where(SubscriptionPause.subscription_id == row.id)
    )
    assert pause.ends_on == date(2027, 3, 31)
    assert row.state == "ACTIVE" and row.next_cycle_index == 2


def test_late_worker_defers_closure_until_backlog_outcomes(db_session, setup):
    row = active(db_session, setup)
    result = w.process_lifecycle(db_session, date(2027, 5, 2))
    assert result["deferred"] == 1 and row.state == "ACTIVE"
    for index, start, end in [
        (0, date(2027, 1, 31), date(2027, 2, 28)),
        (1, date(2027, 2, 28), date(2027, 3, 31)),
        (2, date(2027, 3, 31), date(2027, 4, 30)),
        (3, date(2027, 4, 30), date(2027, 5, 1)),
    ]:
        outcome(db_session, row, index, start, end)
    w.process_lifecycle(db_session, date(2027, 5, 2))
    assert row.state == "CLOSED"


def test_policy_ownership_and_linked_renewal(db_session, setup):
    row = active(db_session, setup)
    stranger = Actor(setup.actor.id, "CUSTOMER", uuid4())
    reject(
        "NOT_FOUND",
        lambda: w.apply_action_record(
            db_session,
            stranger,
            row.id,
            "renew",
            {"start_date": date(2027, 5, 1), "end_date": date(2027, 8, 1)},
        ),
    )
    owner = Actor(setup.actor.id, "CUSTOMER", setup.customer.id)
    new = w.apply_action_record(
        db_session,
        owner,
        row.id,
        "renew",
        {"start_date": date(2027, 5, 1), "end_date": date(2027, 8, 1)},
    )
    assert new.state == "DRAFT" and new.prior_subscription_id == row.id and new.number != row.number
    reject(
        "RENEWAL_OVERLAP",
        lambda: w.apply_action_record(
            db_session,
            owner,
            row.id,
            "renew",
            {"start_date": date(2027, 5, 1), "end_date": date(2027, 8, 1)},
        ),
    )
    row.plan_snapshot = {**row.plan_snapshot, "allow_pause": False}
    db_session.flush()
    reject(
        "POLICY_FORBIDDEN", lambda: w.apply_action_record(db_session, owner, row.id, "pause", {})
    )


def test_started_pause_with_worker_backlog_is_not_erased(db_session, setup):
    row = active(db_session, setup)
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 28))
    w.apply_action_record(db_session, setup.actor, row.id, "pause", {})
    setup.clock.today = lambda: date(2027, 3, 10)
    w.apply_action_record(db_session, setup.actor, row.id, "resume", {})
    pause = db_session.scalar(
        select(SubscriptionPause).where(SubscriptionPause.subscription_id == row.id)
    )
    assert (pause.starts_on, pause.ends_on) == (date(2027, 2, 28), date(2027, 3, 31))
    assert row.next_cycle_index == 1
    assert (
        db_session.scalar(
            select(BillingPeriod).where(
                BillingPeriod.subscription_id == row.id, BillingPeriod.cycle_index == 1
            )
        )
        is None
    )


def test_expired_without_autoclose_and_staff_close_override(db_session, setup):
    row = active(db_session, setup)
    row.plan_snapshot = {**row.plan_snapshot, "auto_close": False, "allow_early_close": False}
    for index, start, end in [
        (0, date(2027, 1, 31), date(2027, 2, 28)),
        (1, date(2027, 2, 28), date(2027, 3, 31)),
        (2, date(2027, 3, 31), date(2027, 4, 30)),
        (3, date(2027, 4, 30), date(2027, 5, 1)),
    ]:
        outcome(db_session, row, index, start, end)
    setup.clock.today = lambda: date(2027, 5, 2)
    w.process_lifecycle(db_session, setup.clock.today())
    assert row.state == "ACTIVE"
    assert "close" in w.allowed_actions(db_session, setup.actor, row, setup.clock.today())
    w.apply_action_record(db_session, setup.actor, row.id, "close", {})
    assert row.state == "CLOSED"


def test_early_close_schedules_next_boundary_without_erasing_period(db_session, setup):
    row = active(db_session, setup)
    reject(
        "DUE_BILLING_PENDING",
        lambda: w.apply_action_record(db_session, setup.actor, row.id, "close", {}),
    )
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 28))
    w.apply_action_record(db_session, setup.actor, row.id, "close", {"reason": "Requested"})
    assert row.state == "ACTIVE" and row.close_effective_on == date(2027, 2, 28)
    w.process_lifecycle(db_session, date(2027, 2, 28))
    assert row.state == "CLOSED"
    assert (
        db_session.scalar(select(BillingPeriod).where(BillingPeriod.subscription_id == row.id))
        is not None
    )


def test_template_explicit_empty_or_null_is_never_copy_fallback(db_session, setup):
    template = w.create_template(
        db_session,
        setup.actor,
        dict(name="Three", plan_id=setup.plan.id, valid_days=7, lines=setup.payload["lines"]),
    )
    for lines in ([], None, [dict(product_id=setup.product.id, quantity=2)]):
        with pytest.raises(DomainError):
            w.create_subscription(
                db_session,
                setup.actor,
                {**setup.payload, "template_id": template.id, "lines": lines},
            )
    draft = w.create_subscription(
        db_session,
        setup.actor,
        {
            **setup.payload,
            "template_id": template.id,
            "lines": [dict(product_id=setup.product.id, quantity=4)],
        },
    )
    line = db_session.scalar(
        select(SubscriptionLine).where(SubscriptionLine.subscription_id == draft.id)
    )
    assert line.quantity == 4


@pytest.mark.parametrize("action", ["pause", "resume", "close", "renew", "confirm"])
def test_every_action_checks_customer_ownership_before_policy(db_session, setup, action):
    row = active(db_session, setup)
    before = len(list(db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == row.id))))
    reject(
        "NOT_FOUND",
        lambda: w.apply_action_record(
            db_session, Actor(setup.actor.id, "CUSTOMER", uuid4()), row.id, action, {}
        ),
    )
    assert row.state == "ACTIVE" and row.next_cycle_index == 0
    assert (
        len(list(db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == row.id))))
        == before
    )


def test_public_action_ownership_precedes_malformed_payload(db_session, setup):
    from app.modules.subscriptions.service import apply_action

    row = active(db_session, setup)
    stranger = Actor(setup.actor.id, "CUSTOMER", uuid4())
    before = len(list(db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == row.id))))
    with pytest.raises(DomainError) as caught:
        apply_action(db_session, stranger, row.id, "renew", {"role": "ADMIN", "start_date": "bad"})
    assert (caught.value.code, caught.value.status_code) == ("NOT_FOUND", 404)
    assert row.state == "ACTIVE" and row.revision == 4
    assert (
        db_session.scalar(select(Subscription).where(Subscription.prior_subscription_id == row.id))
        is None
    )
    assert (
        len(list(db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == row.id))))
        == before
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"start_date": "not-a-date", "end_date": "2027-08-01"},
        {"start_date": "2027-05-01", "end_date": "2027-08-01", "role": "ADMIN"},
    ],
)
def test_public_customer_actions_reject_staff_and_invalid_renewal(db_session, setup, payload):
    from app.modules.subscriptions.service import apply_action

    row = active(db_session, setup)
    owner = Actor(setup.actor.id, "CUSTOMER", setup.customer.id)
    with pytest.raises(DomainError) as forbidden:
        apply_action(db_session, owner, row.id, "confirm", {})
    assert forbidden.value.status_code == 403
    with pytest.raises(DomainError) as invalid:
        apply_action(db_session, owner, row.id, "renew", payload)
    assert invalid.value.status_code == 422
    assert (
        db_session.scalar(select(Subscription).where(Subscription.prior_subscription_id == row.id))
        is None
    )
    assert row.state == "ACTIVE"


def test_public_renewal_returns_safe_linked_draft_without_reopening_closed_term(db_session, setup):
    import json

    from app.modules.subscriptions.service import (
        apply_action,
        get_subscription_for_actor,
        process_lifecycle,
    )

    setup.payload["end_date"] = date(2027, 2, 1)
    row = active(db_session, setup)
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 1))
    assert process_lifecycle(db_session, date(2027, 2, 10))["closed"] == 1
    owner = Actor(setup.actor.id, "CUSTOMER", setup.customer.id)
    setup.product.cost_price = Decimal("999.00")
    setup.product.notes = "private-staff-note"
    db_session.flush()
    detail = apply_action(
        db_session, owner, row.id, "renew", {"start_date": "2027-02-10", "end_date": "2027-05-10"}
    )
    assert detail["state"] == "DRAFT" and detail["prior_subscription_id"] == str(row.id)
    assert detail["id"] != str(row.id) and detail["customer_id"] == str(setup.customer.id)
    assert row.state == "CLOSED"
    assert get_subscription_for_actor(db_session, owner, row.id)["state"] == "CLOSED"
    serialized = json.dumps(detail)
    assert "cost_price" not in serialized and "private-staff-note" not in serialized
    with pytest.raises(DomainError) as hidden:
        get_subscription_for_actor(db_session, Actor(setup.actor.id, "CUSTOMER", uuid4()), row.id)
    assert hidden.value.status_code == 404


@pytest.mark.parametrize("ended_by", ["expiry", "scheduled_close"])
def test_active_edit_without_remaining_cycle_is_rejected_without_mutation(
    db_session, setup, ended_by
):
    row = active(db_session, setup)
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 28))
    if ended_by == "expiry":
        row.end_date = date(2027, 2, 28)
        row.plan_snapshot = {**row.plan_snapshot, "auto_close": False}
        setup.clock.today = lambda: date(2027, 3, 1)
    else:
        row.close_effective_on = date(2027, 2, 28)
    db_session.flush()
    line = db_session.scalar(
        select(SubscriptionLine).where(SubscriptionLine.subscription_id == row.id)
    )
    before = (row.revision, line.quantity, line.unit_price)
    audit_ids = list(
        db_session.scalars(select(AuditEvent.id).where(AuditEvent.entity_id == row.id))
    )
    with pytest.raises(DomainError) as caught:
        w.edit_subscription(
            db_session,
            setup.actor,
            row.id,
            {"lines": [{"product_id": setup.product.id, "quantity": 4}]},
        )
    assert (caught.value.code, caught.value.status_code) == ("CYCLE_OUT_OF_RANGE", 409)
    assert (row.revision, line.quantity, line.unit_price) == before
    assert (
        list(db_session.scalars(select(AuditEvent.id).where(AuditEvent.entity_id == row.id)))
        == audit_ids
    )


def test_template_copy_and_edit_use_one_coherent_locked_version(monkeypatch):
    """Two real sessions overlap: pg_stat_activity proves the editor waits on a row lock."""
    import os
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import create_engine, delete, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from app.models import QuotationTemplate, QuotationTemplateLine

    url = os.environ["TEST_DATABASE_URL"]
    assert make_url(url).get_backend_name() == "postgresql"
    assert make_url(url).database.endswith("_test")
    engine = create_engine(url)
    token = str(uuid4())
    with Session(engine) as db, db.begin():
        customer = Customer(display_name="Template race", email=f"{token}@example.invalid")
        user = User(
            display_name="Template race staff",
            normalized_email=f"race-{token}@example.invalid",
            password_hash="test-only",
            role="STAFF",
        )
        first = Product(
            name="Original product", product_type="SERVICE", sales_price=Decimal("100.00")
        )
        second = Product(
            name="Replacement product", product_type="SERVICE", sales_price=Decimal("200.00")
        )
        plan_a = Plan(
            name="Original race plan",
            base_fee=Decimal("0.00"),
            cadence="MONTHLY",
            available_from=date(2027, 1, 1),
            min_quantity=1,
        )
        plan_b = Plan(
            name="Replacement race plan",
            base_fee=Decimal("0.00"),
            cadence="MONTHLY",
            available_from=date(2027, 1, 1),
            min_quantity=1,
        )
        db.add_all([customer, user, first, second, plan_a, plan_b])
        db.flush()
        actor = Actor(user.id, "STAFF")
        template = w.create_template(
            db,
            actor,
            {
                "name": "Race template",
                "plan_id": plan_a.id,
                "valid_days": 7,
                "lines": [{"product_id": first.id, "quantity": 1}],
            },
        )
        ids = SimpleNamespace(
            customer=customer.id,
            user=user.id,
            first=first.id,
            second=second.id,
            plan_a=plan_a.id,
            plan_b=plan_b.id,
            template=template.id,
        )
    locked, release, editor_ready = threading.Event(), threading.Event(), threading.Event()
    editor_pid = []
    original = w._template

    def held_template(db, identifier, *, lock=False):
        row = original(db, identifier, lock=lock)
        if threading.current_thread().name.startswith("copy"):
            locked.set()
            if not release.wait(8):
                raise AssertionError("Test did not release the copier")
        return row

    monkeypatch.setattr(w, "_template", held_template)

    def copy():
        with Session(engine) as db, db.begin():
            result = w.create_subscription(
                db,
                actor,
                {
                    "customer_id": ids.customer,
                    "plan_id": ids.plan_a,
                    "template_id": ids.template,
                    "start_date": date(2027, 2, 1),
                    "end_date": date(2027, 5, 1),
                    "payment_terms_days": 0,
                },
            )
            return result.id

    def edit():
        with Session(engine) as db, db.begin():
            editor_pid.append(db.scalar(text("SELECT pg_backend_pid()")))
            editor_ready.set()
            w.edit_template(
                db,
                actor,
                ids.template,
                {"plan_id": ids.plan_b, "lines": [{"product_id": ids.second, "quantity": 2}]},
            )

    try:
        with (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="copy") as copier,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="editor") as editor,
        ):
            copied = copier.submit(copy)
            try:
                assert locked.wait(5), "Copier never reached template read"
                edited = editor.submit(edit)
                assert editor_ready.wait(5)
                waiting = False
                deadline = time.monotonic() + 5
                with engine.connect() as observer:
                    while time.monotonic() < deadline and not edited.done():
                        waiting = observer.scalar(
                            text(
                                "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"
                            ),
                            {"pid": editor_pid[0]},
                        )
                        if waiting:
                            break
                        observer.commit()
                        threading.Event().wait(0.02)
                assert waiting, "Concurrent template edit did not wait for the copier's row lock"
            finally:
                release.set()
            copied_id = copied.result(timeout=5)
            edited.result(timeout=5)
        with Session(engine) as db:
            row = db.get(Subscription, copied_id)
            assert row.plan_id == ids.plan_a
            assert (
                db.scalar(
                    select(SubscriptionLine.product_id).where(
                        SubscriptionLine.subscription_id == copied_id
                    )
                )
                == ids.first
            )
            assert db.get(QuotationTemplate, ids.template).plan_id == ids.plan_b
        # A lock read must refresh an already cached template, not only lock its row.
        with Session(engine, expire_on_commit=False) as cached:
            prior = cached.get(QuotationTemplate, ids.template)
            assert prior.plan_id == ids.plan_b
            cached.commit()
            with Session(engine) as db, db.begin():
                w.edit_template(
                    db,
                    actor,
                    ids.template,
                    {"plan_id": ids.plan_a, "lines": [{"product_id": ids.first, "quantity": 1}]},
                )
            with cached.begin():
                assert original(cached, ids.template, lock=True).plan_id == ids.plan_a
    finally:
        release.set()
        with Session(engine) as db, db.begin():
            child_ids = select(Subscription.id).where(Subscription.customer_id == ids.customer)
            db.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == ids.user))
            db.execute(
                delete(SubscriptionLine).where(SubscriptionLine.subscription_id.in_(child_ids))
            )
            db.execute(delete(Subscription).where(Subscription.customer_id == ids.customer))
            db.execute(
                delete(QuotationTemplateLine).where(
                    QuotationTemplateLine.template_id == ids.template
                )
            )
            db.execute(delete(QuotationTemplate).where(QuotationTemplate.id == ids.template))
            db.execute(delete(Product).where(Product.id.in_([ids.first, ids.second])))
            db.execute(delete(Plan).where(Plan.id.in_([ids.plan_a, ids.plan_b])))
            db.execute(delete(User).where(User.id == ids.user))
            db.execute(delete(Customer).where(Customer.id == ids.customer))
        engine.dispose()


def test_template_validity_is_copied_and_survives_plan_refreshes(db_session, setup):
    template = w.create_template(
        db_session,
        setup.actor,
        {
            "name": "Fourteen days",
            "plan_id": setup.plan.id,
            "valid_days": 14,
            "lines": setup.payload["lines"],
        },
    )
    payload = {key: value for key, value in setup.payload.items() if key != "lines"}
    draft = w.create_subscription(db_session, setup.actor, {**payload, "template_id": template.id})
    identifier = draft.id
    db_session.expire_all()
    draft = db_session.get(Subscription, identifier)
    assert draft.plan_snapshot["quotation_valid_days"] == 14
    w.edit_template(db_session, setup.actor, template.id, {"valid_days": 30})
    w.edit_subscription(db_session, setup.actor, draft.id, {"payment_terms_days": 10})
    assert draft.plan_snapshot["quotation_valid_days"] == 14
    w.apply_action_record(db_session, setup.actor, draft.id, "issue-quotation", {"valid_days": 21})
    assert draft.plan_snapshot["quotation_valid_days"] == 21
    assert draft.quotation_valid_until == date(2027, 3, 3)
    w.apply_action_record(db_session, setup.actor, draft.id, "confirm", {})
    assert draft.plan_snapshot["quotation_valid_days"] == 21


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_fee", Decimal("20.00")),
        ("currency", "USD"),
        ("cadence", "DAILY"),
        ("min_quantity", 4),
        ("allow_pause", False),
        ("allow_early_close", False),
        ("allow_renew", False),
        ("auto_close", False),
    ],
)
def test_confirmation_requires_review_after_contractual_plan_changes(
    db_session, setup, field, value
):
    row = w.create_subscription(db_session, setup.actor, setup.payload)
    w.apply_action_record(db_session, setup.actor, row.id, "issue-quotation", {"valid_days": 7})
    quote = dict(row.plan_snapshot)
    revision = row.revision
    setattr(setup.plan, field, value)
    db_session.flush()
    with pytest.raises(DomainError) as caught:
        w.apply_action_record(db_session, setup.actor, row.id, "confirm", {})
    assert (caught.value.code, caught.value.status_code) == ("QUOTATION_PLAN_CHANGED", 409)
    assert row.state == "QUOTATION" and row.plan_snapshot == quote and row.revision == revision


def test_confirmation_compares_tax_id_set_and_keeps_quoted_product_prices(db_session, setup):
    from app.models import PlanTax, TaxRule

    rules = [TaxRule(), TaxRule()]
    db_session.add_all(rules)
    db_session.flush()
    db_session.add_all([PlanTax(plan_id=setup.plan.id, tax_rule_id=rule.id) for rule in rules])
    db_session.flush()
    row = w.create_subscription(db_session, setup.actor, setup.payload)
    w.apply_action_record(db_session, setup.actor, row.id, "issue-quotation", {"valid_days": 7})
    row.plan_snapshot = {
        **row.plan_snapshot,
        "tax_rule_ids": list(reversed(row.plan_snapshot["tax_rule_ids"])),
    }
    setup.product.sales_price = Decimal("700.00")
    db_session.flush()
    w.apply_action_record(db_session, setup.actor, row.id, "confirm", {})
    assert row.state == "CONFIRMED"
    line = db_session.scalar(
        select(SubscriptionLine).where(SubscriptionLine.subscription_id == row.id)
    )
    assert line.unit_price == Decimal("100.00")
    second = w.create_subscription(db_session, setup.actor, setup.payload)
    w.apply_action_record(db_session, setup.actor, second.id, "issue-quotation", {"valid_days": 7})
    db_session.delete(db_session.get(PlanTax, (setup.plan.id, rules[0].id)))
    db_session.flush()
    reject(
        "QUOTATION_PLAN_CHANGED",
        lambda: w.apply_action_record(db_session, setup.actor, second.id, "confirm", {}),
    )


def test_resume_cannot_turn_expiry_into_an_original_schedule_boundary(db_session, setup):
    setup.payload["end_date"] = date(2027, 2, 15)
    setup.clock.today = lambda: date(2027, 1, 31)
    row = active(db_session, setup)
    pause = SubscriptionPause(subscription_id=row.id, starts_on=date(2027, 1, 31))
    db_session.add(pause)
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 15), "PAUSED")
    setup.clock.today = lambda: date(2027, 2, 1)
    revision = row.revision
    audit_ids = list(
        db_session.scalars(select(AuditEvent.id).where(AuditEvent.entity_id == row.id))
    )
    assert w.get_cycle_bounds(w._schedule(row), row.next_cycle_index) is None
    assert "resume" not in w.allowed_actions(db_session, setup.actor, row, setup.clock.today())
    with pytest.raises(DomainError) as caught:
        w.apply_action_record(db_session, setup.actor, row.id, "resume", {})
    assert (caught.value.code, caught.value.status_code) == ("CYCLE_OUT_OF_RANGE", 409)
    assert pause.ends_on is None and row.revision == revision and row.next_cycle_index == 1
    assert (
        list(db_session.scalars(select(AuditEvent.id).where(AuditEvent.entity_id == row.id)))
        == audit_ids
    )
    assert (
        db_session.scalar(
            select(BillingPeriod.disposition).where(BillingPeriod.subscription_id == row.id)
        )
        == "PAUSED"
    )


@pytest.mark.parametrize("role", ["STAFF", "CUSTOMER"])
@pytest.mark.parametrize(
    "flag,action",
    [("allow_pause", "pause"), ("allow_early_close", "close"), ("allow_renew", "renew")],
)
def test_disabled_frozen_policy_rejects_staff_and_actual_customer_owner(
    db_session, setup, role, flag, action
):
    from app.modules.subscriptions.service import apply_action

    setattr(setup.plan, flag, False)
    db_session.flush()
    row = active(db_session, setup)
    assert row.plan_snapshot[flag] is False
    outcome(db_session, row, 0, date(2027, 1, 31), date(2027, 2, 28))
    actor = setup.actor
    if role == "CUSTOMER":
        customer_user = User(
            display_name="Policy owner",
            normalized_email=f"policy-owner-{uuid4()}@example.invalid",
            password_hash="test-only",
            role="CUSTOMER",
            customer_id=setup.customer.id,
        )
        db_session.add(customer_user)
        db_session.flush()
        actor = Actor(customer_user.id, customer_user.role, customer_user.customer_id)
    assert action not in w.allowed_actions(db_session, actor, row, setup.clock.today())
    revision = row.revision
    audits = set(db_session.scalars(select(AuditEvent.id).where(AuditEvent.entity_id == row.id)))
    lines = list(
        db_session.execute(
            select(SubscriptionLine.id, SubscriptionLine.quantity, SubscriptionLine.unit_price)
            .where(SubscriptionLine.subscription_id == row.id)
            .order_by(SubscriptionLine.id)
        )
    )
    payload = {"start_date": "2027-05-01", "end_date": "2027-08-01"} if action == "renew" else {}
    with pytest.raises(DomainError) as caught:
        apply_action(db_session, actor, row.id, action, payload)
    assert (caught.value.code, caught.value.status_code) == ("POLICY_FORBIDDEN", 409)
    assert row.state == "ACTIVE" and row.revision == revision and row.next_cycle_index == 1
    assert (
        set(db_session.scalars(select(AuditEvent.id).where(AuditEvent.entity_id == row.id)))
        == audits
    )
    assert (
        list(
            db_session.execute(
                select(SubscriptionLine.id, SubscriptionLine.quantity, SubscriptionLine.unit_price)
                .where(SubscriptionLine.subscription_id == row.id)
                .order_by(SubscriptionLine.id)
            )
        )
        == lines
    )
    assert (
        db_session.scalar(
            select(SubscriptionPause.id).where(SubscriptionPause.subscription_id == row.id)
        )
        is None
    )
    assert (
        db_session.scalar(
            select(Subscription.id).where(Subscription.prior_subscription_id == row.id)
        )
        is None
    )
