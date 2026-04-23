from unittest.mock import MagicMock, patch

from app.aigc.providers.seedream_ark import SeedreamArkProvider


def test_build_request_payload():
    provider = SeedreamArkProvider(
        api_key="test-key",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=700,
    )
    payload = provider.build_request_payload(
        prompt="virtual try-on",
        image_data_urls=["data:image/jpeg;base64,aaa", "data:image/jpeg;base64,bbb"],
        resolution="2K",
        candidate_count=3,
    )
    assert payload["model"] == "doubao-seedream-4-5-251128"
    assert payload["size"] == "2K"
    assert payload["response_format"] == "url"
    assert payload["sequential_image_generation"] == "disabled"
    assert payload["stream"] is False
    assert payload["watermark"] is True
    assert len(payload["image"]) == 2


@patch("app.aigc.providers.seedream_ark.requests.get")
def test_generate_downloads_images(mock_get):
    mock_resp = MagicMock()
    mock_resp.content = b"\xff\xd8fake-jpeg-data"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    provider = SeedreamArkProvider(
        api_key="test-key",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=700,
    )

    mock_ark_resp = MagicMock()
    mock_item = MagicMock()
    mock_item.url = "https://cdn.example.com/img1.png"
    mock_ark_resp.data = [mock_item]
    provider._client.images.generate = MagicMock(return_value=mock_ark_resp)

    results = provider.generate(
        prompt="virtual try-on",
        image_data_urls=["data:image/jpeg;base64,aaa"],
        resolution="2K",
        candidate_count=2,
    )
    assert len(results) == 1
    assert results[0] == b"\xff\xd8fake-jpeg-data"
    provider._client.images.generate.assert_called_once()
    assert "n" not in provider._client.images.generate.call_args.kwargs
