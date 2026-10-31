"""Retain four decimal places for percentage discount rules.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "discount_rule_revisions",
        "value",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(20, 4),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_discount_rule_revisions_fixed_precision"),
        "discount_rule_revisions",
        "kind <> 'FIXED' OR value = round(value, 2)",
    )


def downgrade():
    # Refuse to round retained financial policy during a schema rollback.
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM discount_rule_revisions WHERE value <> round(value, 2)
          ) THEN
            RAISE EXCEPTION 'Cannot downgrade: discount rules retain precision beyond two decimal places'
              USING ERRCODE = '23514';
          END IF;
        END $$
    """)
    op.drop_constraint(
        op.f("ck_discount_rule_revisions_fixed_precision"),
        "discount_rule_revisions",
        type_="check",
    )
    op.alter_column(
        "discount_rule_revisions",
        "value",
        existing_type=sa.Numeric(20, 4),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
