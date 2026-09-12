import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import Settings


class S3Storage:
    """Stockage S3-compatible : MinIO en local, Cloudflare R2 en production."""

    def __init__(self, s: Settings):
        self.bucket = s.storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=s.storage_endpoint,
            aws_access_key_id=s.storage_access_key,
            aws_secret_access_key=s.storage_secret_key,
            region_name="auto",
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False
