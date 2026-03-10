"""
Entries router composition.
"""

from fastapi import APIRouter

from app.routers import entries_core, entries_s2

router = APIRouter()
router.include_router(entries_core.router, prefix="/entries", tags=["entries"])
router.include_router(entries_s2.router, prefix="/entries", tags=["entries"])
