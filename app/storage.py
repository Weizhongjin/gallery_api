import boto3
from botocore.config import Config


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


def uri_to_key(uri: str) -> str:
    """Convert s3://bucket/key to key."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3:// URI, got: {uri!r}")
    return uri.split("/", 3)[3]


def get_storage() -> S3Storage:
    from app.config import settings
    return S3Storage(
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
    )
