"""Configuration management for the Personal Diary API.

Loads configuration from environment variables with validation.
"""
from typing import List, Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # GCP Configuration
    gcp_project_id: str
    gcp_region: str = "australia-southeast1"
    storage_bucket: str

    # Authentication (optional for Cloud Run with Workload Identity)
    google_application_credentials: Optional[str] = None
    
    # API Configuration
    api_keys: str  # Comma-separated list
    rate_limit_per_minute: int = 100
    
    # Storage Configuration
    signed_url_expiration: int = 3600  # seconds
    
    # Application Settings
    environment: str = "development"
    log_level: str = "INFO"

    # CORS Configuration
    # Comma-separated list of allowed origins (empty string = no CORS)
    # Use "*" for development, specific origins for production
    cors_origins: str = "*"

    # API Metadata
    app_title: str = "Personal Diary REST API"
    app_version: str = "1.0.0"
    app_description: str = """
    Personal diary REST API for storing daily entries with photos.
    
    Features:
    - Create, read, update, and delete diary entries
    - Upload and manage photos with EXIF preservation
    - Search and filter entries by date, tags, and content
    - API key authentication with rate limiting
    """
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False
    )
    
    @property
    def api_key_list(self) -> List[str]:
        """Parse comma-separated API keys into a list."""
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list.

        Returns:
            List of allowed origins, or ["*"] if wildcard, or [] if empty string.
        """
        if not self.cors_origins or self.cors_origins.strip() == "":
            return []
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


# Global settings instance
settings = Settings()  # type: ignore[call-arg]
