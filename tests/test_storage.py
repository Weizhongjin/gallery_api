import pytest
from unittest.mock import MagicMock, patch
from app.storage import S3Storage


@pytest.fixture
def mock_s3():
    mock_client = MagicMock()
    with patch("app.storage.boto3.client", return_value=mock_client):
        storage = S3Storage(
            endpoint_url="http://localhost:9000",
            access_key="key",
            secret_key="secret",
            bucket="test-bucket",
            region="us-east-1",
            force_path_style=True,
        )
    storage._client = mock_client
    return storage, mock_client


def test_upload_returns_s3_uri(mock_s3):
    storage, client = mock_s3
    uri = storage.upload("images/test.jpg", b"fake-image-data", "image/jpeg")
    assert uri == "s3://test-bucket/images/test.jpg"
    client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="images/test.jpg",
        Body=b"fake-image-data",
        ContentType="image/jpeg",
    )


def test_get_presigned_url(mock_s3):
    storage, client = mock_s3
    client.generate_presigned_url.return_value = "https://example.com/signed"
    url = storage.get_presigned_url("images/test.jpg")
    assert url == "https://example.com/signed"
    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "images/test.jpg"},
        ExpiresIn=3600,
    )


def test_uri_to_key():
    from app.storage import uri_to_key
    assert uri_to_key("s3://test-bucket/images/test.jpg") == "images/test.jpg"
    assert uri_to_key("s3://test-bucket/a/b/c/d.jpg") == "a/b/c/d.jpg"
    assert uri_to_key("s3://test-bucket/file.jpg") == "file.jpg"


def test_uri_to_key_invalid():
    from app.storage import uri_to_key
    import pytest
    with pytest.raises(ValueError, match="Expected s3://"):
        uri_to_key("https://example.com/file.jpg")
