from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from app.core.auth import Actor, Role
from app.core.errors import DomainError
from app.models import Invoice, Payment, SubscriptionPause
from app.modules.reporting.service import revenue_series, summary

pytestmark = pytest.mark.integration
START = date(2026, 10, 1)
END = date(2026, 11, 1)


@pytest.mark.parametrize("customer", [None, "A", "B"])
def test_summary_reconciles_stored_records(db_session, reporting_case, customer):
    fixture = reporting_case
    customer_id = fixture["customers"][customer].id if customer else None
    result = summary(db_session, fixture["actor"], START, END, customer_id)
    if customer in (None, "A"):
        expected = fixture["case"]["expectedSummary"][customer or "combined"]["data"]
        assert {key: result[key] for key in expected} == expected
    else:
        assert result["active_subscriptions"] == 1
        assert result["invoiced_gross_in_range"] == "200.00"
        assert result["cash_received_in_range"] == "0.00"
        assert result["outstanding_now"] == result["overdue_now"] == "200.00"
    assert result["metric_basis"]["date_range"] == "[from,to)"
    assert result["metric_basis"]["invoiced"] == "confirmed/paid, tax-inclusive by invoice_date"
    assert result["as_of"] == "2026-11-02"


def test_current_metrics_ignore_range_and_unknown_customer_is_zero(db_session, reporting_case):
    actor = reporting_case["actor"]
    current = summary(db_session, actor, START, END)
    empty_range = summary(db_session, actor, date(2025, 1, 1), date(2025, 2, 1))
    for key in ("active_subscriptions", "outstanding_now", "overdue_now", "overdue_invoice_count"):
        assert current[key] == empty_range[key]
    assert empty_range["invoiced_gross_in_range"] == empty_range["cash_received_in_range"] == "0.00"
    empty_customer = summary(db_session, actor, START, END, uuid4())
    assert empty_customer["active_subscriptions"] == empty_customer["overdue_invoice_count"] == 0
    assert empty_customer["outstanding_now"] == empty_customer["cash_received_in_range"] == "0.00"


def test_prior_invoice_with_multiple_payments_not_multiplied(db_session, reporting_case):
    result = summary(db_session, reporting_case["actor"], date(2026, 9, 1), END)
    assert result["invoiced_gross_in_range"] == "6870.16"
    assert result["cash_received_in_range"] == "3300.00"
    assert result["outstanding_now"] == "3570.16"


def test_active_pause_boundaries_and_open_interval(db_session, reporting_case):
    fixture = reporting_case
    pause = db_session.scalar(select(SubscriptionPause))
    pause.ends_on = fixture["today"]
    db_session.commit()
    assert summary(db_session, fixture["actor"], START, END)["active_subscriptions"] == 3
    pause.ends_on = None
    db_session.commit()
    assert summary(db_session, fixture["actor"], START, END)["active_subscriptions"] == 2
    pause.starts_on = fixture["today"] + timedelta(days=1)
    db_session.commit()
    assert summary(db_session, fixture["actor"], START, END)["active_subscriptions"] == 3


@pytest.mark.parametrize("role", [Role.STAFF, Role.ADMIN])
def test_allowed_roles(db_session, reporting_case, role):
    actor = Actor(reporting_case["actor"].id, role)
    assert summary(db_session, actor, START, END)["invoiced_gross_in_range"] == "5870.16"


def test_customer_role_forbidden_even_with_own_filter(db_session, reporting_case):
    customer_id = reporting_case["customers"]["A"].id
    actor = Actor(uuid4(), Role.CUSTOMER, customer_id)
    for function in (summary, revenue_series):
        with pytest.raises(DomainError) as error:
            function(db_session, actor, START, END, customer_id=customer_id)
        assert error.value.status_code == 403


@pytest.mark.parametrize(
    "start,end", [(END, START), (START, START), (START, START + timedelta(days=367))]
)
def test_invalid_ranges(db_session, reporting_case, start, end):
    for function in (summary, revenue_series):
        with pytest.raises(DomainError) as error:
            function(db_session, reporting_case["actor"], start, end)
        assert error.value.code == "INVALID_REPORT_RANGE"
        assert error.value.status_code == 422


def test_daily_series_reconciles_and_zero_fills(db_session, reporting_case):
    result = revenue_series(db_session, reporting_case["actor"], START, END)
    assert result == reporting_case["case"]["expectedDailySeries"]["data"]
    assert sum(Decimal(bucket["invoiced_gross"]) for bucket in result["buckets"]) == Decimal(
        "5870.16"
    )
    assert sum(Decimal(bucket["cash_received"]) for bucket in result["buckets"]) == Decimal(
        "3050.00"
    )


def test_monthly_series_partial_calendar_buckets(db_session, reporting_case):
    result = revenue_series(
        db_session, reporting_case["actor"], date(2026, 9, 30), date(2026, 11, 2), "MONTHLY"
    )
    assert result["buckets"] == [
        {
            "period_start": "2026-09-30",
            "period_end": "2026-10-01",
            "invoiced_gross": "1000.00",
            "cash_received": "250.00",
        },
        {
            "period_start": "2026-10-01",
            "period_end": "2026-11-01",
            "invoiced_gross": "5870.16",
            "cash_received": "3050.00",
        },
        {
            "period_start": "2026-11-01",
            "period_end": "2026-11-02",
            "invoiced_gross": "600.00",
            "cash_received": "600.00",
        },
    ]


def test_series_customer_filter_and_empty_range(db_session, reporting_case):
    result = revenue_series(
        db_session,
        reporting_case["actor"],
        START,
        END,
        "MONTHLY",
        reporting_case["customers"]["A"].id,
    )
    assert result["buckets"][0]["invoiced_gross"] == "5670.16"
    assert result["buckets"][0]["cash_received"] == "3050.00"
    empty = revenue_series(db_session, reporting_case["actor"], date(2025, 1, 1), date(2025, 1, 3))
    assert len(empty["buckets"]) == 2
    assert all(
        bucket["invoiced_gross"] == bucket["cash_received"] == "0.00" for bucket in empty["buckets"]
    )


def test_series_validation_and_maximum_range(db_session, reporting_case):
    with pytest.raises(DomainError) as error:
        revenue_series(db_session, reporting_case["actor"], START, END, "WEEKLY")
    assert error.value.code == "INVALID_REPORT_CADENCE"
    result = revenue_series(db_session, reporting_case["actor"], START, START + timedelta(days=366))
    assert len(result["buckets"]) == 366


def test_summary_single_read_statement_and_no_mutations(db_session, reporting_case):
    counts = [db_session.scalar(select(func.count(model.id))) for model in (Invoice, Payment)]
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        summary(db_session, reporting_case["actor"], START, END)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert len(statements) == 1
    assert statements[0].lstrip().startswith("SELECT")
    assert counts == [
        db_session.scalar(select(func.count(model.id))) for model in (Invoice, Payment)
    ]
