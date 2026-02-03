"""API routes for diary entry management.

Handles all CRUD operations for diary entries with authentication,
validation, and rate limiting.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Header, status, Request, Body
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models import EntryCreate, EntryUpdate, EntryResponse, PaginatedResponse
from app.services import FirestoreService
from app.config import settings


# Initialise rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="/api/entries",
    tags=["Entries"],
)


# Dependency: Validate API key and extract user_id
async def get_current_user(x_api_key: str = Header(...)) -> str:
    """Validate API key and return user identifier.
    
    Args:
        x_api_key: API key from request header
        
    Returns:
        User identifier extracted from API key
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Validate API key exists in configured keys
    if x_api_key not in settings.api_key_list:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # For now, use API key as user_id
    # In production, this would map to actual user IDs
    return x_api_key


# Dependency: Get Firestore service instance
async def get_firestore_service() -> FirestoreService:
    """Get initialised Firestore service.
    
    Returns:
        FirestoreService instance
    """
    return FirestoreService(
        project_id=settings.gcp_project_id,
        database=settings.firestore_database,
        credentials_path=settings.google_application_credentials,
    )


@router.post(
    "",
    response_model=EntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new diary entry",
    description="Creates a new diary entry with the provided data. Returns the created entry with generated ID and timestamps.",
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def create_entry(
    request: Request,
    entry_data: EntryCreate,
    user_id: str = Depends(get_current_user),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> EntryResponse:
    """Create a new diary entry.
    
    Args:
        request: FastAPI request object (required for rate limiting)
        entry_data: Entry creation data
        user_id: User identifier from API key
        firestore_service: Firestore service instance
        
    Returns:
        Created entry with generated ID and timestamps
        
    Raises:
        HTTPException: If validation fails or creation error occurs
    """
    try:
        entry = firestore_service.create_entry(entry_data, user_id)
        return entry
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create entry: {str(e)}",
        )


@router.get(
    "",
    response_model=PaginatedResponse[EntryResponse],
    summary="List diary entries",
    description="Lists diary entries with pagination and optional filters (tags, date range). Returns entries ordered by timestamp descending (newest first).",
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def list_entries(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated, entries must have all specified tags)"),
    start_date: Optional[str] = Query(None, description="Filter entries from this date (YYYY-MM-DD, inclusive)"),
    end_date: Optional[str] = Query(None, description="Filter entries to this date (YYYY-MM-DD, inclusive)"),
    user_id: str = Depends(get_current_user),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> PaginatedResponse[EntryResponse]:
    """List diary entries with pagination and filtering.
    
    Args:
        request: FastAPI request object (required for rate limiting)
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        tags: Filter by tags (entries must have all specified tags)
        start_date: Filter entries from this date (YYYY-MM-DD, inclusive)
        end_date: Filter entries to this date (YYYY-MM-DD, inclusive)
        user_id: User identifier from API key
        firestore_service: Firestore service instance
        
    Returns:
        Paginated list of entries
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Parse comma-separated tags into list
        parsed_tags = None
        if tags:
            parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        entries = firestore_service.list_entries(
            user_id=user_id,
            page=page,
            page_size=page_size,
            tags=parsed_tags,
            start_date=start_date,
            end_date=end_date,
        )
        return entries
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list entries: {str(e)}",
        )


@router.get(
    "/search",
    response_model=PaginatedResponse[EntryResponse],
    summary="Search diary entries",
    description="Searches diary entries by text content in title and body. Returns paginated results ordered by timestamp descending.",
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def search_entries(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query text"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    user_id: str = Depends(get_current_user),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> PaginatedResponse[EntryResponse]:
    """Search diary entries by text content.
    
    Args:
        request: FastAPI request object (required for rate limiting)
        q: Search query text
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        user_id: User identifier from API key
        firestore_service: Firestore service instance
        
    Returns:
        Paginated list of matching entries
        
    Raises:
        HTTPException: If search fails
    """
    try:
        results = firestore_service.search_entries(
            user_id=user_id,
            search_term=q,
            page=page,
            page_size=page_size,
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.get(
    "/date/{date}",
    response_model=List[EntryResponse],
    summary="Get entries by date",
    description="Retrieves all diary entries for a specific date in YYYY-MM-DD format. Returns entries ordered by timestamp ascending.",
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def get_entries_by_date(
    request: Request,
    date: str = Path(..., description="Date in YYYY-MM-DD format"),
    user_id: str = Depends(get_current_user),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> List[EntryResponse]:
    """Get all entries for a specific date.
    
    Args:
        request: FastAPI request object (required for rate limiting)
        date: Date in YYYY-MM-DD format
        user_id: User identifier from API key
        firestore_service: Firestore service instance
        
    Returns:
        List of entries for the specified date
        
    Raises:
        HTTPException: If date format is invalid
    """
    try:
        entries = firestore_service.get_entries_by_date(user_id, date)
        return entries
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve entries: {str(e)}",
        )


@router.get(
    "/{entry_id}",
    response_model=EntryResponse,
    summary="Retrieve single entry",
    description="Retrieves a specific diary entry by ID. Returns 404 if entry not found or doesn't belong to user.",
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def get_entry(
    request: Request,
    entry_id: str = Path(..., description="Entry identifier"),
    user_id: str = Depends(get_current_user),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> EntryResponse:
    """Retrieve a single diary entry by ID.
    
    Args:
        request: FastAPI request object (required for rate limiting)
        entry_id: Entry identifier
        user_id: User identifier from API key
        firestore_service: Firestore service instance
        
    Returns:
        Entry data
        
    Raises:
        HTTPException: If entry not found or unauthorised
    """
    entry = firestore_service.get_entry(entry_id, user_id)
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )
    
    return entry


@router.put(
    "/{entry_id}",
    response_model=EntryResponse,
    summary="Update diary entry",
    description="Updates an existing diary entry with partial data. Only provided fields will be updated.",
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def update_entry(
    request: Request,
    entry_id: str = Path(..., description="Entry identifier"),
    entry_data: EntryUpdate = Body(...),
    user_id: str = Depends(get_current_user),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> EntryResponse:
    """Update an existing diary entry.
    
    Args:
        request: FastAPI request object (required for rate limiting)
        entry_id: Entry identifier
        entry_data: Partial update data
        user_id: User identifier from API key
        firestore_service: Firestore service instance
        
    Returns:
        Updated entry data
        
    Raises:
        HTTPException: If entry not found, unauthorised, or validation fails
    """
    try:
        entry = firestore_service.update_entry(entry_id, user_id, entry_data)
        
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found",
            )
        
        return entry
    except HTTPException:
        # Re-raise HTTPException to let it propagate with original status code
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update entry: {str(e)}",
        )


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete diary entry",
    description="Permanently deletes a diary entry. This operation cannot be undone.",
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def delete_entry(
    request: Request,
    entry_id: str = Path(..., description="Entry identifier"),
    user_id: str = Depends(get_current_user),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> None:
    """Delete a diary entry.
    
    Args:
        request: FastAPI request object (required for rate limiting)
        entry_id: Entry identifier
        user_id: User identifier from API key
        firestore_service: Firestore service instance
        
    Raises:
        HTTPException: If entry not found or unauthorised
    """
    deleted = firestore_service.delete_entry(entry_id, user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )