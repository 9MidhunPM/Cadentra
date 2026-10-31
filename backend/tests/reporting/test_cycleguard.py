"""CycleGuard reads real PostgreSQL records without executing recovery actions."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.core.auth import Actor, Role, require_actor
from app.core.errors import DomainError
from app.models import BillingPeriod, EmailOutbox, Subscription, SubscriptionPause
from app.modules.reporting.cycleguard import list_alerts

pytestmark = pytest.mark.integration
URL = "/api/v1/reports/cycleguard"


def test_overdue_uses_unpaid_decimal_balance_and_customer_scope(db_session, reporting_case):
    result = list_alerts(db_session, reporting_case["actor"])
    assert result["as_of"] == "2026-11-02"
    assert result["total"] == 2
    assert [item["amount"] for item in result["items"]] == ["2970.16", "200.00"]
    assert [item["occurred_on"] for item in result["items"]] == ["2026-10-20", "2026-10-30"]
    assert all(item["currency"] == "INR" for item in result["items"])
    first = result["items"][0]
    assert first["id"] == f"OVERDUE:{reporting_case['invoices']['A_PARTIAL'].id}"
    assert first["record_type"] == "invoice"
    filtered = list_alerts(
        db_session, reporting_case["actor"], customer_id=reporting_case["customers"]["B"].id
    )
    assert filtered["total"] == 1
    assert filtered["items"][0]["record_id"] == str(reporting_case["invoices"]["B_OVERDUE"].id)
    assert list_alerts(db_session, reporting_case["actor"], customer_id=uuid4())["total"] == 0
    # A fully settled balance is excluded even if its status has not yet been updated.
    paid = reporting_case["invoices"]["A_PRIOR_PAID"]
    paid.status = "CONFIRMED"
    db_session.commit()
    assert list_alerts(db_session, reporting_case["actor"])["total"] == 2


def test_billing_due_calendar_pauses_closure_and_existing_outcomes(db_session, reporting_case):
    subscriptions = reporting_case["subscriptions"]
    paused = subscriptions["A_PAUSED"]
    paused.next_cycle_index = 1  # November 1 is inside the stored pause interval.
    closed = subscriptions["A_EFFECTIVELY_CLOSED"]
    closed.next_cycle_index = 2  # Next original boundary lies after effective closure.
    completed = subscriptions["B_ACTIVE"]
    db_session.add(
        BillingPeriod(
            subscription_id=completed.id,
            cycle_index=0,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 11, 1),
            disposition="PAUSED",
        )
    )
    db_session.commit()
    result = list_alerts(db_session, reporting_case["actor"], "BILLING_DUE")
    items = {item["record_id"]: item for item in result["items"]}
    assert str(completed.id) not in items
    assert str(closed.id) not in items
    assert str(subscriptions["A_FUTURE"].id) not in items
    assert str(subscriptions["A_DRAFT_SUB"].id) not in items
    assert str(subscriptions["A_CLOSED_SUB"].id) not in items
    assert str(subscriptions["A_EXPIRED"].id) in items  # Historical backlog still needs processing.
    assert items[str(paused.id)]["occurred_on"] == "2026-11-01"
    assert "paused" in items[str(paused.id)]["reason"].lower()
    assert "processing" in items[str(paused.id)]["reason"].lower()
    assert all(item["amount"] is None and item["currency"] is None for item in items.values())
    assert [(x["occurred_on"], x["id"]) for x in result["items"]] == sorted(
        (x["occurred_on"], x["id"]) for x in result["items"]
    )


def test_email_failures_never_expose_reset_or_raw_content(db_session, reporting_case):
    invoice = reporting_case["invoices"]["A_PARTIAL"]
    timestamp = datetime(2026, 11, 1, 20, tzinfo=UTC)
    for kind, status, error in [
        ("INVOICE", "FAILED", "SMTPAuthenticationError"),
        ("INVOICE", "FAILED", "raw-password-reset-token-secret@example.com"),
        ("RESET", "FAILED", "SMTPAuthenticationError"),
        ("INVOICE", "SENT", "SMTPAuthenticationError"),
    ]:
        db_session.add(
            EmailOutbox(
                kind=kind,
                aggregate_id=invoice.id,
                recipient="private@example.invalid",
                subject="Secret subject",
                payload={"token": "Never expose this"},
                dedupe_key=str(uuid4()),
                status=status,
                attempts=3,
                last_error=error,
                next_attempt_at=timestamp,
                created_at=timestamp,
            )
        )
    db_session.commit()
    result = list_alerts(db_session, reporting_case["actor"], "EMAIL_FAILED")
    assert result["total"] == 2
    assert {item["error_code"] for item in result["items"]} == {"SMTP_AUTH", "DELIVERY_FAILED"}
    assert all(item["attempts"] == 3 for item in result["items"])
    assert all(item["record_id"] == str(invoice.id) for item in result["items"])
    assert all(item["next_attempt_at"] == "2026-11-01T20:00:00+00:00" for item in result["items"])
    assert all(item["occurred_on"] == "2026-11-02" for item in result["items"])
    assert all(item["amount"] is None for item in result["items"])
    text = str(result)
    for secret in (
        "private@example.invalid",
        "Secret subject",
        "Never expose",
        "raw-password",
        "RESET",
    ):
        assert secret not in text
    assert (
        list_alerts(
            db_session,
            reporting_case["actor"],
            "EMAIL_FAILED",
            customer_id=reporting_case["customers"]["B"].id,
        )["total"]
        == 0
    )


@pytest.mark.parametrize("role,status", [("ADMIN", 200), ("STAFF", 200), ("CUSTOMER", 403)])
def test_http_role_and_pagination_contract(client, reporting_case, role, status):
    client.app.dependency_overrides[require_actor] = lambda: Actor(
        uuid4(), Role(role), reporting_case["customers"]["A"].id if role == "CUSTOMER" else None
    )
    response = client.get(URL, params={"page_size": 1})
    assert response.status_code == status
    if status == 200:
        data = response.json()
        assert set(data) == {"items", "total", "page", "page_size", "as_of"}
        assert data["total"] == 2 and len(data["items"]) == 1
        second = client.get(URL, params={"page": 2, "page_size": 1}).json()
        assert second["items"][0]["id"] != data["items"][0]["id"]
        assert set(data["items"][0]) == {
            "id",
            "kind",
            "record_id",
            "record_type",
            "label",
            "reason",
            "occurred_on",
            "amount",
            "currency",
            "attempts",
            "next_attempt_at",
            "error_code",
        }


def test_http_requires_authentication(client, reporting_case):
    assert client.get(URL).status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {"kind": "RESET"},
        {"page": 0},
        {"page_size": 101},
        {"page_size": 0},
        {"customer_id": "invalid"},
        {"page": 2**63, "page_size": 100},
    ],
)
def test_http_rejects_invalid_queries(client, reporting_case, params):
    client.app.dependency_overrides[require_actor] = lambda: reporting_case["actor"]
    assert client.get(URL, params=params).status_code == 422


def test_service_rechecks_role(db_session, reporting_case):
    with pytest.raises(DomainError) as error:
        list_alerts(db_session, Actor(uuid4(), Role.CUSTOMER, reporting_case["customers"]["A"].id))
    assert error.value.status_code == 403


def test_all_kinds_are_read_only_and_do_not_select_email_payload(db_session, reporting_case):
    before = db_session.execute(select(Subscription.id, Subscription.next_cycle_index)).all()
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        for kind in ("OVERDUE", "BILLING_DUE", "EMAIL_FAILED"):
            list_alerts(db_session, reporting_case["actor"], kind)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    assert all(statement.lstrip().startswith("SELECT") for statement in statements)
    assert not any(
        forbidden in statement
        for statement in statements
        for forbidden in (
            "email_outbox.payload",
            "email_outbox.recipient",
            "email_outbox.subject",
            "FOR UPDATE",
        )
    )
    assert (
        before == db_session.execute(select(Subscription.id, Subscription.next_cycle_index)).all()
    )
    assert not db_session.new and not db_session.dirty and not db_session.deleted


def test_billing_due_bulk_projects_five_thousand_subscriptions(db_session, reporting_case):
    template = reporting_case["subscriptions"]["A_ACTIVE"]
    rows = [
        dict(
            id=uuid4(),
            customer_id=template.customer_id,
            plan_id=template.plan_id,
            state="ACTIVE",
            start_date=date(2026, 11, 2),
            end_date=date(2026, 12, 2),
            plan_snapshot=template.plan_snapshot,
        )
        for _ in range(5000)
    ]
    db_session.execute(Subscription.__table__.insert(), rows)
    db_session.commit()
    db_session.connection()  # Begin the fixture savepoint before measuring report queries.
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        result = list_alerts(db_session, reporting_case["actor"], "BILLING_DUE", page_size=100)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    assert result["total"] >= 5000 and len(result["items"]) == 100
    assert len(statements) <= 24
    assert all(statement.lstrip().startswith("SELECT") for statement in statements)
    assert not any("subscriptions.plan_snapshot \n" in statement for statement in statements)


def test_original_month_end_and_pause_end_boundary(db_session, reporting_case):
    row = reporting_case["subscriptions"]["A_ACTIVE"]
    row.start_date, row.end_date = date(2026, 8, 31), date(2026, 12, 31)
    row.next_cycle_index = 2
    db_session.add(
        SubscriptionPause(
            subscription_id=row.id, starts_on=date(2026, 9, 30), ends_on=date(2026, 10, 31)
        )
    )
    db_session.commit()
    result = list_alerts(db_session, reporting_case["actor"], "BILLING_DUE")
    item = next(item for item in result["items"] if item["record_id"] == str(row.id))
    assert item["occurred_on"] == "2026-10-31"
    assert "paused" not in item["reason"].lower()
