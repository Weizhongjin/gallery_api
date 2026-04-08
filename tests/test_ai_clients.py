import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.ai.vlm_client import VLMClient
from app.ai.embed_client import EmbeddingClient


# --- VLMClient tests ---

def test_vlm_classify_returns_dict():
    """VLMClient.classify returns parsed dict from VLM JSON response."""
    mock_response = {
        "choices": [{
            "message": {
                "content": '{"category": "上衣", "style": ["商务风"], "color": ["藏青色"], "scene": ["通勤"], "detail": ["西装领"]}'
            }
        }]
    }
    client = VLMClient(endpoint="http://vlm:8000", api_key="test", model="qwen-vl-plus")

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
        )
        result = client.classify(image_url="https://example.com/photo.jpg")

    assert result["category"] == "上衣"
    assert "商务风" in result["style"]
    assert result["color"] == ["藏青色"]


def test_vlm_classify_sends_correct_request():
    """VLMClient sends image_url and text in correct OpenAI message format."""
    client = VLMClient(endpoint="http://vlm:8000", api_key="key", model="qwen-vl-plus")

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": '{"category": "裤子", "style": [], "color": [], "scene": [], "detail": []}'}}]},
        )
        client.classify(image_url="https://s3/photo.jpg")

    call_kwargs = mock_post.call_args
    body = call_kwargs[1]["json"]
    assert body["response_format"] == {"type": "json_object"}
    messages = body["messages"]
    content = messages[0]["content"]
    image_parts = [c for c in content if c.get("type") == "image_url"]
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"] == "https://s3/photo.jpg"


def test_vlm_classify_invalid_json_raises():
    """VLMClient raises ValueError if VLM returns non-JSON content."""
    client = VLMClient(endpoint="http://vlm:8000", api_key="key", model="qwen-vl-plus")

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "Sorry, I cannot classify this."}}]},
        )
        with pytest.raises(ValueError, match="VLM returned non-JSON"):
            client.classify(image_url="https://s3/photo.jpg")


# --- EmbeddingClient tests ---

def test_embed_image_returns_vector():
    """EmbeddingClient.embed_image returns float list."""
    client = EmbeddingClient(endpoint="http://embed:8001", model="Marqo/marqo-fashionSigLIP")

    mock_response = {
        "data": [{"embedding": [0.1] * 768, "index": 0}],
        "model": "Marqo/marqo-fashionSigLIP",
    }
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response)
        vector = client.embed_image(image_url="https://example.com/photo.jpg")

    assert len(vector) == 768
    assert isinstance(vector[0], float)


def test_embed_text_returns_vector():
    """EmbeddingClient.embed_text returns float list."""
    client = EmbeddingClient(endpoint="http://embed:8001", model="Marqo/marqo-fashionSigLIP")

    mock_response = {
        "data": [{"embedding": [0.2] * 768, "index": 0}],
        "model": "Marqo/marqo-fashionSigLIP",
    }
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response)
        vector = client.embed_text(text="商务风上衣")

    assert len(vector) == 768


def test_embed_sends_correct_modality():
    """EmbeddingClient sends correct modality field."""
    client = EmbeddingClient(endpoint="http://embed:8001", model="Marqo/marqo-fashionSigLIP")

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"embedding": [0.0] * 768}]},
        )
        client.embed_image(image_url="https://s3/photo.jpg")

    body = mock_post.call_args[1]["json"]
    assert body["modality"] == "image"
    assert body["input"] == "https://s3/photo.jpg"
    assert body["encoding_format"] == "float"
