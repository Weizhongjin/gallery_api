import pytest
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token


@pytest.fixture
def admin_token(db):
    user = User(
        email="admin_tax@example.com",
        password_hash=hash_password("pw"),
        name="Admin",
        role=UserRole.admin,
    )
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


def test_create_taxonomy_node(client, admin_token):
    response = client.post(
        "/taxonomy/nodes",
        json={"dimension": "category", "name": "上衣", "name_en": "Top", "sort_order": 1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "上衣"
    assert data["dimension"] == "category"
    assert data["is_active"] is True


def test_list_taxonomy(client, admin_token):
    client.post(
        "/taxonomy/nodes",
        json={"dimension": "style", "name": "商务风"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    response = client.get("/taxonomy", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_patch_taxonomy_node(client, admin_token):
    create = client.post(
        "/taxonomy/nodes",
        json={"dimension": "color", "name": "红色"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    node_id = create.json()["id"]

    response = client.patch(
        f"/taxonomy/nodes/{node_id}",
        json={"name_en": "Red"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name_en"] == "Red"


def test_delete_taxonomy_node_soft(client, admin_token, db):
    create = client.post(
        "/taxonomy/nodes",
        json={"dimension": "scene", "name": "户外"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    node_id = create.json()["id"]

    response = client.delete(
        f"/taxonomy/nodes/{node_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204

    from app.assets.models import TaxonomyNode
    import uuid
    node = db.get(TaxonomyNode, uuid.UUID(node_id))
    assert node is not None
    assert node.is_active is False


def test_list_candidates_empty(client, admin_token):
    response = client.get("/taxonomy/candidates", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
