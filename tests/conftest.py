"""Pytest configuration and fixtures for testing.

Provides mock Firestore client and test data fixtures.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from app.services.firestore_service import FirestoreService
from app.services.timezone_utils import AEST


@pytest.fixture
def mock_firestore_client():
    """Mock Firestore client for testing without GCP credentials."""
    client = Mock()
    client.collection = Mock()
    return client


@pytest.fixture
def mock_firestore_service():
    """Mock FirestoreService for integration tests (API endpoints)."""
    return MagicMock(spec=FirestoreService)


@pytest.fixture
def mock_firestore_service_unit(mock_firestore_client):
    """Mock FirestoreService for unit tests with actual service instance."""
    with patch('app.services.firestore_service.firestore.Client') as mock_client_class:
        mock_client_class.return_value = mock_firestore_client
        # Pass None for credentials_path to use default credentials (mocked)
        service = FirestoreService(
            project_id="test-project",
            credentials_path=None
        )
        service.client = mock_firestore_client
        return service


@pytest.fixture
def sample_entry_data():
    """Sample entry data for testing."""
    return {
        "user_id": "test_user_123",
        "timestamp": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        "title": "Test Entry",
        "body": "This is a test entry body with some content.",
        "tags": ["test", "sample"],
        "mood": "happy",
        "location": "Sydney, Australia",
        "weather": "sunny, 25°C",
        "created_at": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        "updated_at": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
    }


@pytest.fixture
def sample_firestore_doc(sample_entry_data):
    """Mock Firestore document for testing."""
    doc = Mock()
    doc.id = "test_entry_123"
    doc.exists = True
    doc.to_dict = Mock(return_value=sample_entry_data)
    return doc


@pytest.fixture
def sample_entry_create_data():
    """Sample EntryCreate model data."""
    return {
        "timestamp": datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST),
        "title": "Test Entry",
        "body": "This is a test entry body with some content.",
        "tags": ["test", "sample"],
        "mood": "happy",
        "location": "Sydney, Australia",
        "weather": "sunny, 25°C",
    }


@pytest.fixture
def sample_entry_update_data():
    """Sample EntryUpdate model data."""
    return {
        "title": "Updated Test Entry",
        "body": "This is an updated test entry body.",
        "tags": ["updated", "test"],
        "mood": "excited",
    }


@pytest.fixture
def multiple_entries_data():
    """Multiple entry documents for testing list operations."""
    base_time = datetime(2026, 1, 30, 9, 0, 0, tzinfo=AEST)
    entries = []
    
    for i in range(5):
        entry = {
            "user_id": "test_user_123",
            "timestamp": datetime(2026, 1, 30 - i, 9, 0, 0, tzinfo=AEST),
            "title": f"Test Entry {i + 1}",
            "body": f"This is test entry number {i + 1}.",
            "tags": ["test"] + ([f"tag{i}"] if i > 0 else []),
            "mood": "happy" if i % 2 == 0 else "neutral",
            "location": "Sydney, Australia",
            "weather": "sunny",
            "created_at": base_time,
            "updated_at": base_time,
        }
        
        doc = Mock()
        doc.id = f"entry_{i + 1}"
        doc.exists = True
        doc.to_dict = Mock(return_value=entry)
        
        entries.append(doc)
    
    return entries


@pytest.fixture
def mock_collection_ref():
    """Mock Firestore collection reference."""
    collection = Mock()
    collection.document = Mock()
    collection.where = Mock(return_value=collection)
    collection.order_by = Mock(return_value=collection)
    collection.stream = Mock(return_value=[])
    return collection


@pytest.fixture
def mock_document_ref():
    """Mock Firestore document reference."""
    doc_ref = Mock()
    doc_ref.id = "test_entry_123"
    doc_ref.set = Mock()
    doc_ref.update = Mock()
    doc_ref.delete = Mock()
    doc_ref.get = Mock()
    return doc_ref


@pytest.fixture
def api_key():
    """Test API key."""
    return "test_api_key_12345"


@pytest.fixture
def api_headers(api_key):
    """Headers for API authentication."""
    return {"X-API-Key": api_key}


@pytest.fixture
def test_user_id():
    """Test user identifier."""
    return "test_user_123"


@pytest.fixture
def client(test_user_id, mock_firestore_service):
    """Test client with authentication and service dependencies overridden."""
    import sys
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    
    # Completely mock the slowapi module BEFORE any imports
    mock_slowapi = MagicMock()
    mock_limiter = MagicMock()
    
    # Create a passthrough decorator for the limit method
    def mock_limit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    mock_limiter.limit = mock_limit
    mock_slowapi.Limiter = MagicMock(return_value=mock_limiter)
    
    # Create a proper exception class for RateLimitExceeded
    class MockRateLimitExceeded(Exception):
        pass
    
    mock_slowapi.RateLimitExceeded = MockRateLimitExceeded
    
    # Create mock for slowapi.errors with the exception class
    mock_slowapi_errors = MagicMock()
    mock_slowapi_errors.RateLimitExceeded = MockRateLimitExceeded
    
    # Inject mock into sys.modules before importing app
    sys.modules['slowapi'] = mock_slowapi
    sys.modules['slowapi.util'] = MagicMock()
    sys.modules['slowapi.extension'] = MagicMock()
    sys.modules['slowapi.errors'] = mock_slowapi_errors
    
    try:
        # Now import app with slowapi completely mocked
        from app.main import app
        from app.routes.entries import get_current_user, get_firestore_service
        
        # Override the authentication dependency to bypass API key validation
        async def override_get_current_user() -> str:
            return test_user_id
        
        # Override the Firestore service dependency to use mock
        def override_get_firestore_service():
            return mock_firestore_service
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_firestore_service] = override_get_firestore_service
        
        client = TestClient(app)
        
        yield client
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    finally:
        # Remove mock modules
        if 'slowapi' in sys.modules:
            del sys.modules['slowapi']
        if 'slowapi.util' in sys.modules:
            del sys.modules['slowapi.util']
        if 'slowapi.extension' in sys.modules:
            del sys.modules['slowapi.extension']
        if 'slowapi.errors' in sys.modules:
            del sys.modules['slowapi.errors']


@pytest.fixture
def unauthorized_client(mock_firestore_service):
    """Test client WITHOUT authentication override for testing unauthorized access.
    
    Provides an invalid API key to trigger 401 response from authentication.
    """
    import sys
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    
    # Completely mock the slowapi module BEFORE any imports
    mock_slowapi = MagicMock()
    mock_limiter = MagicMock()
    
    # Create a passthrough decorator for the limit method
    def mock_limit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    mock_limiter.limit = mock_limit
    mock_slowapi.Limiter = MagicMock(return_value=mock_limiter)
    
    # Create a proper exception class for RateLimitExceeded
    class MockRateLimitExceeded(Exception):
        pass
    
    mock_slowapi.RateLimitExceeded = MockRateLimitExceeded
    
    # Create mock for slowapi.errors with the exception class
    mock_slowapi_errors = MagicMock()
    mock_slowapi_errors.RateLimitExceeded = MockRateLimitExceeded
    
    # Inject mock into sys.modules before importing app
    sys.modules['slowapi'] = mock_slowapi
    sys.modules['slowapi.util'] = MagicMock()
    sys.modules['slowapi.extension'] = MagicMock()
    sys.modules['slowapi.errors'] = mock_slowapi_errors
    
    try:
        # Now import app with slowapi completely mocked
        from app.main import app
        from app.routes.entries import get_firestore_service
        
        # Only override the Firestore service dependency, NOT authentication
        def override_get_firestore_service():
            return mock_firestore_service
        
        app.dependency_overrides[get_firestore_service] = override_get_firestore_service
        
        client = TestClient(app)
        
        # Store invalid headers on the client for easy access in tests
        client.headers = {"X-API-Key": "invalid_api_key_12345"}
        
        yield client
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    finally:
        # Remove mock modules
        if 'slowapi' in sys.modules:
            del sys.modules['slowapi']
        if 'slowapi.util' in sys.modules:
            del sys.modules['slowapi.util']
        if 'slowapi.extension' in sys.modules:
            del sys.modules['slowapi.extension']
        if 'slowapi.errors' in sys.modules:
            del sys.modules['slowapi.errors']


@pytest.fixture
def mock_storage_service():
    """Mock StorageService for integration tests."""
    mock = MagicMock()
    # All StorageService methods are async
    mock.upload_photo = AsyncMock()
    mock.get_photo_url = AsyncMock()
    mock.delete_photo = AsyncMock()
    return mock


@pytest.fixture
def photo_client(test_user_id, mock_firestore_service, mock_storage_service):
    """Test client with photo dependencies overridden."""
    import sys
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    
    # Mock slowapi completely
    mock_slowapi = MagicMock()
    mock_limiter = MagicMock()
    
    def mock_limit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    mock_limiter.limit = mock_limit
    mock_slowapi.Limiter = MagicMock(return_value=mock_limiter)
    mock_slowapi.RateLimitExceeded = Exception
    
    # Create mock for slowapi.errors submodule
    mock_slowapi_errors = MagicMock()
    mock_slowapi_errors.RateLimitExceeded = Exception
    
    sys.modules['slowapi'] = mock_slowapi
    sys.modules['slowapi.util'] = MagicMock()
    sys.modules['slowapi.extension'] = MagicMock()
    sys.modules['slowapi.errors'] = mock_slowapi_errors
    
    try:
        from app.main import app
        from app.routes.entries import get_current_user, get_firestore_service
        from app.routes.photos import get_storage_service
        
        # Override dependencies
        async def override_get_current_user() -> str:
            return test_user_id
        
        def override_get_firestore_service():
            return mock_firestore_service
        
        def override_get_storage_service():
            return mock_storage_service
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_firestore_service] = override_get_firestore_service
        app.dependency_overrides[get_storage_service] = override_get_storage_service
        
        client = TestClient(app)
        
        yield client
        
        app.dependency_overrides.clear()
    finally:
        if 'slowapi' in sys.modules:
            del sys.modules['slowapi']
        if 'slowapi.util' in sys.modules:
            del sys.modules['slowapi.util']
        if 'slowapi.extension' in sys.modules:
            del sys.modules['slowapi.extension']
        if 'slowapi.errors' in sys.modules:
            del sys.modules['slowapi.errors']
