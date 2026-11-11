from datetime import timedelta
import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_password_hashing_and_verification():
    plain = "SuperSecure#2026"
    hashed = hash_password(plain)

    assert hashed.startswith("$argon2id$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword#1", hashed) is False


def test_password_strength_validation():
    assert validate_password_strength("weak") is not None
    assert validate_password_strength("alllowercasechars") is not None
    assert validate_password_strength("1234567890") is not None
    assert validate_password_strength("ValidPassword#1") is None


def test_jwt_creation_and_successful_verification():
    token = create_access_token(
        user_id="user-123",
        username="john_doe",
        role="OPERATIONS_MANAGER",
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["username"] == "john_doe"
    assert payload["role"] == "OPERATIONS_MANAGER"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired_token():
    token = create_access_token(
        user_id="user-123",
        username="john_doe",
        role="ANALYST",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_invalid_token():
    invalid_token = "invalid.token.signature"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(invalid_token)


def test_jwt_wrong_secret_fails():
    token = jwt.encode(
        {"sub": "123", "exp": 9999999999, "iat": 1000},
        "wrong-secret-key-1234567890-32bytes-min",
        algorithm="HS256",
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
