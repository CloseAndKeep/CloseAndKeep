"""drop unused subscription fields from users

The MVP uses one-time Stripe payments only (no subscriptions), so these columns
were dead scaffolding. `stripe_customer_id` is kept and now populated at checkout.

Revision ID: 0007_drop_user_subscription_fields
Revises: 0006_gift_order_fulfillment
Create Date: 2026-07-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_drop_user_subscription_fields"
down_revision: Union[str, None] = "0006_gift_order_fulfillment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "subscription_plan")
    op.drop_column("users", "subscription_status")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("subscription_status", sa.String(length=64), nullable=False, server_default="inactive"),
    )
    op.add_column(
        "users",
        sa.Column("subscription_plan", sa.String(length=64), nullable=False, server_default="free"),
    )
