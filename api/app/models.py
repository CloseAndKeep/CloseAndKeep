from datetime import datetime, UTC

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class SessionRecordModel(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ApiKeyModel(Base):
    """Hashed API keys for machine clients (never store the raw secret)."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProspectModel(Base):
    __tablename__ = "prospects"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "crm_provider",
            "crm_external_id",
            name="uq_prospects_owner_crm",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    deal_status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    crm_provider: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    crm_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class IntegrationConnectionModel(Base):
    """OAuth connection to an external CRM (Salesforce / HubSpot)."""

    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "provider", name="uq_integration_owner_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Salesforce org id (00D…) when known; used to route inbound webhooks.
    external_org_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    instance_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    trigger_stage_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Demo Completed"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )


class CrmReminderEventModel(Base):
    """Deduped CRM → cookie-reminder sends (once per opportunity by default)."""

    __tablename__ = "crm_reminder_events"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "external_event_key",
            name="uq_crm_reminder_connection_event",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prospect_id: Mapped[int | None] = mapped_column(
        ForeignKey("prospects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # Stable key: e.g. opportunity Id — one reminder email per opportunity.
    external_event_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stage_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="sent")
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class GiftOrderModel(Base):
    __tablename__ = "gift_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prospect_id: Mapped[int] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gift_id: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Null while status is no_address (recipient has not submitted a ship-to yet).
    shipping_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_payment")
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_request_token: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    address_request_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    address_request_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
