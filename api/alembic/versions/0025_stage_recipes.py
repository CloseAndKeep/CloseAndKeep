"""add CRM stage recipes on integration connections

Revision ID: 0025_stage_recipes
Revises: 0022_shipping_company
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0025_stage_recipes"
down_revision: Union[str, None] = "0024_note_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "integration_connections",
        sa.Column("stage_recipes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integration_connections", "stage_recipes")
