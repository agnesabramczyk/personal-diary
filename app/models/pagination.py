"""Pagination models for list endpoints.

Generic pagination response model for consistent API responses.
"""
from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model.
    
    Provides consistent structure for all list endpoints with pagination support.
    """
    
    items: List[T] = Field(
        ...,
        description="List of items in the current page"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of items across all pages"
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number (1-indexed)"
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page"
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages"
    )
    has_next: bool = Field(
        ...,
        description="Whether there is a next page"
    )
    has_previous: bool = Field(
        ...,
        description="Whether there is a previous page"
    )
    next_cursor: Optional[str] = Field(
        None,
        description="Cursor for fetching next page (if using cursor-based pagination)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 42,
                "page": 1,
                "page_size": 20,
                "total_pages": 3,
                "has_next": True,
                "has_previous": False,
                "next_cursor": "cursor_abc123"
            }
        }
    )
