from pathlib import Path

import boto3
from botocore.config import Config
import tos


class S3Storage:
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        force_path_style: bool = True,
    ):
        addressing_style = "path" if force_path_style else "auto"
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(s3={"addressing_style": addressing_style}),
        )
        self._bucket = bucket

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return f"s3://{self._bucket}/{key}"

    def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )

    def list_objects(self, prefix: str) -> list[str]:
        """List all object keys with the given prefix."""
        keys = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def get_object(self, key: str) -> bytes:
        """Download and return raw bytes for an object key."""
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()


class TosStorage:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "cn-beijing",
    ):
        self._endpoint = endpoint.replace("https://", "").replace("http://", "").strip("/")
        self._client = tos.TosClientV2(access_key, secret_key, self._endpoint, region)
        self._bucket = bucket

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(
            bucket=self._bucket,
            key=key,
            content=data,
            content_length=len(data),
            content_type=content_type,
        )
        return f"s3://{self._bucket}/{key}"

    def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        out = self._client.pre_signed_url(
            tos.HttpMethodType.Http_Method_Get,
            bucket=self._bucket,
            key=key,
            expires=expires,
        )
        return out.signed_url

    def list_objects(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token = None
        while True:
            out = self._client.list_objects_type2(
                bucket=self._bucket,
                prefix=prefix,
                continuation_token=token,
            )
            keys.extend([c.key for c in (out.contents or [])])
            if not out.is_truncated:
                break
            token = out.next_continuation_token
        return keys

    def get_object(self, key: str) -> bytes:
        out = self._client.get_object(bucket=self._bucket, key=key)
        return out.read()


def load_tos_credentials_file(path: str) -> tuple[str, str]:
    """Read AccessKeyId/SecretAccessKey from a local credentials file."""
    cred_path = Path(path).expanduser()
    if not cred_path.exists():
        raise FileNotFoundError(f"TOS credentials file not found: {cred_path}")

    values: dict[str, str] = {}
    for line in cred_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        values[k.strip()] = v.strip()

    ak = values.get("AccessKeyId", "").strip()
    sk = values.get("SecretAccessKey", "").strip()
    if not ak or not sk:
        raise ValueError(f"Invalid TOS credentials file format: {cred_path}")
    return ak, sk


def uri_to_key(uri: str) -> str:
    """Convert s3://bucket/key to key."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3:// URI, got: {uri!r}")
    return uri.split("/", 3)[3]


def get_storage() -> S3Storage | TosStorage:
    from app.config import settings
    provider = (getattr(settings, "storage_provider", "s3") or "s3").strip().lower()

    if provider == "tos":
        tos_cred_file = getattr(settings, "tos_credentials_file", "")
        if tos_cred_file:
            access_key, secret_key = load_tos_credentials_file(tos_cred_file)
        else:
            access_key = settings.s3_access_key
            secret_key = settings.s3_secret_key
        return TosStorage(
            endpoint=getattr(settings, "tos_endpoint", settings.s3_endpoint_url),
            access_key=access_key,
            secret_key=secret_key,
            bucket=getattr(settings, "tos_bucket", settings.s3_bucket),
            region=getattr(settings, "tos_region", settings.s3_region),
        )

    return S3Storage(
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
    )
