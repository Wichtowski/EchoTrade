from __future__ import annotations

from core.services.auth import (
    hash_password,
    hash_secret,
    normalize_email,
    verify_password,
)


def test_normalize_email_trims_and_lowercases() -> None:
    assert normalize_email("  OShki@Example.COM ") == "oshki@example.com"


def test_hash_secret_is_stable_for_same_value() -> None:
    assert hash_secret("token-123") == hash_secret("token-123")
    assert hash_secret("token-123") != hash_secret("token-456")


def test_password_hash_verifies_expected_password() -> None:
    password_hash = hash_password("super-secret-pass")

    assert verify_password("super-secret-pass", password_hash) is True
    assert verify_password("wrong-pass", password_hash) is False
