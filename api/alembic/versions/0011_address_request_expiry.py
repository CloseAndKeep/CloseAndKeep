"""add address_request_expires_at to gift_orders

Revision ID: 0011_address_request_expiry
Revises: 0010_api_keys
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_address_request_expiry"
down_revision: Union[str, None] = "0010_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_orders",
        sa.Column("address_request_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_gift_orders_address_request_expires_at",
        "gift_orders",
        ["address_request_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gift_orders_address_request_expires_at", table_name="gift_orders")
    op.drop_column("gift_orders", "address_request_expires_at")
