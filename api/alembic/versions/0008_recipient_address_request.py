"""add recipient address-request fields to gift orders

Supports orders where the recipient enters their own shipping address via
a emailed magic link. Payment and ops notification stay deferred until an
address exists.

Revision ID: 0008_recipient_address_request
Revises: 0007_drop_user_sub_fields
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_recipient_address_request"
down_revision: Union[str, None] = "0007_drop_user_sub_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gift_orders") as batch_op:
        batch_op.alter_column(
            "shipping_address",
            existing_type=sa.String(length=1000),
            nullable=True,
        )
        batch_op.add_column(sa.Column("recipient_email", sa.String(length=320), nullable=True))
        batch_op.add_column(
            sa.Column("address_request_token", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_request_sent_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_gift_orders_address_request_token",
            ["address_request_token"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("gift_orders") as batch_op:
        batch_op.drop_index("ix_gift_orders_address_request_token")
        batch_op.drop_column("address_request_sent_at")
        batch_op.drop_column("address_request_token")
        batch_op.drop_column("recipient_email")
        batch_op.alter_column(
            "shipping_address",
            existing_type=sa.String(length=1000),
            nullable=False,
        )
