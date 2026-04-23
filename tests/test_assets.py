import io
import pytest
from unittest.mock import MagicMock
from PIL import Image

from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset, AssetType
from app.storage import S3Storage


def make_jpeg_bytes(width=100, height=100) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def editor_token(db):
    user = User(
        email="editor@example.com",
        password_hash=hash_password("pw"),
        name="Editor",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


@pytest.fixture
def mock_storage(monkeypatch):
    storage = MagicMock(spec=S3Storage)
    storage.upload.side_effect = lambda key, data, ct: f"s3://test-bucket/{key}"
    monkeypatch.setattr("app.assets.service.get_storage", lambda: storage)
    return storage


def test_upload_asset_returns_201(client, editor_token, mock_storage):
    image_data = make_jpeg_bytes(2000, 3000)
    response = client.post(
        "/assets/upload",
        files={"file": ("photo.jpg", image_data, "image/jpeg")},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "photo.jpg"
    assert data["width"] == 2000
    assert data["height"] == 3000
    assert data["original_uri"].startswith("s3://")
    assert data["display_uri"].startswith("s3://")
    assert data["thumb_uri"].startswith("s3://")


def test_upload_stores_three_variants(client, editor_token, mock_storage):
    image_data = make_jpeg_bytes(500, 500)
    client.post(
        "/assets/upload",
        files={"file": ("img.jpg", image_data, "image/jpeg")},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert mock_storage.upload.call_count == 3


def test_upload_asset_accepts_asset_type_query(client, editor_token, mock_storage):
    image_data = make_jpeg_bytes(600, 900)
    response = client.post(
        "/assets/upload?asset_type=model_set",
        files={"file": ("model-ref.jpg", image_data, "image/jpeg")},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 201
    assert response.json()["asset_type"] == AssetType.model_set.value


def test_upload_requires_auth(client):
    response = client.post(
        "/assets/upload",
        files={"file": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 403


def test_get_asset(client, editor_token, mock_storage):
    image_data = make_jpeg_bytes()
    upload = client.post(
        "/assets/upload",
        files={"file": ("test.jpg", image_data, "image/jpeg")},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    asset_id = upload.json()["id"]

    response = client.get(
        f"/assets/{asset_id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == asset_id


def test_list_assets(client, editor_token, mock_storage):
    image_data = make_jpeg_bytes()
    client.post(
        "/assets/upload",
        files={"file": ("a.jpg", image_data, "image/jpeg")},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    response = client.get("/assets", headers={"Authorization": f"Bearer {editor_token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


# ─── GET /assets/{id}/file tests ──────────────────────────────────────────────

@pytest.fixture
def file_route_storage(monkeypatch):
    """Mock storage that returns fake bytes for get_object."""
    storage = MagicMock(spec=S3Storage)
    storage.upload.side_effect = lambda key, data, ct: f"s3://test-bucket/{key}"
    storage.get_object.return_value = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    monkeypatch.setattr("app.assets.service.get_storage", lambda: storage)
    monkeypatch.setattr("app.assets.router.get_storage", lambda: storage)
    return storage


def test_get_asset_file_returns_thumb_content(client, editor_token, file_route_storage):
    """Upload then fetch thumb → 200 with image bytes."""
    image_data = make_jpeg_bytes(800, 600)
    upload = client.post(
        "/assets/upload",
        files={"file": ("photo.jpg", image_data, "image/jpeg")},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    asset_id = upload.json()["id"]

    # Fetch via access_token query param (how frontend uses it)
    response = client.get(f"/assets/{asset_id}/file?kind=thumb&access_token={editor_token}")
    assert response.status_code == 200
    assert response.content == b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    assert "image" in response.headers["content-type"]


def test_get_asset_file_returns_404_for_unknown_asset(client, editor_token):
    """Non-existent asset UUID → 404."""
    import uuid
    response = client.get(
        f"/assets/{uuid.uuid4()}/file?kind=thumb",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 404


def test_get_asset_file_returns_404_for_empty_uri(client, editor_token, db, file_route_storage):
    """Asset with empty thumb_uri string → 404 with clear message."""
    asset = Asset(
        filename="nothumb.jpg",
        original_uri="s3://bucket/orig/nothumb.jpg",
        display_uri="s3://bucket/display/nothumb.jpg",
        thumb_uri="",
        width=100,
        height=100,
        file_size=512,
    )
    db.add(asset)
    db.flush()

    response = client.get(
        f"/assets/{asset.id}/file?kind=thumb",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert response.status_code == 404
    assert "not available" in response.json()["detail"].lower()


def test_get_asset_file_requires_auth(client):
    """No token → 401."""
    import uuid
    response = client.get(f"/assets/{uuid.uuid4()}/file?kind=thumb")
    assert response.status_code == 401
