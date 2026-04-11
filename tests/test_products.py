import uuid

import pytest

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetTag,
    AssetType,
    ParseStatus,
    Product,
    ProductTag,
    ProductTagSource,
    TagSource,
    TaxonomyNode,
    DimensionEnum,
)
from app.auth.models import User, UserRole
from app.auth.service import create_access_token, hash_password


@pytest.fixture
def admin_token(db):
    user = User(
        id=uuid.uuid4(),
        email="products-admin@example.com",
        password_hash=hash_password("pw"),
        name="Admin",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return create_access_token(str(user.id))


@pytest.fixture
def sample_asset(db):
    asset = Asset(
        original_uri="s3://bucket/o.jpg",
        display_uri="s3://bucket/d.jpg",
        thumb_uri="s3://bucket/t.jpg",
        filename="B120330.jpg",
        width=1000,
        height=1200,
        file_size=123456,
        feature_status={"classify": "pending", "embed": "pending"},
        asset_type=AssetType.flatlay,
        parse_status=ParseStatus.parsed,
        source_dataset="26春单品平铺图",
        source_relpath="26春单品平铺图/B120330.jpg",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def test_upsert_and_bind_product(client, admin_token, sample_asset, db):
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.post(
        "/products/upsert",
        json={"product_code": "B120330", "list_price": 399.0, "currency": "CNY"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["product_code"] == "B120330"

    bind = client.post(
        f"/assets/{sample_asset.id}/products/bind",
        json={"product_code": "B120330", "relation_role": "flatlay_primary", "source": "manual"},
        headers=headers,
    )
    assert bind.status_code == 201

    lst = client.get(f"/assets/{sample_asset.id}/products", headers=headers)
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["product_code"] == "B120330"


def test_rebuild_product_tags(client, admin_token, sample_asset, db):
    headers = {"Authorization": f"Bearer {admin_token}"}

    product = Product(product_code="B120331")
    db.add(product)
    db.commit()
    db.refresh(product)

    node = TaxonomyNode(dimension=DimensionEnum.category, name="连衣裙", name_en="dress", sort_order=1, is_active=True)
    db.add(node)
    db.commit()
    db.refresh(node)

    db.add(
        AssetTag(
            asset_id=sample_asset.id,
            node_id=node.id,
            source=TagSource.ai,
        )
    )
    db.add(
        AssetProduct(
            asset_id=sample_asset.id,
            product_id=product.id,
            relation_role=AssetProductRole.flatlay_primary,
            source="manual",
        )
    )
    db.commit()

    resp = client.post(f"/products/{product.id}/tags/rebuild", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["aggregated_count"] >= 1

    tags = db.query(ProductTag).filter(ProductTag.product_id == product.id).all()
    assert any(t.node_id == node.id and t.source == ProductTagSource.aggregated for t in tags)
