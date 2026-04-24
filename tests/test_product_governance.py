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
