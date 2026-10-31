"""Persistent baseline shared by all feature modules.

Services own transactions and policy. Revision rows retain historical rule inputs;
only effective_until may be closed when appending a successor revision.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

MONEY = Numeric(18, 2)
RATE = Numeric(9, 4)
subscription_number_seq = Sequence("subscription_number_seq", metadata=Base.metadata)
invoice_number_seq = Sequence("invoice_number_seq", metadata=Base.metadata)


def fk(target: str, **kwargs):
    return mapped_column(PGUUID(as_uuid=True), ForeignKey(target, ondelete="RESTRICT"), **kwargs)


def money(default="0.00"):
    return mapped_column(MONEY, default=Decimal(default), server_default=text(default))


class Record:
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Customer(Record, Base):
    __tablename__ = "customers"
    display_name: Mapped[str] = mapped_column(String(200), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    billing_address: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


class User(Record, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN','STAFF','CUSTOMER')", name="role"),
        CheckConstraint(
            "(role = 'CUSTOMER' AND customer_id IS NOT NULL) OR (role <> 'CUSTOMER' AND customer_id IS NULL)",
            name="customer_role",
        ),
    )
    display_name: Mapped[str] = mapped_column(String(200))
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    customer_id: Mapped[UUID | None] = fk("customers.id", unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class SessionRecord(Record, Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[UUID] = fk("users.id", index=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(Record, Base):
    __tablename__ = "password_reset_tokens"
    user_id: Mapped[UUID] = fk("users.id", index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(Record, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("sales_price >= 0 AND cost_price >= 0", name="prices"),)
    name: Mapped[str] = mapped_column(String(200))
    product_type: Mapped[str] = mapped_column(String(80))
    sales_price: Mapped[Decimal] = money()
    cost_price: Mapped[Decimal] = money()
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class ProductVariant(Record, Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "attribute_name", "attribute_value"),)
    product_id: Mapped[UUID] = fk("products.id", index=True)
    attribute_name: Mapped[str] = mapped_column(String(100))
    attribute_value: Mapped[str] = mapped_column(String(200))
    price_delta: Mapped[Decimal] = money()
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Plan(Record, Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("base_fee >= 0 AND min_quantity >= 1", name="pricing"),
        CheckConstraint("cadence IN ('DAILY','WEEKLY','MONTHLY','YEARLY')", name="cadence"),
        CheckConstraint(
            "available_until IS NULL OR available_until > available_from", name="availability"
        ),
    )
    name: Mapped[str] = mapped_column(String(200))
    base_fee: Mapped[Decimal] = money()
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    cadence: Mapped[str] = mapped_column(String(16))
    min_quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    available_from: Mapped[date] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    allow_pause: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    allow_early_close: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    allow_renew: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    auto_close: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class TaxRule(Record, Base):
    __tablename__ = "tax_rules"


class TaxRuleRevision(Record, Base):
    __tablename__ = "tax_rule_revisions"
    __table_args__ = (
        UniqueConstraint("tax_rule_id", "effective_from"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_window"
        ),
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="valid_window"),
        CheckConstraint("rate_percent >= 0 AND rate_percent <= 100", name="rate"),
    )
    tax_rule_id: Mapped[UUID] = fk("tax_rules.id", index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(200))
    rate_percent: Mapped[Decimal] = mapped_column(RATE)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class TaxRevisionProduct(Base):
    __tablename__ = "tax_revision_products"
    tax_rule_revision_id: Mapped[UUID] = fk("tax_rule_revisions.id", primary_key=True)
    product_id: Mapped[UUID] = fk("products.id", primary_key=True)


class PlanTax(Base):
    __tablename__ = "plan_taxes"
    plan_id: Mapped[UUID] = fk("plans.id", primary_key=True)
    tax_rule_id: Mapped[UUID] = fk("tax_rules.id", primary_key=True)


class QuotationTemplate(Record, Base):
    __tablename__ = "quotation_templates"
    __table_args__ = (CheckConstraint("valid_days > 0", name="valid_days"),)
    name: Mapped[str] = mapped_column(String(200))
    plan_id: Mapped[UUID] = fk("plans.id")
    valid_days: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class QuotationTemplateLine(Record, Base):
    __tablename__ = "quotation_template_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity"),)
    template_id: Mapped[UUID] = fk("quotation_templates.id", index=True)
    product_id: Mapped[UUID] = fk("products.id")
    variant_id: Mapped[UUID | None] = fk("product_variants.id")
    quantity: Mapped[int] = mapped_column(Integer)


class Subscription(Record, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('DRAFT','QUOTATION','CONFIRMED','ACTIVE','CLOSED')", name="state"
        ),
        CheckConstraint("end_date > start_date", name="service_window"),
        CheckConstraint(
            "payment_terms_days >= 0 AND next_cycle_index >= 0 AND revision >= 1", name="counters"
        ),
        CheckConstraint(
            "close_effective_on IS NULL OR (close_effective_on >= start_date AND close_effective_on <= end_date)",
            name="close_date",
        ),
        Index("ix_subscriptions_service", "state", "start_date", "end_date"),
    )
    number: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        server_default=text("'SUB-' || lpad(nextval('subscription_number_seq')::text, 8, '0')"),
    )
    customer_id: Mapped[UUID] = fk("customers.id", index=True)
    plan_id: Mapped[UUID] = fk("plans.id")
    prior_subscription_id: Mapped[UUID | None] = fk("subscriptions.id")
    state: Mapped[str] = mapped_column(String(16), default="DRAFT", server_default="DRAFT")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quotation_valid_until: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    plan_snapshot: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    next_cycle_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    close_effective_on: Mapped[date | None] = mapped_column(Date)
    close_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class SubscriptionLine(Record, Base):
    __tablename__ = "subscription_lines"
    __table_args__ = (CheckConstraint("quantity > 0 AND unit_price >= 0", name="pricing"),)
    subscription_id: Mapped[UUID] = fk("subscriptions.id", index=True)
    product_id: Mapped[UUID] = fk("products.id")
    variant_id: Mapped[UUID | None] = fk("product_variants.id")
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = money()
    price_snapshot: Mapped[dict] = mapped_column(JSONB)
    selected_tax_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )


class SubscriptionPause(Record, Base):
    __tablename__ = "subscription_pauses"
    __table_args__ = (
        CheckConstraint("ends_on IS NULL OR ends_on > starts_on", name="window"),
        Index(
            "uq_subscription_pauses_open",
            "subscription_id",
            unique=True,
            postgresql_where=text("ends_on IS NULL"),
        ),
    )
    subscription_id: Mapped[UUID] = fk("subscriptions.id", index=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)


class BillingPeriod(Record, Base):
    __tablename__ = "billing_periods"
    __table_args__ = (
        UniqueConstraint("subscription_id", "cycle_index"),
        CheckConstraint("cycle_index >= 0 AND period_end > period_start", name="period"),
        CheckConstraint("disposition IN ('INVOICED','PAUSED')", name="disposition"),
    )
    subscription_id: Mapped[UUID] = fk("subscriptions.id")
    cycle_index: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    disposition: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str | None] = mapped_column(Text)


class DiscountRule(Record, Base):
    __tablename__ = "discount_rules"
    __table_args__ = (CheckConstraint("uses_count >= 0", name="uses"),)
    uses_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class DiscountRuleRevision(Record, Base):
    __tablename__ = "discount_rule_revisions"
    __table_args__ = (
        CheckConstraint("kind <> 'FIXED' OR value = round(value, 2)", name="fixed_precision"),
        UniqueConstraint("discount_rule_id", "effective_from"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_window"
        ),
        CheckConstraint("ends_on IS NULL OR ends_on > starts_on", name="valid_window"),
        CheckConstraint(
            "kind IN ('FIXED','PERCENT') AND scope IN ('SUBSCRIPTION','PRODUCTS')", name="kinds"
        ),
        CheckConstraint("value >= 0 AND (kind <> 'PERCENT' OR value <= 100)", name="value"),
        CheckConstraint(
            "min_purchase >= 0 AND min_quantity >= 0 AND (usage_limit IS NULL OR usage_limit >= 0)",
            name="minimums",
        ),
    )
    discount_rule_id: Mapped[UUID] = fk("discount_rules.id", index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    scope: Mapped[str] = mapped_column(String(16))
    min_purchase: Mapped[Decimal] = money()
    min_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class DiscountRevisionProduct(Base):
    __tablename__ = "discount_revision_products"
    discount_rule_revision_id: Mapped[UUID] = fk("discount_rule_revisions.id", primary_key=True)
    product_id: Mapped[UUID] = fk("products.id", primary_key=True)


class Invoice(Record, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','CONFIRMED','PAID','CANCELLED')", name="status"),
        CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND total >= 0 AND discount_total <= subtotal",
            name="amounts",
        ),
        CheckConstraint("total = subtotal - discount_total + tax_total", name="total"),
        CheckConstraint("due_date >= invoice_date", name="due_date"),
        Index("ix_invoices_status_due_customer", "status", "due_date", "customer_id"),
    )
    number: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        server_default=text("'INV-' || lpad(nextval('invoice_number_seq')::text, 8, '0')"),
    )
    subscription_id: Mapped[UUID] = fk("subscriptions.id")
    billing_period_id: Mapped[UUID] = fk("billing_periods.id", unique=True)
    customer_id: Mapped[UUID] = fk("customers.id")
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", server_default="DRAFT")
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    customer_snapshot: Mapped[dict] = mapped_column(JSONB)
    seller_snapshot: Mapped[dict] = mapped_column(JSONB)
    subtotal: Mapped[Decimal] = money()
    discount_total: Mapped[Decimal] = money()
    tax_total: Mapped[Decimal] = money()
    total: Mapped[Decimal] = money()
    discount_rule_id: Mapped[UUID | None] = fk("discount_rules.id")
    discount_rule_revision_id: Mapped[UUID | None] = fk("discount_rule_revisions.id")
    calculation_snapshot: Mapped[dict] = mapped_column(JSONB)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)


class InvoiceLine(Record, Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        UniqueConstraint("invoice_id", "stable_line_key"),
        CheckConstraint(
            "quantity > 0 AND unit_price >= 0 AND gross >= 0 AND discount >= 0 AND discount <= gross AND taxable_amount >= 0 AND tax_total >= 0 AND total >= 0",
            name="amounts",
        ),
        CheckConstraint(
            "taxable_amount = gross - discount AND total = taxable_amount + tax_total", name="total"
        ),
    )
    invoice_id: Mapped[UUID] = fk("invoices.id", index=True)
    stable_line_key: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    product_id: Mapped[UUID | None] = fk("products.id")
    variant_id: Mapped[UUID | None] = fk("product_variants.id")
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = money()
    gross: Mapped[Decimal] = money()
    discount: Mapped[Decimal] = money()
    taxable_amount: Mapped[Decimal] = money()
    tax_total: Mapped[Decimal] = money()
    total: Mapped[Decimal] = money()
    source_snapshot: Mapped[dict] = mapped_column(JSONB)


class InvoiceLineTax(Record, Base):
    __tablename__ = "invoice_line_taxes"
    __table_args__ = (
        CheckConstraint(
            "amount >= 0 AND rate_snapshot >= 0 AND rate_snapshot <= 100", name="amounts"
        ),
    )
    invoice_line_id: Mapped[UUID] = fk("invoice_lines.id", index=True)
    tax_rule_id: Mapped[UUID | None] = fk("tax_rules.id")
    tax_rule_revision_id: Mapped[UUID | None] = fk("tax_rule_revisions.id")
    name_snapshot: Mapped[str] = mapped_column(String(200))
    rate_snapshot: Mapped[Decimal] = mapped_column(RATE)
    amount: Mapped[Decimal] = money()


class DiscountRedemption(Record, Base):
    __tablename__ = "discount_redemptions"
    __table_args__ = (CheckConstraint("amount >= 0", name="amount"),)
    discount_rule_id: Mapped[UUID] = fk("discount_rules.id", index=True)
    invoice_id: Mapped[UUID] = fk("invoices.id", unique=True)
    amount: Mapped[Decimal] = money()


class Payment(Record, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("invoice_id", "request_key"),
        CheckConstraint("amount > 0", name="amount"),
        CheckConstraint(
            "method IN ('MANUAL','BANK_TRANSFER','UPI','CASH','CARD_EXTERNAL','OTHER')",
            name="method",
        ),
        Index("ix_payments_invoice_paid", "invoice_id", "paid_on"),
    )
    invoice_id: Mapped[UUID] = fk("invoices.id")
    method: Mapped[str] = mapped_column(String(24))
    amount: Mapped[Decimal] = money()
    paid_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    external_reference: Mapped[str | None] = mapped_column(String(200))
    request_key: Mapped[str] = mapped_column(String(200))
    request_payload_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[UUID] = fk("users.id")


class EmailOutbox(Record, Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint("kind IN ('RESET','INVOICE')", name="kind"),
        CheckConstraint("status IN ('PENDING','SENDING','SENT','FAILED')", name="status"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index("ix_email_outbox_due", "status", "next_attempt_at"),
    )
    kind: Mapped[str] = mapped_column(String(16))
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    payload: Mapped[dict] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", server_default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditEvent(Record, Base):
    __tablename__ = "audit_events"
    actor_user_id: Mapped[UUID | None] = fk("users.id")
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(80))
    redacted_details: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
