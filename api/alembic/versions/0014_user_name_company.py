"""add name and company to users

Revision ID: 0014_user_name_company
Revises: 0013_drop_prospect_title_company
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_user_name_company"
down_revision: Union[str, None] = "0013_drop_prospect_title_company"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("company", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "company")
    op.drop_column("users", "name")
