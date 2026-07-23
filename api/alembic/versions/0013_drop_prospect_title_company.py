"""drop title and company columns from prospects

Revision ID: 0013_drop_prospect_title_company
Revises: 0012_salesforce_integrations
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_drop_prospect_title_company"
down_revision: Union[str, None] = "0012_salesforce_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("prospects", "title")
    op.drop_column("prospects", "company")


def downgrade() -> None:
    op.add_column(
        "prospects",
        sa.Column("company", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "prospects",
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
    )
    op.alter_column("prospects", "company", server_default=None)
    op.alter_column("prospects", "title", server_default=None)
