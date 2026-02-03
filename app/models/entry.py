"""Entry models for diary entries.

Pydantic models for creating, updating, and retrieving diary entries.
All timestamps use AEST timezone.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class EntryCreate(BaseModel):
    """Model for creating a new diary entry."""
    
    timestamp: datetime = Field(
        ...,
        description="Entry timestamp in AEST timezone"
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Entry title"
    )
    body: str = Field(
        ...,
        min_length=1,
        description="Entry body content"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorising the entry"
    )
    mood: Optional[str] = Field(
        None,
        max_length=50,
        description="Mood description"
    )
    location: Optional[str] = Field(
        None,
        max_length=200,
        description="Location where entry was written"
    )
    weather: Optional[str] = Field(
        None,
        max_length=100,
        description="Weather conditions"
    )
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalise tags."""
        if not v:
            return []
        
        # Remove empty strings and strip whitespace
        normalised = [tag.strip() for tag in v if tag.strip()]
        
        # Check for duplicate tags
        if len(normalised) != len(set(normalised)):
            raise ValueError("Duplicate tags are not allowed")
        
        # Validate tag length
        for tag in normalised:
            if len(tag) > 50:
                raise ValueError(f"Tag '{tag}' exceeds maximum length of 50 characters")
        
        return normalised
    
    @field_validator('title', 'body')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure title and body are not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()


class EntryUpdate(BaseModel):
    """Model for updating an existing diary entry.
    
    All fields are optional to support partial updates.
    """
    
    timestamp: Optional[datetime] = Field(
        None,
        description="Entry timestamp in AEST timezone"
    )
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Entry title"
    )
    body: Optional[str] = Field(
        None,
        min_length=1,
        description="Entry body content"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Tags for categorising the entry"
    )
    mood: Optional[str] = Field(
        None,
        max_length=50,
        description="Mood description"
    )
    location: Optional[str] = Field(
        None,
        max_length=200,
        description="Location where entry was written"
    )
    weather: Optional[str] = Field(
        None,
        max_length=100,
        description="Weather conditions"
    )
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalise tags."""
        if v is None:
            return None
        
        if not v:
            return []
        
        # Remove empty strings and strip whitespace
        normalised = [tag.strip() for tag in v if tag.strip()]
        
        # Check for duplicate tags
        if len(normalised) != len(set(normalised)):
            raise ValueError("Duplicate tags are not allowed")
        
        # Validate tag length
        for tag in normalised:
            if len(tag) > 50:
                raise ValueError(f"Tag '{tag}' exceeds maximum length of 50 characters")
        
        return normalised
    
    @field_validator('title', 'body')
    @classmethod
    def validate_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure title and body are not empty or whitespace only if provided."""
        if v is None:
            return None
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()


class EntryResponse(BaseModel):
    """Model for diary entry responses."""
    
    id: str = Field(
        ...,
        description="Unique entry identifier"
    )
    user_id: str = Field(
        ...,
        description="User identifier"
    )
    timestamp: datetime = Field(
        ...,
        description="Entry timestamp in AEST timezone"
    )
    title: str = Field(
        ...,
        description="Entry title"
    )
    body: str = Field(
        ...,
        description="Entry body content"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorising the entry"
    )
    mood: Optional[str] = Field(
        None,
        description="Mood description"
    )
    location: Optional[str] = Field(
        None,
        description="Location where entry was written"
    )
    weather: Optional[str] = Field(
        None,
        description="Weather conditions"
    )
    created_at: datetime = Field(
        ...,
        description="Entry creation timestamp in AEST timezone"
    )
    updated_at: datetime = Field(
        ...,
        description="Entry last update timestamp in AEST timezone"
    )
    photo_count: int = Field(
        default=0,
        description="Number of photos attached to this entry"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "entry_123abc",
                "user_id": "user_456def",
                "timestamp": "2026-01-30T09:00:00+10:00",
                "title": "Morning coffee at the beach",
                "body": "Started the day with a beautiful sunrise walk along the beach. The weather was perfect and I felt grateful for this peaceful moment.",
                "tags": ["morning", "beach", "gratitude"],
                "mood": "peaceful",
                "location": "Bondi Beach, Sydney",
                "weather": "sunny, 24°C",
                "created_at": "2026-01-30T09:15:00+10:00",
                "updated_at": "2026-01-30T09:15:00+10:00",
                "photo_count": 2
            }
        }
    )
