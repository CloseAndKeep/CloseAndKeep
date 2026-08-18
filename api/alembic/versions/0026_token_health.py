"""token health columns on integration connections

Revision ID: 0026_token_health
Revises: 0022_shipping_company
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0026_token_health"
down_revision: Union[str, None] = "0025_stage_recipes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "integration_connections",
        sa.Column(
            "token_status",
            sa.String(length=32),
            nullable=False,
            server_default="ok",
        ),
    )
    op.add_column(
        "integration_connections",
        sa.Column("token_error_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "integration_connections",
        sa.Column(
            "reconnect_email_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("integration_connections", "reconnect_email_sent_at")
    op.drop_column("integration_connections", "token_error_at")
    op.drop_column("integration_connections", "token_status")
