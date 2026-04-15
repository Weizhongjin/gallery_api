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
        json={"product_code": "B120330", "year": 2026, "list_price": 399.0, "currency": "CNY"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["product_code"] == "B120330"
    assert resp.json()["year"] == 2026

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


def test_list_products_returns_paged_payload(client, admin_token, db):
    headers = {"Authorization": f"Bearer {admin_token}"}
    db.add(Product(product_code="B120001"))
    db.add(Product(product_code="B120002"))
    db.commit()

    resp = client.get("/products?page=1&page_size=1", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] >= 2
    assert len(body["items"]) == 1


def test_list_products_supports_year_and_price_range(client, admin_token, db):
    headers = {"Authorization": f"Bearer {admin_token}"}
    db.add(Product(product_code="B910001", year=2026, list_price=5200))
    db.add(Product(product_code="B910002", year=2025, list_price=2200))
    db.commit()

    resp = client.get(
        "/products?page=1&page_size=50&year_from=2026&list_price_min=5000",
        headers=headers,
    )
    assert resp.status_code == 200
    codes = {x["product_code"] for x in resp.json()["items"]}
    assert "B910001" in codes
    assert "B910002" not in codes


def test_list_products_puts_tmpuid_last(client, admin_token, db):
    headers = {"Authorization": f"Bearer {admin_token}"}
    db.add(Product(product_code="TMPUID-XYZ"))
    db.add(Product(product_code="B120999"))
    db.commit()

    resp = client.get("/products?page=1&page_size=50", headers=headers)
    assert resp.status_code == 200
    codes = [x["product_code"] for x in resp.json()["items"]]
    assert "TMPUID-XYZ" in codes
    assert "B120999" in codes
    assert codes.index("TMPUID-XYZ") > codes.index("B120999")


def test_list_products_supports_attribute_filters(client, admin_token, db):
    headers = {"Authorization": f"Bearer {admin_token}"}

    p1 = Product(product_code="P-RED-FORMAL")
    p2 = Product(product_code="P-BLUE")
    p3 = Product(product_code="P-RED")
    db.add_all([p1, p2, p3])

    red = TaxonomyNode(dimension=DimensionEnum.color, name="红色", sort_order=1, is_active=True)
    blue = TaxonomyNode(dimension=DimensionEnum.color, name="蓝色", sort_order=2, is_active=True)
    formal = TaxonomyNode(dimension=DimensionEnum.style, name="通勤", sort_order=1, is_active=True)
    db.add_all([red, blue, formal])
    db.commit()
    db.refresh(red)
    db.refresh(blue)
    db.refresh(formal)
    db.refresh(p1)
    db.refresh(p2)
    db.refresh(p3)

    db.add_all(
        [
            ProductTag(product_id=p1.id, node_id=red.id, source=ProductTagSource.human),
            ProductTag(product_id=p1.id, node_id=formal.id, source=ProductTagSource.human),
            ProductTag(product_id=p2.id, node_id=blue.id, source=ProductTagSource.human),
            ProductTag(product_id=p3.id, node_id=red.id, source=ProductTagSource.human),
        ]
    )
    db.commit()

    # Same dimension (color): OR merge.
    resp_or = client.get(
        f"/products?page=1&page_size=50&tag_ids={red.id}&tag_ids={blue.id}",
        headers=headers,
    )
    assert resp_or.status_code == 200
    codes_or = {x["product_code"] for x in resp_or.json()["items"]}
    assert {"P-RED-FORMAL", "P-BLUE", "P-RED"}.issubset(codes_or)

    # Across dimensions: AND intersection.
    resp_and = client.get(
        f"/products?page=1&page_size=50&tag_ids={red.id}&tag_ids={blue.id}&tag_ids={formal.id}",
        headers=headers,
    )
    assert resp_and.status_code == 200
    codes_and = {x["product_code"] for x in resp_and.json()["items"]}
    assert codes_and == {"P-RED-FORMAL"}


def test_list_products_supports_attribute_filters_via_asset_tags(client, admin_token, db):
    headers = {"Authorization": f"Bearer {admin_token}"}

    node = TaxonomyNode(dimension=DimensionEnum.style, name="测试风格", sort_order=1, is_active=True)
    product = Product(product_code="P-ASSET-TAG-ONLY")
    asset = Asset(
        original_uri="s3://bucket/o2.jpg",
        display_uri="s3://bucket/d2.jpg",
        thumb_uri="s3://bucket/t2.jpg",
        filename="X10001.jpg",
        width=800,
        height=1200,
        file_size=234567,
        feature_status={"classify": "done", "embed": "done"},
        asset_type=AssetType.flatlay,
        parse_status=ParseStatus.parsed,
    )
    db.add_all([node, product, asset])
    db.commit()
    db.refresh(node)
    db.refresh(product)
    db.refresh(asset)

    db.add(
        AssetProduct(
            asset_id=asset.id,
            product_id=product.id,
            relation_role=AssetProductRole.flatlay_primary,
            source="manual",
        )
    )
    db.add(
        AssetTag(
            asset_id=asset.id,
            node_id=node.id,
            source=TagSource.ai,
        )
    )
    db.commit()

    # product_tag is intentionally absent; filtering should still match by asset_tag.
    resp = client.get(f"/products?page=1&page_size=50&tag_ids={node.id}", headers=headers)
    assert resp.status_code == 200
    codes = {x["product_code"] for x in resp.json()["items"]}
    assert "P-ASSET-TAG-ONLY" in codes


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
