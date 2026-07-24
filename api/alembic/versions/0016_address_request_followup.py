"""add address_request_followup_sent_at to gift_orders

Revision ID: 0016_address_request_followup
Revises: 0015_gift_order_redeem_code
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_address_request_followup"
down_revision: Union[str, None] = "0015_gift_order_redeem_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_orders",
        sa.Column("address_request_followup_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gift_orders", "address_request_followup_sent_at")
