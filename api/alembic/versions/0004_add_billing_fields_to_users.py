"""add billing fields to users

Revision ID: 0004_add_billing_fields_to_users
Revises: 0003_create_gift_orders
Create Date: 2026-05-06 11:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_add_billing_fields_to_users"
down_revision: Union[str, None] = "0003_create_gift_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("subscription_status", sa.String(length=64), nullable=False, server_default="inactive"),
    )
    op.add_column(
        "users",
        sa.Column("subscription_plan", sa.String(length=64), nullable=False, server_default="free"),
    )
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "subscription_plan")
    op.drop_column("users", "subscription_status")
    op.drop_column("users", "stripe_customer_id")
