"""API route handlers for Personal Diary API.

This module exports all route modules for inclusion in the main application.
"""

from functools import lru_cache

from app.routes.entries import router as entries_router
from app.routes.photos import router as photos_router
from app.services import StorageService


@lru_cache()
def get_storage_service() -> StorageService:
    """Provide singleton StorageService instance.
    
    Returns:
        Configured StorageService instance for dependency injection.
    """
    return StorageService()


__all__ = ["entries_router", "photos_router", "get_storage_service"]
