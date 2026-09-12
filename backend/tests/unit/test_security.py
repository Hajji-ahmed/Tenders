from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_and_verify():
    h = hash_password("S3cret!!")
    assert h != "S3cret!!"
    assert verify_password("S3cret!!", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("user-id-123")
    assert decode_access_token(token) == "user-id-123"


def _forge(**claims) -> str:
    return jwt.encode(claims, get_settings().secret_key, algorithm="HS256")


def test_token_with_excessive_lifetime_is_rejected():
    now = datetime.now(UTC)
    token = _forge(sub="x", iat=now, exp=now + timedelta(days=3650))
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_token_without_exp_is_rejected():
    token = _forge(sub="x", iat=datetime.now(UTC))
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_expired_token_is_rejected():
    now = datetime.now(UTC)
    token = _forge(sub="x", iat=now - timedelta(hours=2), exp=now - timedelta(hours=1))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)
