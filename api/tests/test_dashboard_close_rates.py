"""Gifted vs ungifted close-rate cohorts on GET /dashboard/summary."""

from __future__ import annotations

from conftest import create_order, create_prospect, mark_order_paid_db, signup


def _set_order(order_id: int, *, payment_status: str | None = None, status: str | None = None) -> None:
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    with SessionLocal() as db:
        order = db.get(GiftOrderModel, order_id)
        if payment_status is not None:
            order.payment_status = payment_status
        if status is not None:
            order.status = status
        db.add(order)
        db.commit()


def test_empty_summary_includes_zero_close_rate_counts(auth_client):
    summary = auth_client.get("/dashboard/summary").json()
    assert summary["gifted_won"] == 0
    assert summary["gifted_lost"] == 0
    assert summary["ungifted_won"] == 0
    assert summary["ungifted_lost"] == 0


def test_unpaid_draft_does_not_count_as_gifted(auth_client, stripe_stub):
    won = create_prospect(auth_client, name="Won draft", email="won-draft@example.com", deal_status="won")
    lost = create_prospect(auth_client, name="Lost draft", email="lost-draft@example.com", deal_status="lost")
    create_order(auth_client, won["id"])
    create_order(auth_client, lost["id"])

    summary = auth_client.get("/dashboard/summary").json()
    assert summary["gifted_won"] == 0
    assert summary["gifted_lost"] == 0
    assert summary["ungifted_won"] == 1
    assert summary["ungifted_lost"] == 1


def test_paid_order_counts_prospect_as_gifted(auth_client, stripe_stub):
    gifted_won = create_prospect(auth_client, name="Gifted won", email="gw@example.com", deal_status="won")
    gifted_lost = create_prospect(auth_client, name="Gifted lost", email="gl@example.com", deal_status="lost")
    create_prospect(auth_client, name="Ungifted won", email="uw@example.com", deal_status="won")
    create_prospect(auth_client, name="Ungifted lost", email="ul@example.com", deal_status="lost")
    create_prospect(auth_client, name="Open gifted", email="og@example.com", deal_status="open")

    mark_order_paid_db(create_order(auth_client, gifted_won["id"])["id"])
    mark_order_paid_db(create_order(auth_client, gifted_lost["id"])["id"])

    summary = auth_client.get("/dashboard/summary").json()
    assert summary["won"] == 2
    assert summary["lost"] == 2
    assert summary["gifted_won"] == 1
    assert summary["gifted_lost"] == 1
    assert summary["ungifted_won"] == 1
    assert summary["ungifted_lost"] == 1


def test_authorized_owed_and_fulfillment_statuses_count_as_gifted(auth_client, stripe_stub):
    cases = [
        ("auth@example.com", "authorized", "no_address"),
        ("owed@example.com", "owed", "queued"),
        ("shipped@example.com", "pending", "shipped"),
        ("delivered@example.com", "canceled", "delivered"),
    ]
    for email, payment_status, status in cases:
        prospect = create_prospect(auth_client, name=email, email=email, deal_status="won")
        order = create_order(auth_client, prospect["id"])
        _set_order(order["id"], payment_status=payment_status, status=status)

    canceled = create_prospect(auth_client, name="Canceled only", email="canceled@example.com", deal_status="won")
    canceled_order = create_order(auth_client, canceled["id"])
    _set_order(canceled_order["id"], payment_status="canceled", status="canceled")

    summary = auth_client.get("/dashboard/summary").json()
    assert summary["gifted_won"] == 4
    assert summary["ungifted_won"] == 1
    assert summary["gifted_lost"] == 0
    assert summary["ungifted_lost"] == 0


def test_one_progressed_order_makes_prospect_gifted(auth_client, stripe_stub):
    prospect = create_prospect(auth_client, name="Mixed", email="mixed@example.com", deal_status="won")
    create_order(auth_client, prospect["id"])
    mark_order_paid_db(create_order(auth_client, prospect["id"])["id"])

    summary = auth_client.get("/dashboard/summary").json()
    assert summary["gifted_won"] == 1
    assert summary["ungifted_won"] == 0


def test_close_rate_counts_are_scoped_to_owner(make_client, stripe_stub):
    owner = signup(make_client(), "owner-rates@example.com")
    other = signup(make_client(), "other-rates@example.com")
    gifted = create_prospect(owner, name="Owner gifted", email="ogw@example.com", deal_status="won")
    mark_order_paid_db(create_order(owner, gifted["id"])["id"])
    create_prospect(other, name="Other won", email="ow@example.com", deal_status="won")

    owner_summary = owner.get("/dashboard/summary").json()
    other_summary = other.get("/dashboard/summary").json()
    assert owner_summary["gifted_won"] == 1
    assert owner_summary["ungifted_won"] == 0
    assert other_summary["gifted_won"] == 0
    assert other_summary["ungifted_won"] == 1
