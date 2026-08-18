"""Dashboard “needs you today” buckets: unpaid, no-address, just shipped."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import create_prospect, signup
from sqlalchemy import select

from app.db import SessionLocal
from app.models import GiftOrderModel, UserModel


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(UserModel).where(UserModel.email == email.strip().lower()))
        assert user is not None
        return user.id


def _insert_order(
    *,
    owner_user_id: int,
    prospect_id: int,
    recipient_name: str,
    status: str,
    payment_status: str,
    address_request_expires_at: datetime | None = None,
    address_request_token: str | None = None,
    requested_at: datetime | None = None,
) -> int:
    with SessionLocal() as db:
        order = GiftOrderModel(
            owner_user_id=owner_user_id,
            prospect_id=prospect_id,
            gift_id="cookies-4",
            recipient_name=recipient_name,
            note="Thanks for the meeting.",
            status=status,
            payment_status=payment_status,
            address_request_expires_at=address_request_expires_at,
            address_request_token=address_request_token,
        )
        if requested_at is not None:
            order.requested_at = requested_at
        db.add(order)
        db.commit()
        db.refresh(order)
        return order.id


def _item(order_id: int, recipient_name: str, status: str) -> dict:
    return {
        "id": order_id,
        "recipient_name": recipient_name,
        "status": status,
        "href": f"/orders/{order_id}",
    }


def test_needs_attention_empty_for_new_user(auth_client):
    resp = auth_client.get("/dashboard/needs-attention")
    assert resp.status_code == 200
    assert resp.json() == {"unpaid": [], "no_address": [], "just_shipped": []}


def test_needs_attention_requires_auth(client):
    assert client.get("/dashboard/needs-attention").status_code == 401


def test_needs_attention_buckets(auth_client, prospect_id):
    owner_id = _user_id("seller@example.com")
    now = datetime.now(UTC)

    unpaid_id = _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Unpaid Dana",
        status="pending_payment",
        payment_status="pending",
        requested_at=now - timedelta(minutes=2),
    )
    unpaid_address_id = _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Unpaid Address",
        status="no_address",
        payment_status="pending",
        address_request_token="tok_unpaid_addr",
        address_request_expires_at=now + timedelta(days=5),
        requested_at=now - timedelta(minutes=1),
    )
    waiting_id = _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Waiting Sam",
        status="no_address",
        payment_status="authorized",
        address_request_token="tok_waiting",
        address_request_expires_at=now + timedelta(days=4),
        requested_at=now - timedelta(minutes=4),
    )
    owed_id = _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Owed Pat",
        status="no_address",
        payment_status="owed",
        address_request_token="tok_owed",
        address_request_expires_at=now + timedelta(days=3),
        requested_at=now - timedelta(minutes=3),
    )
    expired_id = _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Expired Hold",
        status="no_address",
        payment_status="authorized",
        address_request_token="tok_expired",
        address_request_expires_at=now - timedelta(hours=1),
    )
    shipped_id = _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Shipped Riley",
        status="shipped",
        payment_status="paid",
    )
    _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Queued Skip",
        status="queued",
        payment_status="paid",
    )
    _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Delivered Skip",
        status="delivered",
        payment_status="paid",
    )
    _insert_order(
        owner_user_id=owner_id,
        prospect_id=prospect_id,
        recipient_name="Canceled Skip",
        status="canceled",
        payment_status="canceled",
    )

    body = auth_client.get("/dashboard/needs-attention").json()
    assert body["unpaid"] == [
        _item(unpaid_address_id, "Unpaid Address", "no_address"),
        _item(unpaid_id, "Unpaid Dana", "pending_payment"),
    ]
    assert body["no_address"] == [
        _item(owed_id, "Owed Pat", "no_address"),
        _item(waiting_id, "Waiting Sam", "no_address"),
    ]
    assert body["just_shipped"] == [_item(shipped_id, "Shipped Riley", "shipped")]
    assert expired_id not in {item["id"] for item in body["no_address"]}
    assert expired_id not in {item["id"] for item in body["unpaid"]}


def test_needs_attention_is_owner_scoped(make_client):
    owner = signup(make_client(), "owner-attn@example.com")
    other = signup(make_client(), "other-attn@example.com")
    owner_prospect = create_prospect(owner, name="Owned", email="owned-attn@example.com")
    other_prospect = create_prospect(other, name="Other", email="other-attn@example.com")

    owner_order = _insert_order(
        owner_user_id=_user_id("owner-attn@example.com"),
        prospect_id=owner_prospect["id"],
        recipient_name="Owner Gift",
        status="pending_payment",
        payment_status="pending",
    )
    other_order = _insert_order(
        owner_user_id=_user_id("other-attn@example.com"),
        prospect_id=other_prospect["id"],
        recipient_name="Other Gift",
        status="shipped",
        payment_status="paid",
    )

    owner_body = owner.get("/dashboard/needs-attention").json()
    other_body = other.get("/dashboard/needs-attention").json()

    assert [item["id"] for item in owner_body["unpaid"]] == [owner_order]
    assert owner_body["just_shipped"] == []
    assert [item["id"] for item in other_body["just_shipped"]] == [other_order]
    assert other_body["unpaid"] == []


def test_needs_attention_caps_each_list(auth_client, prospect_id):
    owner_id = _user_id("seller@example.com")
    base = datetime.now(UTC)
    for index in range(9):
        _insert_order(
            owner_user_id=owner_id,
            prospect_id=prospect_id,
            recipient_name=f"Unpaid {index}",
            status="pending_payment",
            payment_status="pending",
            requested_at=base + timedelta(minutes=index),
        )
        _insert_order(
            owner_user_id=owner_id,
            prospect_id=prospect_id,
            recipient_name=f"Hold {index}",
            status="no_address",
            payment_status="authorized",
            address_request_token=f"tok_cap_{index}",
            address_request_expires_at=base + timedelta(days=2),
            requested_at=base + timedelta(minutes=index),
        )
        _insert_order(
            owner_user_id=owner_id,
            prospect_id=prospect_id,
            recipient_name=f"Ship {index}",
            status="shipped",
            payment_status="paid",
            requested_at=base + timedelta(minutes=index),
        )

    body = auth_client.get("/dashboard/needs-attention").json()
    assert len(body["unpaid"]) == 8
    assert len(body["no_address"]) == 8
    assert len(body["just_shipped"]) == 8
    assert body["unpaid"][0]["recipient_name"] == "Unpaid 8"
    assert body["no_address"][0]["recipient_name"] == "Hold 8"
    assert body["just_shipped"][0]["recipient_name"] == "Ship 8"
