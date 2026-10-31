"""Explicit demo role-testing grants; existing sessions remain ordinary sessions."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dev_access_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("operator_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dev_csrf", sa.String(128), nullable=False),
        sa.Column("credential_fingerprint", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_dev_access_grants_operator_admin_id", "dev_access_grants", ["operator_admin_id"])
    op.create_index("ix_dev_access_grants_expires_at", "dev_access_grants", ["expires_at"])
    op.add_column("sessions", sa.Column("dev_grant_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key("fk_sessions_dev_grant_id_dev_access_grants", "sessions", "dev_access_grants", ["dev_grant_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_sessions_dev_grant_id", "sessions", ["dev_grant_id"])


def downgrade():
    # Removing the linkage must never convert impersonated sessions into ordinary ones.
    op.execute("UPDATE sessions SET revoked_at = now() WHERE dev_grant_id IS NOT NULL AND revoked_at IS NULL")
    op.drop_index("ix_sessions_dev_grant_id", table_name="sessions")
    op.drop_constraint("fk_sessions_dev_grant_id_dev_access_grants", "sessions", type_="foreignkey")
    op.drop_column("sessions", "dev_grant_id")
    op.drop_table("dev_access_grants")
