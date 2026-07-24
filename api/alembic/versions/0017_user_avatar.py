"""add avatar columns to users

Revision ID: 0017_user_avatar
Revises: 0016_address_request_followup
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017_user_avatar"
down_revision: Union[str, None] = "0016_address_request_followup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("avatar_content_type", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_content_type")
    op.drop_column("users", "avatar_data")
