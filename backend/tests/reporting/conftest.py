"""Persist the audited reporting case through the actual PostgreSQL models."""

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.core import clock
from app.core.auth import Actor, Role
from app.models import (
    BillingPeriod,
    Customer,
    Invoice,
    InvoiceLine,
    Payment,
    Plan,
    Subscription,
    SubscriptionPause,
    User,
)


@pytest.fixture
def reporting_case(db_session, monkeypatch):
    case = json.loads(Path(__file__).with_name("summary_cases.json").read_text())
    today = date.fromisoformat(case["clock"]["business_date"])

    class FixedClock(clock.Clock):
        def today(self):
            return today

    monkeypatch.setattr(clock, "_clock", FixedClock())
    customers = {}
    for entry in case["customers"]:
        row = Customer(display_name=entry["display_name"], email=f"{uuid4()}@example.invalid")
        db_session.add(row)
        db_session.flush()
        customers[entry["key"]] = row
    admin = User(
        display_name="Reporting fixture admin",
        normalized_email=f"{uuid4()}@example.invalid",
        password_hash="test-fixture-not-a-login-password",
        role="ADMIN",
    )
    plan = Plan(
        name="Reporting fixture",
        base_fee=Decimal("0.00"),
        cadence="MONTHLY",
        available_from=date(2026, 1, 1),
        min_quantity=1,
    )
    db_session.add_all([admin, plan])
    db_session.flush()
    # Canonical portal reads require a valid frozen financial/scheduling snapshot.
    # These records use the fixture plan's actual zero fee; reports still read
    # stored invoice/payment amounts independently of this subscription metadata.
    plan_snapshot = {
        "schema_version": 1,
        "plan_id": str(plan.id),
        "name": plan.name,
        "base_fee": "0.00",
        "currency": "INR",
        "cadence": plan.cadence,
        "min_quantity": plan.min_quantity,
        "allow_pause": plan.allow_pause,
        "allow_early_close": plan.allow_early_close,
        "allow_renew": plan.allow_renew,
        "auto_close": plan.auto_close,
        "tax_rule_ids": [],
    }
    subscriptions = {}
    for entry in case["subscriptions"]:
        row = Subscription(
            customer_id=customers[entry["customer_key"]].id,
            plan_id=plan.id,
            state=entry["state"],
            plan_snapshot=dict(plan_snapshot),
            start_date=date.fromisoformat(entry["start_date"]),
            end_date=date.fromisoformat(entry["end_date"]),
            close_effective_on=date.fromisoformat(entry["close_effective_on"])
            if entry["close_effective_on"]
            else None,
        )
        db_session.add(row)
        db_session.flush()
        subscriptions[entry["key"]] = row
        for pause in entry["pauses"]:
            db_session.add(
                SubscriptionPause(
                    subscription_id=row.id,
                    starts_on=date.fromisoformat(pause["starts_on"]),
                    ends_on=date.fromisoformat(pause["ends_on"]) if pause["ends_on"] else None,
                )
            )
    invoices = {}
    for entry in case["invoices"]:
        invoice_date = date.fromisoformat(entry["invoice_date"])
        support = Subscription(
            customer_id=customers[entry["customer_key"]].id,
            plan_id=plan.id,
            state="CLOSED",
            plan_snapshot=dict(plan_snapshot),
            start_date=invoice_date,
            end_date=invoice_date + timedelta(days=1),
        )
        db_session.add(support)
        db_session.flush()
        period = BillingPeriod(
            subscription_id=support.id,
            cycle_index=0,
            period_start=invoice_date,
            period_end=invoice_date + timedelta(days=1),
            disposition="INVOICED",
        )
        db_session.add(period)
        db_session.flush()
        total = Decimal(entry["total"])
        row = Invoice(
            subscription_id=support.id,
            billing_period_id=period.id,
            customer_id=customers[entry["customer_key"]].id,
            status=entry["status"],
            invoice_date=invoice_date,
            due_date=date.fromisoformat(entry["due_date"]),
            subtotal=total,
            total=total,
            customer_snapshot={"display_name": "Fixture"},
            seller_snapshot={"name": "Brightloop"},
            calculation_snapshot={},
            cancellation_reason="Fixture cancellation" if entry["status"] == "CANCELLED" else None,
        )
        db_session.add(row)
        db_session.flush()
        invoices[entry["key"]] = row
        db_session.add(
            InvoiceLine(
                invoice_id=row.id,
                stable_line_key="L1",
                description="Fixture charge",
                quantity=1,
                unit_price=total,
                gross=total,
                discount=Decimal("0.00"),
                taxable_amount=total,
                total=total,
                source_snapshot={},
            )
        )
    for entry in case["payments"]:
        db_session.add(
            Payment(
                invoice_id=invoices[entry["invoice_key"]].id,
                method="MANUAL",
                amount=Decimal(entry["amount"]),
                paid_on=date.fromisoformat(entry["paid_on"]),
                request_key=entry["key"],
                request_payload_hash="0" * 64,
                created_by=admin.id,
            )
        )
    # Commit the nested savepoint; the shared conftest rolls back the outer test transaction.
    db_session.commit()
    return {
        "case": case,
        "customers": customers,
        "subscriptions": subscriptions,
        "invoices": invoices,
        "actor": Actor(admin.id, Role.ADMIN),
        "today": today,
    }
