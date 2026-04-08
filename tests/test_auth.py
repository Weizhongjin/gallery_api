import uuid
import pytest
from app.auth.service import hash_password, verify_password, create_access_token, decode_token
from app.auth.models import User, UserRole


def test_password_hash_and_verify():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_create_and_decode_token():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    assert decode_token(token) == user_id


def test_login_success(client, db):
    user = User(
        email="test@example.com",
        password_hash=hash_password("password123"),
        name="Test User",
        role=UserRole.admin,
    )
    db.add(user)
    db.flush()

    response = client.post("/auth/login", json={"email": "test@example.com", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, db):
    user = User(
        email="user2@example.com",
        password_hash=hash_password("correct"),
        name="User2",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()

    response = client.post("/auth/login", json={"email": "user2@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_get_me(client, db):
    user = User(
        email="me@example.com",
        password_hash=hash_password("pw"),
        name="Me",
        role=UserRole.viewer,
    )
    db.add(user)
    db.flush()

    login = client.post("/auth/login", json={"email": "me@example.com", "password": "pw"})
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
    assert response.json()["role"] == "viewer"
