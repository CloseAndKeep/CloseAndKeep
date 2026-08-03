"""Authentication tests — Test.MD §1 (signup, login, logout).

Focus on validation, email normalization, and account-enumeration safety.
"""

from __future__ import annotations

from conftest import mark_email_verified, signup, signup_payload


# --- §1.1 Signup -------------------------------------------------------------


def test_signup_requires_email_verification_before_session(client):
    resp = client.post(
        "/auth/signup",
        json=signup_payload("new@example.com", name="New User", company="New Co"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("verification_required") is True
    assert client.get("/auth/me").status_code == 401

    # Correct password still cannot log in until verified.
    blocked = client.post(
        "/auth/login",
        json={"email": "new@example.com", "password": "strong-pass-123"},
    )
    assert blocked.status_code == 403
    assert "verification" in blocked.json()["detail"].lower()

    mark_email_verified("new@example.com")
    assert (
        client.post(
            "/auth/login",
            json={"email": "new@example.com", "password": "strong-pass-123"},
        ).status_code
        == 200
    )
    me = client.get("/auth/me")
    assert me.status_code == 200
    profile = me.json()
    assert profile["email"] == "new@example.com"
    assert profile["name"] == "New User"
    assert profile["company"] == "New Co"
    assert profile["role"] == "user"
    assert profile["email_verified"] is True


def test_signup_rejects_invalid_email(client):
    resp = client.post(
        "/auth/signup",
        json=signup_payload("not-an-email"),
    )
    assert resp.status_code == 422


def test_signup_enforces_min_password_length(client):
    resp = client.post(
        "/auth/signup",
        json=signup_payload("shortpw@example.com", "short"),
    )
    assert resp.status_code == 422


def test_signup_rejects_password_without_letter_and_digit(client):
    resp = client.post(
        "/auth/signup",
        json=signup_payload("weakpw@example.com", "alllettersonly"),
    )
    assert resp.status_code == 422


def test_signup_requires_name_and_company(client):
    base = {"email": "profile@example.com", "password": "strong-pass-123"}
    assert client.post("/auth/signup", json={**base, "company": "Acme"}).status_code == 422
    assert client.post("/auth/signup", json={**base, "name": "Ada"}).status_code == 422
    assert (
        client.post(
            "/auth/signup",
            json={**base, "name": "  ", "company": "Acme"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/auth/signup",
            json={**base, "name": "Ada", "company": "   "},
        ).status_code
        == 422
    )


def test_signup_duplicate_email_does_not_enumerate(client):
    payload = signup_payload("dupe@example.com")
    assert client.post("/auth/signup", json=payload).status_code == 200

    resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "already in use" not in detail
    assert "unable to create account" in detail


def test_signup_normalizes_email_case(client):
    assert (
        client.post(
            "/auth/signup",
            json=signup_payload("Mixed@Example.com"),
        ).status_code
        == 200
    )

    # Same address in a different case is treated as a duplicate.
    resp = client.post(
        "/auth/signup",
        json=signup_payload("mixed@example.com"),
    )
    assert resp.status_code == 400
    assert "unable to create account" in resp.json()["detail"].lower()


# --- §1.2 Login --------------------------------------------------------------


def test_login_with_valid_credentials(client):
    signup(client, "login@example.com")
    client.post("/auth/logout")

    resp = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "strong-pass-123"},
    )
    assert resp.status_code == 200, resp.text
    assert client.get("/auth/me").json()["email"] == "login@example.com"


def test_login_accepts_email_in_any_case(client):
    signup(client, "case@example.com")
    client.post("/auth/logout")

    resp = client.post(
        "/auth/login",
        json={"email": "CASE@Example.com", "password": "strong-pass-123"},
    )
    assert resp.status_code == 200, resp.text


def test_login_wrong_password_and_unknown_email_are_indistinguishable(client):
    signup(client, "real@example.com")
    client.post("/auth/logout")

    wrong_pw = client.post(
        "/auth/login",
        json={"email": "real@example.com", "password": "wrong-password"},
    )
    unknown = client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "strong-pass-123"},
    )

    assert wrong_pw.status_code == 401
    assert unknown.status_code == 401
    # No account enumeration: identical failure response for both cases.
    assert wrong_pw.json()["detail"] == unknown.json()["detail"]


# --- §1.3 Logout -------------------------------------------------------------


def test_logout_invalidates_session(client):
    signup(client, "bye@example.com")
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_me_requires_authentication(client):
    assert client.get("/auth/me").status_code == 401


def test_me_includes_has_avatar_false_by_default(auth_client):
    me = auth_client.get("/auth/me").json()
    assert me["has_avatar"] is False
    assert me["name"] == "Test Seller"
    assert me["email"]


# Minimal 1x1 PNG
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_avatar_upload_get_and_delete(auth_client):
    upload = auth_client.post(
        "/auth/me/avatar",
        files={"file": ("photo.png", _TINY_PNG, "image/png")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["has_avatar"] is True

    me = auth_client.get("/auth/me").json()
    assert me["has_avatar"] is True

    avatar = auth_client.get("/auth/me/avatar")
    assert avatar.status_code == 200
    assert avatar.headers["content-type"].startswith("image/png")
    assert avatar.content == _TINY_PNG

    removed = auth_client.delete("/auth/me/avatar")
    assert removed.status_code == 200
    assert removed.json()["has_avatar"] is False
    assert auth_client.get("/auth/me/avatar").status_code == 404


def test_avatar_rejects_non_image(auth_client):
    resp = auth_client.post(
        "/auth/me/avatar",
        files={"file": ("notes.txt", b"not-an-image", "text/plain")},
    )
    assert resp.status_code == 400
    assert "jpeg" in resp.json()["detail"].lower() or "png" in resp.json()["detail"].lower()


def test_avatar_rejects_oversized(auth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "avatar_max_bytes", 16)
    resp = auth_client.post(
        "/auth/me/avatar",
        files={"file": ("photo.png", _TINY_PNG, "image/png")},
    )
    assert resp.status_code == 400
    assert "mb" in resp.json()["detail"].lower() or "smaller" in resp.json()["detail"].lower()


# --- Change password ---------------------------------------------------------


def test_change_password_updates_credentials(client):
    signup(client, "pwchange@example.com")
    resp = client.post(
        "/auth/me/password",
        json={
            "current_password": "strong-pass-123",
            "new_password": "even-stronger-456",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == "Password updated."

    client.post("/auth/logout")
    assert (
        client.post(
            "/auth/login",
            json={"email": "pwchange@example.com", "password": "strong-pass-123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login",
            json={"email": "pwchange@example.com", "password": "even-stronger-456"},
        ).status_code
        == 200
    )


def test_change_password_rejects_wrong_current(auth_client):
    resp = auth_client.post(
        "/auth/me/password",
        json={
            "current_password": "not-the-right-one",
            "new_password": "even-stronger-456",
        },
    )
    assert resp.status_code == 400
    assert "current password" in resp.json()["detail"].lower()


def test_change_password_enforces_policy(auth_client):
    resp = auth_client.post(
        "/auth/me/password",
        json={
            "current_password": "hunter2-correct-horse",
            "new_password": "short",
        },
    )
    assert resp.status_code == 422


def test_change_password_rejects_same_password(auth_client):
    resp = auth_client.post(
        "/auth/me/password",
        json={
            "current_password": "hunter2-correct-horse",
            "new_password": "hunter2-correct-horse",
        },
    )
    assert resp.status_code == 400
    assert "different" in resp.json()["detail"].lower()


def test_change_password_forbidden_for_guest(client):
    assert client.post("/auth/guest").status_code == 200
    resp = client.post(
        "/auth/me/password",
        json={
            "current_password": "anything-goes",
            "new_password": "even-stronger-456",
        },
    )
    assert resp.status_code == 403


def test_change_password_requires_authentication(client):
    assert (
        client.post(
            "/auth/me/password",
            json={
                "current_password": "strong-pass-123",
                "new_password": "even-stronger-456",
            },
        ).status_code
        == 401
    )


# --- Guest sessions ----------------------------------------------------------


def test_guest_login_creates_ephemeral_session(client):
    resp = client.post("/auth/guest")
    assert resp.status_code == 200, resp.text

    me = client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "guest"
    assert body["is_guest"] is True
    assert body["has_avatar"] is False
    assert body["name"] is None
    assert body["company"] is None
    assert body["email"].startswith("guest-")
    assert body["email"].endswith("@guest.example.com")


def test_guest_logout_discards_empty_guest(client):
    from app.db import SessionLocal
    from app.models import ProspectModel, UserModel
    from sqlalchemy import select

    assert client.post("/auth/guest").status_code == 200
    guest_id = client.get("/auth/me").json()["user_id"]

    create = client.post(
        "/prospects",
        json={
            "name": "Temp Prospect",
            "email": "temp@acme.example",
        },
    )
    assert create.status_code == 201, create.text

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401

    # No gift order → empty guest (and cascaded prospects) can be removed.
    with SessionLocal() as db:
        assert db.get(UserModel, guest_id) is None
        assert db.scalars(select(ProspectModel)).all() == []


def test_guest_order_survives_logout_but_next_guest_cannot_see_it(client, stripe_stub):
    from app.db import SessionLocal
    from app.models import GiftOrderModel, UserModel
    from sqlalchemy import select

    assert client.post("/auth/guest").status_code == 200
    guest_id = client.get("/auth/me").json()["user_id"]

    prospect = client.post(
        "/prospects",
        json={
            "name": "Ship Me",
            "email": "ship@acme.example",
        },
    )
    assert prospect.status_code == 201, prospect.text
    prospect_id = prospect.json()["id"]

    order = client.post(
        "/gift-orders",
        json={
            "prospect_id": prospect_id,
            "gift_id": "cookies-4",
            "recipient_name": "Ship Me",
            "shipping_address": "1 Main St",
            "note": "Thanks for the demo",
        },
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    assert client.post("/auth/logout").status_code == 200

    # Order remains for fulfillment / admin shipping.
    with SessionLocal() as db:
        assert db.get(UserModel, guest_id) is not None
        assert db.get(GiftOrderModel, order_id) is not None

    # A new guest starts clean and cannot see the prior order.
    assert client.post("/auth/guest").status_code == 200
    listed = client.get("/gift-orders")
    assert listed.status_code == 200
    assert listed.json() == []
    assert client.get(f"/gift-orders/{order_id}").status_code == 404


def test_guest_cannot_password_login(client):
    assert client.post("/auth/guest").status_code == 200
    email = client.get("/auth/me").json()["email"]
    client.post("/auth/logout")

    resp = client.post(
        "/auth/login",
        json={"email": email, "password": "anything-at-all"},
    )
    assert resp.status_code == 401


def test_login_rotates_session_cookie(client):
    from app.config import settings

    signup(client, "rotate@example.com")
    first = client.cookies.get(settings.session_cookie_name)
    client.post("/auth/logout")

    client.post(
        "/auth/login",
        json={"email": "rotate@example.com", "password": "strong-pass-123"},
    )
    second = client.cookies.get(settings.session_cookie_name)
    assert first and second and first != second


def test_signup_promotes_admin_email(client):
    signup(client, "admin@example.com", "admin-strong-pass-1")
    me = client.get("/auth/me").json()
    assert me["role"] == "admin"
    assert me["is_guest"] is False


def test_signup_promotes_closeandkeep_domain(client):
    signup(client, "ops@closeandkeep.com", "domain-admin-pass-1")
    me = client.get("/auth/me").json()
    assert me["role"] == "admin"
    assert me["email"] == "ops@closeandkeep.com"


def test_guest_then_signup_discards_empty_guest(client):
    from app.db import SessionLocal
    from app.models import UserModel

    assert client.post("/auth/guest").status_code == 200
    guest_id = client.get("/auth/me").json()["user_id"]

    assert (
        client.post(
            "/auth/signup",
            json=signup_payload("upgraded@example.com"),
        ).status_code
        == 200
    )
    # Signup clears the guest session but does not authenticate until verified.
    assert client.get("/auth/me").status_code == 401

    with SessionLocal() as db:
        assert db.get(UserModel, guest_id) is None

    mark_email_verified("upgraded@example.com")
    assert (
        client.post(
            "/auth/login",
            json={"email": "upgraded@example.com", "password": "strong-pass-123"},
        ).status_code
        == 200
    )
    me = client.get("/auth/me").json()
    assert me["email"] == "upgraded@example.com"
    assert me["role"] == "user"


def test_verify_email_token_logs_user_in(client, monkeypatch):
    captured: dict[str, str] = {}

    def _capture(*, to_email: str, verify_url: str, name: str | None = None) -> None:
        captured["to"] = to_email
        captured["url"] = verify_url
        captured["name"] = name or ""

    monkeypatch.setattr("app.main.send_email_verification", _capture)

    assert (
        client.post(
            "/auth/signup",
            json=signup_payload("verify-me@example.com", name="Vera User"),
        ).status_code
        == 200
    )
    assert "token=" in captured["url"]
    token = captured["url"].split("token=", 1)[1]

    resp = client.post("/auth/verify-email", json={"token": token})
    assert resp.status_code == 200, resp.text
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "verify-me@example.com"
    assert me.json()["email_verified"] is True


def test_verify_email_rejects_invalid_token(client):
    resp = client.post("/auth/verify-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()


def test_resend_verification_is_anti_enumeration(client, monkeypatch):
    sent: list[str] = []

    def _capture(*, to_email: str, verify_url: str, name: str | None = None) -> None:
        sent.append(to_email)

    monkeypatch.setattr("app.main.send_email_verification", _capture)

    assert (
        client.post(
            "/auth/signup",
            json=signup_payload("needs-link@example.com"),
        ).status_code
        == 200
    )
    sent.clear()

    known = client.post(
        "/auth/resend-verification",
        json={"email": "needs-link@example.com"},
    )
    unknown = client.post(
        "/auth/resend-verification",
        json={"email": "nobody@example.com"},
    )
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]
    assert sent == ["needs-link@example.com"]


def test_auth_endpoints_are_rate_limited(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_auth_ip", 3)
    monkeypatch.setattr(settings, "rate_limit_auth_email", 100)

    for i in range(3):
        resp = client.post(
            "/auth/login",
            json={"email": f"spray{i}@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 401

    limited = client.post(
        "/auth/login",
        json={"email": "spray-more@example.com", "password": "wrong-password"},
    )
    assert limited.status_code == 429


def test_guest_login_is_rate_limited(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_auth_ip", 2)
    monkeypatch.setattr(settings, "rate_limit_auth_email", 100)

    assert client.post("/auth/guest").status_code == 200
    client.post("/auth/logout")
    assert client.post("/auth/guest").status_code == 200
    client.post("/auth/logout")
    assert client.post("/auth/guest").status_code == 429
