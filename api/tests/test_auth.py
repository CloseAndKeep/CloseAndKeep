"""Authentication tests — Test.MD §1 (signup, login, logout).

Focus on validation, email normalization, and account-enumeration safety.
"""

from __future__ import annotations


# --- §1.1 Signup -------------------------------------------------------------


def test_signup_creates_user_and_authenticates(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "new@example.com", "password": "strong-pass-123"},
    )
    assert resp.status_code == 200, resp.text

    # The session cookie now authenticates follow-up requests.
    me = client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "user"


def test_signup_rejects_invalid_email(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "not-an-email", "password": "strong-pass-123"},
    )
    assert resp.status_code == 422


def test_signup_enforces_min_password_length(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "shortpw@example.com", "password": "short"},
    )
    assert resp.status_code == 422


def test_signup_duplicate_email_returns_409(client):
    payload = {"email": "dupe@example.com", "password": "strong-pass-123"}
    assert client.post("/auth/signup", json=payload).status_code == 200

    resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 409
    # Message must not reveal which field failed beyond "already in use".
    assert "already in use" in resp.json()["detail"].lower()


def test_signup_normalizes_email_case(client):
    assert (
        client.post(
            "/auth/signup",
            json={"email": "Mixed@Example.com", "password": "strong-pass-123"},
        ).status_code
        == 200
    )

    # Same address in a different case is treated as a duplicate.
    resp = client.post(
        "/auth/signup",
        json={"email": "mixed@example.com", "password": "strong-pass-123"},
    )
    assert resp.status_code == 409


# --- §1.2 Login --------------------------------------------------------------


def test_login_with_valid_credentials(client):
    client.post(
        "/auth/signup",
        json={"email": "login@example.com", "password": "strong-pass-123"},
    )
    client.post("/auth/logout")

    resp = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "strong-pass-123"},
    )
    assert resp.status_code == 200, resp.text
    assert client.get("/auth/me").json()["email"] == "login@example.com"


def test_login_accepts_email_in_any_case(client):
    client.post(
        "/auth/signup",
        json={"email": "case@example.com", "password": "strong-pass-123"},
    )
    client.post("/auth/logout")

    resp = client.post(
        "/auth/login",
        json={"email": "CASE@Example.com", "password": "strong-pass-123"},
    )
    assert resp.status_code == 200, resp.text


def test_login_wrong_password_and_unknown_email_are_indistinguishable(client):
    client.post(
        "/auth/signup",
        json={"email": "real@example.com", "password": "strong-pass-123"},
    )
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
    client.post(
        "/auth/signup",
        json={"email": "bye@example.com", "password": "strong-pass-123"},
    )
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_me_requires_authentication(client):
    assert client.get("/auth/me").status_code == 401
