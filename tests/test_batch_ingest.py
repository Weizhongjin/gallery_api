import pytest
from unittest.mock import MagicMock, patch
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.service import _derive_group_from_key


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


def test_derive_group_from_key_prefers_code_like_folder():
    group_path, group_name = _derive_group_from_key(
        "images/25冬季图片/A712742/69.jpg",
        fallback_prefix="images/25冬季图片/",
    )
    assert group_path == "images/25冬季图片/A712742"
    assert group_name == "A712742"


def test_derive_group_from_key_uses_parent_when_no_code():
    group_path, group_name = _derive_group_from_key(
        "images/2026春季广告logo/套装/15112171&15142111/1.jpg",
        fallback_prefix="images/2026春季广告logo/",
    )
    assert group_path == "images/2026春季广告logo/套装/15112171&15142111"
    assert group_name == "15112171&15142111"
