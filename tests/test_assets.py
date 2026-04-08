import io
import pytest
from unittest.mock import MagicMock
from PIL import Image

from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
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
