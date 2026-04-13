from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetTag,
    DimensionEnum,
    Product,
    TagSource,
    TaxonomyNode,
)
from app.auth.models import User, UserRole
from app.auth.service import create_access_token, hash_password


@pytest.fixture
def viewer_token(db):
    user = User(
        email="viewer_search_product@example.com",
        password_hash=hash_password("pw"),
        name="Viewer",
        role=UserRole.viewer,
    )
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


def test_product_attribute_search_groups_assets_by_product(client, db, viewer_token):
    product = Product(product_code="B540121", name="测试商品")
    node = TaxonomyNode(dimension=DimensionEnum.category, name="外套")
    db.add_all([product, node])
    db.flush()

    a1 = Asset(
        original_uri="s3://b/a1.jpg",
        display_uri="s3://b/a1_d.jpg",
        thumb_uri="s3://b/a1_t.jpg",
        filename="B540121_1.jpg",
        width=1200,
        height=1800,
        file_size=111,
        feature_status={},
    )
    a2 = Asset(
        original_uri="s3://b/a2.jpg",
        display_uri="s3://b/a2_d.jpg",
        thumb_uri="s3://b/a2_t.jpg",
        filename="B540121_2.jpg",
        width=1200,
        height=1800,
        file_size=112,
        feature_status={},
    )
    db.add_all([a1, a2])
    db.flush()

    db.add_all(
        [
            AssetProduct(asset_id=a1.id, product_id=product.id, relation_role=AssetProductRole.flatlay_primary),
            AssetProduct(asset_id=a2.id, product_id=product.id, relation_role=AssetProductRole.model_ref),
            AssetTag(asset_id=a1.id, node_id=node.id, source=TagSource.ai),
            AssetTag(asset_id=a2.id, node_id=node.id, source=TagSource.ai),
        ]
    )
    db.flush()

    resp = client.get(
        f"/search/products?tag_ids={node.id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["product_code"] == "B540121"
    assert item["matched_asset_count"] == 2
    assert item["cover_asset_id"] is not None
    assert item["cover_thumb_uri"]


def test_product_semantic_search_returns_product_dimension(client, db, viewer_token):
    p1 = Product(product_code="B530022")
    p2 = Product(product_code="B530023")
    db.add_all([p1, p2])
    db.flush()

    a1 = Asset(
        original_uri="s3://b/s1.jpg",
        display_uri="s3://b/s1_d.jpg",
        thumb_uri="s3://b/s1_t.jpg",
        filename="B530022.jpg",
        width=1000,
        height=1500,
        file_size=201,
        feature_status={},
    )
    a2 = Asset(
        original_uri="s3://b/s2.jpg",
        display_uri="s3://b/s2_d.jpg",
        thumb_uri="s3://b/s2_t.jpg",
        filename="B530023.jpg",
        width=1000,
        height=1500,
        file_size=202,
        feature_status={},
    )
    db.add_all([a1, a2])
    db.flush()

    db.add_all(
        [
            AssetProduct(asset_id=a1.id, product_id=p1.id, relation_role=AssetProductRole.flatlay_primary),
            AssetProduct(asset_id=a2.id, product_id=p2.id, relation_role=AssetProductRole.flatlay_primary),
        ]
    )
    db.flush()

    vec_1 = "[" + ",".join(["0.1"] * 768) + "]"
    vec_2 = "[" + ",".join(["0.9"] * 768) + "]"
    db.execute(
        text("INSERT INTO asset_embedding (asset_id, model_ver, vector) VALUES (:id, :ver, CAST(:v AS vector))"),
        {"id": str(a1.id), "ver": "v1", "v": vec_1},
    )
    db.execute(
        text("INSERT INTO asset_embedding (asset_id, model_ver, vector) VALUES (:id, :ver, CAST(:v AS vector))"),
        {"id": str(a2.id), "ver": "v1", "v": vec_2},
    )
    db.flush()

    mock_embed = MagicMock()
    mock_embed.embed_text.return_value = [0.1] * 768

    with patch("app.search.router.get_embedding_client", return_value=mock_embed):
        resp = client.post(
            "/search/products/semantic",
            json={"text": "米白色西装外套", "limit": 20, "page": 1, "page_size": 10},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert body["items"][0]["product_code"] == "B530022"
    assert body["items"][0]["match_reasons"] == ["semantic"]
