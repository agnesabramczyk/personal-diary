"""Firestore service layer for diary entries.

Handles all interactions with Cloud Firestore database.
"""
from typing import Optional, List, Dict, Any
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.models import EntryCreate, EntryUpdate, EntryResponse, PaginatedResponse
from app.services.timezone_utils import now_aest, ensure_aest, date_to_aest_range


class FirestoreService:
    """Service for managing diary entries in Firestore."""
    
    ENTRIES_COLLECTION = "entries"
    PHOTOS_COLLECTION = "photos"
    
    def __init__(
        self,
        project_id: str,
        database: str = "(default)",
        credentials_path: Optional[str] = None
    ):
        """Initialise Firestore service.

        Args:
            project_id: GCP project ID
            database: Firestore database name (defaults to "(default)")
            credentials_path: Path to service account credentials JSON file.
        """
        # When credentials_path is None, Client() uses default credentials
        # (Application Default Credentials via Workload Identity in Cloud Run)
        if credentials_path:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.client = firestore.Client(
                project=project_id,
                database=database,
                credentials=credentials
            )
        else:
            self.client = firestore.Client(project=project_id, database=database)
        self._credentials_path = credentials_path
    
    def create_entry(
        self, 
        entry_data: EntryCreate, 
        user_id: str
    ) -> EntryResponse:
        """Create a new diary entry.
        
        Args:
            entry_data: Entry creation data
            user_id: User identifier
            
        Returns:
            Created entry with generated ID and timestamps
        """
        current_time = now_aest()
        
        # Ensure timestamp is in AEST
        entry_timestamp = ensure_aest(entry_data.timestamp)
        
        # Prepare document data
        doc_data = {
            "user_id": user_id,
            "timestamp": entry_timestamp,
            "title": entry_data.title,
            "body": entry_data.body,
            "tags": entry_data.tags,
            "mood": entry_data.mood,
            "location": entry_data.location,
            "weather": entry_data.weather,
            "created_at": current_time,
            "updated_at": current_time,
        }
        
        # Create document with auto-generated ID
        doc_ref = self.client.collection(self.ENTRIES_COLLECTION).document()
        doc_ref.set(doc_data)
        
        # Return response with generated ID and photo count (0 for new entry)
        return EntryResponse(
            id=doc_ref.id,
            user_id=user_id,
            timestamp=entry_timestamp,
            title=entry_data.title,
            body=entry_data.body,
            tags=entry_data.tags,
            mood=entry_data.mood,
            location=entry_data.location,
            weather=entry_data.weather,
            created_at=current_time,
            updated_at=current_time,
            photo_count=0,
        )
    
    def get_entry(self, entry_id: str, user_id: str) -> Optional[EntryResponse]:
        """Retrieve a single entry by ID.
        
        Args:
            entry_id: Entry identifier
            user_id: User identifier (for access control)
            
        Returns:
            Entry if found and belongs to user, None otherwise
        """
        doc_ref = self.client.collection(self.ENTRIES_COLLECTION).document(entry_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        doc_data = doc.to_dict()
        if doc_data is None:
            return None
        
        # Verify entry belongs to user
        if doc_data.get("user_id") != user_id:
            return None
        
        # Count associated photos
        photo_count = self._count_entry_photos(entry_id)
        
        return self._doc_to_entry_response(entry_id, doc_data, photo_count)
    
    def update_entry(
        self,
        entry_id: str,
        user_id: str,
        entry_data: EntryUpdate
    ) -> Optional[EntryResponse]:
        """Update an existing entry.
        
        Args:
            entry_id: Entry identifier
            user_id: User identifier (for access control)
            entry_data: Partial update data
            
        Returns:
            Updated entry if found and belongs to user, None otherwise
        """
        doc_ref = self.client.collection(self.ENTRIES_COLLECTION).document(entry_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        doc_data = doc.to_dict()
        if doc_data is None:
            return None
        
        # Verify entry belongs to user
        if doc_data.get("user_id") != user_id:
            return None
        
        # Build update dict with only provided fields
        updates = {"updated_at": now_aest()}
        
        if entry_data.timestamp is not None:
            updates["timestamp"] = ensure_aest(entry_data.timestamp)
        if entry_data.title is not None:
            updates["title"] = entry_data.title
        if entry_data.body is not None:
            updates["body"] = entry_data.body
        if entry_data.tags is not None:
            updates["tags"] = entry_data.tags
        if entry_data.mood is not None:
            updates["mood"] = entry_data.mood
        if entry_data.location is not None:
            updates["location"] = entry_data.location
        if entry_data.weather is not None:
            updates["weather"] = entry_data.weather
        
        # Apply updates
        doc_ref.update(updates)
        
        # Get updated document
        updated_doc = doc_ref.get()
        updated_data = updated_doc.to_dict()
        if updated_data is None:
            return None
        
        # Count associated photos
        photo_count = self._count_entry_photos(entry_id)
        
        return self._doc_to_entry_response(entry_id, updated_data, photo_count)
    
    def delete_entry(self, entry_id: str, user_id: str) -> bool:
        """Delete an entry (hard delete).
        
        Args:
            entry_id: Entry identifier
            user_id: User identifier (for access control)
            
        Returns:
            True if entry was deleted, False if not found or unauthorised
        """
        doc_ref = self.client.collection(self.ENTRIES_COLLECTION).document(entry_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        doc_data = doc.to_dict()
        if doc_data is None:
            return False
        
        # Verify entry belongs to user
        if doc_data.get("user_id") != user_id:
            return False
        
        # Delete the entry
        doc_ref.delete()
        
        return True
    
    def list_entries(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        tags: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> PaginatedResponse[EntryResponse]:
        """List entries with pagination and filtering.
        
        Args:
            user_id: User identifier
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            tags: Filter by tags (entries must have all specified tags)
            start_date: Filter entries from this date (YYYY-MM-DD, inclusive)
            end_date: Filter entries to this date (YYYY-MM-DD, inclusive)
            
        Returns:
            Paginated list of entries ordered by timestamp descending
        """
        # Validate pagination parameters
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        
        # Start query
        query = self.client.collection(self.ENTRIES_COLLECTION).where(
            filter=FieldFilter("user_id", "==", user_id)
        )
        
        # Apply date range filters
        if start_date:
            start_dt, _ = date_to_aest_range(start_date)
            query = query.where(filter=FieldFilter("timestamp", ">=", start_dt))
        
        if end_date:
            _, end_dt = date_to_aest_range(end_date)
            query = query.where(filter=FieldFilter("timestamp", "<=", end_dt))
        
        # Apply tag filters (entries must have all specified tags)
        if tags:
            for tag in tags:
                query = query.where(filter=FieldFilter("tags", "array_contains", tag))
        
        # Order by timestamp descending (newest first)
        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
        
        # Get total count (need to fetch all for accurate count with filters)
        all_docs = list(query.stream())
        total = len(all_docs)
        
        # Calculate pagination
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        has_next = page < total_pages
        has_previous = page > 1
        
        # Get page of results
        offset = (page - 1) * page_size
        page_docs = all_docs[offset:offset + page_size]
        
        # Convert to response models
        items = []
        for doc in page_docs:
            doc_data = doc.to_dict()
            if doc_data is not None:
                photo_count = self._count_entry_photos(doc.id)
                items.append(self._doc_to_entry_response(doc.id, doc_data, photo_count))
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
            next_cursor=None,  # Cursor-based pagination not implemented yet
        )
    
    def get_entries_by_date(
        self,
        user_id: str,
        date_str: str
    ) -> List[EntryResponse]:
        """Get all entries for a specific date.
        
        Args:
            user_id: User identifier
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            List of entries for the specified date, ordered by timestamp
            
        Raises:
            ValueError: If date format is invalid
        """
        # Parse date and get AEST range
        start_dt, end_dt = date_to_aest_range(date_str)
        
        # Query entries within date range
        query = (
            self.client.collection(self.ENTRIES_COLLECTION)
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("timestamp", ">=", start_dt))
            .where(filter=FieldFilter("timestamp", "<=", end_dt))
            .order_by("timestamp", direction=firestore.Query.ASCENDING)
        )
        
        docs = query.stream()
        
        entries = []
        for doc in docs:
            doc_data = doc.to_dict()
            if doc_data is not None:
                photo_count = self._count_entry_photos(doc.id)
                entries.append(self._doc_to_entry_response(doc.id, doc_data, photo_count))
        
        return entries
    
    def search_entries(
        self,
        user_id: str,
        search_term: str,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResponse[EntryResponse]:
        """Search entries by text content.
        
        Note: Firestore doesn't support native full-text search.
        This implementation searches for exact substring matches in title and body.
        For production, consider using Algolia or Elasticsearch.
        
        Args:
            user_id: User identifier
            search_term: Text to search for in title and body
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            
        Returns:
            Paginated list of matching entries ordered by timestamp descending
        """
        # Validate pagination parameters
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        
        # Get all user entries (Firestore limitation - must filter in memory)
        query = (
            self.client.collection(self.ENTRIES_COLLECTION)
            .where(filter=FieldFilter("user_id", "==", user_id))
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
        )
        
        all_docs = query.stream()
        
        # Filter by search term (case-insensitive substring match)
        search_lower = search_term.lower()
        matching_docs = []
        
        for doc in all_docs:
            doc_data = doc.to_dict()
            if doc_data is not None:
                title = doc_data.get("title", "").lower()
                body = doc_data.get("body", "").lower()
                
                if search_lower in title or search_lower in body:
                    matching_docs.append((doc.id, doc_data))
        
        # Calculate pagination
        total = len(matching_docs)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        has_next = page < total_pages
        has_previous = page > 1
        
        # Get page of results
        offset = (page - 1) * page_size
        page_docs = matching_docs[offset:offset + page_size]
        
        # Convert to response models
        items = []
        for doc_id, doc_data in page_docs:
            photo_count = self._count_entry_photos(doc_id)
            items.append(self._doc_to_entry_response(doc_id, doc_data, photo_count))
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
            next_cursor=None,
        )
    
    def create_photo(self, photo_data: Dict[str, Any]) -> None:
        """Create a new photo document in Firestore.
        
        Args:
            photo_data: Photo metadata to store
        """
        photo_id = photo_data.get("id")
        if not photo_id:
            raise ValueError("Photo data must include 'id' field")
        
        doc_ref = self.client.collection(self.PHOTOS_COLLECTION).document(photo_id)
        doc_ref.set(photo_data)
    
    def get_photo(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a photo document by ID.
        
        Args:
            photo_id: Photo identifier
            
        Returns:
            Photo metadata if found, None otherwise
        """
        doc_ref = self.client.collection(self.PHOTOS_COLLECTION).document(photo_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        doc_data = doc.to_dict()
        return doc_data
    
    def delete_photo(self, photo_id: str) -> None:
        """Delete a photo document from Firestore.
        
        Args:
            photo_id: Photo identifier
        """
        doc_ref = self.client.collection(self.PHOTOS_COLLECTION).document(photo_id)
        doc_ref.delete()
    
    def _count_entry_photos(self, entry_id: str) -> int:
        """Count photos associated with an entry.
        
        Args:
            entry_id: Entry identifier
            
        Returns:
            Number of photos for this entry
        """
        photos_query = self.client.collection(self.PHOTOS_COLLECTION).where(
            filter=FieldFilter("entry_id", "==", entry_id)
        )
        photos = list(photos_query.stream())
        return len(photos)
    
    def _doc_to_entry_response(
        self,
        doc_id: str,
        doc_data: Dict[str, Any],
        photo_count: int
    ) -> EntryResponse:
        """Convert Firestore document to EntryResponse model.
        
        Args:
            doc_id: Document ID
            doc_data: Document data dict
            photo_count: Number of photos for this entry
            
        Returns:
            EntryResponse model
        """
        # Ensure timestamps are in AEST
        timestamp = ensure_aest(doc_data["timestamp"])
        created_at = ensure_aest(doc_data["created_at"])
        updated_at = ensure_aest(doc_data["updated_at"])
        
        return EntryResponse(
            id=doc_id,
            user_id=doc_data["user_id"],
            timestamp=timestamp,
            title=doc_data["title"],
            body=doc_data["body"],
            tags=doc_data.get("tags", []),
            mood=doc_data.get("mood"),
            location=doc_data.get("location"),
            weather=doc_data.get("weather"),
            created_at=created_at,
            updated_at=updated_at,
            photo_count=photo_count,
        )