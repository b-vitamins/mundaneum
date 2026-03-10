"""
Explicit MinIO storage service for Mundaneum.
"""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.logging import get_logger

logger = get_logger(__name__)

BUCKET_NAME = "mundaneum-files"


class StorageError(Exception):
    """Raised when storage operations fail."""

    pass


class StorageUnavailableError(StorageError):
    """Raised when storage is unavailable."""

    pass


class StorageService:
    """Own MinIO bucket policy and file operations."""

    def __init__(self, client: Minio):
        self.client = client

    def ensure_bucket(self) -> bool:
        try:
            if not self.client.bucket_exists(BUCKET_NAME):
                self.client.make_bucket(BUCKET_NAME)
                logger.info("Created bucket '%s'", BUCKET_NAME)
            return True
        except S3Error as exc:
            logger.error("Failed to ensure bucket: %s", exc)
            return False
        except Exception as exc:
            logger.warning("MinIO unavailable: %s", exc)
            return False

    def is_available(self) -> bool:
        try:
            self.client.list_buckets()
            return True
        except Exception:
            return False

    def upload_file(
        self,
        file_key: str,
        data: BinaryIO | bytes,
        content_type: str = "application/octet-stream",
        size: int | None = None,
    ) -> str:
        try:
            if isinstance(data, bytes):
                data = BytesIO(data)
                size = len(data.getvalue())

            if size is None:
                raise StorageError("Size is required for stream uploads")

            self.client.put_object(
                BUCKET_NAME,
                file_key,
                data,
                length=size,
                content_type=content_type,
            )
            logger.debug("Uploaded file: %s", file_key)
            return file_key
        except S3Error as exc:
            logger.error("Failed to upload file %s: %s", file_key, exc)
            raise StorageError(f"Failed to upload file: {exc}") from exc

    def download_file(self, file_key: str) -> bytes:
        try:
            response = self.client.get_object(BUCKET_NAME, file_key)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as exc:
            logger.error("Failed to download file %s: %s", file_key, exc)
            raise StorageError(f"Failed to download file: {exc}") from exc

    def delete_file(self, file_key: str) -> bool:
        try:
            self.client.remove_object(BUCKET_NAME, file_key)
            logger.debug("Deleted file: %s", file_key)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            logger.error("Failed to delete file %s: %s", file_key, exc)
            raise StorageError(f"Failed to delete file: {exc}") from exc

    def get_presigned_url(self, file_key: str, expires_hours: int = 1) -> str:
        from datetime import timedelta

        try:
            return self.client.presigned_get_object(
                BUCKET_NAME,
                file_key,
                expires=timedelta(hours=expires_hours),
            )
        except S3Error as exc:
            logger.error("Failed to generate presigned URL for %s: %s", file_key, exc)
            raise StorageError(f"Failed to generate URL: {exc}") from exc

    def list_files(self, prefix: str = "") -> list[str]:
        try:
            objects = self.client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except S3Error as exc:
            logger.error("Failed to list files: %s", exc)
            raise StorageError(f"Failed to list files: {exc}") from exc
