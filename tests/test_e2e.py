"""End-to-end tests covering complete workflows.

Tests full user scenarios from entry creation through photo management
to deletion, ensuring all components work together correctly.
"""
from datetime import datetime
from io import BytesIO

from app.models.entry import EntryResponse
from app.services.timezone_utils import AEST


class TestEntryLifecycle:
    """Test complete lifecycle of a diary entry."""
    
    def test_complete_entry_workflow(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test create -> retrieve -> update -> delete workflow."""
        # Step 1: Create entry
        create_response = EntryResponse(
            id="e2e_entry_1",
            user_id="test_user_123",
            timestamp=datetime(2026, 2, 1, 10, 0, 0, tzinfo=AEST),
            title="E2E Test Entry",
            body="Testing complete workflow.",
            tags=["e2e", "test"],
            mood="focused",
            location="Brisbane, Australia",
            weather="sunny",
            created_at=datetime(2026, 2, 1, 10, 0, 0, tzinfo=AEST),
            updated_at=datetime(2026, 2, 1, 10, 0, 0, tzinfo=AEST),
            photo_count=0,
        )
        mock_firestore_service.create_entry.return_value = create_response
        
        create_result = client.post(
            "/api/entries",
            json={
                "timestamp": "2026-02-01T10:00:00+10:00",
                "title": "E2E Test Entry",
                "body": "Testing complete workflow.",
                "tags": ["e2e", "test"],
                "mood": "focused",
                "location": "Brisbane, Australia",
                "weather": "sunny",
            },
            headers=api_headers,
        )
        assert create_result.status_code == 201
        entry_id = create_result.json()["id"]
        assert entry_id == "e2e_entry_1"
        
        # Step 2: Retrieve created entry
        mock_firestore_service.get_entry.return_value = create_response
        
        get_result = client.get(
            f"/api/entries/{entry_id}",
            headers=api_headers,
        )
        assert get_result.status_code == 200
        assert get_result.json()["title"] == "E2E Test Entry"
        
        # Step 3: Update entry
        updated_response = create_response.model_copy()
        updated_response.title = "Updated E2E Entry"
        updated_response.body = "Updated workflow test."
        mock_firestore_service.update_entry.return_value = updated_response
        
        update_result = client.put(
            f"/api/entries/{entry_id}",
            json={
                "title": "Updated E2E Entry",
                "body": "Updated workflow test.",
            },
            headers=api_headers,
        )
        assert update_result.status_code == 200
        assert update_result.json()["title"] == "Updated E2E Entry"
        
        # Step 4: Verify entry appears in list
        from app.models.pagination import PaginatedResponse
        list_response = PaginatedResponse(
            items=[updated_response],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = list_response
        
        list_result = client.get("/api/entries", headers=api_headers)
        assert list_result.status_code == 200
        assert list_result.json()["total"] == 1
        
        # Step 5: Delete entry
        mock_firestore_service.delete_entry.return_value = True
        
        delete_result = client.delete(
            f"/api/entries/{entry_id}",
            headers=api_headers,
        )
        assert delete_result.status_code == 204
        
        # Step 6: Verify entry is gone
        mock_firestore_service.get_entry.return_value = None
        
        verify_result = client.get(
            f"/api/entries/{entry_id}",
            headers=api_headers,
        )
        assert verify_result.status_code == 404


class TestPhotoWorkflow:
    """Test complete photo upload and management workflow."""
    
    def test_complete_photo_workflow(
        self,
        photo_client,
        mock_firestore_service,
        mock_storage_service,
        api_headers,
    ):
        """Test entry creation -> photo upload -> retrieve -> delete photo -> delete entry."""
        # Step 1: Create entry for photo
        entry_response = EntryResponse(
            id="photo_entry_1",
            user_id="test_user_123",
            timestamp=datetime(2026, 2, 1, 11, 0, 0, tzinfo=AEST),
            title="Entry with Photos",
            body="Testing photo workflow.",
            tags=["photos"],
            mood="happy",
            location="Sydney, Australia",
            weather="sunny",
            created_at=datetime(2026, 2, 1, 11, 0, 0, tzinfo=AEST),
            updated_at=datetime(2026, 2, 1, 11, 0, 0, tzinfo=AEST),
            photo_count=0,
        )
        mock_firestore_service.create_entry.return_value = entry_response
        
        create_result = photo_client.post(
            "/api/entries",
            json={
                "timestamp": "2026-02-01T11:00:00+10:00",
                "title": "Entry with Photos",
                "body": "Testing photo workflow.",
                "tags": ["photos"],
                "mood": "happy",
            },
            headers=api_headers,
        )
        assert create_result.status_code == 201
        entry_id = create_result.json()["id"]
        
        # Step 2: Upload photo to entry
        mock_firestore_service.get_entry.return_value = entry_response
        mock_storage_service.upload_photo.return_value = {
            "id": "photo_1",
            "entry_id": entry_id,
            "filename": "test_photo.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 512000,
            "storage_path": f"photos/{entry_id}/photo_1.jpg",
            "thumbnail_path": f"photos/{entry_id}/photo_1_thumb.jpg",
            "photo_url": f"https://storage.example.com/{entry_id}/photo_1.jpg",
            "thumbnail_url": f"https://storage.example.com/{entry_id}/photo_1_thumb.jpg",
            "exif_data": {"Make": "Apple", "Model": "iPhone 15"},
            "caption": "Sunset view",
            "created_at": datetime(2026, 2, 1, 11, 5, 0, tzinfo=AEST),
        }
        
        files = {"file": ("test_photo.jpg", BytesIO(b"fake image data"), "image/jpeg")}
        data = {"caption": "Sunset view"}
        
        upload_result = photo_client.post(
            f"/api/entries/{entry_id}/photos",
            files=files,
            data=data,
            headers=api_headers,
        )
        assert upload_result.status_code == 201
        photo_id = upload_result.json()["id"]
        assert photo_id == "photo_1"
        
        # Step 3: Retrieve photo
        mock_firestore_service.get_photo.return_value = {
            "id": photo_id,
            "entry_id": entry_id,
            "filename": "test_photo.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 512000,
            "storage_path": f"photos/{entry_id}/photo_1.jpg",
            "thumbnail_path": f"photos/{entry_id}/photo_1_thumb.jpg",
            "caption": "Sunset view",
            "exif_data": {"Make": "Apple", "Model": "iPhone 15"},
            "created_at": datetime(2026, 2, 1, 11, 5, 0, tzinfo=AEST),
        }
        mock_storage_service.get_photo_url.return_value = {
            "photo_url": f"https://storage.example.com/{entry_id}/photo_1.jpg",
            "thumbnail_url": f"https://storage.example.com/{entry_id}/photo_1_thumb.jpg",
        }
        
        get_photo_result = photo_client.get(
            f"/api/photos/{photo_id}",
            headers=api_headers,
        )
        assert get_photo_result.status_code == 200
        photo_data = get_photo_result.json()
        assert photo_data["caption"] == "Sunset view"
        assert "photo_url" in photo_data
        
        # Step 4: Upload second photo
        mock_storage_service.upload_photo.return_value = {
            "id": "photo_2",
            "entry_id": entry_id,
            "filename": "test_photo_2.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 612000,
            "storage_path": f"photos/{entry_id}/photo_2.jpg",
            "thumbnail_path": f"photos/{entry_id}/photo_2_thumb.jpg",
            "photo_url": f"https://storage.example.com/{entry_id}/photo_2.jpg",
            "thumbnail_url": f"https://storage.example.com/{entry_id}/photo_2_thumb.jpg",
            "exif_data": {},
            "caption": "Morning coffee",
            "created_at": datetime(2026, 2, 1, 11, 10, 0, tzinfo=AEST),
        }
        
        files2 = {"file": ("test_photo_2.jpg", BytesIO(b"another fake image"), "image/jpeg")}
        data2 = {"caption": "Morning coffee"}
        
        upload_result2 = photo_client.post(
            f"/api/entries/{entry_id}/photos",
            files=files2,
            data=data2,
            headers=api_headers,
        )
        assert upload_result2.status_code == 201
        
        # Step 5: Delete first photo
        mock_firestore_service.get_photo.return_value = {
            "id": photo_id,
            "entry_id": entry_id,
            "filename": "test_photo.jpg",
        }
        mock_storage_service.delete_photo.return_value = None
        
        delete_photo_result = photo_client.delete(
            f"/api/photos/{photo_id}",
            headers=api_headers,
        )
        assert delete_photo_result.status_code == 204
        
        # Step 6: Verify first photo is deleted
        mock_firestore_service.get_photo.return_value = None
        
        verify_photo_result = photo_client.get(
            f"/api/photos/{photo_id}",
            headers=api_headers,
        )
        assert verify_photo_result.status_code == 404
        
        # Step 7: Delete entry (which should cascade to remaining photo)
        mock_firestore_service.delete_entry.return_value = True
        
        delete_entry_result = photo_client.delete(
            f"/api/entries/{entry_id}",
            headers=api_headers,
        )
        assert delete_entry_result.status_code == 204


class TestSearchAndFilterWorkflow:
    """Test search and filtering workflows."""
    
    def test_search_workflow(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test creating entries then searching and filtering them."""
        from app.models.pagination import PaginatedResponse
        
        # Step 1: Create multiple entries with different tags
        entries = []
        for i in range(3):
            entry = EntryResponse(
                id=f"search_entry_{i}",
                user_id="test_user_123",
                timestamp=datetime(2026, 2, i+1, 12, 0, 0, tzinfo=AEST),
                title=f"Entry {i+1}",
                body=f"Content for entry {i+1} about coding.",
                tags=["coding"] if i < 2 else ["personal"],
                mood="productive" if i < 2 else "relaxed",
                location="Brisbane, Australia",
                weather="sunny",
                created_at=datetime(2026, 2, i+1, 12, 0, 0, tzinfo=AEST),
                updated_at=datetime(2026, 2, i+1, 12, 0, 0, tzinfo=AEST),
                photo_count=0,
            )
            entries.append(entry)
            
            mock_firestore_service.create_entry.return_value = entry
            create_result = client.post(
                "/api/entries",
                json={
                    "timestamp": f"2026-02-0{i+1}T12:00:00+10:00",
                    "title": f"Entry {i+1}",
                    "body": f"Content for entry {i+1} about coding.",
                    "tags": ["coding"] if i < 2 else ["personal"],
                    "mood": "productive" if i < 2 else "relaxed",
                },
                headers=api_headers,
            )
            assert create_result.status_code == 201
        
        # Step 2: List all entries
        list_response = PaginatedResponse(
            items=entries,
            total=3,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = list_response
        
        list_result = client.get("/api/entries", headers=api_headers)
        assert list_result.status_code == 200
        assert list_result.json()["total"] == 3
        
        # Step 3: Filter by tag
        coding_entries = [e for e in entries if "coding" in e.tags]
        filtered_response = PaginatedResponse(
            items=coding_entries,
            total=2,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = filtered_response
        
        filter_result = client.get(
            "/api/entries?tags=coding",
            headers=api_headers,
        )
        assert filter_result.status_code == 200
        assert filter_result.json()["total"] == 2
        
        # Step 4: Search by text
        search_response = PaginatedResponse(
            items=entries,
            total=3,
            page=1,
            page_size=20,
            total_pages=1,
            has_next=False,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.search_entries.return_value = search_response
        
        search_result = client.get(
            "/api/entries/search?q=coding",
            headers=api_headers,
        )
        assert search_result.status_code == 200
        assert search_result.json()["total"] == 3
        
        # Step 5: Get entries by specific date
        date_entries = [entries[0]]
        mock_firestore_service.get_entries_by_date.return_value = date_entries
        
        date_result = client.get(
            "/api/entries/date/2026-02-01",
            headers=api_headers,
        )
        assert date_result.status_code == 200
        assert len(date_result.json()) == 1
        
        # Step 6: Test pagination
        page_response = PaginatedResponse(
            items=entries[:2],
            total=3,
            page=1,
            page_size=2,
            total_pages=2,
            has_next=True,
            has_previous=False,
            next_cursor=None,
        )
        mock_firestore_service.list_entries.return_value = page_response
        
        page_result = client.get(
            "/api/entries?page=1&page_size=2",
            headers=api_headers,
        )
        assert page_result.status_code == 200
        data = page_result.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["has_next"] is True


class TestErrorHandlingWorkflow:
    """Test error handling in complete workflows."""
    
    def test_unauthorised_access_workflow(
        self,
        unauthorized_client,
        mock_firestore_service,
    ):
        """Test that unauthorised requests fail at all endpoints."""
        # Attempt to create entry
        create_result = unauthorized_client.post(
            "/api/entries",
            json={
                "timestamp": "2026-02-01T12:00:00+10:00",
                "title": "Unauthorised Entry",
                "body": "This should fail.",
            },
        )
        assert create_result.status_code == 401
        
        # Attempt to list entries
        list_result = unauthorized_client.get("/api/entries")
        assert list_result.status_code == 401
        
        # Attempt to get entry
        get_result = unauthorized_client.get("/api/entries/some_id")
        assert get_result.status_code == 401
        
        # Attempt to update entry
        update_result = unauthorized_client.put(
            "/api/entries/some_id",
            json={"title": "Updated"},
        )
        assert update_result.status_code == 401
        
        # Attempt to delete entry
        delete_result = unauthorized_client.delete("/api/entries/some_id")
        assert delete_result.status_code == 401
    
    def test_not_found_workflow(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test handling of non-existent resources."""
        # Get non-existent entry
        mock_firestore_service.get_entry.return_value = None
        
        get_result = client.get(
            "/api/entries/nonexistent_id",
            headers=api_headers,
        )
        assert get_result.status_code == 404
        
        # Update non-existent entry
        mock_firestore_service.update_entry.return_value = None
        
        update_result = client.put(
            "/api/entries/nonexistent_id",
            json={"title": "Updated"},
            headers=api_headers,
        )
        assert update_result.status_code == 404
        
        # Delete non-existent entry
        mock_firestore_service.delete_entry.return_value = False
        
        delete_result = client.delete(
            "/api/entries/nonexistent_id",
            headers=api_headers,
        )
        assert delete_result.status_code == 404
    
    def test_validation_error_workflow(
        self,
        client,
        mock_firestore_service,
        api_headers,
    ):
        """Test validation errors throughout workflow."""
        # Create entry with missing required fields
        create_result = client.post(
            "/api/entries",
            json={
                "title": "No timestamp or body",
            },
            headers=api_headers,
        )
        assert create_result.status_code == 422
        
        # Search with missing query parameter
        search_result = client.get(
            "/api/entries/search",
            headers=api_headers,
        )
        assert search_result.status_code == 422
        
        # Invalid date format - configure mock to raise ValueError
        mock_firestore_service.get_entries_by_date.side_effect = ValueError(
            "Invalid date format: invalid-date"
        )
        
        date_result = client.get(
            "/api/entries/date/invalid-date",
            headers=api_headers,
        )
        # This should return 400 for invalid date format
        assert date_result.status_code == 400
        assert "error" in date_result.json()
        assert "Invalid date format" in date_result.json()["error"]["message"]
