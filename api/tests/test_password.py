"""Placeholder backend test suite.

This is a starting point — expand against Test.MD before launch (auth, prospects,
gift orders, payments, and admin fulfillment all need coverage).

Run with:  pip install -r requirements-dev.txt && pytest
"""

from app.main import hash_password, verify_password


def test_password_round_trips():
    hashed = hash_password("hunter2-correct-horse")
    assert hashed != "hunter2-correct-horse"
    assert verify_password("hunter2-correct-horse", hashed)


def test_wrong_password_is_rejected():
    hashed = hash_password("the-right-password")
    assert not verify_password("the-wrong-password", hashed)
