"""Configuration management for the Personal Diary API.

Loads configuration from environment variables with validation.
"""
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # GCP Configuration
    gcp_project_id: str
    gcp_region: str = "australia-southeast1"
    storage_bucket: str
    
    # Authentication
    google_application_credentials: str
    
    # API Configuration
    api_keys: str  # Comma-separated list
    rate_limit_per_minute: int = 100
    
    # Storage Configuration
    signed_url_expiration: int = 3600  # seconds
    
    # Application Settings
    environment: str = "development"
    log_level: str = "INFO"
    
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
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
    
    @property
    def api_key_list(self) -> List[str]:
        """Parse comma-separated API keys into a list."""
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


# Global settings instance
settings = Settings()