import pytest
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset, AssetProduct, AssetProductRole, Product, Lookbook


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


# --- Section-based editor tests ---


@pytest.fixture
def product_with_ranked_assets(db):
    product = Product(product_code="B103125", name="西装外套")
    db.add(product)
    db.flush()

    assets = []
    for i, (suffix, role) in enumerate([
        ("flatlay", AssetProductRole.flatlay_primary),
        ("ad", AssetProductRole.advertising_ref),
        ("model", AssetProductRole.model_ref),
    ]):
        a = Asset(
            original_uri=f"s3://b/o_{suffix}.jpg",
            display_uri=f"s3://b/d_{suffix}.jpg",
            thumb_uri=f"s3://b/t_{suffix}.jpg",
            filename=f"{suffix}.jpg",
            width=100, height=100, file_size=1024 * (i + 1), feature_status={},
        )
        db.add(a)
        db.flush()
        assets.append(a)
        ap = AssetProduct(
            asset_id=a.id, product_id=product.id,
            relation_role=role, source="test",
        )
        db.add(ap)

    db.flush()
    # Expected order by role priority: flatlay_primary(1), model_ref(3), advertising_ref(4)
    return {
        "product_id": product.id,
        "expected_asset_ids": [str(assets[0].id), str(assets[2].id), str(assets[1].id)],
    }


def test_add_product_section_uses_role_priority(client, editor_token, product_with_ranked_assets):
    lb = client.post("/lookbooks", json={"title": "Section LB"}, headers={"Authorization": f"Bearer {editor_token}"})
    lb_id = lb.json()["id"]

    response = client.post(
        f"/lookbooks/{lb_id}/sections/products",
        json={"product_id": str(product_with_ranked_assets["product_id"])},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["product_id"] == str(product_with_ranked_assets["product_id"])
    assert [item["asset_id"] for item in body["items"]] == product_with_ranked_assets["expected_asset_ids"]
    assert body["cover_asset_id"] == product_with_ranked_assets["expected_asset_ids"][0]


def test_add_product_section_rejects_duplicate(client, editor_token, product_with_ranked_assets):
    lb = client.post("/lookbooks", json={"title": "Dup LB"}, headers={"Authorization": f"Bearer {editor_token}"})
    lb_id = lb.json()["id"]

    resp1 = client.post(
        f"/lookbooks/{lb_id}/sections/products",
        json={"product_id": str(product_with_ranked_assets["product_id"])},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        f"/lookbooks/{lb_id}/sections/products",
        json={"product_id": str(product_with_ranked_assets["product_id"])},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp2.status_code == 409


@pytest.fixture
def seeded_section(db, editor_user, sample_asset, sample_product):
    lb = Lookbook(title="Editor Shape LB", created_by=editor_user.id)
    db.add(lb)
    db.flush()

    second_asset = Asset(
        original_uri="s3://b/o_ed.jpg", display_uri="s3://b/d_ed.jpg", thumb_uri="s3://b/t_ed.jpg",
        filename="ed.jpg", width=100, height=100, file_size=2048, feature_status={},
    )
    db.add(second_asset)
    db.flush()

    from app.assets.models import LookbookProductSection, LookbookSectionItem
    section = LookbookProductSection(
        lookbook_id=lb.id, product_id=sample_product.id, sort_order=0, cover_asset_id=sample_asset.id,
    )
    db.add(section)
    db.flush()

    item1 = LookbookSectionItem(section_id=section.id, asset_id=sample_asset.id, sort_order=0, source="system", is_cover=True)
    item2 = LookbookSectionItem(section_id=section.id, asset_id=second_asset.id, sort_order=1, source="manual", is_cover=False)
    db.add_all([item1, item2])
    db.flush()

    return {"lookbook_id": str(lb.id), "product_id": str(sample_product.id)}


def test_get_lookbook_sections_returns_editor_shape(client, editor_token, seeded_section):
    response = client.get(
        f"/lookbooks/{seeded_section['lookbook_id']}/sections",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["product_id"] == seeded_section["product_id"]
    assert len(body[0]["items"]) == 2


def test_buyer_items_are_flattened_from_sections(client, admin_token, editor_token, buyer_user, seeded_section):
    lb_id = seeded_section["lookbook_id"]

    # Publish and grant buyer access
    client.post(f"/lookbooks/{lb_id}/publish", headers={"Authorization": f"Bearer {editor_token}"})
    client.post(
        f"/lookbooks/{lb_id}/access",
        json={"user_id": str(buyer_user.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    buyer_token = create_access_token(str(buyer_user.id))
    response = client.get(
        f"/my/lookbooks/{lb_id}/items",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert all("asset_id" in item for item in items)


# --- Section item refinement tests ---

@pytest.fixture
def sample_product(db):
    from app.assets.models import Product
    product = Product(product_code="TEST-001", name="Test Product")
    db.add(product)
    db.flush()
    return product


def test_create_product_section_and_item(db, editor_user, sample_asset, sample_product):
    from app.assets.models import Lookbook, LookbookProductSection, LookbookSectionItem

    lb = Lookbook(title="Model Test LB", created_by=editor_user.id)
    db.add(lb)
    db.flush()

    section = LookbookProductSection(
        lookbook_id=lb.id,
        product_id=sample_product.id,
        sort_order=0,
        cover_asset_id=sample_asset.id,
    )
    db.add(section)
    db.flush()

    item = LookbookSectionItem(
        section_id=section.id,
        asset_id=sample_asset.id,
        sort_order=0,
        source="system",
        is_cover=True,
    )
    db.add(item)
    db.flush()

    assert section.product_id == sample_product.id
    assert section.lookbook_id == lb.id
    assert item.asset_id == sample_asset.id
    assert item.source == "system"
    assert item.is_cover is True


@pytest.fixture
def seeded_section_with_two_items(db, editor_user, sample_asset, sample_product):
    from app.assets.models import Lookbook, LookbookProductSection, LookbookSectionItem
    from app.assets.models import Asset as _Asset

    lb = Lookbook(title="Section Test LB", created_by=editor_user.id)
    db.add(lb)
    db.flush()

    second_asset = _Asset(
        original_uri="s3://b/o2.jpg", display_uri="s3://b/d2.jpg", thumb_uri="s3://b/t2.jpg",
        filename="o2.jpg", width=100, height=100, file_size=2048, feature_status={},
    )
    db.add(second_asset)
    db.flush()

    section = LookbookProductSection(
        lookbook_id=lb.id,
        product_id=sample_product.id,
        sort_order=0,
        cover_asset_id=sample_asset.id,
    )
    db.add(section)
    db.flush()

    item1 = LookbookSectionItem(
        section_id=section.id, asset_id=sample_asset.id, sort_order=0, source="system", is_cover=True,
    )
    item2 = LookbookSectionItem(
        section_id=section.id, asset_id=second_asset.id, sort_order=1, source="system", is_cover=False,
    )
    db.add_all([item1, item2])
    db.flush()

    return {
        "lookbook_id": str(lb.id),
        "section_id": str(section.id),
        "cover_asset_id": str(sample_asset.id),
        "fallback_asset_id": str(second_asset.id),
    }


def test_remove_section_item_updates_section_cover(client, editor_token, seeded_section_with_two_items):
    # Delete the cover item
    response = client.delete(
        f"/lookbooks/{seeded_section_with_two_items['lookbook_id']}"
        f"/sections/{seeded_section_with_two_items['section_id']}"
        f"/items/{seeded_section_with_two_items['cover_asset_id']}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 204

    # Verify cover fell back to the remaining item
    refreshed = client.get(
        f"/lookbooks/{seeded_section_with_two_items['lookbook_id']}/sections",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert refreshed.status_code == 200
    section = refreshed.json()[0]
    assert section["cover_asset_id"] == seeded_section_with_two_items["fallback_asset_id"]
    assert len(section["items"]) == 1
    assert section["items"][0]["is_cover"] is True


def test_remove_last_section_item_clears_cover(client, editor_token, db, sample_product):
    from app.assets.models import Lookbook, LookbookProductSection, LookbookSectionItem

    lb = Lookbook(title="Empty Section LB", created_by=db.get(User, db.query(User).filter(User.email == "editor_lb@example.com").first().id).id if False else editor_token)
    # Use editor_user from token — we'll look up by email isn't clean, so pass through conftest
    # Instead, create directly with DB
    import uuid as _uuid
    editor = db.query(User).filter(User.email == "editor_lb@example.com").first()

    lb = Lookbook(title="Empty Section LB", created_by=editor.id)
    db.add(lb)
    db.flush()

    section = LookbookProductSection(
        lookbook_id=lb.id,
        product_id=sample_product.id,
        sort_order=0,
        cover_asset_id=None,
    )
    db.add(section)
    db.flush()

    asset = Asset(
        original_uri="s3://b/o3.jpg", display_uri="s3://b/d3.jpg", thumb_uri="s3://b/t3.jpg",
        filename="o3.jpg", width=100, height=100, file_size=512, feature_status={},
    )
    db.add(asset)
    db.flush()

    section.cover_asset_id = asset.id
    item = LookbookSectionItem(
        section_id=section.id, asset_id=asset.id, sort_order=0, source="system", is_cover=True,
    )
    db.add(item)
    db.flush()

    # Delete the only item
    response = client.delete(
        f"/lookbooks/{str(lb.id)}/sections/{str(section.id)}/items/{str(asset.id)}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 204

    # Verify cover is cleared
    refreshed = client.get(
        f"/lookbooks/{str(lb.id)}/sections",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert refreshed.status_code == 200
    sec = refreshed.json()[0]
    assert sec["cover_asset_id"] is None
    assert len(sec["items"]) == 0
