"""Photo management routes.

Handles photo upload, retrieval, and deletion for diary entries.
"""
from functools import lru_cache
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models import PhotoResponse
from app.services.storage_service import StorageService
from app.services.firestore_service import FirestoreService
from app.routes.entries import get_current_user, get_firestore_service


@lru_cache()
def get_storage_service() -> StorageService:
    """Provide singleton StorageService instance.
    
    Returns:
        Configured StorageService instance for dependency injection.
    """
    return StorageService()


router = APIRouter(prefix="/api", tags=["photos"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/entries/{entry_id}/photos",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload photo to entry",
    description="Upload a photo to an existing diary entry. Maximum file size 50MB. Supported formats: JPEG, PNG.",
)
@limiter.limit("10/minute")
async def upload_photo(
    request: Request,
    entry_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    firestore: Annotated[FirestoreService, Depends(get_firestore_service)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    file: UploadFile = File(..., description="Photo file to upload (max 50MB)"),
    caption: str = Form(None, max_length=500, description="Optional caption for the photo"),
) -> PhotoResponse:
    """Upload a photo to an entry.
    
    Validates the entry exists and belongs to the user, then uploads the photo
    with thumbnail generation and EXIF preservation.
    """
    # Verify entry exists and belongs to user
    entry = firestore.get_entry(entry_id, user_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found or unauthorised",
        )
    
    # Upload photo
    try:
        # Extract file content and metadata from UploadFile
        file_content = await file.read()
        
        # Validate filename is present
        if file.filename is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required",
            )
        
        # Validate content type is present
        if file.content_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content type is required",
            )
        
        # Call storage service with correct parameters
        photo_data = await storage.upload_photo(
            entry_id=entry_id,
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            caption=caption,
        )
        
        # Convert Dict to PhotoResponse
        return PhotoResponse(**photo_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload photo: {str(e)}",
        )


@router.get(
    "/photos/{photo_id}",
    response_model=PhotoResponse,
    summary="Get photo metadata",
    description="Retrieve photo metadata with fresh signed URLs for viewing.",
)
@limiter.limit("30/minute")
async def get_photo(
    request: Request,
    photo_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    firestore: Annotated[FirestoreService, Depends(get_firestore_service)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> PhotoResponse:
    """Get photo metadata with fresh signed URLs.
    
    Verifies the photo's entry belongs to the user before returning data.
    """
    # Get photo metadata from Firestore
    photo_data = firestore.get_photo(photo_id)
    if not photo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )
    
    # Verify entry belongs to user
    entry = firestore.get_entry(photo_data["entry_id"], user_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found or unauthorised",
        )
    
    # Get fresh signed URLs
    try:
        urls = await storage.get_photo_url(photo_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve photo: {str(e)}",
        )
    
    # Combine metadata and fresh URLs into PhotoResponse
    return PhotoResponse(
        id=photo_data["id"],
        entry_id=photo_data["entry_id"],
        filename=photo_data["filename"],
        content_type=photo_data["content_type"],
        size_bytes=photo_data["size_bytes"],
        storage_path=photo_data["storage_path"],
        thumbnail_path=photo_data["thumbnail_path"],
        photo_url=urls["photo_url"],
        thumbnail_url=urls["thumbnail_url"],
        exif_data=photo_data.get("exif_data", {}),
        caption=photo_data.get("caption"),
        created_at=photo_data["created_at"],
    )


@router.delete(
    "/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete photo",
    description="Delete a photo and its thumbnail from storage and database.",
)
@limiter.limit("20/minute")
async def delete_photo(
    request: Request,
    photo_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    firestore: Annotated[FirestoreService, Depends(get_firestore_service)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> None:
    """Delete a photo.
    
    Verifies the photo's entry belongs to the user before deletion.
    Removes photo and thumbnail from Cloud Storage and metadata from Firestore.
    """
    # Get photo to verify ownership
    photo_data = firestore.get_photo(photo_id)
    if not photo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )
    
    # Verify entry belongs to user
    entry = firestore.get_entry(photo_data["entry_id"], user_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found or unauthorised",
        )
    
    # Delete photo
    try:
        await storage.delete_photo(photo_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete photo: {str(e)}",
        )