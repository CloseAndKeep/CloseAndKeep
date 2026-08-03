"""user monthly billing + CRM auto-order fields

Revision ID: 0018_monthly_billing
Revises: 0017_user_avatar
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0018_monthly_billing"
down_revision: Union[str, None] = "0017_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "billing_mode",
            sa.String(length=32),
            nullable=False,
            server_default="per_order",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "auto_order_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("auto_order_gift_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "stripe_default_payment_method_id",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "gift_orders",
        sa.Column("billing_period", sa.String(length=7), nullable=True),
    )
    op.create_index(
        "ix_gift_orders_billing_period",
        "gift_orders",
        ["billing_period"],
    )


def downgrade() -> None:
    op.drop_index("ix_gift_orders_billing_period", table_name="gift_orders")
    op.drop_column("gift_orders", "billing_period")
    op.drop_column("users", "stripe_default_payment_method_id")
    op.drop_column("users", "auto_order_gift_id")
    op.drop_column("users", "auto_order_enabled")
    op.drop_column("users", "billing_mode")
