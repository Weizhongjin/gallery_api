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


def test_load_tos_credentials_file(tmp_path):
    from app.storage import load_tos_credentials_file

    cred = tmp_path / "AccessKey.txt"
    cred.write_text("AccessKeyId: test-ak\nSecretAccessKey: test-sk\n", encoding="utf-8")
    ak, sk = load_tos_credentials_file(str(cred))
    assert ak == "test-ak"
    assert sk == "test-sk"


def test_get_storage_uses_tos_credentials_file(monkeypatch):
    from app.storage import get_storage, TosStorage
    from app.config import settings

    monkeypatch.setattr(settings, "storage_provider", "tos")
    monkeypatch.setattr(settings, "tos_endpoint", "https://tos-cn-beijing.volces.com")
    monkeypatch.setattr(settings, "tos_region", "cn-beijing")
    monkeypatch.setattr(settings, "tos_bucket", "joeffe")
    monkeypatch.setattr(settings, "tos_credentials_file", "/tmp/fake-cred")
    monkeypatch.setattr(settings, "s3_force_path_style", True)

    with patch("app.storage.load_tos_credentials_file", return_value=("ak-1", "sk-1")) as mock_load:
        with patch("app.storage.tos.TosClientV2") as mock_tos_client:
            mock_tos_client.return_value = MagicMock()
            storage = get_storage()

    mock_load.assert_called_once_with("/tmp/fake-cred")
    mock_tos_client.assert_called_once_with("ak-1", "sk-1", "tos-cn-beijing.volces.com", "cn-beijing")
    assert isinstance(storage, TosStorage)
