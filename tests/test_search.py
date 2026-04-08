import pytest
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset, AssetTag, DimensionEnum, TagSource, TaxonomyNode


@pytest.fixture
def viewer_token(db):
    user = User(
        email="viewer_search@example.com",
        password_hash=hash_password("pw"),
        name="Viewer",
        role=UserRole.viewer,
    )
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


@pytest.fixture
def tagged_assets(db):
    node_cat = TaxonomyNode(dimension=DimensionEnum.category, name="上衣_搜索")
    node_style = TaxonomyNode(dimension=DimensionEnum.style, name="商务风_搜索")
    db.add_all([node_cat, node_style])
    db.flush()

    asset1 = Asset(original_uri="s3://b/s1.jpg", display_uri="s3://b/s1d.jpg", thumb_uri="s3://b/s1t.jpg",
                   filename="s1.jpg", width=100, height=100, file_size=100, feature_status={})
    asset2 = Asset(original_uri="s3://b/s2.jpg", display_uri="s3://b/s2d.jpg", thumb_uri="s3://b/s2t.jpg",
                   filename="s2.jpg", width=100, height=100, file_size=100, feature_status={})
    db.add_all([asset1, asset2])
    db.flush()

    # asset1 has both tags; asset2 has only category
    db.add(AssetTag(asset_id=asset1.id, node_id=node_cat.id, source=TagSource.ai))
    db.add(AssetTag(asset_id=asset1.id, node_id=node_style.id, source=TagSource.ai))
    db.add(AssetTag(asset_id=asset2.id, node_id=node_cat.id, source=TagSource.ai))
    db.flush()

    return {"asset1": asset1, "asset2": asset2, "cat": node_cat, "style": node_style}


def test_search_by_single_tag(client, viewer_token, tagged_assets):
    cat_id = str(tagged_assets["cat"].id)
    response = client.get(f"/search?tag_ids={cat_id}", headers={"Authorization": f"Bearer {viewer_token}"})
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert str(tagged_assets["asset1"].id) in ids
    assert str(tagged_assets["asset2"].id) in ids


def test_search_multi_tag_and(client, viewer_token, tagged_assets):
    cat_id = str(tagged_assets["cat"].id)
    style_id = str(tagged_assets["style"].id)
    response = client.get(
        f"/search?tag_ids={cat_id}&tag_ids={style_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    # only asset1 has both tags
    assert str(tagged_assets["asset1"].id) in ids
    assert str(tagged_assets["asset2"].id) not in ids


def test_search_by_dimension(client, viewer_token, tagged_assets):
    response = client.get("/search?dimension=category", headers={"Authorization": f"Bearer {viewer_token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
