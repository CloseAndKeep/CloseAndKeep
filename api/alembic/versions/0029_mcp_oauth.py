"""MCP Connect OAuth clients, tokens, and order drafts

Revision ID: 0029_mcp_oauth
Revises: 0028_notify_dead_letter
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0029_mcp_oauth"
down_revision: Union[str, None] = "0028_notify_dead_letter"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_clients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=64), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column("token_endpoint_auth_method", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index("ix_mcp_oauth_clients_client_id", "mcp_oauth_clients", ["client_id"])

    op.create_table(
        "mcp_oauth_auth_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2000), nullable=False),
        sa.Column("scopes", sa.String(length=255), nullable=False),
        sa.Column("resource", sa.String(length=500), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index("ix_mcp_oauth_auth_codes_code_hash", "mcp_oauth_auth_codes", ["code_hash"])
    op.create_index("ix_mcp_oauth_auth_codes_client_id", "mcp_oauth_auth_codes", ["client_id"])
    op.create_index("ix_mcp_oauth_auth_codes_user_id", "mcp_oauth_auth_codes", ["user_id"])
    op.create_index("ix_mcp_oauth_auth_codes_expires_at", "mcp_oauth_auth_codes", ["expires_at"])

    op.create_table(
        "mcp_oauth_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scopes", sa.String(length=255), nullable=False),
        sa.Column("resource", sa.String(length=500), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index(
        "ix_mcp_oauth_tokens_access_token_hash", "mcp_oauth_tokens", ["access_token_hash"]
    )
    op.create_index(
        "ix_mcp_oauth_tokens_refresh_token_hash", "mcp_oauth_tokens", ["refresh_token_hash"]
    )
    op.create_index("ix_mcp_oauth_tokens_client_id", "mcp_oauth_tokens", ["client_id"])
    op.create_index("ix_mcp_oauth_tokens_user_id", "mcp_oauth_tokens", ["user_id"])
    op.create_index(
        "ix_mcp_oauth_tokens_access_expires_at", "mcp_oauth_tokens", ["access_expires_at"]
    )
    op.create_index(
        "ix_mcp_oauth_tokens_refresh_expires_at", "mcp_oauth_tokens", ["refresh_expires_at"]
    )

    op.create_table(
        "mcp_order_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("draft_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(length=2000), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id"),
    )
    op.create_index("ix_mcp_order_drafts_draft_id", "mcp_order_drafts", ["draft_id"])
    op.create_index("ix_mcp_order_drafts_user_id", "mcp_order_drafts", ["user_id"])
    op.create_index("ix_mcp_order_drafts_expires_at", "mcp_order_drafts", ["expires_at"])


def downgrade() -> None:
    op.drop_table("mcp_order_drafts")
    op.drop_table("mcp_oauth_tokens")
    op.drop_table("mcp_oauth_auth_codes")
    op.drop_table("mcp_oauth_clients")
