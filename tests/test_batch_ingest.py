import pytest
from unittest.mock import MagicMock, patch
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token


@pytest.fixture
def editor_token(db):
    user = User(email="editor_bi@example.com", password_hash=hash_password("pw"), name="Ed", role=UserRole.editor)
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


def test_batch_ingest_storage_returns_job(client, editor_token):
    """POST /assets/batch-ingest/storage returns job_id."""
    import io
    from PIL import Image

    # Create a real minimal JPEG in memory
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), color=(100, 150, 200)).save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    mock_s3 = MagicMock()
    mock_s3.list_objects.return_value = [
        "images/product/001.jpg",
        "images/product/002.jpg",
    ]
    mock_s3.get_object.return_value = image_bytes
    mock_s3.upload.return_value = "s3://bucket/some/key.jpg"
    mock_s3.get_presigned_url.return_value = "https://signed.example.com/key.jpg"

    with patch("app.assets.service.get_storage", return_value=mock_s3):
        response = client.post(
            "/assets/batch-ingest/storage",
            json={"prefix": "images/product/", "stages": []},
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert response.status_code == 202
    assert "job_id" in response.json()
