import pytest
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token


@pytest.fixture
def admin_token(db):
    user = User(
        email="admin@example.com",
        password_hash=hash_password("pw"),
        name="Admin",
        role=UserRole.admin,
    )
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


@pytest.fixture
def editor_token(db):
    user = User(
        email="editor@example.com",
        password_hash=hash_password("pw"),
        name="Editor",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


def test_create_user(client, admin_token):
    response = client.post(
        "/users",
        json={"email": "buyer1@example.com", "password": "pass123", "name": "Buyer One", "role": "buyer", "company": "ABC Corp"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "buyer1@example.com"
    assert data["role"] == "buyer"
    assert "password" not in data
    assert "password_hash" not in data


def test_create_user_requires_admin(client, editor_token):
    response = client.post(
        "/users",
        json={"email": "x@example.com", "password": "pw", "name": "X", "role": "viewer"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 403


def test_list_users(client, admin_token):
    response = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_patch_user(client, admin_token):
    create = client.post(
        "/users",
        json={"email": "patch@example.com", "password": "pw", "name": "Patch Me", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    user_id = create.json()["id"]

    response = client.patch(
        f"/users/{user_id}",
        json={"name": "Patched"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Patched"


def test_delete_user_soft(client, admin_token, db):
    create = client.post(
        "/users",
        json={"email": "delete@example.com", "password": "pw", "name": "Del", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    user_id = create.json()["id"]

    response = client.delete(f"/users/{user_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 204

    from app.auth.models import User as UserModel
    import uuid
    user = db.get(UserModel, uuid.UUID(user_id))
    assert user is not None
    assert user.is_active is False
