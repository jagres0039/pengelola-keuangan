"""add transaction_items table + low_balance_threshold

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-14 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add transaction_items table + low_balance_threshold column on users."""
    op.add_column(
        "users",
        sa.Column(
            "low_balance_threshold",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="100000",
        ),
    )

    op.create_table(
        "transaction_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_transaction_items_transaction_id",
        "transaction_items",
        ["transaction_id"],
    )


def downgrade() -> None:
    """Reverse changes."""
    op.drop_index("ix_transaction_items_transaction_id", table_name="transaction_items")
    op.drop_table("transaction_items")
    op.drop_column("users", "low_balance_threshold")
