"""
MinIO storage service for Folio.

Handles file storage (PDFs, attachments) in MinIO/S3-compatible storage.
"""

from functools import lru_cache
from io import BytesIO
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

BUCKET_NAME = "folio-files"


class StorageError(Exception):
    """Raised when storage operations fail."""

    pass


class StorageUnavailableError(StorageError):
    """Raised when storage is unavailable."""

    pass


@lru_cache(maxsize=1)
def get_client() -> Minio:
    """Get cached MinIO client."""
    # Parse URL to extract host and determine if secure
    url = settings.minio_url
    secure = url.startswith("https://")
    host = url.replace("https://", "").replace("http://", "")

    return Minio(
        host,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
    )


def ensure_bucket() -> bool:
    """Ensure the storage bucket exists. Returns True if successful."""
    try:
        client = get_client()
        if not client.bucket_exists(BUCKET_NAME):
            client.make_bucket(BUCKET_NAME)
            logger.info("Created bucket '%s'", BUCKET_NAME)
        return True
    except S3Error as e:
        logger.error("Failed to ensure bucket: %s", e)
        return False
    except Exception as e:
        logger.warning("MinIO unavailable: %s", e)
        return False


def is_available() -> bool:
    """Check if MinIO storage is reachable."""
    try:
        client = get_client()
        client.list_buckets()
        return True
    except Exception:
        return False


def upload_file(
    file_key: str,
    data: BinaryIO | bytes,
    content_type: str = "application/octet-stream",
    size: int | None = None,
) -> str:
    """
    Upload a file to storage.

    Args:
        file_key: Unique key/path for the file
        data: File content as bytes or file-like object
        content_type: MIME type of the file
        size: Size in bytes (required if data is a stream without length)

    Returns:
        The file key if successful

    Raises:
        StorageError: If upload fails
    """
    try:
        client = get_client()

        # Convert bytes to BytesIO if needed
        if isinstance(data, bytes):
            data = BytesIO(data)
            size = len(data.getvalue())

        if size is None:
            raise StorageError("Size is required for stream uploads")

        client.put_object(
            BUCKET_NAME,
            file_key,
            data,
            length=size,
            content_type=content_type,
        )
        logger.debug("Uploaded file: %s", file_key)
        return file_key

    except S3Error as e:
        logger.error("Failed to upload file %s: %s", file_key, e)
        raise StorageError(f"Failed to upload file: {e}") from e


def download_file(file_key: str) -> bytes:
    """
    Download a file from storage.

    Args:
        file_key: Key/path of the file to download

    Returns:
        File content as bytes

    Raises:
        StorageError: If download fails
    """
    try:
        client = get_client()
        response = client.get_object(BUCKET_NAME, file_key)
        data = response.read()
        response.close()
        response.release_conn()
        return data

    except S3Error as e:
        logger.error("Failed to download file %s: %s", file_key, e)
        raise StorageError(f"Failed to download file: {e}") from e


def delete_file(file_key: str) -> bool:
    """
    Delete a file from storage.

    Args:
        file_key: Key/path of the file to delete

    Returns:
        True if deleted, False if not found
    """
    try:
        client = get_client()
        client.remove_object(BUCKET_NAME, file_key)
        logger.debug("Deleted file: %s", file_key)
        return True

    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        logger.error("Failed to delete file %s: %s", file_key, e)
        raise StorageError(f"Failed to delete file: {e}") from e


def get_presigned_url(file_key: str, expires_hours: int = 1) -> str:
    """
    Generate a presigned URL for temporary file access.

    Args:
        file_key: Key/path of the file
        expires_hours: Hours until the URL expires

    Returns:
        Presigned URL string
    """
    from datetime import timedelta

    try:
        client = get_client()
        return client.presigned_get_object(
            BUCKET_NAME,
            file_key,
            expires=timedelta(hours=expires_hours),
        )
    except S3Error as e:
        logger.error("Failed to generate presigned URL for %s: %s", file_key, e)
        raise StorageError(f"Failed to generate URL: {e}") from e


def list_files(prefix: str = "") -> list[str]:
    """
    List files in storage with optional prefix filter.

    Args:
        prefix: Filter files starting with this prefix

    Returns:
        List of file keys
    """
    try:
        client = get_client()
        objects = client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    except S3Error as e:
        logger.error("Failed to list files: %s", e)
        raise StorageError(f"Failed to list files: {e}") from e
