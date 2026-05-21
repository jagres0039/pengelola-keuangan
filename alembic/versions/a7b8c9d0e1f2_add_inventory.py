"""add inventory_items + inventory_movements tables

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-22 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False, server_default="pcs"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_inventory_items_user_id", "inventory_items", ["user_id"])
    op.create_index("ix_inventory_user_name", "inventory_items", ["user_id", "name"])

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            sa.Integer(),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("qty_delta", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "reason",
            sa.String(length=16),
            nullable=False,
            server_default="adjustment",
        ),
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
    op.create_index("ix_inventory_movements_user_id", "inventory_movements", ["user_id"])
    op.create_index(
        "ix_movements_user_occurred",
        "inventory_movements",
        ["user_id", "occurred_at"],
    )
    op.create_index(
        "ix_movements_item_occurred",
        "inventory_movements",
        ["inventory_item_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_movements_item_occurred", table_name="inventory_movements")
    op.drop_index("ix_movements_user_occurred", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_user_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")

    op.drop_index("ix_inventory_user_name", table_name="inventory_items")
    op.drop_index("ix_inventory_items_user_id", table_name="inventory_items")
    op.drop_table("inventory_items")
