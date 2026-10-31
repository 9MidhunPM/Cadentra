"""Frozen fictional lifecycle and settlement intentions for the commerce demo.

This module only describes inputs. The coordinator replays them through the
subscription and billing adapters; it does not fabricate financial records.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from app.modules.billing.demo_import import DemoCycleIntent
from app.modules.subscriptions.demo_import import DemoScenario

from .profile import catalog, customers, plans

SCENARIO_COUNT = 192


@dataclass(frozen=True)
class ScheduledScenario(DemoScenario):
    """Adapter-compatible identity plus the coordinator's dated event schedule.

    The top-level import manifest must hash these scheduling fields as well as
    the subscription adapter's canonical identity fields.
    """

    draft_on: date
    quotation_on: date | None = None
    confirmed_on: date | None = None
    activated_on: date | None = None
    pause_on: date | None = None
    close_on: date | None = None
    bill_through: date | None = None
    quotation_valid_days: int = 30


def _months(day: date, offset: int) -> date:
    year, zero_month = divmod(day.year * 12 + day.month - 1 + offset, 12)
    month = zero_month + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def scenarios(anchor: date) -> list[ScheduledScenario]:
    """192 reproducible scenarios, with six monthly history buckets at most.

    Paused is an ACTIVE subscription with a pause interval, not another stored
    state. Closed terms have three original monthly cycles and are closed only
    after those outcomes exist. All daily/weekly/yearly plans occur in the
    unactivated cohort, so the historical replay stays bounded.
    """
    if type(anchor) is not date or not 2 <= anchor.year <= 9998:
        raise ValueError("A representable business date with one-year margin is required")
    customer_rows, product_rows, plan_rows = customers(), catalog(), plans(anchor)
    month_start = anchor.replace(day=1)
    history_start = _months(month_start, -5)
    result: list[ScheduledScenario] = []
    targets = (
        ["ACTIVE"] * 84 + ["PAUSED"] * 12 + ["DRAFT"] * 24
        + ["QUOTATION"] * 24 + ["CONFIRMED"] * 24 + ["CLOSED"] * 24
    )
    for index, target in enumerate(targets):
        historical = target in {"ACTIVE", "PAUSED", "CLOSED"}
        plan = plan_rows[index % (4 if historical else 8)]
        product = product_rows[(index * 7) % len(product_rows)]
        other = product_rows[(index * 7 + 11) % len(product_rows)]
        lines = [
            {
                "product_id": product["id"],
                "variant_id": product["variants"][index % 2]["id"],
                "quantity": 1 + index % 5,
            },
            {"product_id": other["id"], "variant_id": None, "quantity": 1 + index % 3},
        ]
        if historical:
            start = history_start + timedelta(days=index % 21)
            end = _months(start, 3 if target == "CLOSED" else 12)
            draft_on = start
            quotation_on = confirmed_on = activated_on = start
            # Pausing on a boundary requires that day's due period to be settled
            # first. The pause then starts on the next original boundary.
            pause_on = _months(start, 3) if target == "PAUSED" else None
            close_on = end if target == "CLOSED" else None
            bill_through = min(anchor, end - timedelta(days=1))
        else:
            start = anchor + timedelta(days=15 + index % 24)
            end = _months(start, 12 if plan["cadence"] == "YEARLY" else 6)
            draft_on = anchor - timedelta(days=2)
            quotation_on = anchor - timedelta(days=1) if target != "DRAFT" else None
            confirmed_on = anchor if target == "CONFIRMED" else None
            activated_on = pause_on = close_on = bill_through = None
        result.append(ScheduledScenario(
            key=f"commerce-{index + 1:03d}",
            customer_id=customer_rows[index % len(customer_rows)]["id"],
            plan_id=plan["id"],
            start_date=start,
            end_date=end,
            payment_terms_days=(7, 14, 30)[index % 3],
            lines=lines,
            target=target,
            draft_on=draft_on,
            quotation_on=quotation_on,
            confirmed_on=confirmed_on,
            activated_on=activated_on,
            pause_on=pause_on,
            close_on=close_on,
            bill_through=bill_through,
        ))
    return result


def cycle_intent(
    subscription_id: UUID,
    scenario_index: int,
    cycle_index: int,
    period_start: date,
    anchor: date,
) -> DemoCycleIntent:
    """Choose real service commands with no future payments or delivery claims.

    Twenty stable buckets yield one cancelled, one draft, three unpaid, three
    partially paid and twelve paid intentions. Amounts are computed solely by
    the billing adapter from the issued invoice's immutable total.
    """
    if (
        type(scenario_index) is not int or not 0 <= scenario_index < SCENARIO_COUNT
        or type(cycle_index) is not int or cycle_index < 0
        or type(period_start) is not date or type(anchor) is not date
        or period_start > anchor
    ):
        raise ValueError("A valid scenario, cycle and nonfuture period are required")
    bucket = (scenario_index * 7 + cycle_index) % 20
    invoice_state = "CANCELLED" if bucket == 0 else "DRAFT" if bucket == 1 else "CONFIRMED"
    payment_mode = "NONE" if bucket < 5 else "PARTIAL" if bucket < 8 else "PAID"
    if payment_mode == "PAID":
        payment_dates = (
            min(period_start + timedelta(days=2), anchor),
            min(period_start + timedelta(days=7), anchor),
        )
    elif payment_mode == "PARTIAL":
        payment_dates = (min(period_start + timedelta(days=3), anchor),)
    else:
        payment_dates = ()
    return DemoCycleIntent(
        subscription_id=subscription_id,
        cycle_index=cycle_index,
        issue_date=period_start,
        as_of=period_start,
        payment_mode=payment_mode,
        invoice_state=invoice_state,
        payment_dates=payment_dates,
        cancel_reason="Fictional demo order cancelled; no funds transferred.",
    )
