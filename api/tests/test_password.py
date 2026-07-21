"""Password hashing helpers — bcrypt truncate / verify edge cases."""

from app.main import hash_password, verify_password, _BCRYPT_MAX_PASSWORD_BYTES


def test_password_round_trips():
    hashed = hash_password("hunter2-correct-horse")
    assert hashed != "hunter2-correct-horse"
    assert verify_password("hunter2-correct-horse", hashed)


def test_wrong_password_is_rejected():
    hashed = hash_password("the-right-password")
    assert not verify_password("the-wrong-password", hashed)


def test_passwords_longer_than_bcrypt_limit_still_verify():
    """bcrypt only uses 72 bytes; we truncate before hash/verify so long passwords work."""
    long_pw = "x" * (_BCRYPT_MAX_PASSWORD_BYTES + 40)
    hashed = hash_password(long_pw)
    assert verify_password(long_pw, hashed)
    # Differing only past the 72-byte boundary is treated as the same password.
    almost = "x" * _BCRYPT_MAX_PASSWORD_BYTES + "y" * 10
    assert verify_password(almost, hashed)


def test_verify_returns_false_for_corrupt_hash():
    assert not verify_password("anything", "not-a-valid-bcrypt-hash")
