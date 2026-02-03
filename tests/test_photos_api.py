"""Integration tests for photo API endpoints.

Tests all photo routes with mocked services.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from io import BytesIO

from app.models.photo import PhotoResponse
from app.models.entry import EntryResponse
from app.services.timezone_utils import AEST


@pytest.fixture
def sample_photo_response():
    """Sample PhotoResponse for testing."""
    return PhotoResponse(
        id="test_photo_123",
        entry_id="test_entry_123",
        filename="test_image.jpg",
        content_type="image/jpeg",
        size_bytes=1024000,
        storage_path="photos/test_entry_123/test_photo_123.jpg",
        thumbnail_path="photos/test_entry_123/test_photo_123_thumb.jpg",
        photo_url="https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123.jpg?signed=true",
        thumbnail_url="https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123_thumb.jpg?signed=true",
        caption="Test photo caption",
        exif_data={
            "Make": "Apple",
            "Model": "iPhone 15 Pro",
            "DateTime": "2026:01:30 09:00:00",
            "GPSLatitude": -33.8688,
            "GPSLongitude": 151.2093,
        },
        created_at=datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
    )


@pytest.fixture
def sample_entry_for_photo():
    """Sample EntryResponse for photo upload testing."""
    return EntryResponse(
        id="test_entry_123",
        user_id="test_user_123",
        timestamp=datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        title="Test Entry",
        body="Entry for photo testing.",
        tags=["test"],
        mood="happy",
        location="Sydney, Australia",
        weather="sunny",
        created_at=datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        updated_at=datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        photo_count=0,
    )


@pytest.fixture
def mock_upload_file():
    """Mock UploadFile for testing file uploads."""
    file = Mock()
    file.filename = "test_image.jpg"
    file.content_type = "image/jpeg"
    file.size = 1024000
    file.file = BytesIO(b"fake image data")
    file.read = AsyncMock(return_value=b"fake image data")
    file.seek = Mock()
    return file


class TestUploadPhoto:
    """Tests for POST /api/entries/{entry_id}/photos endpoint."""
    
    def test_upload_photo_success(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        sample_photo_response,
        api_headers,
    ):
        """Test successful photo upload."""
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        # Return dict matching storage_service.upload_photo signature
        mock_storage_service.upload_photo.return_value = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 1024000,
            "storage_path": "photos/test_entry_123/test_photo_123.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_123_thumb.jpg",
            "photo_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123.jpg?signed=true",
            "thumbnail_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123_thumb.jpg?signed=true",
            "exif_data": {
                "Make": "Apple",
                "Model": "iPhone 15 Pro",
                "DateTime": "2026:01:30 09:00:00",
                "GPSLatitude": -33.8688,
                "GPSLongitude": 151.2093,
            },
            "caption": "Test photo caption",
            "created_at": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        }
        
        files = {"file": ("test_image.jpg", BytesIO(b"fake image data"), "image/jpeg")}
        data = {"caption": "Test photo caption"}
        
        response = photo_client.post(
            "/api/entries/test_entry_123/photos",
            files=files,
            data=data,
            headers=api_headers,
        )
        
        assert response.status_code == 201
        result = response.json()
        assert result["id"] == "test_photo_123"
        assert result["entry_id"] == "test_entry_123"
        assert result["filename"] == "test_image.jpg"
        assert result["caption"] == "Test photo caption"
        
    def test_upload_photo_without_caption(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        sample_photo_response,
        api_headers,
    ):
        """Test uploading photo without caption."""
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        # Return dict matching storage_service.upload_photo signature, without caption
        mock_storage_service.upload_photo.return_value = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 1024000,
            "storage_path": "photos/test_entry_123/test_photo_123.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_123_thumb.jpg",
            "photo_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123.jpg?signed=true",
            "thumbnail_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123_thumb.jpg?signed=true",
            "exif_data": {
                "Make": "Apple",
                "Model": "iPhone 15 Pro",
                "DateTime": "2026:01:30 09:00:00",
                "GPSLatitude": -33.8688,
                "GPSLongitude": 151.2093,
            },
            "caption": None,
            "created_at": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        }
        
        files = {"file": ("test_image.jpg", BytesIO(b"fake image data"), "image/jpeg")}
        
        response = photo_client.post(
            "/api/entries/test_entry_123/photos",
            files=files,
            headers=api_headers,
        )
        
        assert response.status_code == 201
        result = response.json()
        assert result["caption"] is None
        
    def test_upload_photo_entry_not_found(
        self,
        photo_client,
        mock_firestore_service,
        api_headers,
    ):
        """Test uploading photo to non-existent entry returns 404."""
        mock_firestore_service.get_entry.return_value = None
        
        files = {"file": ("test_image.jpg", BytesIO(b"fake image data"), "image/jpeg")}
        
        response = photo_client.post(
            "/api/entries/nonexistent_entry/photos",
            files=files,
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "Entry not found or unauthorised" in response.json()["error"]["message"]
        
    def test_upload_photo_unauthorised_entry(
        self,
        photo_client,
        mock_firestore_service,
        api_headers,
    ):
        """Test uploading photo to entry belonging to another user returns 404."""
        # get_entry returns None when entry doesn't belong to user
        mock_firestore_service.get_entry.return_value = None
        
        files = {"file": ("test_image.jpg", BytesIO(b"fake image data"), "image/jpeg")}
        
        response = photo_client.post(
            "/api/entries/other_user_entry/photos",
            files=files,
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "unauthorised" in response.json()["error"]["message"].lower()
        
    def test_upload_photo_invalid_file(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test uploading invalid file returns 400."""
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        mock_storage_service.upload_photo.side_effect = ValueError("Invalid file type")
        
        files = {"file": ("test.txt", BytesIO(b"not an image"), "text/plain")}
        
        response = photo_client.post(
            "/api/entries/test_entry_123/photos",
            files=files,
            headers=api_headers,
        )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["error"]["message"]
        
    def test_upload_photo_file_too_large(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test uploading file exceeding size limit returns 400."""
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        mock_storage_service.upload_photo.side_effect = ValueError(
            "File too large. Maximum size is 50MB"
        )
        
        files = {"file": ("huge_image.jpg", BytesIO(b"x" * 60000000), "image/jpeg")}
        
        response = photo_client.post(
            "/api/entries/test_entry_123/photos",
            files=files,
            headers=api_headers,
        )
        
        assert response.status_code == 400
        assert "too large" in response.json()["error"]["message"].lower()
        
    def test_upload_photo_storage_error(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test storage service error returns 500."""
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        mock_storage_service.upload_photo.side_effect = Exception("Storage service error")
        
        files = {"file": ("test_image.jpg", BytesIO(b"fake image data"), "image/jpeg")}
        
        response = photo_client.post(
            "/api/entries/test_entry_123/photos",
            files=files,
            headers=api_headers,
        )
        
        assert response.status_code == 500
        assert "Failed to upload photo" in response.json()["error"]["message"]
        
    def test_upload_photo_missing_file(
        self,
        photo_client,
        api_headers,
    ):
        """Test uploading without file returns 422."""
        response = photo_client.post(
            "/api/entries/test_entry_123/photos",
            headers=api_headers,
        )
        
        assert response.status_code == 422


class TestGetPhoto:
    """Tests for GET /api/photos/{photo_id} endpoint."""
    
    def test_get_photo_success(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_photo_response,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test successful photo retrieval."""
        # Mock firestore.get_photo() to return photo metadata dict
        photo_data = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 1024000,
            "storage_path": "photos/test_entry_123/test_photo_123.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_123_thumb.jpg",
            "caption": "Test photo caption",
            "exif_data": {},
            "created_at": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        }
        mock_firestore_service.get_photo.return_value = photo_data
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        
        # Mock storage.get_photo_url() to return dict with URLs
        mock_storage_service.get_photo_url.return_value = {
            "photo_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123.jpg?signed=true",
            "thumbnail_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123_thumb.jpg?signed=true",
        }
        
        response = photo_client.get(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["id"] == "test_photo_123"
        assert result["entry_id"] == "test_entry_123"
        assert "photo_url" in result
        assert "thumbnail_url" in result
        
    def test_get_photo_with_exif_data(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_photo_response,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test getting photo with EXIF metadata."""
        # Mock firestore.get_photo() to return photo metadata dict with EXIF data
        photo_data = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 1024000,
            "storage_path": "photos/test_entry_123/test_photo_123.jpg",
            "thumbnail_path": "photos/test_entry_123/test_photo_123_thumb.jpg",
            "caption": "Test photo caption",
            "exif_data": {
                "Make": "Apple",
                "Model": "iPhone 15 Pro",
                "DateTime": "2026:01:30 09:00:00",
                "GPSLatitude": -33.8688,
                "GPSLongitude": 151.2093,
            },
            "created_at": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        }
        mock_firestore_service.get_photo.return_value = photo_data
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        
        # Mock storage.get_photo_url() to return dict with URLs
        mock_storage_service.get_photo_url.return_value = {
            "photo_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123.jpg?signed=true",
            "thumbnail_url": "https://storage.googleapis.com/bucket/photos/test_entry_123/test_photo_123_thumb.jpg?signed=true",
        }
        
        response = photo_client.get(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "exif_data" in result
        assert result["exif_data"]["Make"] == "Apple"
        assert result["exif_data"]["Model"] == "iPhone 15 Pro"
        
    def test_get_photo_not_found(
        self,
        photo_client,
        mock_firestore_service,
        api_headers,
    ):
        """Test getting non-existent photo returns 404."""
        mock_firestore_service.get_photo.return_value = None
        
        response = photo_client.get(
            "/api/photos/nonexistent_photo",
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["error"]["message"].lower()
        
    def test_get_photo_unauthorised_entry(
        self,
        photo_client,
        mock_firestore_service,
        api_headers,
    ):
        """Test getting photo from entry belonging to another user returns 404."""
        # Mock firestore.get_photo() to return photo metadata
        photo_data = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
        }
        mock_firestore_service.get_photo.return_value = photo_data
        # Entry verification fails (returns None for other user's entry)
        mock_firestore_service.get_entry.return_value = None
        
        response = photo_client.get(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "unauthorised" in response.json()["error"]["message"].lower()
        
    def test_get_photo_storage_error(
        self,
        photo_client,
        mock_storage_service,
        api_headers,
    ):
        """Test storage service error returns 500."""
        mock_storage_service.get_photo_url.side_effect = Exception("Storage service error")
        
        response = photo_client.get(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 500
        assert "Failed to retrieve photo" in response.json()["error"]["message"]


class TestDeletePhoto:
    """Tests for DELETE /api/photos/{photo_id} endpoint."""
    
    def test_delete_photo_success(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test successful photo deletion."""
        photo_data = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
        }
        mock_firestore_service.get_photo.return_value = photo_data
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        mock_storage_service.delete_photo.return_value = None
        
        response = photo_client.delete(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 204
        assert response.content == b''
        mock_storage_service.delete_photo.assert_called_once_with("test_photo_123")
        
    def test_delete_photo_not_found(
        self,
        photo_client,
        mock_firestore_service,
        api_headers,
    ):
        """Test deleting non-existent photo returns 404."""
        mock_firestore_service.get_photo.return_value = None
        
        response = photo_client.delete(
            "/api/photos/nonexistent_photo",
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["error"]["message"].lower()
        
    def test_delete_photo_unauthorised_entry(
        self,
        photo_client,
        mock_firestore_service,
        api_headers,
    ):
        """Test deleting photo from entry belonging to another user returns 404."""
        photo_data = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
        }
        mock_firestore_service.get_photo.return_value = photo_data
        # Entry verification fails
        mock_firestore_service.get_entry.return_value = None
        
        response = photo_client.delete(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "unauthorised" in response.json()["error"]["message"].lower()
        
    def test_delete_photo_storage_not_found(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test deleting photo when storage deletion fails returns 404."""
        photo_data = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
        }
        mock_firestore_service.get_photo.return_value = photo_data
        mock_firestore_service.get_entry.return_value = None
        mock_storage_service.delete_photo.side_effect = ValueError("Photo not found in storage")
        mock_firestore_service.get_photo.return_value = photo_data
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        mock_storage_service.delete_photo.side_effect = ValueError("Photo not found in storage")
        
        response = photo_client.delete(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["error"]["message"].lower()
        
    def test_delete_photo_storage_error(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        sample_entry_for_photo,
        api_headers,
    ):
        """Test storage service error during deletion returns 500."""
        photo_data = {
            "id": "test_photo_123",
            "entry_id": "test_entry_123",
            "filename": "test_image.jpg",
        }
        mock_firestore_service.get_photo.return_value = photo_data
        mock_firestore_service.get_entry.return_value = sample_entry_for_photo
        mock_storage_service.delete_photo.side_effect = Exception("Storage service error")
        
        response = photo_client.delete(
            "/api/photos/test_photo_123",
            headers=api_headers,
        )
        
        assert response.status_code == 500
        assert "Failed to delete photo" in response.json()["error"]["message"]
