"""Unit tests for FirestoreService.

Tests all CRUD operations and helper methods with mocked Firestore client.
"""
import pytest
from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock

from app.models.entry import EntryCreate, EntryUpdate
from app.services.timezone_utils import AEST


class TestCreateEntry:
    """Tests for create_entry method."""
    
    def test_create_entry_success(
        self,
        mock_firestore_service_unit,
        sample_entry_create_data,
        mock_collection_ref,
        mock_document_ref,
    ):
        """Test successful entry creation."""
        # Setup mocks
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = mock_document_ref
        
        # Create entry
        entry_create = EntryCreate(**sample_entry_create_data)
        result = mock_firestore_service_unit.create_entry(entry_create, "test_user_123")
        
        # Verify collection and document calls
        mock_firestore_service_unit.client.collection.assert_called_once_with("entries")
        mock_collection_ref.document.assert_called_once()
        mock_document_ref.set.assert_called_once()
        
        # Verify result
        assert result.id == "test_entry_123"
        assert result.user_id == "test_user_123"
        assert result.title == "Test Entry"
        assert result.body == "This is a test entry body with some content."
        assert result.tags == ["test", "sample"]
        assert result.mood == "happy"
        assert result.photo_count == 0
        
    def test_create_entry_timestamps_in_aest(
        self,
        mock_firestore_service_unit,
        sample_entry_create_data,
        mock_collection_ref,
        mock_document_ref,
    ):
        """Test that created entry has AEST timestamps."""
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = mock_document_ref
        
        entry_create = EntryCreate(**sample_entry_create_data)
        result = mock_firestore_service_unit.create_entry(entry_create, "test_user_123")
        
        # Verify timestamps have AEST timezone
        assert result.timestamp.tzinfo == AEST
        assert result.created_at.tzinfo == AEST
        assert result.updated_at.tzinfo == AEST
        
    def test_create_entry_minimal_data(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
        mock_document_ref,
    ):
        """Test creating entry with minimal required fields."""
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = mock_document_ref
        
        minimal_data: Dict[str, Any] = {
            "timestamp": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
            "title": "Minimal Entry",
            "body": "Just the basics.",
        }
        
        entry_create = EntryCreate(**minimal_data)
        result = mock_firestore_service_unit.create_entry(entry_create, "test_user_123")
        
        assert result.title == "Minimal Entry"
        assert result.body == "Just the basics."
        assert result.tags == []
        assert result.mood is None
        assert result.location is None
        assert result.weather is None


class TestGetEntry:
    """Tests for get_entry method."""
    
    def test_get_entry_success(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        mock_collection_ref,
    ):
        """Test successful entry retrieval."""
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value.get.return_value = sample_firestore_doc
        
        # Mock photo count query
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        mock_firestore_service_unit.client.collection.side_effect = [
            mock_collection_ref,
            photos_collection,
        ]
        
        result = mock_firestore_service_unit.get_entry("test_entry_123", "test_user_123")
        
        assert result is not None
        assert result.id == "test_entry_123"
        assert result.user_id == "test_user_123"
        assert result.title == "Test Entry"
        
    def test_get_entry_not_found(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test getting non-existent entry returns None."""
        doc = Mock()
        doc.exists = False
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value.get.return_value = doc
        
        result = mock_firestore_service_unit.get_entry("nonexistent_id", "test_user_123")
        
        assert result is None
        
    def test_get_entry_wrong_user(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        mock_collection_ref,
    ):
        """Test that user cannot access another user's entry."""
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value.get.return_value = sample_firestore_doc
        
        result = mock_firestore_service_unit.get_entry("test_entry_123", "different_user")
        
        assert result is None
        
    def test_get_entry_with_photos(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        mock_collection_ref,
    ):
        """Test entry retrieval includes photo count."""
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value.get.return_value = sample_firestore_doc
        
        # Mock 3 photos
        photo_docs = [Mock(), Mock(), Mock()]
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = photo_docs
        mock_firestore_service_unit.client.collection.side_effect = [
            mock_collection_ref,
            photos_collection,
        ]
        
        result = mock_firestore_service_unit.get_entry("test_entry_123", "test_user_123")
        
        assert result.photo_count == 3


class TestUpdateEntry:
    """Tests for update_entry method."""
    
    def test_update_entry_success(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        sample_entry_update_data,
        mock_collection_ref,
    ):
        """Test successful entry update."""
        # Mock document reference
        doc_ref = Mock()
        doc_ref.get.side_effect = [
            sample_firestore_doc,  # First get for verification
            sample_firestore_doc,  # Second get after update
        ]
        doc_ref.update = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        # Mock photo count
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        mock_firestore_service_unit.client.collection.side_effect = [
            mock_collection_ref,
            photos_collection,
        ]
        
        entry_update = EntryUpdate(**sample_entry_update_data)
        result = mock_firestore_service_unit.update_entry(
            "test_entry_123",
            "test_user_123",
            entry_update
        )
        
        assert result is not None
        doc_ref.update.assert_called_once()
        
    def test_update_entry_partial(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        mock_collection_ref,
    ):
        """Test partial update with only some fields."""
        doc_ref = Mock()
        doc_ref.get.side_effect = [
            sample_firestore_doc,
            sample_firestore_doc,
        ]
        doc_ref.update = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        mock_firestore_service_unit.client.collection.side_effect = [
            mock_collection_ref,
            photos_collection,
        ]
        
        # Update only title
        entry_update = EntryUpdate(title="Updated Title Only")
        result = mock_firestore_service_unit.update_entry(
            "test_entry_123",
            "test_user_123",
            entry_update
        )
        
        assert result is not None
        doc_ref.update.assert_called_once()
        
        # Verify only title and updated_at in update call
        update_call_args = doc_ref.update.call_args[0][0]
        assert "title" in update_call_args
        assert "updated_at" in update_call_args
        assert "body" not in update_call_args
        
    def test_update_entry_not_found(
        self,
        mock_firestore_service_unit,
        sample_entry_update_data,
        mock_collection_ref,
    ):
        """Test updating non-existent entry returns None."""
        doc = Mock()
        doc.exists = False
        
        doc_ref = Mock()
        doc_ref.get.return_value = doc
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        entry_update = EntryUpdate(**sample_entry_update_data)
        result = mock_firestore_service_unit.update_entry(
            "nonexistent_id",
            "test_user_123",
            entry_update
        )
        
        assert result is None
        doc_ref.update.assert_not_called()
        
    def test_update_entry_wrong_user(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        sample_entry_update_data,
        mock_collection_ref,
    ):
        """Test that user cannot update another user's entry."""
        doc_ref = Mock()
        doc_ref.get.return_value = sample_firestore_doc
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        entry_update = EntryUpdate(**sample_entry_update_data)
        result = mock_firestore_service_unit.update_entry(
            "test_entry_123",
            "different_user",
            entry_update
        )
        
        assert result is None
        doc_ref.update.assert_not_called()


class TestDeleteEntry:
    """Tests for delete_entry method."""
    
    def test_delete_entry_success(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        mock_collection_ref,
    ):
        """Test successful entry deletion."""
        doc_ref = Mock()
        doc_ref.get.return_value = sample_firestore_doc
        doc_ref.delete = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        result = mock_firestore_service_unit.delete_entry("test_entry_123", "test_user_123")
        
        assert result is True
        doc_ref.delete.assert_called_once()
        
    def test_delete_entry_not_found(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test deleting non-existent entry returns False."""
        doc = Mock()
        doc.exists = False
        
        doc_ref = Mock()
        doc_ref.get.return_value = doc
        doc_ref.delete = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        result = mock_firestore_service_unit.delete_entry("nonexistent_id", "test_user_123")
        
        assert result is False
        doc_ref.delete.assert_not_called()
        
    def test_delete_entry_wrong_user(
        self,
        mock_firestore_service_unit,
        sample_firestore_doc,
        mock_collection_ref,
    ):
        """Test that user cannot delete another user's entry."""
        doc_ref = Mock()
        doc_ref.get.return_value = sample_firestore_doc
        doc_ref.delete = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        result = mock_firestore_service_unit.delete_entry("test_entry_123", "different_user")
        
        assert result is False
        doc_ref.delete.assert_not_called()


class TestListEntries:
    """Tests for list_entries method."""
    
    def test_list_entries_basic(
        self,
        mock_firestore_service_unit,
        multiple_entries_data,
        mock_collection_ref,
    ):
        """Test basic entry listing."""
        mock_collection_ref.stream.return_value = multiple_entries_data
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        # Mock photo counts to return 0
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        
        def collection_side_effect(name):
            if name == "entries":
                return mock_collection_ref
            return photos_collection
        
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        
        result = mock_firestore_service_unit.list_entries("test_user_123", page=1, page_size=20)
        
        assert result.total == 5
        assert len(result.items) == 5
        assert result.page == 1
        assert result.page_size == 20
        assert result.total_pages == 1
        assert result.has_next is False
        assert result.has_previous is False
        
    def test_list_entries_pagination(
        self,
        mock_firestore_service_unit,
        multiple_entries_data,
        mock_collection_ref,
    ):
        """Test entry listing with pagination."""
        mock_collection_ref.stream.return_value = multiple_entries_data
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        
        def collection_side_effect(name):
            if name == "entries":
                return mock_collection_ref
            return photos_collection
        
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        
        # Get page 1 with 2 items per page
        result = mock_firestore_service_unit.list_entries(
            "test_user_123",
            page=1,
            page_size=2
        )
        
        assert result.total == 5
        assert len(result.items) == 2
        assert result.page == 1
        assert result.total_pages == 3
        assert result.has_next is True
        assert result.has_previous is False
        
    def test_list_entries_empty(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test listing when no entries exist."""
        mock_collection_ref.stream.return_value = []
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        result = mock_firestore_service_unit.list_entries("test_user_123")
        
        assert result.total == 0
        assert len(result.items) == 0
        assert result.total_pages == 0
        
    def test_list_entries_validates_pagination(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test that invalid pagination parameters are corrected."""
        mock_collection_ref.stream.return_value = []
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        # Negative page should be corrected to 1
        result = mock_firestore_service_unit.list_entries("test_user_123", page=-1, page_size=20)
        assert result.page == 1
        
        # Page size over 100 should be capped
        result = mock_firestore_service_unit.list_entries("test_user_123", page=1, page_size=150)
        assert result.page_size == 100


class TestGetEntriesByDate:
    """Tests for get_entries_by_date method."""
    
    def test_get_entries_by_date_success(
        self,
        mock_firestore_service_unit,
        multiple_entries_data,
        mock_collection_ref,
    ):
        """Test getting entries for specific date."""
        # Return first 2 entries (same date)
        mock_collection_ref.stream.return_value = multiple_entries_data[:2]
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        
        def collection_side_effect(name):
            if name == "entries":
                return mock_collection_ref
            return photos_collection
        
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        
        result = mock_firestore_service_unit.get_entries_by_date("test_user_123", "2026-01-30")
        
        assert len(result) == 2
        assert all(isinstance(entry.timestamp, datetime) for entry in result)
        
    def test_get_entries_by_date_no_results(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test getting entries when none exist for date."""
        mock_collection_ref.stream.return_value = []
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        result = mock_firestore_service_unit.get_entries_by_date("test_user_123", "2026-01-01")
        
        assert len(result) == 0
        
    def test_get_entries_by_date_invalid_format(
        self,
        mock_firestore_service_unit,
    ):
        """Test that invalid date format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            mock_firestore_service_unit.get_entries_by_date("test_user_123", "invalid-date")


class TestSearchEntries:
    """Tests for search_entries method."""
    
    def test_search_entries_with_results(
        self,
        mock_firestore_service_unit,
        multiple_entries_data,
        mock_collection_ref,
    ):
        """Test searching entries with matching results."""
        mock_collection_ref.stream.return_value = multiple_entries_data
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        
        def collection_side_effect(name):
            if name == "entries":
                return mock_collection_ref
            return photos_collection
        
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        
        result = mock_firestore_service_unit.search_entries(
            "test_user_123",
            "test entry",
            page=1,
            page_size=20
        )
        
        # All 5 entries should match "test entry" in title
        assert result.total == 5
        assert len(result.items) == 5
        
    def test_search_entries_no_results(
        self,
        mock_firestore_service_unit,
        multiple_entries_data,
        mock_collection_ref,
    ):
        """Test search with no matching entries."""
        mock_collection_ref.stream.return_value = multiple_entries_data
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        
        def collection_side_effect(name):
            if name == "entries":
                return mock_collection_ref
            return photos_collection
        
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        
        result = mock_firestore_service_unit.search_entries(
            "test_user_123",
            "nonexistent search term xyz",
            page=1,
            page_size=20
        )
        
        assert result.total == 0
        assert len(result.items) == 0
        
    def test_search_entries_pagination(
        self,
        mock_firestore_service_unit,
        multiple_entries_data,
        mock_collection_ref,
    ):
        """Test search with pagination."""
        mock_collection_ref.stream.return_value = multiple_entries_data
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        
        def collection_side_effect(name):
            if name == "entries":
                return mock_collection_ref
            return photos_collection
        
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        
        result = mock_firestore_service_unit.search_entries(
            "test_user_123",
            "test",
            page=1,
            page_size=2
        )
        
        assert result.total == 5
        assert len(result.items) == 2
        assert result.page == 1
        assert result.total_pages == 3
        assert result.has_next is True
        assert result.has_previous is False
        
    def test_search_entries_case_insensitive(
        self,
        mock_firestore_service_unit,
        multiple_entries_data,
        mock_collection_ref,
    ):
        """Test that search is case-insensitive."""
        mock_collection_ref.stream.return_value = multiple_entries_data
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        
        photos_collection = Mock()
        photos_collection.where.return_value.stream.return_value = []
        
        def collection_side_effect(name):
            if name == "entries":
                return mock_collection_ref
            return photos_collection
        
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        
        # Search with different casing
        result_lower = mock_firestore_service_unit.search_entries(
            "test_user_123",
            "test entry",
            page=1,
            page_size=20
        )
        
        # Reset mock
        mock_firestore_service_unit.client.collection.side_effect = collection_side_effect
        mock_collection_ref.stream.return_value = multiple_entries_data
        
        result_upper = mock_firestore_service_unit.search_entries(
            "test_user_123",
            "TEST ENTRY",
            page=1,
            page_size=20
        )
        
        # Should return same number of results regardless of case
        assert result_lower.total == result_upper.total
        assert result_lower.total == 5


class TestCreatePhoto:
    """Tests for create_photo method."""
    
    def test_create_photo_success(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test successful photo creation."""
        doc_ref = Mock()
        doc_ref.set = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        photo_data: Dict[str, Any] = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "user_id": "test_user_123",
            "filename": "test_photo.jpg",
            "content_type": "image/jpeg",
            "size": 1024000,
            "storage_path": "photos/test_entry_123/test_photo_123.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_123_thumb.jpg",
            "uploaded_at": datetime(2026, 1, 30, 12, 0, 0, tzinfo=AEST),
        }
        
        mock_firestore_service_unit.create_photo(photo_data)
        
        # Verify collection and document calls
        mock_firestore_service_unit.client.collection.assert_called_once_with("photos")
        mock_collection_ref.document.assert_called_once_with("test_photo_123")
        doc_ref.set.assert_called_once_with(photo_data)
        
    def test_create_photo_with_exif(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test photo creation with EXIF metadata."""
        doc_ref = Mock()
        doc_ref.set = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        photo_data: Dict[str, Any] = {
            "id": "test_photo_456",
            "entry_id": "test_entry_123",
            "user_id": "test_user_123",
            "filename": "iphone_photo.jpg",
            "content_type": "image/jpeg",
            "size": 2048000,
            "storage_path": "photos/test_entry_123/test_photo_456.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_456_thumb.jpg",
            "uploaded_at": datetime(2026, 1, 30, 12, 0, 0, tzinfo=AEST),
            "exif_data": {
                "Make": "Apple",
                "Model": "iPhone 15 Pro",
                "DateTime": "2026:01:30 12:00:00",
                "GPSLatitude": -27.4698,
                "GPSLongitude": 153.0251,
            }
        }
        
        mock_firestore_service_unit.create_photo(photo_data)
        
        doc_ref.set.assert_called_once_with(photo_data)
        
    def test_create_photo_missing_id_raises_error(
        self,
        mock_firestore_service_unit,
    ):
        """Test that photo without ID raises ValueError."""
        photo_data: Dict[str, Any] = {
            "entry_id": "test_entry_123",
            "user_id": "test_user_123",
            "filename": "test_photo.jpg",
        }
        
        with pytest.raises(ValueError, match="Photo data must include 'id' field"):
            mock_firestore_service_unit.create_photo(photo_data)


class TestGetPhoto:
    """Tests for get_photo method."""
    
    def test_get_photo_success(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test successful photo retrieval."""
        # Create mock document with photo data
        photo_data: Dict[str, Any] = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "user_id": "test_user_123",
            "filename": "test_photo.jpg",
            "content_type": "image/jpeg",
            "size": 1024000,
            "storage_path": "photos/test_entry_123/test_photo_123.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_123_thumb.jpg",
            "uploaded_at": datetime(2026, 1, 30, 12, 0, 0, tzinfo=AEST),
        }
        
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = photo_data
        
        doc_ref = Mock()
        doc_ref.get.return_value = mock_doc
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        result = mock_firestore_service_unit.get_photo("test_photo_123")
        
        # Verify calls
        mock_firestore_service_unit.client.collection.assert_called_once_with("photos")
        mock_collection_ref.document.assert_called_once_with("test_photo_123")
        doc_ref.get.assert_called_once()
        
        # Verify result
        assert result == photo_data
        assert result["id"] == "test_photo_123"
        assert result["filename"] == "test_photo.jpg"
        
    def test_get_photo_with_exif_data(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test retrieving photo with EXIF metadata."""
        photo_data: Dict[str, Any] = {
            "id": "test_photo_456",
            "entry_id": "test_entry_123",
            "user_id": "test_user_123",
            "filename": "iphone_photo.jpg",
            "content_type": "image/jpeg",
            "size": 2048000,
            "storage_path": "photos/test_entry_123/test_photo_456.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_456_thumb.jpg",
            "uploaded_at": datetime(2026, 1, 30, 12, 0, 0, tzinfo=AEST),
            "exif_data": {
                "Make": "Apple",
                "Model": "iPhone 15 Pro",
                "DateTime": "2026:01:30 12:00:00",
                "GPSLatitude": -27.4698,
                "GPSLongitude": 153.0251,
            }
        }
        
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = photo_data
        
        doc_ref = Mock()
        doc_ref.get.return_value = mock_doc
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        result = mock_firestore_service_unit.get_photo("test_photo_456")
        
        assert result is not None
        assert "exif_data" in result
        assert result["exif_data"]["Make"] == "Apple"
        assert result["exif_data"]["Model"] == "iPhone 15 Pro"
        
    def test_get_photo_not_found(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test getting non-existent photo returns None."""
        mock_doc = Mock()
        mock_doc.exists = False
        
        doc_ref = Mock()
        doc_ref.get.return_value = mock_doc
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        result = mock_firestore_service_unit.get_photo("nonexistent_photo_id")
        
        assert result is None
        mock_collection_ref.document.assert_called_once_with("nonexistent_photo_id")


class TestDeletePhoto:
    """Tests for delete_photo method."""
    
    def test_delete_photo_success(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test successful photo deletion."""
        doc_ref = Mock()
        doc_ref.delete = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        mock_firestore_service_unit.delete_photo("test_photo_123")
        
        # Verify collection and document calls
        mock_firestore_service_unit.client.collection.assert_called_once_with("photos")
        mock_collection_ref.document.assert_called_once_with("test_photo_123")
        doc_ref.delete.assert_called_once()
        
    def test_delete_photo_calls_firestore_correctly(
        self,
        mock_firestore_service_unit,
        mock_collection_ref,
    ):
        """Test that delete_photo makes correct Firestore calls."""
        doc_ref = Mock()
        doc_ref.delete = Mock()
        
        mock_firestore_service_unit.client.collection.return_value = mock_collection_ref
        mock_collection_ref.document.return_value = doc_ref
        
        # Delete photo
        mock_firestore_service_unit.delete_photo("photo_to_delete")
        
        # Verify the exact sequence of calls
        assert mock_firestore_service_unit.client.collection.call_count == 1
        assert mock_collection_ref.document.call_count == 1
        assert doc_ref.delete.call_count == 1
        
        # Verify correct photo ID was used
        mock_collection_ref.document.assert_called_with("photo_to_delete")
