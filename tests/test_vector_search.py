import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from sqlalchemy import text

from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset


@pytest.fixture
def viewer_token(db):
    user = User(email="viewer_vs@example.com", password_hash=hash_password("pw"), name="Viewer", role=UserRole.viewer)
    db.add(user)
    db.flush()
    return create_access_token(str(user.id))


@pytest.fixture
def asset_with_embedding(db):
    asset = Asset(
        original_uri="s3://b/vs1.jpg", display_uri="s3://b/vs1d.jpg", thumb_uri="s3://b/vs1t.jpg",
        filename="vs1.jpg", width=100, height=100, file_size=100,
        feature_status={"embed": "done"},
    )
    db.add(asset)
    db.flush()

    # Insert embedding via raw SQL (pgvector)
    vector_str = "[" + ",".join(["0.1"] * 768) + "]"
    db.execute(
        text("INSERT INTO asset_embedding (asset_id, model_ver, vector) VALUES (:id, :ver, CAST(:v AS vector))"),
        {"id": str(asset.id), "ver": "v1", "v": vector_str},
    )
    db.flush()
    return asset


def test_semantic_search_returns_results(client, viewer_token, asset_with_embedding):
    mock_embed = MagicMock()
    mock_embed.embed_text.return_value = [0.1] * 768

    with patch("app.search.router.get_embedding_client", return_value=mock_embed):
        response = client.post(
            "/search/semantic",
            json={"text": "商务风上衣"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    ids = [r["id"] for r in results]
    assert str(asset_with_embedding.id) in ids


def test_vector_search_from_image_upload(client, viewer_token, asset_with_embedding):
    buf = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buf, format="JPEG")

    mock_embed = MagicMock()
    mock_embed.embed_image.return_value = [0.1] * 768

    mock_storage = MagicMock()
    mock_storage.upload.return_value = "s3://test/search-tmp/query.jpg"
    mock_storage.get_presigned_url.return_value = "https://signed/search-tmp/query.jpg"

    with patch("app.search.router.get_embedding_client", return_value=mock_embed), \
         patch("app.search.router.get_storage", return_value=mock_storage):
        response = client.post(
            "/search/vector",
            files={"file": ("query.jpg", buf.getvalue(), "image/jpeg")},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
