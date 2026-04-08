import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.assets.models import Asset, AssetTag, TaxonomyNode, DimensionEnum, TagSource
from app.auth.models import User, UserRole
from app.auth.service import hash_password


@pytest.fixture
def sample_asset(db):
    asset = Asset(
        original_uri="s3://b/o.jpg", display_uri="s3://b/d.jpg", thumb_uri="s3://b/t.jpg",
        filename="o.jpg", width=100, height=100, file_size=100,
        feature_status={"classify": "pending", "embed": "pending"},
    )
    db.add(asset)
    db.flush()
    return asset


@pytest.fixture
def taxonomy_node(db):
    node = TaxonomyNode(dimension=DimensionEnum.category, name="上衣")
    db.add(node)
    db.flush()
    return node


def test_trigger_uses_background_by_default(db, sample_asset):
    """trigger_asset_processing uses BackgroundTasks when async_mode=background."""
    from app.assets.service import trigger_asset_processing

    mock_background = MagicMock()

    with patch("app.ai.processing.classify_asset"):
        trigger_asset_processing(db, sample_asset, ["classify"], mock_background, async_mode="background")

    mock_background.add_task.assert_called_once()


def test_trigger_uses_celery_when_mode_set(db, sample_asset):
    """trigger_asset_processing calls celery_process_asset.delay when async_mode=celery."""
    from app.assets.service import trigger_asset_processing

    mock_background = MagicMock()

    with patch("app.ai.tasks.celery_process_asset") as mock_task:
        mock_task.delay = MagicMock()
        trigger_asset_processing(db, sample_asset, ["classify"], mock_background, async_mode="celery")

    mock_task.delay.assert_called_once_with(str(sample_asset.id), ["classify"])


def test_run_reprocess_uses_celery_when_mode_set(db, sample_asset):
    """run_reprocess_job dispatches celery_run_reprocess_job.delay when async_mode=celery."""
    from app.assets.models import ProcessingJob
    from app.assets.service import run_reprocess_job

    job = ProcessingJob(stages=["classify"], total=1, status="pending")
    db.add(job)
    db.flush()

    with patch("app.ai.tasks.celery_run_reprocess_job") as mock_task:
        mock_task.delay = MagicMock()
        run_reprocess_job(db, job.id, ["classify"], async_mode="celery")

    mock_task.delay.assert_called_once_with(str(job.id), ["classify"])
