"""one-time HubSpot Marketplace install claims

Revision ID: 0029_hubspot_pending_installs
Revises: 0028_notify_dead_letter
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0029_hubspot_pending_installs"
down_revision: Union[str, None] = "0028_notify_dead_letter"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hubspot_pending_installs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("portal_id", sa.String(length=64), nullable=True),
        sa.Column("access_token_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=2048), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hubspot_pending_installs_code_hash",
        "hubspot_pending_installs",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        "ix_hubspot_pending_installs_portal_id",
        "hubspot_pending_installs",
        ["portal_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_hubspot_pending_installs_portal_id", table_name="hubspot_pending_installs")
    op.drop_index("ix_hubspot_pending_installs_code_hash", table_name="hubspot_pending_installs")
    op.drop_table("hubspot_pending_installs")
