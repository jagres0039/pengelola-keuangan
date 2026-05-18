"""add email/password auth + link code

Revision ID: a1b2c3d4e5f6
Revises: 70c7c604b592
Create Date: 2026-05-13 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "70c7c604b592"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add email/password auth columns to users + make telegram_user_id nullable."""
    op.alter_column("users", "telegram_user_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("link_code", sa.String(length=16), nullable=True))
    op.add_column(
        "users",
        sa.Column("link_code_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Reverse changes."""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "link_code_expires_at")
    op.drop_column("users", "link_code")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
    op.alter_column("users", "telegram_user_id", existing_type=sa.BigInteger(), nullable=False)
