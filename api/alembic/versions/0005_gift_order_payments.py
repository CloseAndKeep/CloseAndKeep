"""add payment fields to gift orders

Revision ID: 0005_gift_order_payments
Revises: 0004_add_billing_fields_to_users
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_gift_order_payments"
down_revision: Union[str, None] = "0004_add_billing_fields_to_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_orders",
        sa.Column("payment_status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "gift_orders",
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "gift_orders",
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_gift_orders_stripe_checkout_session_id",
        "gift_orders",
        ["stripe_checkout_session_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "UPDATE gift_orders SET payment_status = 'paid' "
            "WHERE status IN ('queued', 'ordered', 'shipped', 'delivered')"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_gift_orders_stripe_checkout_session_id", table_name="gift_orders")
    op.drop_column("gift_orders", "stripe_price_id")
    op.drop_column("gift_orders", "stripe_checkout_session_id")
    op.drop_column("gift_orders", "payment_status")
