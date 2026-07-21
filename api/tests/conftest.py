"""Shared pytest fixtures for the CloseAndKeep backend suite.

This module wires up an isolated environment *before* the application package is
imported so tests never touch the real dev database or reach out to Stripe/Resend:

- ``DATABASE_URL`` points at a throwaway SQLite file created per test session.
- Stripe/Resend keys are seeded so the payment code paths run, while the Stripe
  SDK itself is stubbed via the ``stripe_stub`` fixture.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# --- Environment setup (must run before `app.*` is imported) -----------------

# Ensure `import app.*` resolves regardless of the directory pytest is invoked
# from (the package lives in the `api/` folder, one level above `tests/`).
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

# Point the app at a disposable SQLite database instead of the dev DB.
_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(prefix="closeandkeep_test_", suffix=".db")
os.close(_TEST_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

# Seed payment/email config so the checkout code paths execute. The Stripe SDK
# is stubbed per-test, so these values are never sent anywhere.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
os.environ.setdefault("STRIPE_PRICE_ID", "price_default_test")
# Keep email a no-op (send_new_order_notification short-circuits without a key).
os.environ.setdefault("RESEND_API_KEY", "")
os.environ.setdefault("ADMIN_EMAILS", "admin@example.com")


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Create all tables once for the test session."""
    import app.models  # noqa: F401  (registers models on Base.metadata)
    from app.db import Base, engine

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
    try:
        os.unlink(_TEST_DB_PATH)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _clean_tables():
    """Empty every table before each test for isolation."""
    from app.db import Base, engine

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


class StripeStub:
    """Records Stripe SDK calls and returns test-controlled responses.

    The application reads Stripe objects via ``obj[key]`` subscripting, so plain
    dicts are sufficient stand-ins for ``StripeObject`` instances here.
    """

    def __init__(self) -> None:
        self.session_create_calls: list[dict] = []
        self.customer_create_calls: list[dict] = []
        self.customer_retrieve_calls: list[str] = []
        # Response returned by Customer.retrieve. Defaults to a live, existing
        # customer so a stored id is reused; set to None to simulate a customer
        # that does not exist in the current Stripe mode (raises InvalidRequest).
        self.retrieved_customer: dict | None = {"id": "cus_test_123"}
        # Response returned by checkout.Session.create.
        self.created_session = {
            "id": "cs_test_created",
            "url": "https://checkout.stripe.test/pay/cs_test_created",
        }
        # Response returned by checkout.Session.retrieve (used by session reuse
        # and payment sync). Defaults to an open, unpaid session.
        self.retrieved_session = {
            "id": "cs_test_created",
            "status": "open",
            "payment_status": "unpaid",
            "url": "https://checkout.stripe.test/pay/cs_test_created",
        }

    # --- fake Stripe SDK surface --------------------------------------------
    def _session_create(self, **params):
        self.session_create_calls.append(params)
        return dict(self.created_session)

    def _session_retrieve(self, session_id, **_kwargs):
        result = dict(self.retrieved_session)
        result.setdefault("id", session_id)
        return result

    def _customer_create(self, **params):
        self.customer_create_calls.append(params)
        return {"id": "cus_test_123"}

    def _customer_retrieve(self, customer_id, **_kwargs):
        self.customer_retrieve_calls.append(customer_id)
        if self.retrieved_customer is None:
            import stripe

            raise stripe.error.InvalidRequestError(
                f"No such customer: '{customer_id}'", param="customer"
            )
        result = dict(self.retrieved_customer)
        result.setdefault("id", customer_id)
        return result


@pytest.fixture
def stripe_stub(monkeypatch):
    """Patch the Stripe SDK used by the app with an in-memory recorder."""
    import stripe

    stub = StripeStub()
    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(stub._session_create))
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", staticmethod(stub._session_retrieve))
    monkeypatch.setattr(stripe.Customer, "create", staticmethod(stub._customer_create))
    monkeypatch.setattr(stripe.Customer, "retrieve", staticmethod(stub._customer_retrieve))
    return stub


@pytest.fixture
def make_client():
    """Factory for independent, cookie-isolated TestClients on the same app.

    Useful for multi-user scenarios (tenancy, admin vs. regular user) where each
    client needs its own session cookie.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    created = []

    def _make():
        c = TestClient(app)
        c.__enter__()
        created.append(c)
        return c

    yield _make
    for c in created:
        c.__exit__(None, None, None)


def signup(client, email: str, password: str = "strong-pass-123"):
    resp = client.post("/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return client


def create_prospect(client, *, name="Dana Buyer", email="dana@example.com", deal_status="open"):
    resp = client.post(
        "/prospects",
        json={
            "name": name,
            "title": "VP Ops",
            "company": "Acme Co",
            "email": email,
            "deal_status": deal_status,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_order(client, prospect_id: int, gift_id: str = "cookies-4"):
    resp = client.post("/gift-orders", json=make_order_payload(prospect_id, gift_id))
    assert resp.status_code == 201, resp.text
    return resp.json()


def mark_order_paid_db(order_id: int) -> None:
    """Flip an order to paid/queued directly in the DB (fulfillment setup)."""
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    with SessionLocal() as db:
        order = db.get(GiftOrderModel, order_id)
        order.payment_status = "paid"
        order.status = "queued"
        db.add(order)
        db.commit()


@pytest.fixture
def admin_client(make_client):
    """A TestClient authenticated as an admin (email is in ADMIN_EMAILS)."""
    c = make_client()
    signup(c, "admin@example.com", "admin-strong-pass")
    return c


@pytest.fixture
def auth_client(client):
    """A TestClient authenticated as a freshly signed-up regular user."""
    resp = client.post(
        "/auth/signup",
        json={"email": "seller@example.com", "password": "hunter2-correct-horse"},
    )
    assert resp.status_code == 200, resp.text
    return client


@pytest.fixture
def prospect_id(auth_client):
    """Create a prospect owned by the authenticated user and return its id."""
    resp = auth_client.post(
        "/prospects",
        json={
            "name": "Dana Buyer",
            "title": "VP Ops",
            "company": "Acme Co",
            "email": "dana@example.com",
            "deal_status": "open",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def make_order_payload(prospect_id: int, gift_id: str = "cookies-4") -> dict:
    return {
        "prospect_id": prospect_id,
        "gift_id": gift_id,
        "recipient_name": "Dana Buyer",
        "shipping_address": "123 Main St\nSpringfield, IL 62704",
        "note": "Thanks for the great meeting!",
    }
