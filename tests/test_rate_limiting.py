"""Tests for rate limiting functionality.

Verifies that rate limits are keyed by API key, not by IP address.
"""
from unittest.mock import Mock
from fastapi import Request


class TestRateLimitKeyFunction:
    """Tests for the rate limiting key function."""

    def test_get_api_key_for_rate_limit_with_valid_key(self):
        """Test that the key function extracts API key from X-API-Key header."""
        from app.main import get_api_key_for_rate_limit

        # Create mock request with X-API-Key header
        request = Mock(spec=Request)
        request.headers = {"X-API-Key": "test_api_key_123"}

        # Verify the function returns the API key
        result = get_api_key_for_rate_limit(request)
        assert result == "test_api_key_123"

    def test_get_api_key_for_rate_limit_without_key(self):
        """Test that the key function returns 'anonymous' when no API key provided."""
        from app.main import get_api_key_for_rate_limit

        # Create mock request without X-API-Key header
        request = Mock(spec=Request)
        request.headers = {}

        # Verify the function returns 'anonymous'
        result = get_api_key_for_rate_limit(request)
        assert result == "anonymous"

    def test_get_api_key_for_rate_limit_case_sensitive(self):
        """Test that API keys are case-sensitive for rate limiting."""
        from app.main import get_api_key_for_rate_limit

        # Test lowercase key
        request1 = Mock(spec=Request)
        request1.headers = {"X-API-Key": "test_key_abc"}
        result1 = get_api_key_for_rate_limit(request1)

        # Test uppercase key
        request2 = Mock(spec=Request)
        request2.headers = {"X-API-Key": "TEST_KEY_ABC"}
        result2 = get_api_key_for_rate_limit(request2)

        # Verify they're treated as different keys
        assert result1 == "test_key_abc"
        assert result2 == "TEST_KEY_ABC"
        assert result1 != result2

    def test_get_api_key_for_rate_limit_different_keys(self):
        """Test that different API keys return different rate limit keys."""
        from app.main import get_api_key_for_rate_limit

        request1 = Mock(spec=Request)
        request1.headers = {"X-API-Key": "user_1_key"}
        result1 = get_api_key_for_rate_limit(request1)

        request2 = Mock(spec=Request)
        request2.headers = {"X-API-Key": "user_2_key"}
        result2 = get_api_key_for_rate_limit(request2)

        # Verify different keys have separate rate limit buckets
        assert result1 == "user_1_key"
        assert result2 == "user_2_key"
        assert result1 != result2


class TestRateLimiterConfiguration:
    """Tests for rate limiter configuration.

    Note: These tests verify the actual implementation but may encounter
    mocked slowapi if other tests have run first. The key function tests
    above provide the primary verification.
    """

    def test_limiter_configuration_in_source_code(self):
        """Test that app/main.py configures limiter with API key function.

        This test reads the source code directly to verify the configuration,
        avoiding issues with mocked slowapi in the test environment.
        """
        import os
        main_file_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "app",
            "main.py"
        )

        with open(main_file_path, "r") as f:
            source_code = f.read()

        # Verify the limiter is initialised with get_api_key_for_rate_limit
        assert "limiter = Limiter(key_func=get_api_key_for_rate_limit)" in source_code

        # Verify we're NOT using get_remote_address
        assert "Limiter(key_func=get_remote_address)" not in source_code

    def test_key_function_defined_before_limiter(self):
        """Test that the API key function is defined before the limiter."""
        import os
        main_file_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "app",
            "main.py"
        )

        with open(main_file_path, "r") as f:
            lines = f.readlines()

        # Find line numbers
        key_func_line = None
        limiter_line = None

        for i, line in enumerate(lines):
            if "def get_api_key_for_rate_limit" in line:
                key_func_line = i
            if "limiter = Limiter(key_func=" in line:
                limiter_line = i

        # Verify both exist and key_func is defined before limiter
        assert key_func_line is not None, "get_api_key_for_rate_limit not found"
        assert limiter_line is not None, "limiter initialisation not found"
        assert key_func_line < limiter_line, "Key function must be defined before limiter"


class TestRateLimitDocumentation:
    """Tests to verify rate limiting behaviour is properly documented."""

    def test_rate_limit_function_has_docstring(self):
        """Test that the rate limit key function has proper documentation."""
        from app.main import get_api_key_for_rate_limit

        assert get_api_key_for_rate_limit.__doc__ is not None
        assert "API key" in get_api_key_for_rate_limit.__doc__
        assert "per api key" in get_api_key_for_rate_limit.__doc__.lower()

    def test_rate_limit_function_documents_anonymous_behaviour(self):
        """Test that the function documents the 'anonymous' fallback."""
        from app.main import get_api_key_for_rate_limit

        assert "anonymous" in get_api_key_for_rate_limit.__doc__.lower()
