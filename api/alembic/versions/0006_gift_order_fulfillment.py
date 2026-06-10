"""add fulfillment fields (tracking number, admin notes) to gift orders

Revision ID: 0006_gift_order_fulfillment
Revises: 0005_gift_order_payments
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_gift_order_fulfillment"
down_revision: Union[str, None] = "0005_gift_order_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_orders",
        sa.Column("tracking_number", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "gift_orders",
        sa.Column("admin_notes", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gift_orders", "admin_notes")
    op.drop_column("gift_orders", "tracking_number")
