import uuid
from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import MagicMock, patch
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset, ProcessingJob


@pytest.fixture
def editor_token(db):
    user = User(email="editor_rp@example.com", password_hash=hash_password("pw"), name="Ed", role=UserRole.editor)
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


@pytest.fixture
def sample_asset(db):
    asset = Asset(
        original_uri="s3://b/o.jpg", display_uri="s3://b/d.jpg", thumb_uri="s3://b/t.jpg",
        filename="o.jpg", width=100, height=100, file_size=100,
        feature_status={"classify": "done", "embed": "done"},
    )
    db.add(asset)
    db.flush()
    return asset


def test_trigger_single_process(client, editor_token, sample_asset):
    """POST /assets/{id}/process returns 202."""
    with patch("app.ai.processing.classify_asset"), patch("app.ai.processing.embed_asset"):
        response = client.post(
            f"/assets/{sample_asset.id}/process",
            json={"stages": ["classify", "embed"]},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert response.status_code == 202
    data = response.json()
    assert "asset_id" in data
    assert data["stages"] == ["classify", "embed"]


def test_reprocess_all_returns_job(client, editor_token, sample_asset, monkeypatch):
    """POST /assets/reprocess returns job_id."""
    from app.assets import router as assets_router

    monkeypatch.setattr(assets_router.settings, "async_mode", "background")
    with patch("app.assets.router.run_reprocess_job_standalone") as mock_background_runner:
        response = client.post(
            "/assets/reprocess",
            json={"stages": ["classify"]},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["stages"] == ["classify"]
    mock_background_runner.assert_called_once()


def test_reprocess_all_dispatches_celery_when_mode_set(client, editor_token, sample_asset, monkeypatch):
    """POST /assets/reprocess dispatches Celery directly when async_mode=celery."""
    from app.assets import router as assets_router

    monkeypatch.setattr(assets_router.settings, "async_mode", "celery")
    with patch("app.assets.router.run_reprocess_job") as mock_run_reprocess:
        with patch("app.assets.router.run_reprocess_job_standalone") as mock_background_runner:
            response = client.post(
                "/assets/reprocess",
                json={"stages": ["classify"]},
                headers={"Authorization": f"Bearer {editor_token}"},
            )

    assert response.status_code == 202
    assert mock_run_reprocess.call_count == 1
    assert mock_run_reprocess.call_args.kwargs["async_mode"] == "celery"
    mock_background_runner.assert_not_called()


def test_get_job_status(client, editor_token, db):
    """GET /jobs/{job_id} returns job status."""
    job = ProcessingJob(
        id=uuid.uuid4(),
        status="running",
        stages=["classify"],
        total=10,
        processed=3,
        failed_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    db.add(job)
    db.flush()

    response = client.get(
        f"/jobs/{job.id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["total"] == 10
    assert data["processed"] == 3
    assert data["completed"] == 3
    assert data["remaining"] == 7
    assert data["progress_pct"] == 30.0
    assert data["elapsed_seconds"] is not None
    assert data["throughput_items_per_min"] is not None
