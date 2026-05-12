"""create gift orders table

Revision ID: 0003_create_gift_orders
Revises: 0002_users_and_prospects
Create Date: 2026-05-06 10:52:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_create_gift_orders"
down_revision: Union[str, None] = "0002_users_and_prospects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gift_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("prospect_id", sa.Integer(), nullable=False),
        sa.Column("gift_id", sa.String(length=64), nullable=False),
        sa.Column("recipient_name", sa.String(length=255), nullable=False),
        sa.Column("shipping_address", sa.String(length=1000), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gift_orders_owner_user_id", "gift_orders", ["owner_user_id"], unique=False)
    op.create_index("ix_gift_orders_prospect_id", "gift_orders", ["prospect_id"], unique=False)
    op.create_index("ix_gift_orders_requested_at", "gift_orders", ["requested_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_gift_orders_requested_at", table_name="gift_orders")
    op.drop_index("ix_gift_orders_prospect_id", table_name="gift_orders")
    op.drop_index("ix_gift_orders_owner_user_id", table_name="gift_orders")
    op.drop_table("gift_orders")
