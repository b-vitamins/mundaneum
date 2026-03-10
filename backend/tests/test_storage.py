"""
Unit tests for storage service.
"""

import pytest

from app.services.storage import (
    StorageError,
    StorageService,
)
from app.services.service_container import build_service_container


def test_get_client_returns_minio_instance():
    """Test that the storage service is built around a Minio client."""
    services = build_service_container()
    storage = services.storage.service
    assert isinstance(storage, StorageService)
    assert storage.client is services.storage.client


def test_storage_error_is_exception():
    """Test that StorageError can be raised and caught."""
    with pytest.raises(StorageError):
        raise StorageError("test error")
