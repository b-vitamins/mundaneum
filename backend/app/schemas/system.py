"""
System-level response models.
"""

from pydantic import BaseModel


class StatsResponse(BaseModel):
    """Library statistics response model."""

    entries: int
    authors: int
    collections: int
