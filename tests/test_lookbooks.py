import pytest
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset


@pytest.fixture
def editor_user(db):
    user = User(
        email="editor_lb@example.com",
        password_hash=hash_password("pw"),
        name="Editor",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def editor_token(editor_user):
    return create_access_token(str(editor_user.id))


@pytest.fixture
def admin_user(db):
    user = User(
        email="admin_lb@example.com",
        password_hash=hash_password("pw"),
        name="Admin",
        role=UserRole.admin,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(str(admin_user.id))


@pytest.fixture
def buyer_user(db):
    user = User(
        email="buyer_lb@example.com",
        password_hash=hash_password("pw"),
        name="Buyer",
        role=UserRole.buyer,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def sample_asset(db):
    asset = Asset(
        original_uri="s3://b/o.jpg", display_uri="s3://b/d.jpg", thumb_uri="s3://b/t.jpg",
        filename="o.jpg", width=100, height=100, file_size=1024, feature_status={},
    )
    db.add(asset)
    db.flush()
    return asset


def test_create_lookbook(client, editor_token):
    response = client.post(
        "/lookbooks",
        json={"title": "Spring 2026"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Spring 2026"
    assert response.json()["is_published"] is False


def test_add_item_to_lookbook(client, editor_token, sample_asset):
    lb = client.post(
        "/lookbooks",
        json={"title": "LB1"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    lb_id = lb.json()["id"]

    response = client.post(
        f"/lookbooks/{lb_id}/items",
        json={"asset_id": str(sample_asset.id), "sort_order": 1},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 201

    list_resp = client.get(
        f"/lookbooks/{lb_id}/items",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["asset_id"] == str(sample_asset.id)
    assert items[0]["sort_order"] == 1


def test_publish_lookbook(client, editor_token):
    lb = client.post(
        "/lookbooks", json={"title": "Pub LB"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    lb_id = lb.json()["id"]

    response = client.post(f"/lookbooks/{lb_id}/publish", headers={"Authorization": f"Bearer {editor_token}"})
    assert response.status_code == 200
    assert response.json()["is_published"] is True


def test_assign_buyer_to_lookbook(client, admin_token, editor_token, buyer_user):
    lb = client.post(
        "/lookbooks", json={"title": "Buyer LB"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    lb_id = lb.json()["id"]

    response = client.post(
        f"/lookbooks/{lb_id}/access",
        json={"user_id": str(buyer_user.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201

    list_response = client.get(
        f"/lookbooks/{lb_id}/access",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_response.status_code == 200
    access_list = list_response.json()
    assert any(a["user_id"] == str(buyer_user.id) for a in access_list)


def test_buyer_sees_assigned_lookbooks(client, admin_token, editor_token, buyer_user):
    # Create and publish a lookbook
    lb = client.post(
        "/lookbooks", json={"title": "For Buyer"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    lb_id = lb.json()["id"]
    client.post(f"/lookbooks/{lb_id}/publish", headers={"Authorization": f"Bearer {editor_token}"})

    # Assign buyer
    client.post(
        f"/lookbooks/{lb_id}/access",
        json={"user_id": str(buyer_user.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Buyer gets their lookbooks
    buyer_token = create_access_token(str(buyer_user.id))
    response = client.get("/my/lookbooks", headers={"Authorization": f"Bearer {buyer_token}"})
    assert response.status_code == 200
    ids = [lb["id"] for lb in response.json()]
    assert lb_id in ids
