"""Integration tests for diary entries API endpoints.

Tests all API routes with mocked Firestore service.
"""
import pytest
from datetime import datetime

from app.models.entry import EntryResponse
from app.models.pagination import PaginatedResponse
from app.services.timezone_utils import AEST


@pytest.fixture
def sample_entry_response():
    """Sample EntryResponse for testing."""
    return EntryResponse(
        id="test_entry_123",
        user_id="test_user_123",
        timestamp=datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        title="Test Entry",
        body="This is a test entry body.",
        tags=["test", "sample"],
        mood="happy",
        location="Sydney, Australia",
        weather="sunny, 25°C",
        created_at=datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        updated_at=datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        photo_count=0,
    )


class TestCreateEntry:
    """Tests for POST /api/entries endpoint."""
    
    def test_create_entry_success(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test successful entry creation."""
        mock_firestore_service.create_entry.return_value = sample_entry_response
        
        request_data = {
            "timestamp": "2026-01-30T09:00:00+10:00",
            "title": "Test Entry",
            "body": "This is a test entry body.",
            "tags": ["test", "sample"],
            "mood": "happy",
            "location": "Sydney, Australia",
            "weather": "sunny, 25°C",
        }
        
        response = client.post(
            "/api/entries",
            json=request_data,
            headers=api_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "test_entry_123"
        assert data["title"] == "Test Entry"
        assert data["user_id"] == "test_user_123"
        
    def test_create_entry_minimal_fields(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test creating entry with minimal required fields."""
        mock_firestore_service.create_entry.return_value = sample_entry_response
        
        request_data = {
            "timestamp": "2026-01-30T09:00:00+10:00",
            "title": "Minimal Entry",
            "body": "Just the basics.",
        }
        
        response = client.post(
            "/api/entries",
            json=request_data,
            headers=api_headers,
        )
        
        assert response.status_code == 201
        
    def test_create_entry_missing_required_fields(
        self,
        client,
        api_headers,
    ):
        """Test that missing required fields returns validation error."""
        request_data = {
            "title": "Missing timestamp and body",
        }
        
        response = client.post(
            "/api/entries",
            json=request_data,
            headers=api_headers,
        )
        
        assert response.status_code == 422
        
    def test_create_entry_unauthorised(
        self,
        unauthorized_client,
    ):
        """Test that missing API key returns 401."""
        request_data = {
            "timestamp": "2026-01-30T09:00:00+10:00",
            "title": "Test Entry",
            "body": "This should fail.",
        }
        
        response = unauthorized_client.post(
            "/api/entries",
            json=request_data,
        )
        
        assert response.status_code == 401


class TestGetEntry:
    """Tests for GET /api/entries/{entry_id} endpoint."""
    
    def test_get_entry_success(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test successful entry retrieval."""
        mock_firestore_service.get_entry.return_value = sample_entry_response
        
        response = client.get(
            "/api/entries/test_entry_123",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_entry_123"
        assert data["title"] == "Test Entry"
        
    def test_get_entry_not_found(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test getting non-existent entry returns 404."""
        mock_firestore_service.get_entry.return_value = None
        
        response = client.get(
            "/api/entries/nonexistent_id",
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "Entry not found" in response.json()["error"]["message"]
        
    def test_get_entry_unauthorised(
        self,
        unauthorized_client,
    ):
        """Test that missing API key returns 401."""
        response = unauthorized_client.get("/api/entries/test_entry_123")
        
        assert response.status_code == 401


class TestUpdateEntry:
    """Tests for PUT /api/entries/{entry_id} endpoint."""
    
    def test_update_entry_success(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test successful entry update."""
        updated_entry = sample_entry_response.model_copy()
        updated_entry.title = "Updated Title"
        mock_firestore_service.update_entry.return_value = updated_entry
        
        request_data = {
            "title": "Updated Title",
        }
        
        response = client.put(
            "/api/entries/test_entry_123",
            json=request_data,
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        
    def test_update_entry_full_update(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test full entry update with all fields."""
        mock_firestore_service.update_entry.return_value = sample_entry_response
        
        request_data = {
            "timestamp": "2026-01-30T10:00:00+10:00",
            "title": "Fully Updated",
            "body": "All fields updated.",
            "tags": ["updated"],
            "mood": "excited",
            "location": "Melbourne, Australia",
            "weather": "cloudy",
        }
        
        response = client.put(
            "/api/entries/test_entry_123",
            json=request_data,
            headers=api_headers,
        )
        
        assert response.status_code == 200
        
    def test_update_entry_not_found(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test updating non-existent entry returns 404."""
        mock_firestore_service.update_entry.return_value = None
        
        request_data = {
            "title": "Updated Title",
        }
        
        response = client.put(
            "/api/entries/nonexistent_id",
            json=request_data,
            headers=api_headers,
        )
        
        assert response.status_code == 404
        
    def test_update_entry_unauthorised(
        self,
        unauthorized_client,
    ):
        """Test that missing API key returns 401."""
        response = unauthorized_client.put(
            "/api/entries/test_entry_123",
            json={"title": "Updated"},
        )
        
        assert response.status_code == 401


class TestDeleteEntry:
    """Tests for DELETE /api/entries/{entry_id} endpoint."""
    
    def test_delete_entry_success(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test successful entry deletion."""
        mock_firestore_service.delete_entry.return_value = True
        
        response = client.delete(
            "/api/entries/test_entry_123",
            headers=api_headers,
        )
        
        assert response.status_code == 204
        assert response.content == b''
        
    def test_delete_entry_not_found(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test deleting non-existent entry returns 404."""
        mock_firestore_service.delete_entry.return_value = False
        
        response = client.delete(
            "/api/entries/nonexistent_id",
            headers=api_headers,
        )
        
        assert response.status_code == 404
        
    def test_delete_entry_unauthorised(
        self,
        unauthorized_client,
    ):
        """Test that missing API key returns 401."""
        response = unauthorized_client.delete("/api/entries/test_entry_123")
        
        assert response.status_code == 401


class TestListEntries:
    """Tests for GET /api/entries endpoint."""
    
    def test_list_entries_default_pagination(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test listing entries with default pagination."""
        paginated_response = PaginatedResponse(
            items=[sample_entry_response],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 1
        
    def test_list_entries_custom_pagination(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test listing entries with custom pagination."""
        paginated_response = PaginatedResponse(
            items=[sample_entry_response],
            total=10,
            page=2,
            page_size=5,
            total_pages=2,
            has_next=False,
            has_previous=True,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries?page=2&page_size=5",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
        assert data["has_previous"] is True
        
    def test_list_entries_with_tags_filter(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test listing entries filtered by tags."""
        paginated_response = PaginatedResponse(
            items=[sample_entry_response],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries?tags=test,sample",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        mock_firestore_service.list_entries.assert_called_once()
        call_kwargs = mock_firestore_service.list_entries.call_args[1]
        assert call_kwargs["tags"] == ["test", "sample"]
        
    def test_list_entries_with_date_range(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test listing entries with date range filter."""
        paginated_response = PaginatedResponse(
            items=[sample_entry_response],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries?start_date=2026-01-01&end_date=2026-01-31",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        call_kwargs = mock_firestore_service.list_entries.call_args[1]
        assert call_kwargs["start_date"] == "2026-01-01"
        assert call_kwargs["end_date"] == "2026-01-31"
        
    def test_list_entries_empty_results(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test listing when no entries exist."""
        paginated_response = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            total_pages=0,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0


class TestGetEntriesByDate:
    """Tests for GET /api/entries/date/{date} endpoint."""
    
    def test_get_entries_by_date_success(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test getting entries for specific date."""
        mock_firestore_service.get_entries_by_date.return_value = [
            sample_entry_response
        ]
        
        response = client.get(
            "/api/entries/date/2026-01-30",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test_entry_123"
        
    def test_get_entries_by_date_no_results(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test getting entries when none exist for date."""
        mock_firestore_service.get_entries_by_date.return_value = []
        
        response = client.get(
            "/api/entries/date/2026-01-01",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
        
    def test_get_entries_by_date_invalid_format(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test that invalid date format returns 400."""
        mock_firestore_service.get_entries_by_date.side_effect = ValueError(
            "Invalid date format"
        )
        
        response = client.get(
            "/api/entries/date/invalid-date",
            headers=api_headers,
        )
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["error"]["message"]


class TestSearchEntries:
    """Tests for GET /api/entries/search endpoint."""
    
    def test_search_entries_success(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test searching entries with results."""
        paginated_response = PaginatedResponse(
            items=[sample_entry_response],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.search_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries/search?q=test",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        
    def test_search_entries_missing_query(
        self,
        client,
        api_headers,
    ):
        """Test that missing search query returns validation error."""
        response = client.get(
            "/api/entries/search",
            headers=api_headers,
        )
        
        assert response.status_code == 422
        
    def test_search_entries_with_pagination(
        self,
        client,
        mock_firestore_service,
        sample_entry_response,
        api_headers,
    ):
        """Test searching with custom pagination."""
        paginated_response = PaginatedResponse(
            items=[sample_entry_response],
            total=10,
            page=2,
            page_size=5,
            total_pages=2,
            has_next=False,
            has_previous=True,
            next_cursor=None,
        )
        mock_firestore_service.search_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries/search?q=test&page=2&page_size=5",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
        
    def test_search_entries_no_results(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test searching when no entries match query."""
        paginated_response = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            total_pages=0,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.search_entries.return_value = paginated_response
        
        response = client.get(
            "/api/entries/search?q=nonexistent",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0
