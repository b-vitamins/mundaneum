"""
Unit tests for storage service.
"""

import pytest

from app.services.storage import (
    StorageError,
    get_client,
)


def test_get_client_returns_minio_instance():
    """Test that get_client returns a Minio client instance."""
    client = get_client()
    assert client is not None
    # Should return the same cached instance
    assert get_client() is client


def test_storage_error_is_exception():
    """Test that StorageError can be raised and caught."""
    with pytest.raises(StorageError):
        raise StorageError("test error")
