"""Session lifecycle — expiry, refresh rotation, and purge helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def test_expired_session_is_rejected(auth_client, monkeypatch):
    from app.config import settings
    from app.db import SessionLocal
    from app.models import SessionRecordModel

    cookie_name = settings.session_cookie_name
    session_id = auth_client.cookies.get(cookie_name)
    assert session_id

    with SessionLocal() as db:
        record = db.get(SessionRecordModel, session_id)
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.add(record)
        db.commit()

    assert auth_client.get("/auth/me").status_code == 401


def test_near_expiry_session_is_rotated(auth_client):
    from app.config import settings
    from app.db import SessionLocal
    from app.models import SessionRecordModel

    cookie_name = settings.session_cookie_name
    old_id = auth_client.cookies.get(cookie_name)
    assert old_id

    with SessionLocal() as db:
        record = db.get(SessionRecordModel, old_id)
        # Within the refresh threshold so the next authenticated request rotates.
        record.expires_at = datetime.now(UTC) + timedelta(
            minutes=max(1, settings.session_refresh_threshold_minutes - 1)
        )
        db.add(record)
        db.commit()

    me = auth_client.get("/auth/me")
    assert me.status_code == 200
    new_id = auth_client.cookies.get(cookie_name)
    assert new_id
    assert new_id != old_id

    with SessionLocal() as db:
        assert db.get(SessionRecordModel, old_id) is None
        assert db.get(SessionRecordModel, new_id) is not None


def test_purge_expired_sessions_removes_stale_rows(auth_client):
    from app.db import SessionLocal
    from app.models import SessionRecordModel
    from app.session_store import purge_expired_sessions
    from app.config import settings

    session_id = auth_client.cookies.get(settings.session_cookie_name)
    with SessionLocal() as db:
        record = db.get(SessionRecordModel, session_id)
        record.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.add(record)
        db.commit()

    removed = purge_expired_sessions()
    assert removed >= 1

    with SessionLocal() as db:
        assert db.get(SessionRecordModel, session_id) is None


def test_purge_orphaned_guests_keeps_guests_with_orders(client, stripe_stub):
    from app.db import SessionLocal
    from app.models import UserModel
    from app.session_store import delete_session, purge_orphaned_guests
    from app.config import settings
    from conftest import create_prospect, create_order

    assert client.post("/auth/guest").status_code == 200
    guest_with_order_id = client.get("/auth/me").json()["user_id"]
    prospect = create_prospect(client, email="keep@example.com")
    create_order(client, prospect["id"])
    delete_session(client.cookies.get(settings.session_cookie_name))

    # Empty guest (no orders) should be purged.
    assert client.post("/auth/guest").status_code == 200
    empty_guest_id = client.get("/auth/me").json()["user_id"]
    delete_session(client.cookies.get(settings.session_cookie_name))

    purged = purge_orphaned_guests()
    assert purged >= 1

    with SessionLocal() as db:
        assert db.get(UserModel, guest_with_order_id) is not None
        assert db.get(UserModel, empty_guest_id) is None
