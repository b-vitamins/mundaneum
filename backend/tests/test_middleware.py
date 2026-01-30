"""
Unit tests for middleware.
"""

from app.middleware import get_request_id, request_id_ctx


def test_request_id_context_default():
    """Test that request ID context returns None by default."""
    assert get_request_id() is None


def test_request_id_context_set_and_get():
    """Test setting and getting request ID from context."""
    token = request_id_ctx.set("test-123")
    try:
        assert get_request_id() == "test-123"
    finally:
        request_id_ctx.reset(token)

    # Should be None after reset
    assert get_request_id() is None
