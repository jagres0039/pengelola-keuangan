"""add profile_mode column on users (standar | pengusaha)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-22 00:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ``profile_mode`` column to users; existing rows default to ``standar``."""
    op.add_column(
        "users",
        sa.Column(
            "profile_mode",
            sa.String(length=16),
            nullable=False,
            server_default="standar",
        ),
    )


def downgrade() -> None:
    """Reverse changes."""
    op.drop_column("users", "profile_mode")
