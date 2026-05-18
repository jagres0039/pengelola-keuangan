"""add subscription columns on users + payments table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-17 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TRIAL_DAYS = 14


def upgrade() -> None:
    """Add subscription fields + payments table; backfill existing users with fresh trial."""
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True),
    )

    backfill_ends_at = datetime.now(UTC) + timedelta(days=TRIAL_DAYS)
    op.execute(
        sa.text("UPDATE users SET trial_ends_at = :ts WHERE trial_ends_at IS NULL").bindparams(
            ts=backfill_ends_at
        )
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("proof_note", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_user_status", "payments", ["user_id", "status"])


def downgrade() -> None:
    """Reverse changes."""
    op.drop_index("ix_payments_user_status", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_column("users", "subscription_ends_at")
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "is_admin")
