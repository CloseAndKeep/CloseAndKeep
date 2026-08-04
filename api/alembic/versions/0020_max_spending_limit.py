"""user max spending limit fields

Revision ID: 0020_max_spending_limit
Revises: 0019_email_verification
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020_max_spending_limit"
down_revision: Union[str, None] = "0019_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("max_spending_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "spending_limit_notified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "spending_limit_notified_at")
    op.drop_column("users", "max_spending_cents")
