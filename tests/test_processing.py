import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.assets.models import Asset, AssetEmbedding, AssetTag, DimensionEnum, TagSource, TaxonomyCandidate, TaxonomyNode
from app.auth.models import User, UserRole
from app.auth.service import hash_password


@pytest.fixture
def sample_asset(db):
    asset = Asset(
        original_uri="s3://bucket/orig.jpg",
        display_uri="s3://bucket/display.jpg",
        thumb_uri="s3://bucket/thumb.jpg",
        filename="orig.jpg",
        width=1200, height=1600, file_size=2048,
        feature_status={"classify": "pending", "embed": "pending"},
    )
    db.add(asset)
    db.flush()
    return asset


@pytest.fixture
def taxonomy_nodes(db):
    nodes = [
        TaxonomyNode(dimension=DimensionEnum.category, name="上衣"),
        TaxonomyNode(dimension=DimensionEnum.style, name="商务风"),
        TaxonomyNode(dimension=DimensionEnum.color, name="藏青色"),
        TaxonomyNode(dimension=DimensionEnum.scene, name="通勤"),
        TaxonomyNode(dimension=DimensionEnum.detail, name="西装领"),
    ]
    db.add_all(nodes)
    db.flush()
    return {n.name: n for n in nodes}


def test_classify_writes_asset_tags(db, sample_asset, taxonomy_nodes):
    from app.ai.processing import classify_asset

    mock_vlm = MagicMock()
    mock_vlm.classify.return_value = {
        "category": "上衣",
        "style": ["商务风"],
        "color": ["藏青色"],
        "scene": ["通勤"],
        "detail": ["西装领"],
    }
    mock_storage = MagicMock()
    mock_storage.get_presigned_url.return_value = "https://signed.example.com/display.jpg"

    classify_asset(db, sample_asset, vlm_client=mock_vlm, storage=mock_storage)

    tags = db.query(AssetTag).filter(AssetTag.asset_id == sample_asset.id).all()
    assert len(tags) == 5
    assert all(t.source == TagSource.ai for t in tags)

    db.refresh(sample_asset)
    assert sample_asset.feature_status["classify"] == "done"


def test_classify_unknown_label_creates_candidate(db, sample_asset, taxonomy_nodes):
    from app.ai.processing import classify_asset

    mock_vlm = MagicMock()
    mock_vlm.classify.return_value = {
        "category": "上衣",
        "style": ["未知风格XYZ"],  # not in taxonomy
        "color": [],
        "scene": [],
        "detail": [],
    }
    mock_storage = MagicMock()
    mock_storage.get_presigned_url.return_value = "https://signed.example.com/display.jpg"

    classify_asset(db, sample_asset, vlm_client=mock_vlm, storage=mock_storage)

    cand = db.query(TaxonomyCandidate).filter(TaxonomyCandidate.raw_label == "未知风格XYZ").first()
    assert cand is not None
    assert cand.dimension == DimensionEnum.style
    assert cand.hit_count == 1


def test_classify_clears_existing_ai_tags(db, sample_asset, taxonomy_nodes):
    from app.ai.processing import classify_asset

    # pre-existing AI tag
    old_tag = AssetTag(asset_id=sample_asset.id, node_id=taxonomy_nodes["商务风"].id, source=TagSource.ai)
    db.add(old_tag)
    db.flush()

    mock_vlm = MagicMock()
    mock_vlm.classify.return_value = {
        "category": "上衣", "style": [], "color": [], "scene": [], "detail": []
    }
    mock_storage = MagicMock()
    mock_storage.get_presigned_url.return_value = "https://signed.example.com/display.jpg"

    classify_asset(db, sample_asset, vlm_client=mock_vlm, storage=mock_storage)

    remaining = db.query(AssetTag).filter(
        AssetTag.asset_id == sample_asset.id, AssetTag.source == TagSource.ai
    ).all()
    # only "上衣" tag should remain (商务风 cleared, 上衣 added)
    assert len(remaining) == 1


def test_embed_asset_writes_embedding(db, sample_asset):
    from app.ai.processing import embed_asset

    mock_embed = MagicMock()
    mock_embed.embed_image.return_value = [0.1] * 768
    mock_storage = MagicMock()
    mock_storage.get_presigned_url.return_value = "https://signed.example.com/display.jpg"

    embed_asset(db, sample_asset, embed_client=mock_embed, storage=mock_storage, model_ver="v1")

    embedding = db.query(AssetEmbedding).filter(AssetEmbedding.asset_id == sample_asset.id).first()
    assert embedding is not None
    assert embedding.model_ver == "v1"

    db.refresh(sample_asset)
    assert sample_asset.feature_status["embed"] == "done"
