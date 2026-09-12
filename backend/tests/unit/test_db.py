import uuid

from app.models import User


def test_user_roundtrip(db):
    u = User(email="user@example.com", password_hash="x")
    db.add(u)
    db.flush()
    assert isinstance(u.id, uuid.UUID)
    assert db.get(User, u.id).email == "user@example.com"
