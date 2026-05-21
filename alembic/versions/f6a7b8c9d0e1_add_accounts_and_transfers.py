"""add accounts + transfers + transactions.account_id (multi-akun kas)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-22 02:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create accounts/transfers and add nullable transactions.account_id."""
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default="cash",
        ),
        sa.Column(
            "opening_balance",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])
    op.create_index("ix_accounts_user_kind", "accounts", ["user_id", "kind"])

    op.create_table(
        "transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_transfers_user_id", "transfers", ["user_id"])
    op.create_index("ix_transfers_user_occurred", "transfers", ["user_id", "occurred_at"])

    op.add_column(
        "transactions",
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])


def downgrade() -> None:
    """Reverse changes."""
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_column("transactions", "account_id")

    op.drop_index("ix_transfers_user_occurred", table_name="transfers")
    op.drop_index("ix_transfers_user_id", table_name="transfers")
    op.drop_table("transfers")

    op.drop_index("ix_accounts_user_kind", table_name="accounts")
    op.drop_index("ix_accounts_user_id", table_name="accounts")
    op.drop_table("accounts")
