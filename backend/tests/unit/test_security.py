from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_and_verify():
    h = hash_password("S3cret!!")
    assert h != "S3cret!!"
    assert verify_password("S3cret!!", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("user-id-123")
    assert decode_access_token(token) == "user-id-123"
