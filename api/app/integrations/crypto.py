"""Encrypt CRM OAuth tokens at rest with Fernet."""

from __future__ import annotations

import hashlib
import base64

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


def _fernet() -> Fernet:
    raw = settings.integration_token_fernet_key
    if raw:
        key = raw.encode("utf-8") if isinstance(raw, str) else raw
        # Accept either a full Fernet key or any secret (derive a Fernet key).
        try:
            return Fernet(key)
        except (ValueError, TypeError):
            digest = hashlib.sha256(raw.encode("utf-8")).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    # Dev/test fallback so local suites work without env; never use in production.
    digest = hashlib.sha256(b"closeandkeep-dev-integration-token-key").digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt integration token.") from exc
