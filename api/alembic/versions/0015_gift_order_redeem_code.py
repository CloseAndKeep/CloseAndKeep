"""add redeem_code to gift_orders

Revision ID: 0015_gift_order_redeem_code
Revises: 0014_user_name_company
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_gift_order_redeem_code"
down_revision: Union[str, None] = "0014_user_name_company"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_orders", sa.Column("redeem_code", sa.String(length=32), nullable=True))
    op.create_index("ix_gift_orders_redeem_code", "gift_orders", ["redeem_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_gift_orders_redeem_code", table_name="gift_orders")
    op.drop_column("gift_orders", "redeem_code")
