import uuid
from sqlalchemy import text
from app.assets.models import Asset, AssetType, ParseStatus, Product
from app.aigc.models import (
    AigcTask, AigcTaskStatus, AigcTaskCandidate,
    AigcPromptTemplate, AigcPromptTemplateStatus,
)
from app.auth.models import User, UserRole
from app.auth.service import hash_password


def _make_user(db):
    user = User(
        email="aigc_test@example.com",
        password_hash=hash_password("pw"),
        name="AigcTester",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()
    return user


def _make_product(db):
    product = Product(product_code="AIGC-TEST-001")
    db.add(product)
    db.flush()
    return product


def _make_flatlay_asset(db):
    asset = Asset(
        original_uri="s3://bucket/flat.jpg",
        display_uri="s3://bucket/flat-display.jpg",
        thumb_uri="s3://bucket/flat-thumb.jpg",
        filename="flat.jpg",
        width=1000,
        height=1200,
        file_size=12345,
        feature_status={},
        asset_type=AssetType.flatlay,
        parse_status=ParseStatus.parsed,
    )
    db.add(asset)
    db.flush()
    return asset


def _ensure_aigc_task_optimization_columns(db):
    db.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS workflow_type varchar NOT NULL DEFAULT 'base'"))
    db.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS source_task_id uuid NULL"))
    db.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS source_candidate_id uuid NULL"))
    db.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS optimize_prompt varchar NULL"))


def test_aigc_task_defaults(db):
    user = _make_user(db)
    product = _make_product(db)
    asset = _make_flatlay_asset(db)

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=asset.id,
        flatlay_original_uri=asset.original_uri,
        reference_source="library",
        reference_asset_id=asset.id,
        reference_original_uri=asset.original_uri,
        template_version=1,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    assert task.status == AigcTaskStatus.queued
    assert task.face_deidentify_enabled is True
    assert task.timeout_seconds == 900
    assert task.candidate_count == 2
    assert task.provider == "seedream_ark"
    assert task.model_name == "doubao-seedream-4-5-251128"


def test_aigc_task_optimization_defaults_and_lineage(db):
    _ensure_aigc_task_optimization_columns(db)
    user = _make_user(db)
    product = _make_product(db)
    asset = _make_flatlay_asset(db)

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=asset.id,
        flatlay_original_uri=asset.original_uri,
        reference_source="library",
        template_version=1,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    assert task.workflow_type == "base"
    assert task.source_task_id is None
    assert task.source_candidate_id is None
    assert task.optimize_prompt is None


def test_aigc_task_candidate(db):
    user = _make_user(db)
    product = _make_product(db)
    asset = _make_flatlay_asset(db)

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=asset.id,
        flatlay_original_uri=asset.original_uri,
        reference_source="library",
        template_version=1,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    candidate = AigcTaskCandidate(
        task_id=task.id,
        seq_no=1,
        image_uri="s3://bucket/candidate-1.jpg",
        thumb_uri="s3://bucket/candidate-1-thumb.jpg",
        width=1024,
        height=1536,
        file_size=50000,
    )
    db.add(candidate)
    db.flush()

    assert candidate.is_selected is False
    assert candidate.seq_no == 1


def test_asset_is_ai_generated_default(db):
    asset = Asset(
        original_uri="s3://bucket/test.jpg",
        display_uri="s3://bucket/test-d.jpg",
        thumb_uri="s3://bucket/test-t.jpg",
        filename="test.jpg",
        width=100,
        height=100,
        file_size=100,
        feature_status={},
    )
    db.add(asset)
    db.flush()
    assert asset.is_ai_generated is False


def test_aigc_prompt_template(db):
    user = _make_user(db)
    template = AigcPromptTemplate(
        name="虚拟试穿 v1",
        status=AigcPromptTemplateStatus.active,
        is_default=True,
        created_by=user.id,
    )
    db.add(template)
    db.flush()

    assert template.is_default is True
    assert template.status == AigcPromptTemplateStatus.active
