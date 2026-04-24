import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetType,
    Lookbook,
    LookbookProductSection,
    ParseStatus,
    Product,
    ProductSalesSummary,
    ProductTag,
    ProductTagSource,
    TaxonomyNode,
    DimensionEnum,
)
from app.auth.models import User, UserRole
from app.auth.service import create_access_token, hash_password
from app.products.governance import derive_product_governance_state, GovernanceState


def test_derive_governance_state_marks_missing_model_and_missing_advertising():
    state = derive_product_governance_state(
        flatlay_count=1,
        model_count=0,
        advertising_count=0,
        has_ai_assets=False,
        lookbook_count=0,
        tag_count=1,
    )

    assert state.completeness_state == "missing_model"
    assert state.aux_tags == ["missing_advertising", "lookbook_unused", "tagging_incomplete"]
    assert state.recommended_action == "start_aigc"


def test_derive_governance_state_missing_all_assets():
    state = derive_product_governance_state(
        flatlay_count=0,
        model_count=0,
        advertising_count=0,
        has_ai_assets=False,
        lookbook_count=0,
        tag_count=0,
    )
    assert state.completeness_state == "missing_all_assets"
    assert "lookbook_unused" in state.aux_tags
    assert "tagging_incomplete" in state.aux_tags
    assert state.recommended_action == "bind_assets"


def test_derive_governance_state_missing_flatlay():
    state = derive_product_governance_state(
        flatlay_count=0,
        model_count=1,
        advertising_count=1,
        has_ai_assets=False,
        lookbook_count=0,
        tag_count=3,
    )
    assert state.completeness_state == "missing_flatlay"
    assert "lookbook_unused" in state.aux_tags
    assert state.recommended_action == "bind_assets"


def test_derive_governance_state_complete_with_missing_advertising():
    state = derive_product_governance_state(
        flatlay_count=1,
        model_count=1,
        advertising_count=0,
        has_ai_assets=True,
        lookbook_count=1,
        tag_count=3,
    )
    assert state.completeness_state == "complete"
    assert "missing_advertising" in state.aux_tags
    assert "has_ai_assets" in state.aux_tags
    assert state.recommended_action == "generate_advertising_asset"


def test_derive_governance_state_complete_all_good():
    state = derive_product_governance_state(
        flatlay_count=2,
        model_count=3,
        advertising_count=1,
        has_ai_assets=False,
        lookbook_count=2,
        tag_count=5,
    )
    assert state.completeness_state == "complete"
    assert state.aux_tags == []
    assert state.recommended_action == "add_to_lookbook"


# ── API test fixtures ──────────────────────────────────────────────


def _make_asset(db, filename, asset_type=AssetType.flatlay):
    asset = Asset(
        original_uri=f"s3://bucket/o/{filename}",
        display_uri=f"s3://bucket/d/{filename}",
        thumb_uri=f"s3://bucket/t/{filename}",
        filename=filename,
        width=800,
        height=1200,
        file_size=12345,
        feature_status={},
        asset_type=asset_type,
        parse_status=ParseStatus.parsed,
    )
    db.add(asset)
    db.flush()
    return asset


def _link(db, asset, product, role=AssetProductRole.manual):
    db.add(AssetProduct(asset_id=asset.id, product_id=product.id, relation_role=role, source="manual"))
    db.flush()


@pytest.fixture
def governance_fixture(db):
    """Create 4 products with distinct completeness states."""
    fixture_user = User(
        email="gov-fixture@example.com",
        password_hash=hash_password("pw"),
        name="Gov Fixture",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(fixture_user)
    db.flush()

    # Product 1: missing_all_assets (no assets at all)
    p1 = Product(product_code="GOV-001", name="No Assets Product")
    db.add(p1)
    db.flush()

    # Product 2: missing_flatlay (has model + advertising but no flatlay)
    p2 = Product(product_code="GOV-002", name="Missing Flatlay")
    db.add(p2)
    db.flush()
    a2a = _make_asset(db, "gov002_model.jpg", AssetType.model_set)
    a2b = _make_asset(db, "gov002_ad.jpg", AssetType.advertising)
    _link(db, a2a, p2)
    _link(db, a2b, p2)

    # Product 3: missing_model (has flatlay but no model, no advertising, 1 tag, in lookbook)
    p3 = Product(product_code="GOV-003", name="Missing Model")
    db.add(p3)
    db.flush()
    a3 = _make_asset(db, "gov003_flat.jpg", AssetType.flatlay)
    _link(db, a3, p3)
    node = TaxonomyNode(dimension=DimensionEnum.category, name="上衣", sort_order=1, is_active=True)
    db.add(node)
    db.flush()
    db.add(ProductTag(product_id=p3.id, node_id=node.id, source=ProductTagSource.human))
    lb = Lookbook(title="Test LB", is_published=False, created_by=fixture_user.id)
    db.add(lb)
    db.flush()
    db.add(LookbookProductSection(lookbook_id=lb.id, product_id=p3.id, sort_order=0))

    # Product 4: complete but missing advertising, in lookbook, tags >= 2
    p4 = Product(product_code="GOV-004", name="Complete Missing Ad")
    db.add(p4)
    db.flush()
    a4a = _make_asset(db, "gov004_flat.jpg", AssetType.flatlay)
    a4b = _make_asset(db, "gov004_model.jpg", AssetType.model_set)
    _link(db, a4a, p4)
    _link(db, a4b, p4)
    db.add(ProductTag(product_id=p4.id, node_id=node.id, source=ProductTagSource.human))
    node2 = TaxonomyNode(dimension=DimensionEnum.style, name="通勤", sort_order=1, is_active=True)
    db.add(node2)
    db.flush()
    db.add(ProductTag(product_id=p4.id, node_id=node2.id, source=ProductTagSource.human))

    db.commit()
    return {
        "p1_id": str(p1.id),
        "p2_id": str(p2.id),
        "p3_id": str(p3.id),
        "p4_id": str(p4.id),
    }


@pytest.fixture
def admin_token(db):
    user = User(
        email="gov-admin@example.com",
        password_hash=hash_password("pw"),
        name="Gov Admin",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return create_access_token(str(user.id))


# ── Governance API tests ───────────────────────────────────────────


def test_governance_summary_counts_missing_states(client, admin_token, governance_fixture):
    response = client.get(
        "/products/governance/summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_products"] == 4
    assert body["missing_all_assets"] == 1
    assert body["missing_flatlay"] == 1
    assert body["missing_model"] == 1
    assert body["missing_advertising"] == 2
    assert body["in_lookbook"] == 1


def test_governance_items_filters_missing_model(client, admin_token, governance_fixture):
    response = client.get(
        "/products/governance/items?problem=missing_model&page=1&page_size=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["completeness_state"] == "missing_model"
    assert body["items"][0]["recommended_action"] == "start_aigc"


def test_governance_items_defaults_to_all(client, admin_token, governance_fixture):
    response = client.get(
        "/products/governance/items?page=1&page_size=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4


def test_governance_items_supports_search(client, admin_token, governance_fixture):
    response = client.get(
        "/products/governance/items?q=GOV-003&page=1&page_size=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["product_code"] == "GOV-003"
