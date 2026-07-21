"""Unit tests for the in-process sliding-window rate limiter."""

from __future__ import annotations

import pytest
from fastapi import HTTPException


def test_limiter_allows_up_to_limit_then_blocks():
    from app.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter()
    for _ in range(3):
        limiter.check("k", limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        limiter.check("k", limit=3, window_seconds=60)
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"]


def test_limiter_keys_are_isolated():
    from app.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter()
    limiter.check("a", limit=1, window_seconds=60)
    # Different key is still allowed.
    limiter.check("b", limit=1, window_seconds=60)
    with pytest.raises(HTTPException):
        limiter.check("a", limit=1, window_seconds=60)


def test_limiter_disabled_when_limit_non_positive():
    from app.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter()
    for _ in range(20):
        limiter.check("unlimited", limit=0, window_seconds=60)


def test_limiter_window_expires_hits(monkeypatch):
    from app.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter()
    clock = {"now": 1000.0}

    monkeypatch.setattr("app.rate_limit.time.monotonic", lambda: clock["now"])
    limiter.check("w", limit=1, window_seconds=10)
    with pytest.raises(HTTPException):
        limiter.check("w", limit=1, window_seconds=10)

    clock["now"] = 1011.0  # past the window
    limiter.check("w", limit=1, window_seconds=10)


def test_client_ip_prefers_first_forwarded_hop():
    from app.rate_limit import client_ip
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.1")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    request = Request(scope)
    assert client_ip(request) == "203.0.113.9"


def test_client_ip_falls_back_to_direct_client():
    from app.rate_limit import client_ip
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": ("198.51.100.4", 12345),
        "server": ("test", 80),
    }
    request = Request(scope)
    assert client_ip(request) == "198.51.100.4"


def test_order_create_ip_rate_limit(make_client, stripe_stub, monkeypatch):
    from app.config import settings
    from conftest import create_prospect, make_order_payload, signup

    monkeypatch.setattr(settings, "rate_limit_order_create", 100)
    monkeypatch.setattr(settings, "rate_limit_order_create_ip", 2)

    user_a = signup(make_client(), "a@example.com")
    user_b = signup(make_client(), "b@example.com")
    prospect_a = create_prospect(user_a, email="pa@example.com")
    prospect_b = create_prospect(user_b, email="pb@example.com")

    # Same TestClient default IP shared across users → IP bucket fills first.
    assert user_a.post("/gift-orders", json=make_order_payload(prospect_a["id"])).status_code == 201
    assert user_b.post("/gift-orders", json=make_order_payload(prospect_b["id"])).status_code == 201
    limited = user_a.post("/gift-orders", json=make_order_payload(prospect_a["id"]))
    assert limited.status_code == 429
