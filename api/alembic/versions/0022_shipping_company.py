"""add optional company name on gift order shipping

Revision ID: 0022_shipping_company
Revises: 0021_structured_shipping_address
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0022_shipping_company"
down_revision: Union[str, None] = "0021_structured_shipping_address"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_orders",
        sa.Column("shipping_company", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gift_orders", "shipping_company")
