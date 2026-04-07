"""Object store service for persisting backtest CSV results (MinIO / AWS S3)."""
import logging
import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Default URL lifetime for pre-signed download links
PRESIGNED_URL_DEFAULT_EXPIRY = 3600  # 1 hour


class ObjectStoreService:
    """S3-compatible object store for backtest CSV files.

    Works with MinIO locally (set OBJECT_STORE_ENDPOINT to the MinIO URL) and
    AWS S3 in production (omit OBJECT_STORE_ENDPOINT for native AWS endpoint
    resolution).

    Environment variables:
        OBJECT_STORE_ENDPOINT    MinIO URL, e.g. http://localhost:9000.
                                 Omit (or leave empty) for AWS S3.
        OBJECT_STORE_ACCESS_KEY  Access key / AWS access key ID.
        OBJECT_STORE_SECRET_KEY  Secret key / AWS secret access key.
        OBJECT_STORE_BUCKET      Bucket name (default: quato-backtests).
        OBJECT_STORE_REGION      Region (default: us-east-1).
    """

    def __init__(self) -> None:
        endpoint = os.getenv("OBJECT_STORE_ENDPOINT") or None  # empty string → None
        self.bucket = os.getenv("OBJECT_STORE_BUCKET", "quato-backtests")
        # Public URL used to rewrite presigned URLs for external access.
        # e.g. https://minio.yourdomain.com  (no trailing slash)
        self._public_endpoint = os.getenv("OBJECT_STORE_PUBLIC_ENDPOINT") or None

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("OBJECT_STORE_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("OBJECT_STORE_SECRET_KEY"),
            region_name=os.getenv("OBJECT_STORE_REGION", "us-east-1"),
            # s3v4 signing is required by MinIO and works with AWS S3
            config=Config(signature_version="s3v4"),
        )
        logger.info(
            "ObjectStoreService configured — endpoint=%s, public=%s, bucket=%s",
            endpoint or "AWS S3",
            self._public_endpoint or "same as endpoint",
            self.bucket,
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it does not already exist.

        Safe to call on every startup — a no-op when the bucket is present.
        """
        try:
            self._client.head_bucket(Bucket=self.bucket)
            logger.info("Object store bucket '%s' already exists", self.bucket)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self.bucket)
                logger.info("Created object store bucket '%s'", self.bucket)
            else:
                raise

    def upload_backtest_csv(self, task_id: str, local_path: str) -> str:
        """Upload a backtest results CSV and return its object key.

        Args:
            task_id:    Task identifier used to namespace the object.
            local_path: Absolute path to the local CSV file to upload.

        Returns:
            The object key, e.g. "backtests/<task_id>/results.csv".
        """
        key = f"backtests/{task_id}/results.csv"
        self._client.upload_file(local_path, self.bucket, key)
        logger.info("Uploaded %s → s3://%s/%s", local_path, self.bucket, key)
        return key

    def upload_tearsheet(self, task_id: str, local_path: str) -> str:
        """Upload a tear sheet PDF and return its object key.

        Args:
            task_id:    Task identifier used to namespace the object.
            local_path: Absolute path to the local PDF file to upload.

        Returns:
            The object key, e.g. "backtests/<task_id>/tearsheet.pdf".
        """
        key = f"backtests/{task_id}/tearsheet.pdf"
        self._client.upload_file(local_path, self.bucket, key)
        logger.info("Uploaded %s → s3://%s/%s", local_path, self.bucket, key)
        return key

    def get_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = PRESIGNED_URL_DEFAULT_EXPIRY,
    ) -> str:
        """Generate a pre-signed URL for direct download without credentials.

        Args:
            object_key: The S3 object key returned by upload_backtest_csv.
            expires_in: URL lifetime in seconds (default 1 hour).

        Returns:
            A time-limited HTTPS URL the client can GET directly.
        """
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )
        if self._public_endpoint and self._client.meta.endpoint_url:
            # Replace the internal Docker hostname with the public-facing URL.
            url = url.replace(self._client.meta.endpoint_url, self._public_endpoint, 1)
        return url
