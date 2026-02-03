"""Photo models for diary entry photos.

Pydantic models for uploading and retrieving photos attached to diary entries.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PhotoUpload(BaseModel):
    """Model for photo upload metadata (file content handled separately via multipart/form-data)."""
    
    entry_id: str = Field(
        ...,
        description="Entry identifier this photo belongs to"
    )
    caption: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional caption for the photo"
    )


class PhotoResponse(BaseModel):
    """Model for photo responses."""
    
    id: str = Field(
        ...,
        description="Unique photo identifier"
    )
    entry_id: str = Field(
        ...,
        description="Entry identifier this photo belongs to"
    )
    filename: str = Field(
        ...,
        description="Original filename"
    )
    content_type: str = Field(
        ...,
        description="MIME type (image/jpeg or image/png)"
    )
    size_bytes: int = Field(
        ...,
        description="File size in bytes"
    )
    storage_path: str = Field(
        ...,
        description="Storage path in Cloud Storage"
    )
    thumbnail_path: str = Field(
        ...,
        description="Thumbnail storage path in Cloud Storage"
    )
    photo_url: str = Field(
        ...,
        description="Signed URL to access full-size photo (expires after configured time)"
    )
    thumbnail_url: str = Field(
        ...,
        description="Signed URL to access thumbnail (expires after configured time)"
    )
    exif_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="EXIF metadata extracted from photo"
    )
    caption: Optional[str] = Field(
        None,
        description="Optional caption for the photo"
    )
    created_at: datetime = Field(
        ...,
        description="Photo upload timestamp in AEST timezone"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "photo_123abc",
                "entry_id": "entry_456def",
                "filename": "IMG_1234.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 2048576,
                "storage_path": "photos/user_789/entry_456def/photo_123abc.jpg",
                "thumbnail_path": "photos/user_789/entry_456def/photo_123abc_thumb.jpg",
                "photo_url": "https://storage.googleapis.com/bucket/photos/...",
                "thumbnail_url": "https://storage.googleapis.com/bucket/photos/...",
                "exif_data": {
                    "Make": "Apple",
                    "Model": "iPhone 15 Pro",
                    "DateTime": "2026:01:30 09:00:00",
                    "GPSLatitude": "-33.8688",
                    "GPSLongitude": "151.2093"
                },
                "caption": "Beautiful sunrise at the beach",
                "created_at": "2026-01-30T09:15:00+10:00"
            }
        }
    )
