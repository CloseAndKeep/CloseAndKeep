"""Salesforce integrations: connections, CRM ids on prospects, reminder events

Revision ID: 0012_salesforce_integrations
Revises: 0011_address_request_expiry
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_salesforce_integrations"
down_revision: Union[str, None] = "0011_address_request_expiry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("crm_provider", sa.String(length=32), nullable=True))
    op.add_column("prospects", sa.Column("crm_external_id", sa.String(length=64), nullable=True))
    op.create_index("ix_prospects_crm_provider", "prospects", ["crm_provider"])
    op.create_index("ix_prospects_crm_external_id", "prospects", ["crm_external_id"])
    op.create_index(
        "uq_prospects_owner_crm",
        "prospects",
        ["owner_user_id", "crm_provider", "crm_external_id"],
        unique=True,
    )

    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_org_id", sa.String(length=64), nullable=True),
        sa.Column("instance_url", sa.String(length=512), nullable=True),
        sa.Column("access_token_encrypted", sa.String(length=2048), nullable=True),
        sa.Column("refresh_token_encrypted", sa.String(length=2048), nullable=True),
        sa.Column(
            "trigger_stage_name",
            sa.String(length=255),
            nullable=False,
            server_default="Demo Completed",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_connections_owner_user_id",
        "integration_connections",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_integration_connections_provider",
        "integration_connections",
        ["provider"],
    )
    op.create_index(
        "ix_integration_connections_external_org_id",
        "integration_connections",
        ["external_org_id"],
    )
    op.create_index(
        "uq_integration_owner_provider",
        "integration_connections",
        ["owner_user_id", "provider"],
        unique=True,
    )

    op.create_table(
        "crm_reminder_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("prospect_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_event_key", sa.String(length=128), nullable=False),
        sa.Column("stage_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="sent"),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["integration_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crm_reminder_events_connection_id",
        "crm_reminder_events",
        ["connection_id"],
    )
    op.create_index(
        "ix_crm_reminder_events_owner_user_id",
        "crm_reminder_events",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_crm_reminder_events_prospect_id",
        "crm_reminder_events",
        ["prospect_id"],
    )
    op.create_index(
        "ix_crm_reminder_events_external_event_key",
        "crm_reminder_events",
        ["external_event_key"],
    )
    op.create_index(
        "uq_crm_reminder_connection_event",
        "crm_reminder_events",
        ["connection_id", "external_event_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_crm_reminder_connection_event", table_name="crm_reminder_events")
    op.drop_index("ix_crm_reminder_events_external_event_key", table_name="crm_reminder_events")
    op.drop_index("ix_crm_reminder_events_prospect_id", table_name="crm_reminder_events")
    op.drop_index("ix_crm_reminder_events_owner_user_id", table_name="crm_reminder_events")
    op.drop_index("ix_crm_reminder_events_connection_id", table_name="crm_reminder_events")
    op.drop_table("crm_reminder_events")

    op.drop_index("uq_integration_owner_provider", table_name="integration_connections")
    op.drop_index("ix_integration_connections_external_org_id", table_name="integration_connections")
    op.drop_index("ix_integration_connections_provider", table_name="integration_connections")
    op.drop_index("ix_integration_connections_owner_user_id", table_name="integration_connections")
    op.drop_table("integration_connections")

    op.drop_index("uq_prospects_owner_crm", table_name="prospects")
    op.drop_index("ix_prospects_crm_external_id", table_name="prospects")
    op.drop_index("ix_prospects_crm_provider", table_name="prospects")
    op.drop_column("prospects", "crm_external_id")
    op.drop_column("prospects", "crm_provider")
