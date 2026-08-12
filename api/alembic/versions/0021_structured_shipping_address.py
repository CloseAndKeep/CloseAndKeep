"""split gift order shipping address into street/city/state/postal

Revision ID: 0021_structured_shipping_address
Revises: 0020_max_spending_limit
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0021_structured_shipping_address"
down_revision: Union[str, None] = "0020_max_spending_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_orders",
        sa.Column("shipping_street", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "gift_orders",
        sa.Column("shipping_street2", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "gift_orders",
        sa.Column("shipping_city", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "gift_orders",
        sa.Column("shipping_state", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "gift_orders",
        sa.Column("shipping_postal_code", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "gift_orders",
        sa.Column("shipping_country", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gift_orders", "shipping_country")
    op.drop_column("gift_orders", "shipping_postal_code")
    op.drop_column("gift_orders", "shipping_state")
    op.drop_column("gift_orders", "shipping_city")
    op.drop_column("gift_orders", "shipping_street2")
    op.drop_column("gift_orders", "shipping_street")
