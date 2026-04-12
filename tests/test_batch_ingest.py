import pytest
from unittest.mock import MagicMock, patch
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import AssetType, ParseStatus
from app.assets.service import _derive_group_from_key, _infer_from_storage_key


@pytest.fixture
def editor_token(db):
    user = User(email="editor_bi@example.com", password_hash=hash_password("pw"), name="Ed", role=UserRole.editor)
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


def test_batch_ingest_storage_returns_job(client, editor_token, monkeypatch):
    """POST /assets/batch-ingest/storage returns job_id."""
    import io
    from PIL import Image
    from app.config import settings

    monkeypatch.setattr(settings, "async_mode", "background")

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
        with patch("app.assets.service._ingest_storage_batch_standalone") as mock_runner:
            response = client.post(
                "/assets/batch-ingest/storage",
                json={"prefix": "images/product/", "stages": []},
                headers={"Authorization": f"Bearer {editor_token}"},
            )

    assert response.status_code == 202
    assert "job_id" in response.json()
    mock_runner.assert_called_once()


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


def test_infer_advertising_set_single_digit_folder_uses_group_tempuid():
    asset_type, dataset, rel, status, codes = _infer_from_storage_key(
        "images/2026春季广告logo/套装/5/12.jpg",
        prefix="images/",
    )
    assert asset_type == AssetType.advertising
    assert dataset == "2026春季广告logo"
    assert rel == "2026春季广告logo/套装/5/12.jpg"
    assert status == ParseStatus.parsed
    assert len(codes) == 1
    assert codes[0].startswith("TMPUID-GRP-5-")


def test_infer_advertising_set_real_folder_keeps_real_codes():
    asset_type, dataset, rel, status, codes = _infer_from_storage_key(
        "images/2026春季广告logo/套装/15112171&15142111/1.jpg",
        prefix="images/",
    )
    assert asset_type == AssetType.advertising
    assert dataset == "2026春季广告logo"
    assert rel == "2026春季广告logo/套装/15112171&15142111/1.jpg"
    assert status == ParseStatus.parsed
    assert codes == ["15112171", "15142111"]


def test_infer_flatlay_uses_filename_code_when_regex_miss():
    asset_type, dataset, rel, status, codes = _infer_from_storage_key(
        "images/25冬单品平铺图/A7S0200.jpg",
        prefix="images/",
    )
    assert asset_type == AssetType.flatlay
    assert dataset == "25冬单品平铺图"
    assert rel == "25冬单品平铺图/A7S0200.jpg"
    assert status == ParseStatus.parsed
    assert codes == ["A7S0200"]


def test_infer_flatlay_uses_numeric_filename_code_when_not_tiny_index():
    asset_type, dataset, rel, status, codes = _infer_from_storage_key(
        "images/26春单品平铺图/50308.JPG",
        prefix="images/",
    )
    assert asset_type == AssetType.flatlay
    assert dataset == "26春单品平铺图"
    assert rel == "26春单品平铺图/50308.JPG"
    assert status == ParseStatus.parsed
    assert codes == ["50308"]
