import io
import pytest
from unittest.mock import MagicMock
from PIL import Image

from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset, AssetTag, DimensionEnum, TagSource, TaxonomyNode
from app.storage import S3Storage


def make_jpeg() -> bytes:
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def editor_token(db):
    user = User(
        email="editor_tags@example.com",
        password_hash=hash_password("pw"),
        name="Editor",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


@pytest.fixture
def sample_asset(db):
    asset = Asset(
        original_uri="s3://bucket/orig.jpg",
        display_uri="s3://bucket/display.jpg",
        thumb_uri="s3://bucket/thumb.jpg",
        filename="orig.jpg",
        width=100,
        height=100,
        file_size=1024,
        feature_status={},
    )
    db.add(asset)
    db.flush()
    return asset


@pytest.fixture
def sample_node(db):
    node = TaxonomyNode(
        dimension=DimensionEnum.category,
        name="上衣",
    )
    db.add(node)
    db.flush()
    return node


def test_patch_human_tags_add(client, editor_token, sample_asset, sample_node):
    response = client.patch(
        f"/assets/{sample_asset.id}/tags",
        json={"add": [str(sample_node.id)], "remove": []},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert any(t["node_id"] == str(sample_node.id) and t["source"] == "human" for t in data["tags"])


def test_patch_human_tags_remove(client, editor_token, sample_asset, sample_node, db):
    tag = AssetTag(asset_id=sample_asset.id, node_id=sample_node.id, source=TagSource.human)
    db.add(tag)
    db.flush()

    response = client.patch(
        f"/assets/{sample_asset.id}/tags",
        json={"add": [], "remove": [str(sample_node.id)]},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    assert not any(t["node_id"] == str(sample_node.id) for t in response.json()["tags"])


def test_list_assets_filter_by_tag(client, editor_token, sample_asset, sample_node, db):
    tag = AssetTag(asset_id=sample_asset.id, node_id=sample_node.id, source=TagSource.ai)
    db.add(tag)
    db.flush()

    response = client.get(
        f"/assets?tag_ids={sample_node.id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    ids = [a["id"] for a in response.json()]
    assert str(sample_asset.id) in ids


def test_get_asset_tags_readonly(client, editor_token, sample_asset, sample_node, db):
    tag = AssetTag(asset_id=sample_asset.id, node_id=sample_node.id, source=TagSource.ai)
    db.add(tag)
    db.flush()

    response = client.get(
        f"/assets/{sample_asset.id}/tags",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert any(t["node_id"] == str(sample_node.id) and t["source"] == "ai" for t in body)


def test_get_asset_tags_not_found(client, editor_token):
    response = client.get(
        "/assets/00000000-0000-0000-0000-000000000000/tags",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 404
