from datetime import datetime, UTC

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # per_order (default) | monthly — monthly accrues owed orders and charges at month end.
    billing_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="per_order")
    auto_order_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # cookies-4 | cookies-12 when auto_order_enabled.
    auto_order_gift_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_default_payment_method_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    # Cap on open monthly (owed) balance in cents; null means no limit.
    max_spending_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Set when we email about a hit limit; cleared when limit changes or balance drops.
    spending_limit_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Small profile photo stored in-DB (MVP; can move to object storage later).
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    avatar_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Null until the user confirms their email (guests are exempt at the auth gate).
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_verification_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    # [{stage_name, gift_id, note?}]. Null → fallback to trigger_stage_name + cookies-4.
    stage_recipes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # ok | needs_reconnect — set when OAuth refresh fails (tokens cleared).
    token_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    token_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconnect_email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    # Structured pieces are preferred; shipping_address is the formatted display string.
    shipping_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_street2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shipping_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    shipping_country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_payment")
    # pending | authorized | paid | canceled | owed (monthly unpaid; may still fulfill)
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # YYYY-MM grouping for month-end charges when payment_status is owed.
    billing_period: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_request_token: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    redeem_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )
    address_request_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    address_request_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    address_request_followup_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )


class NoteTemplateModel(Base):
    """Per-user saved cookie-note text for reuse on new gift orders."""

    __tablename__ = "note_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class NotifyDeadLetterModel(Base):
    """Retry queue when the ops new-order Resend email fails after money is on the line."""

    __tablename__ = "notify_dead_letters"
    __table_args__ = (
        UniqueConstraint("order_id", "context", name="uq_notify_dead_letter_order_context"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("gift_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # e.g. ops-new-order — only this context is written today.
    context: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # pending | sent | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
