"""shared subscription platform baseline

Revision ID: 0001
Revises: None
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SEQUENCE subscription_number_seq")
    op.execute("CREATE SEQUENCE invoice_number_seq")
    op.create_table(
        "customers",
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column(
            "billing_address",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(op.f("ix_customers_display_name"), "customers", ["display_name"], unique=False)
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=False)
    op.create_table(
        "discount_rules",
        sa.Column("uses_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("uses_count >= 0", name=op.f("ck_discount_rules_uses")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_rules")),
    )
    op.create_table(
        "email_outbox",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('RESET','INVOICE')", name=op.f("ck_email_outbox_kind")),
        sa.CheckConstraint(
            "status IN ('PENDING','SENDING','SENT','FAILED')", name=op.f("ck_email_outbox_status")
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_email_outbox_attempts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_email_outbox_dedupe_key")),
    )
    op.create_index(
        "ix_email_outbox_due", "email_outbox", ["status", "next_attempt_at"], unique=False
    )
    op.create_table(
        "plans",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "base_fee",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("min_quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("available_from", sa.Date(), nullable=False),
        sa.Column("available_until", sa.Date(), nullable=True),
        sa.Column("allow_pause", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "allow_early_close", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("allow_renew", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("auto_close", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cadence IN ('DAILY','WEEKLY','MONTHLY','YEARLY')", name=op.f("ck_plans_cadence")
        ),
        sa.CheckConstraint(
            "available_until IS NULL OR available_until > available_from",
            name=op.f("ck_plans_availability"),
        ),
        sa.CheckConstraint("base_fee >= 0 AND min_quantity >= 1", name=op.f("ck_plans_pricing")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
    )
    op.create_table(
        "products",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("product_type", sa.String(length=80), nullable=False),
        sa.Column(
            "sales_price",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "cost_price",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sales_price >= 0 AND cost_price >= 0", name=op.f("ck_products_prices")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_table(
        "tax_rules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tax_rules")),
    )
    op.create_table(
        "discount_rule_revisions",
        sa.Column("discount_rule_id", sa.UUID(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column(
            "min_purchase",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("min_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('FIXED','PERCENT') AND scope IN ('SUBSCRIPTION','PRODUCTS')",
            name=op.f("ck_discount_rule_revisions_kinds"),
        ),
        sa.CheckConstraint(
            "value >= 0 AND (kind <> 'PERCENT' OR value <= 100)",
            name=op.f("ck_discount_rule_revisions_value"),
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name=op.f("ck_discount_rule_revisions_effective_window"),
        ),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on > starts_on",
            name=op.f("ck_discount_rule_revisions_valid_window"),
        ),
        sa.CheckConstraint(
            "min_purchase >= 0 AND min_quantity >= 0 AND (usage_limit IS NULL OR usage_limit >= 0)",
            name=op.f("ck_discount_rule_revisions_minimums"),
        ),
        sa.ForeignKeyConstraint(
            ["discount_rule_id"],
            ["discount_rules.id"],
            name=op.f("fk_discount_rule_revisions_discount_rule_id_discount_rules"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_rule_revisions")),
        sa.UniqueConstraint(
            "discount_rule_id",
            "effective_from",
            name=op.f("uq_discount_rule_revisions_discount_rule_id"),
        ),
    )
    op.create_index(
        op.f("ix_discount_rule_revisions_discount_rule_id"),
        "discount_rule_revisions",
        ["discount_rule_id"],
        unique=False,
    )
    op.create_table(
        "plan_taxes",
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("tax_rule_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_plan_taxes_plan_id_plans"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tax_rule_id"],
            ["tax_rules.id"],
            name=op.f("fk_plan_taxes_tax_rule_id_tax_rules"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("plan_id", "tax_rule_id", name=op.f("pk_plan_taxes")),
    )
    op.create_table(
        "product_variants",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("attribute_name", sa.String(length=100), nullable=False),
        sa.Column("attribute_value", sa.String(length=200), nullable=False),
        sa.Column(
            "price_delta",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_variants_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_variants")),
        sa.UniqueConstraint(
            "product_id",
            "attribute_name",
            "attribute_value",
            name=op.f("uq_product_variants_product_id"),
        ),
    )
    op.create_index(
        op.f("ix_product_variants_product_id"), "product_variants", ["product_id"], unique=False
    )
    op.create_table(
        "quotation_templates",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("valid_days > 0", name=op.f("ck_quotation_templates_valid_days")),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name=op.f("fk_quotation_templates_plan_id_plans"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_templates")),
    )
    op.create_table(
        "subscriptions",
        sa.Column(
            "number",
            sa.String(length=40),
            server_default=sa.text(
                "'SUB-' || lpad(nextval('subscription_number_seq')::text, 8, '0')"
            ),
            nullable=False,
        ),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("prior_subscription_id", sa.UUID(), nullable=True),
        sa.Column("state", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("quotation_valid_until", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column(
            "plan_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("next_cycle_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("close_effective_on", sa.Date(), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('DRAFT','QUOTATION','CONFIRMED','ACTIVE','CLOSED')",
            name=op.f("ck_subscriptions_state"),
        ),
        sa.CheckConstraint(
            "close_effective_on IS NULL OR (close_effective_on >= start_date AND close_effective_on <= end_date)",
            name=op.f("ck_subscriptions_close_date"),
        ),
        sa.CheckConstraint("end_date > start_date", name=op.f("ck_subscriptions_service_window")),
        sa.CheckConstraint(
            "payment_terms_days >= 0 AND next_cycle_index >= 0 AND revision >= 1",
            name=op.f("ck_subscriptions_counters"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_subscriptions_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name=op.f("fk_subscriptions_plan_id_plans"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prior_subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_subscriptions_prior_subscription_id_subscriptions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint("number", name=op.f("uq_subscriptions_number")),
    )
    op.create_index(
        op.f("ix_subscriptions_customer_id"), "subscriptions", ["customer_id"], unique=False
    )
    op.create_index(
        "ix_subscriptions_service",
        "subscriptions",
        ["state", "start_date", "end_date"],
        unique=False,
    )
    op.create_table(
        "tax_rule_revisions",
        sa.Column("tax_rule_id", sa.UUID(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("rate_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name=op.f("ck_tax_rule_revisions_effective_window"),
        ),
        sa.CheckConstraint(
            "rate_percent >= 0 AND rate_percent <= 100", name=op.f("ck_tax_rule_revisions_rate")
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name=op.f("ck_tax_rule_revisions_valid_window"),
        ),
        sa.ForeignKeyConstraint(
            ["tax_rule_id"],
            ["tax_rules.id"],
            name=op.f("fk_tax_rule_revisions_tax_rule_id_tax_rules"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tax_rule_revisions")),
        sa.UniqueConstraint(
            "tax_rule_id", "effective_from", name=op.f("uq_tax_rule_revisions_tax_rule_id")
        ),
    )
    op.create_index(
        op.f("ix_tax_rule_revisions_tax_rule_id"),
        "tax_rule_revisions",
        ["tax_rule_id"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role = 'CUSTOMER' AND customer_id IS NOT NULL) OR (role <> 'CUSTOMER' AND customer_id IS NULL)",
            name=op.f("ck_users_customer_role"),
        ),
        sa.CheckConstraint("role IN ('ADMIN','STAFF','CUSTOMER')", name=op.f("ck_users_role")),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_users_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("customer_id", name=op.f("uq_users_customer_id")),
        sa.UniqueConstraint("normalized_email", name=op.f("uq_users_normalized_email")),
    )
    op.create_table(
        "audit_events",
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "redacted_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"], unique=False)
    op.create_table(
        "billing_periods",
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("disposition", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "disposition IN ('INVOICED','PAUSED')", name=op.f("ck_billing_periods_disposition")
        ),
        sa.CheckConstraint(
            "cycle_index >= 0 AND period_end > period_start", name=op.f("ck_billing_periods_period")
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_billing_periods_subscription_id_subscriptions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_periods")),
        sa.UniqueConstraint(
            "subscription_id", "cycle_index", name=op.f("uq_billing_periods_subscription_id")
        ),
    )
    op.create_table(
        "discount_revision_products",
        sa.Column("discount_rule_revision_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["discount_rule_revision_id"],
            ["discount_rule_revisions.id"],
            name=op.f(
                "fk_discount_revision_products_discount_rule_revision_id_discount_rule_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_discount_revision_products_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "discount_rule_revision_id", "product_id", name=op.f("pk_discount_revision_products")
        ),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False
    )
    op.create_table(
        "quotation_template_lines",
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_quotation_template_lines_quantity")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_quotation_template_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["quotation_templates.id"],
            name=op.f("fk_quotation_template_lines_template_id_quotation_templates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_quotation_template_lines_variant_id_product_variants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_template_lines")),
    )
    op.create_index(
        op.f("ix_quotation_template_lines_template_id"),
        "quotation_template_lines",
        ["template_id"],
        unique=False,
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("csrf_token", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "subscription_lines",
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "unit_price",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("price_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "selected_tax_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0 AND unit_price >= 0", name=op.f("ck_subscription_lines_pricing")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_subscription_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_subscription_lines_subscription_id_subscriptions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_subscription_lines_variant_id_product_variants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_lines")),
    )
    op.create_index(
        op.f("ix_subscription_lines_subscription_id"),
        "subscription_lines",
        ["subscription_id"],
        unique=False,
    )
    op.create_table(
        "subscription_pauses",
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on > starts_on", name=op.f("ck_subscription_pauses_window")
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_subscription_pauses_subscription_id_subscriptions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_pauses")),
    )
    op.create_index(
        op.f("ix_subscription_pauses_subscription_id"),
        "subscription_pauses",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        "uq_subscription_pauses_open",
        "subscription_pauses",
        ["subscription_id"],
        unique=True,
        postgresql_where=sa.text("ends_on IS NULL"),
    )
    op.create_table(
        "tax_revision_products",
        sa.Column("tax_rule_revision_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_tax_revision_products_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tax_rule_revision_id"],
            ["tax_rule_revisions.id"],
            name=op.f("fk_tax_revision_products_tax_rule_revision_id_tax_rule_revisions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "tax_rule_revision_id", "product_id", name=op.f("pk_tax_revision_products")
        ),
    )
    op.create_table(
        "invoices",
        sa.Column(
            "number",
            sa.String(length=40),
            server_default=sa.text("'INV-' || lpad(nextval('invoice_number_seq')::text, 8, '0')"),
            nullable=False,
        ),
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("billing_period_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("customer_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("seller_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "subtotal",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "discount_total",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "tax_total",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "total",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("discount_rule_id", sa.UUID(), nullable=True),
        sa.Column("discount_rule_revision_id", sa.UUID(), nullable=True),
        sa.Column("calculation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','PAID','CANCELLED')", name=op.f("ck_invoices_status")
        ),
        sa.CheckConstraint("due_date >= invoice_date", name=op.f("ck_invoices_due_date")),
        sa.CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND total >= 0 AND discount_total <= subtotal",
            name=op.f("ck_invoices_amounts"),
        ),
        sa.CheckConstraint(
            "total = subtotal - discount_total + tax_total", name=op.f("ck_invoices_total")
        ),
        sa.ForeignKeyConstraint(
            ["billing_period_id"],
            ["billing_periods.id"],
            name=op.f("fk_invoices_billing_period_id_billing_periods"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_invoices_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["discount_rule_id"],
            ["discount_rules.id"],
            name=op.f("fk_invoices_discount_rule_id_discount_rules"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["discount_rule_revision_id"],
            ["discount_rule_revisions.id"],
            name=op.f("fk_invoices_discount_rule_revision_id_discount_rule_revisions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_invoices_subscription_id_subscriptions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("billing_period_id", name=op.f("uq_invoices_billing_period_id")),
        sa.UniqueConstraint("number", name=op.f("uq_invoices_number")),
    )
    op.create_index(
        "ix_invoices_status_due_customer",
        "invoices",
        ["status", "due_date", "customer_id"],
        unique=False,
    )
    op.create_table(
        "discount_redemptions",
        sa.Column("discount_rule_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_discount_redemptions_amount")),
        sa.ForeignKeyConstraint(
            ["discount_rule_id"],
            ["discount_rules.id"],
            name=op.f("fk_discount_redemptions_discount_rule_id_discount_rules"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_discount_redemptions_invoice_id_invoices"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_redemptions")),
        sa.UniqueConstraint("invoice_id", name=op.f("uq_discount_redemptions_invoice_id")),
    )
    op.create_index(
        op.f("ix_discount_redemptions_discount_rule_id"),
        "discount_redemptions",
        ["discount_rule_id"],
        unique=False,
    )
    op.create_table(
        "invoice_lines",
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("stable_line_key", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "unit_price",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "gross",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "discount",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "taxable_amount",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "tax_total",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "total",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("source_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0 AND unit_price >= 0 AND gross >= 0 AND discount >= 0 AND discount <= gross AND taxable_amount >= 0 AND tax_total >= 0 AND total >= 0",
            name=op.f("ck_invoice_lines_amounts"),
        ),
        sa.CheckConstraint(
            "taxable_amount = gross - discount AND total = taxable_amount + tax_total",
            name=op.f("ck_invoice_lines_total"),
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_invoice_lines_invoice_id_invoices"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_invoice_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_invoice_lines_variant_id_product_variants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_lines")),
        sa.UniqueConstraint(
            "invoice_id", "stable_line_key", name=op.f("uq_invoice_lines_invoice_id")
        ),
    )
    op.create_index(
        op.f("ix_invoice_lines_invoice_id"), "invoice_lines", ["invoice_id"], unique=False
    )
    op.create_table(
        "payments",
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("external_reference", sa.String(length=200), nullable=True),
        sa.Column("request_key", sa.String(length=200), nullable=False),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('MANUAL','BANK_TRANSFER','UPI','CASH','CARD_EXTERNAL','OTHER')",
            name=op.f("ck_payments_method"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payments_amount")),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_payments_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_payments_invoice_id_invoices"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("invoice_id", "request_key", name=op.f("uq_payments_invoice_id")),
    )
    op.create_index("ix_payments_invoice_paid", "payments", ["invoice_id", "paid_on"], unique=False)
    op.create_table(
        "invoice_line_taxes",
        sa.Column("invoice_line_id", sa.UUID(), nullable=False),
        sa.Column("tax_rule_id", sa.UUID(), nullable=True),
        sa.Column("tax_rule_revision_id", sa.UUID(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("rate_snapshot", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=18, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount >= 0 AND rate_snapshot >= 0 AND rate_snapshot <= 100",
            name=op.f("ck_invoice_line_taxes_amounts"),
        ),
        sa.ForeignKeyConstraint(
            ["invoice_line_id"],
            ["invoice_lines.id"],
            name=op.f("fk_invoice_line_taxes_invoice_line_id_invoice_lines"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tax_rule_id"],
            ["tax_rules.id"],
            name=op.f("fk_invoice_line_taxes_tax_rule_id_tax_rules"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tax_rule_revision_id"],
            ["tax_rule_revisions.id"],
            name=op.f("fk_invoice_line_taxes_tax_rule_revision_id_tax_rule_revisions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_line_taxes")),
    )
    op.create_index(
        op.f("ix_invoice_line_taxes_invoice_line_id"),
        "invoice_line_taxes",
        ["invoice_line_id"],
        unique=False,
    )

    op.execute("""
        CREATE FUNCTION guard_rule_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE rule_id uuid; locked_id uuid; overlap_exists boolean;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Rule revisions are retained' USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'UPDATE' AND (
            (to_jsonb(NEW) - 'effective_until') IS DISTINCT FROM
              (to_jsonb(OLD) - 'effective_until') OR
            OLD.effective_until IS NOT NULL OR NEW.effective_until IS NULL
          ) THEN
            RAISE EXCEPTION 'Revision payload is immutable; only close an open interval'
              USING ERRCODE = '23514';
          END IF;
          rule_id := (to_jsonb(NEW) ->> TG_ARGV[1])::uuid;
          EXECUTE format('SELECT id FROM %I WHERE id = $1 FOR UPDATE', TG_ARGV[0])
            INTO locked_id USING rule_id;
          EXECUTE format(
            'SELECT EXISTS(SELECT 1 FROM %I WHERE %I = $1 AND id <> $2 AND '
            'daterange(effective_from,effective_until,''[)'') && daterange($3,$4,''[)''))',
            TG_TABLE_NAME, TG_ARGV[1])
            INTO overlap_exists USING rule_id, NEW.id, NEW.effective_from, NEW.effective_until;
          IF overlap_exists THEN
            RAISE EXCEPTION 'Rule revision intervals overlap' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION guard_revision_membership() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE revision_created_at timestamptz;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Rule revision memberships are immutable' USING ERRCODE = '23514';
          END IF;
          EXECUTE format('SELECT created_at FROM %I WHERE id = $1', TG_ARGV[0])
            INTO revision_created_at USING (to_jsonb(NEW) ->> TG_ARGV[1])::uuid;
          IF revision_created_at IS DISTINCT FROM transaction_timestamp() THEN
            RAISE EXCEPTION 'Add memberships in the transaction creating their revision'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $$
    """)
    for table, parent, parent_field in (
        ("tax_rule_revisions", "tax_rules", "tax_rule_id"),
        ("discount_rule_revisions", "discount_rules", "discount_rule_id"),
    ):
        op.execute(
            f"CREATE TRIGGER guard_revision BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION guard_rule_revision('{parent}', '{parent_field}')"
        )
    for table, revision_table, revision_field in (
        ("tax_revision_products", "tax_rule_revisions", "tax_rule_revision_id"),
        ("discount_revision_products", "discount_rule_revisions", "discount_rule_revision_id"),
    ):
        op.execute(
            f"CREATE TRIGGER guard_membership BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION guard_revision_membership('{revision_table}', '{revision_field}')"
        )


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS guard_rule_revision() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_revision_membership() CASCADE")
    op.drop_index(op.f("ix_invoice_line_taxes_invoice_line_id"), table_name="invoice_line_taxes")
    op.drop_table("invoice_line_taxes")
    op.drop_index("ix_payments_invoice_paid", table_name="payments")
    op.drop_table("payments")
    op.drop_index(op.f("ix_invoice_lines_invoice_id"), table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index(
        op.f("ix_discount_redemptions_discount_rule_id"), table_name="discount_redemptions"
    )
    op.drop_table("discount_redemptions")
    op.drop_index("ix_invoices_status_due_customer", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("tax_revision_products")
    op.drop_index(
        "uq_subscription_pauses_open",
        table_name="subscription_pauses",
        postgresql_where=sa.text("ends_on IS NULL"),
    )
    op.drop_index(op.f("ix_subscription_pauses_subscription_id"), table_name="subscription_pauses")
    op.drop_table("subscription_pauses")
    op.drop_index(op.f("ix_subscription_lines_subscription_id"), table_name="subscription_lines")
    op.drop_table("subscription_lines")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_expires_at"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(
        op.f("ix_quotation_template_lines_template_id"), table_name="quotation_template_lines"
    )
    op.drop_table("quotation_template_lines")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_table("discount_revision_products")
    op.drop_table("billing_periods")
    op.drop_index(op.f("ix_audit_events_entity_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("users")
    op.drop_index(op.f("ix_tax_rule_revisions_tax_rule_id"), table_name="tax_rule_revisions")
    op.drop_table("tax_rule_revisions")
    op.drop_index("ix_subscriptions_service", table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_customer_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("quotation_templates")
    op.drop_index(op.f("ix_product_variants_product_id"), table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_table("plan_taxes")
    op.drop_index(
        op.f("ix_discount_rule_revisions_discount_rule_id"), table_name="discount_rule_revisions"
    )
    op.drop_table("discount_rule_revisions")
    op.drop_table("tax_rules")
    op.drop_table("products")
    op.drop_table("plans")
    op.drop_index("ix_email_outbox_due", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_table("discount_rules")
    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    op.drop_index(op.f("ix_customers_display_name"), table_name="customers")
    op.drop_table("customers")
    op.execute("DROP SEQUENCE invoice_number_seq")
    op.execute("DROP SEQUENCE subscription_number_seq")
