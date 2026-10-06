"""Password hashing regression tests."""

from app.application.password_service import hash_password, verify_password


def test_hash_password_uses_scrypt_format() -> None:
    password_hash = hash_password("secure-password")
    assert password_hash.startswith("scrypt$")
    parts = password_hash.split("$")
    assert len(parts) == 3
    assert len(parts[1]) == 32
    assert len(parts[2]) == 64


def test_verify_password_accepts_matching_password() -> None:
    password = "secure-password"
    password_hash = hash_password(password)
    assert verify_password(password, password_hash) is True


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = hash_password("secure-password")
    assert verify_password("wrong-password", password_hash) is False


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("secure-password", "not-a-valid-hash") is False
