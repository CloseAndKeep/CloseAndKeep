from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from secrets import token_urlsafe

from sqlalchemy import delete, select

from .config import settings
from .db import SessionLocal
from .models import GiftOrderModel, SessionRecordModel, UserModel


@dataclass
class SessionRecord:
    session_id: str
    user_id: int
    expires_at: datetime


def _compute_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)


def _as_aware_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC.

    We always persist UTC timestamps, but SQLite (used for local dev) returns
    them without tzinfo. Comparing a naive value against an aware `datetime.now(UTC)`
    raises `TypeError`, so we normalise here before any comparison.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def create_session(user_id: int) -> SessionRecord:
    session_id = token_urlsafe(32)
    expires_at = _compute_expires_at()
    with SessionLocal() as db:
        db.add(
            SessionRecordModel(
                session_id=session_id,
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        db.commit()
    return SessionRecord(session_id=session_id, user_id=user_id, expires_at=expires_at)


def get_session(session_id: str | None) -> SessionRecord | None:
    if not session_id:
        return None
    with SessionLocal() as db:
        record = db.get(SessionRecordModel, session_id)
        if not record:
            return None
        expires_at = _as_aware_utc(record.expires_at)
        if expires_at <= datetime.now(UTC):
            db.delete(record)
            db.commit()
            return None

        return SessionRecord(
            session_id=record.session_id,
            user_id=record.user_id,
            expires_at=expires_at,
        )


def rotate_session(session_id: str | None, user_id: int) -> SessionRecord:
    delete_session(session_id)
    return create_session(user_id=user_id)


def refresh_session_if_needed(session_id: str | None) -> SessionRecord | None:
    record = get_session(session_id)
    if not record:
        return None

    refresh_threshold = timedelta(minutes=settings.session_refresh_threshold_minutes)
    if record.expires_at - datetime.now(UTC) <= refresh_threshold:
        return rotate_session(session_id=record.session_id, user_id=record.user_id)
    return record


def delete_session(session_id: str | None) -> None:
    if not session_id:
        return
    with SessionLocal() as db:
        record = db.get(SessionRecordModel, session_id)
        if not record:
            return
        db.delete(record)
        db.commit()


def purge_expired_sessions() -> int:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        expired = db.scalars(select(SessionRecordModel.session_id).where(SessionRecordModel.expires_at <= now)).all()
        count = len(expired)
        if count:
            db.execute(delete(SessionRecordModel).where(SessionRecordModel.expires_at <= now))
        db.commit()
        return count


def purge_orphaned_guests() -> int:
    """Delete session-less guests that never placed a gift order.

    Guests with gift orders are retained so fulfillment can still ship them.
    A later guest cannot see those orders because each guest has a unique user id.
    """
    with SessionLocal() as db:
        guests = db.scalars(select(UserModel).where(UserModel.role == "guest")).all()
        deleted = 0
        for guest in guests:
            has_session = db.scalar(
                select(SessionRecordModel.session_id)
                .where(SessionRecordModel.user_id == guest.id)
                .limit(1)
            )
            if has_session:
                continue
            has_order = db.scalar(
                select(GiftOrderModel.id).where(GiftOrderModel.owner_user_id == guest.id).limit(1)
            )
            if has_order:
                continue
            db.delete(guest)
            deleted += 1
        if deleted:
            db.commit()
        return deleted
