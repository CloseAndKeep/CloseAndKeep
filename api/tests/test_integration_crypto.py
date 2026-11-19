"""CRM token encryption fail-closed behavior."""

from __future__ import annotations

import pytest

from app.integrations import crypto


def test_fernet_allows_dev_fallback_when_key_missing(monkeypatch):
    monkeypatch.setattr(crypto.settings, "integration_token_fernet_key", "")
    monkeypatch.setattr(crypto.settings, "app_env", "development")
    token = crypto.encrypt_token("access-token")
    assert crypto.decrypt_token(token) == "access-token"


def test_fernet_fails_closed_in_production_without_key(monkeypatch):
    monkeypatch.setattr(crypto.settings, "integration_token_fernet_key", "")
    monkeypatch.setattr(crypto.settings, "app_env", "production")
    with pytest.raises(RuntimeError, match="INTEGRATION_TOKEN_FERNET_KEY"):
        crypto.encrypt_token("access-token")
