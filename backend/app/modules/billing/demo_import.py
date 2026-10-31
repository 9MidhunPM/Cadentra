"""Private, scoped demo billing orchestration over the normal financial services.

The CLI owner supplies a historical-clock context and handles dataset provenance,
discount isolation and worker coordination. This module never changes the clock,
inserts financial rows directly, runs global billing or sends email.
"""

import json
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.demo_contacts import is_demo_contact
from app.core.errors import DomainError
from app.core.money import money, money_string
from app.models import AuditEvent, BillingPeriod, EmailOutbox, Invoice, Payment, Subscription, User

from .invoice_schemas import PaymentWrite
from .invoices import cancel_invoice, confirm_invoice, record_payment
from .issuance import issue_due_period

Factory = Callable[[], Session]
DateContext = Callable[[date], AbstractContextManager]


def _invalid(message: str):
    raise DomainError("DEMO_IMPORT_INVALID", message, 422)


def _reconcile(message: str):
    raise DomainError("DEMO_IMPORT_RECONCILIATION", message)


@dataclass(frozen=True)
class DemoScope:
    namespace: str
    customer_ids: frozenset[UUID]
    subscription_ids: frozenset[UUID]

    def __post_init__(self):
        if (
            not isinstance(self.namespace, str)
            or not self.namespace.strip()
            or len(self.namespace) > 128
            or any(ord(char) < 32 or ord(char) == 127 for char in self.namespace)
        ):
            _invalid("A nonempty demo namespace of at most 128 characters is required.")
        for values in (self.customer_ids, self.subscription_ids):
            if type(values) is not frozenset or any(type(value) is not UUID for value in values):
                _invalid("Demo scope IDs must be frozensets of UUIDs.")


@dataclass(frozen=True)
class DemoCycleIntent:
    subscription_id: UUID
    cycle_index: int
    issue_date: date
    as_of: date
    payment_mode: Literal["NONE", "PARTIAL", "PAID"] = "NONE"
    invoice_state: Literal["CONFIRMED", "DRAFT", "CANCELLED"] = "CONFIRMED"
    payment_dates: tuple[date, ...] = ()
    cancel_reason: str = "Imported demo cancellation"

    def __post_init__(self):
        if type(self.subscription_id) is not UUID:
            _invalid("A subscription UUID is required.")
        if type(self.cycle_index) is not int or self.cycle_index < 0:
            _invalid("A nonnegative integer cycle index is required.")
        if type(self.issue_date) is not date or type(self.as_of) is not date:
            _invalid("Issue and service dates must be dates, not datetimes or strings.")
        if self.as_of > self.issue_date:
            _invalid("The service cutoff cannot follow the issue date.")
        if type(self.payment_mode) is not str or self.payment_mode not in {
            "NONE",
            "PARTIAL",
            "PAID",
        }:
            _invalid("Unknown demo payment mode.")
        if type(self.invoice_state) is not str or self.invoice_state not in {
            "CONFIRMED",
            "DRAFT",
            "CANCELLED",
        }:
            _invalid("Unknown demo invoice state.")
        if self.invoice_state != "CONFIRMED" and self.payment_mode != "NONE":
            _invalid("Draft and cancelled invoices cannot request payments.")
        if (
            type(self.payment_dates) is not tuple
            or any(type(day) is not date for day in self.payment_dates)
            or len(self.payment_dates) > (2 if self.payment_mode == "PAID" else 1)
            or any(day < self.issue_date for day in self.payment_dates)
        ):
            _invalid("Supply at most two payment dates, on or after issue; two require PAID.")
        if (
            not isinstance(self.cancel_reason, str)
            or not self.cancel_reason.strip()
            or len(self.cancel_reason) > 10000
        ):
            _invalid("A nonempty cancellation reason of at most 10000 characters is required.")


@dataclass(frozen=True)
class DemoCycleReceipt:
    period_id: UUID
    invoice_id: UUID | None
    status: str
    total: str
    paid: str
    balance: str


@contextmanager
def _on_date(at_date: DateContext, day: date):
    with at_date(day):
        if get_clock().today() != day:
            _invalid("The supplied historical context did not set the core business date.")
        yield


def _declaration_id(scope: DemoScope, intent: DemoCycleIntent) -> UUID:
    key = json.dumps(
        [scope.namespace, str(intent.subscription_id), intent.cycle_index],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return uuid5(NAMESPACE_URL, "cadentra/demo-billing/" + key)


def _scoped_subscription(db: Session, actor, scope, intent, *, lock=False):
    if intent.subscription_id not in scope.subscription_ids:
        raise DomainError("DEMO_SCOPE_VIOLATION", "Subscription is outside this demo scope.", 403)
    query = select(Subscription).where(Subscription.id == intent.subscription_id)
    subscription = db.scalar(query.with_for_update() if lock else query)
    user = db.get(User, actor.id)
    if user is None or not user.active or user.role not in {"ADMIN", "STAFF"}:
        raise DomainError("FORBIDDEN", "A persisted active operator is required.", 403)
    if subscription is None or subscription.customer_id not in scope.customer_ids:
        raise DomainError("DEMO_SCOPE_VIOLATION", "Customer is outside this demo scope.", 403)
    marker = db.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.entity_type == "CUSTOMER",
            AuditEvent.entity_id == subscription.customer_id,
            AuditEvent.action == "DEMO_CONTACT_NO_EMAIL",
        )
        .limit(1)
    )
    if marker is None or not is_demo_contact(db, customer_id=subscription.customer_id):
        raise DomainError("DEMO_SCOPE_VIOLATION", "Customer lacks durable demo provenance.", 403)
    return subscription


def _declare(factory, actor, scope, intent):
    declaration_id = _declaration_id(scope, intent)
    with factory() as db, db.begin():
        subscription = _scoped_subscription(db, actor, scope, intent, lock=True)
        canonical = {
            "schema_version": 1,
            "namespace": scope.namespace,
            "customer_id": str(subscription.customer_id),
            "subscription_id": str(intent.subscription_id),
            "cycle_index": intent.cycle_index,
            "issue_date": intent.issue_date.isoformat(),
            "as_of": intent.as_of.isoformat(),
            "payment_mode": intent.payment_mode,
            "invoice_state": intent.invoice_state,
            "payment_dates": [day.isoformat() for day in intent.payment_dates],
            "cancel_reason": intent.cancel_reason,
        }
        existing = db.get(AuditEvent, declaration_id)
        if existing is not None:
            if (
                existing.entity_type != "SUBSCRIPTION"
                or existing.entity_id != subscription.id
                or existing.action != "DEMO_BILLING_INTENT"
                or existing.redacted_details != canonical
            ):
                raise DomainError("DEMO_INTENT_CONFLICT", "The declared demo intent has changed.")
            return
        prior_period = db.scalar(
            select(BillingPeriod.id).where(
                BillingPeriod.subscription_id == subscription.id,
                BillingPeriod.cycle_index == intent.cycle_index,
            )
        )
        if prior_period is not None:
            raise DomainError(
                "DEMO_INTENT_CONFLICT", "Cannot adopt a period created before this intent."
            )
        db.add(
            AuditEvent(
                id=declaration_id,
                actor_user_id=actor.id,
                entity_type="SUBSCRIPTION",
                entity_id=subscription.id,
                action="DEMO_BILLING_INTENT",
                redacted_details=canonical,
            )
        )


def _read_rows(factory, actor, scope, intent, period_id):
    with factory() as db:
        subscription = _scoped_subscription(db, actor, scope, intent)
        period = db.get(BillingPeriod, period_id)
        if (
            period is None
            or period.subscription_id != subscription.id
            or period.cycle_index != intent.cycle_index
        ):
            _reconcile("The returned period does not match this demo intent.")
        invoice = db.scalar(select(Invoice).where(Invoice.billing_period_id == period.id))
        if invoice is None:
            if period.disposition != "PAUSED" or intent.payment_mode != "NONE":
                _reconcile("The demo intent has no matching invoice.")
            return period, None, ()
        if (
            invoice.subscription_id != subscription.id
            or invoice.customer_id != subscription.customer_id
            or invoice.invoice_date != intent.issue_date
        ):
            _reconcile("The invoice does not match this demo scope or issue date.")
        if (
            db.scalar(
                select(EmailOutbox.id)
                .where(EmailOutbox.kind == "INVOICE", EmailOutbox.aggregate_id == invoice.id)
                .limit(1)
            )
            is not None
        ):
            _reconcile("A demo invoice must not have an email outbox entry.")
        payments = tuple(db.scalars(select(Payment).where(Payment.invoice_id == invoice.id)))
        return period, invoice, payments


def _commands(scope, intent, total):
    if intent.payment_mode == "NONE" or total == 0:
        return ()
    if intent.payment_mode == "PARTIAL" and total < Decimal("0.02"):
        _invalid("A partial demo payment needs a total of at least two cents.")
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        if total == Decimal("0.01"):
            amounts = (total,)
        else:
            first = min(
                max(money(total * Decimal("0.40")), Decimal("0.01")), total - Decimal("0.01")
            )
            amounts = (first,) if intent.payment_mode == "PARTIAL" else (first, total - first)
    dates = intent.payment_dates or (intent.issue_date,)
    identity = _declaration_id(scope, intent).hex
    return tuple(
        PaymentWrite(
            method="MANUAL",
            amount=money_string(amount),
            paid_on=dates[min(index, len(dates) - 1)],
            note=f"Demo dataset import ({scope.namespace}); no funds transfer.",
            external_reference=f"demo:{identity}:{index}",
            request_key=f"demo:{identity}:{index}",
        )
        for index, amount in enumerate(amounts)
    )


def _matching_payments(payments, commands):
    expected = {command.request_key: command for command in commands}
    if len({row.request_key for row in payments}) != len(payments):
        _reconcile("Demo payments contain duplicate request keys.")
    for row in payments:
        command = expected.get(row.request_key)
        if command is None or any(
            getattr(row, field) != getattr(command, field)
            for field in ("method", "amount", "paid_on", "note", "external_reference")
        ):
            _reconcile("An existing payment differs from the declared demo commands.")


def replay_demo_cycle(factory, actor, scope, intent, *, at_date):
    """Declare once, issue/replay, settle through services and verify real rows."""
    if not isinstance(scope, DemoScope) or not isinstance(intent, DemoCycleIntent):
        _invalid("Validated demo scope and cycle intent are required.")
    if not callable(at_date):
        _invalid("A historical business-date context factory is required.")
    if getattr(actor, "role", None) not in ("ADMIN", "STAFF"):
        raise DomainError("FORBIDDEN", "Only operators can import demo billing.", 403)
    with _on_date(at_date, intent.issue_date):
        _declare(factory, actor, scope, intent)
        outcome = issue_due_period(
            factory, intent.subscription_id, intent.cycle_index, intent.as_of, actor=actor
        )
    if outcome.period_id is None:
        _reconcile("The declared demo cycle is not due.")
    period, invoice, payments = _read_rows(factory, actor, scope, intent, outcome.period_id)
    if invoice is None:
        return DemoCycleReceipt(period.id, None, "PAUSED", "0.00", "0.00", "0.00")
    commands = _commands(scope, intent, invoice.total)
    _matching_payments(payments, commands)
    if intent.invoice_state == "DRAFT":
        if invoice.status != "DRAFT" or payments:
            _reconcile("The declared draft invoice has already changed state.")
    elif intent.invoice_state == "CANCELLED":
        if payments or (
            invoice.status == "CANCELLED"
            and invoice.cancellation_reason != intent.cancel_reason.strip()
        ):
            _reconcile("The declared cancellation does not match this invoice.")
        if invoice.status != "CANCELLED":
            try:
                with _on_date(at_date, intent.issue_date), factory() as db:
                    cancel_invoice(db, actor, invoice.id, intent.cancel_reason)
            except DomainError as error:
                if error.code != "INVALID_TRANSITION":
                    raise
                # A concurrent matching cancellation may have committed first.
                _, latest, latest_payments = _read_rows(factory, actor, scope, intent, period.id)
                if (
                    latest.status != "CANCELLED"
                    or latest_payments
                    or latest.cancellation_reason != intent.cancel_reason.strip()
                ):
                    raise
    else:
        with _on_date(at_date, intent.issue_date), factory() as db:
            confirm_invoice(db, actor, invoice.id)
        for command in commands:
            with _on_date(at_date, command.paid_on), factory() as db:
                record_payment(db, actor, invoice.id, command)
    period, invoice, payments = _read_rows(factory, actor, scope, intent, period.id)
    _matching_payments(payments, commands)
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        paid = money(sum((row.amount for row in payments), Decimal("0.00")))
        expected_paid = money(sum((command.amount for command in commands), Decimal("0.00")))
        balance = money(invoice.total - paid)
    expected_status = intent.invoice_state
    if expected_status == "CONFIRMED" and paid == invoice.total:
        expected_status = "PAID"
    if (
        len(payments) != len(commands)
        or paid != expected_paid
        or paid > invoice.total
        or invoice.status != expected_status
    ):
        _reconcile("Persisted demo totals or status do not match the declared commands.")
    return DemoCycleReceipt(
        period.id,
        invoice.id,
        invoice.status,
        money_string(invoice.total),
        money_string(paid),
        money_string(balance),
    )
