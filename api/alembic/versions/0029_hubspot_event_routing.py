"""HubSpot portal routing: wider stage event keys and single-use OAuth state.

Revision ID: 0029_hubspot_event_routing
Revises: 0028_notify_dead_letter
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0029_hubspot_event_routing"
down_revision: Union[str, None] = "0028_notify_dead_letter"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "crm_reminder_events",
        "external_event_key",
        existing_type=sa.String(length=128),
        type_=sa.String(length=512),
        existing_nullable=False,
    )
    op.create_table(
        "oauth_states",
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.alter_column(
        "crm_reminder_events",
        "external_event_key",
        existing_type=sa.String(length=512),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
