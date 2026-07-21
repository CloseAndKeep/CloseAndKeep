"""add stripe_payment_intent_id for authorize-then-capture orders

Revision ID: 0009_stripe_payment_intent
Revises: 0008_recipient_address_request
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_stripe_payment_intent"
down_revision: Union[str, None] = "0008_recipient_address_request"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gift_orders") as batch_op:
        batch_op.add_column(
            sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True)
        )
        batch_op.create_index(
            "ix_gift_orders_stripe_payment_intent_id",
            ["stripe_payment_intent_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("gift_orders") as batch_op:
        batch_op.drop_index("ix_gift_orders_stripe_payment_intent_id")
        batch_op.drop_column("stripe_payment_intent_id")
