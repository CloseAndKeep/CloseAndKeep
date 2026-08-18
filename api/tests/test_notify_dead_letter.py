"""Failed ops new-order notify: dead letter + retry job. Resend is stubbed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import create_order, mark_order_paid_db
from sqlalchemy import select


def _submit_ops_notify(order_id: int) -> None:
    from app.db import SessionLocal
    from app.fulfillment import ManualEmailFulfillment
    from app.models import GiftOrderModel, ProspectModel, UserModel

    with SessionLocal() as db:
        order = db.get(GiftOrderModel, order_id)
        prospect = db.get(ProspectModel, order.prospect_id)
        owner = db.get(UserModel, order.owner_user_id)
        ManualEmailFulfillment().submit_queued_order(
            order, prospect=prospect, owner=owner, db=db
        )


def _dead_letter_rows(order_id: int) -> list[dict]:
    from app.db import SessionLocal
    from app.models import NotifyDeadLetterModel

    with SessionLocal() as db:
        rows = db.scalars(
            select(NotifyDeadLetterModel).where(
                NotifyDeadLetterModel.order_id == order_id
            )
        ).all()
        return [
            {
                "id": row.id,
                "order_id": row.order_id,
                "context": row.context,
                "status": row.status,
                "attempt_count": row.attempt_count,
                "last_error": row.last_error,
            }
            for row in rows
        ]


def _age_dead_letter(order_id: int) -> None:
    from app.db import SessionLocal
    from app.models import NotifyDeadLetterModel

    with SessionLocal() as db:
        row = db.scalar(
            select(NotifyDeadLetterModel).where(
                NotifyDeadLetterModel.order_id == order_id
            )
        )
        assert row is not None
        row.last_attempt_at = datetime.now(UTC) - timedelta(minutes=10)
        db.add(row)
        db.commit()


def test_failed_resend_creates_dead_letter(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import resend
    from app.config import settings

    created = create_order(auth_client, prospect_id)
    mark_order_paid_db(created["id"])
    monkeypatch.setattr(settings, "resend_api_key", "re_test_dummy")
    monkeypatch.setattr(settings, "resend_from", "ops@example.com")

    def _boom(_payload):
        raise RuntimeError("resend down")

    monkeypatch.setattr(resend.Emails, "send", staticmethod(_boom))
    _submit_ops_notify(created["id"])

    rows = _dead_letter_rows(created["id"])
    assert len(rows) == 1
    assert rows[0]["context"] == "ops-new-order"
    assert rows[0]["status"] == "pending"
    assert rows[0]["attempt_count"] == 1
    assert rows[0]["last_error"]


def test_failed_ops_notify_does_not_enqueue_unpaid(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    created = create_order(auth_client, prospect_id)
    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification", lambda **_kw: False
    )
    _submit_ops_notify(created["id"])
    assert _dead_letter_rows(created["id"]) == []


def test_retry_marks_sent_when_resend_succeeds(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import resend
    from app.config import settings
    from app.db import SessionLocal
    from app.jobs.notify_dead_letters import retry_notify_dead_letters

    created = create_order(auth_client, prospect_id)
    mark_order_paid_db(created["id"])
    monkeypatch.setattr(settings, "resend_api_key", "re_test_dummy")
    monkeypatch.setattr(settings, "resend_from", "ops@example.com")
    monkeypatch.setattr(
        resend.Emails,
        "send",
        staticmethod(lambda _payload: (_ for _ in ()).throw(RuntimeError("resend down"))),
    )
    _submit_ops_notify(created["id"])
    assert _dead_letter_rows(created["id"])[0]["status"] == "pending"

    monkeypatch.setattr(resend.Emails, "send", staticmethod(lambda _payload: {"id": "email_1"}))
    with SessionLocal() as db:
        result = retry_notify_dead_letters(db, min_interval=timedelta(0))

    assert result["sent"] == 1
    assert result["failed"] == 0
    rows = _dead_letter_rows(created["id"])
    assert len(rows) == 1
    assert rows[0]["status"] == "sent"
    assert rows[0]["attempt_count"] == 2
    assert rows[0]["last_error"] is None


def test_retry_caps_attempts_and_marks_failed(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    from app.db import SessionLocal
    from app.jobs.notify_dead_letters import retry_notify_dead_letters
    from app.models import NotifyDeadLetterModel
    from app.notify_dead_letter import MAX_NOTIFY_ATTEMPTS, OPS_NEW_ORDER_CONTEXT

    created = create_order(auth_client, prospect_id)
    mark_order_paid_db(created["id"])
    with SessionLocal() as db:
        db.add(
            NotifyDeadLetterModel(
                order_id=created["id"],
                context=OPS_NEW_ORDER_CONTEXT,
                last_error="Resend down",
                attempt_count=MAX_NOTIFY_ATTEMPTS - 1,
                status="pending",
            )
        )
        db.commit()

    monkeypatch.setattr(
        "app.jobs.notify_dead_letters.send_new_order_notification",
        lambda **_kw: False,
    )
    with SessionLocal() as db:
        result = retry_notify_dead_letters(db, min_interval=timedelta(0))

    assert result["retried"] == 1
    assert result["failed"] == 1
    assert result["sent"] == 0
    rows = _dead_letter_rows(created["id"])
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["attempt_count"] == MAX_NOTIFY_ATTEMPTS

    with SessionLocal() as db:
        again = retry_notify_dead_letters(db, min_interval=timedelta(0))
    assert again["retried"] == 0
    assert again["candidates"] == 0
    assert _dead_letter_rows(created["id"])[0]["status"] == "failed"


def test_retry_job_endpoint_and_internal_list(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    created = create_order(auth_client, prospect_id)
    mark_order_paid_db(created["id"])
    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification", lambda **_kw: False
    )
    _submit_ops_notify(created["id"])
    _age_dead_letter(created["id"])

    listed = auth_client.get("/internal/jobs/notify-dead-letters")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["order_id"] == created["id"]
    assert items[0]["status"] == "pending"

    monkeypatch.setattr(
        "app.jobs.notify_dead_letters.send_new_order_notification",
        lambda **_kw: True,
    )
    ran = auth_client.post("/internal/jobs/notify-dead-letters")
    assert ran.status_code == 200
    body = ran.json()
    assert body["sent"] == 1
    assert body["pending"] == 0

    empty = auth_client.get("/internal/jobs/notify-dead-letters")
    assert empty.json()["items"] == []


def test_notify_dead_letters_requires_secret_in_production(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "cron_secret", "expected-secret")

    denied = client.post("/internal/jobs/notify-dead-letters")
    assert denied.status_code == 401

    ok = client.post(
        "/internal/jobs/notify-dead-letters",
        headers={"X-Cron-Secret": "expected-secret"},
    )
    assert ok.status_code == 200
    assert ok.json()["retried"] == 0
