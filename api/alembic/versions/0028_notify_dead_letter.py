"""ops new-order notify dead letters for paid/authorized/owed orders

Revision ID: 0028_notify_dead_letter
Revises: 0022_shipping_company
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0028_notify_dead_letter"
down_revision: Union[str, None] = "0026_token_health"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notify_dead_letters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("context", sa.String(length=64), nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["gift_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "context", name="uq_notify_dead_letter_order_context"),
    )
    op.create_index("ix_notify_dead_letters_order_id", "notify_dead_letters", ["order_id"])
    op.create_index("ix_notify_dead_letters_context", "notify_dead_letters", ["context"])
    op.create_index("ix_notify_dead_letters_status", "notify_dead_letters", ["status"])


def downgrade() -> None:
    op.drop_index("ix_notify_dead_letters_status", table_name="notify_dead_letters")
    op.drop_index("ix_notify_dead_letters_context", table_name="notify_dead_letters")
    op.drop_index("ix_notify_dead_letters_order_id", table_name="notify_dead_letters")
    op.drop_table("notify_dead_letters")
