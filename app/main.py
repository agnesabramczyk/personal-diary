"""Main FastAPI application entry point for Personal Diary REST API.

This module initialises the FastAPI application with configuration,
middleware, and routes.
"""
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings


# Initialise rate limiter
limiter = Limiter(key_func=get_remote_address)


# Create FastAPI application
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add rate limiting state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint providing API information.
    
    Returns:
        Dictionary containing API metadata and available endpoints.
    """
    return {
        "name": settings.app_title,
        "version": settings.app_version,
        "environment": settings.environment,
        "documentation": "/docs",
        "health_check": "/health",
        "endpoints": {
            "entries": "/api/v1/entries",
            "photos": "/api/v1/photos"
        }
    }


@app.get("/health", tags=["Health"])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint for monitoring and load balancers.
    
    Args:
        request: FastAPI request object (required for rate limiting).
    
    Returns:
        Dictionary containing health status and timestamp.
    """
    current_time = datetime.now(timezone.utc)
    
    return {
        "status": "healthy",
        "timestamp": current_time.isoformat(),
        "service": settings.app_title,
        "version": settings.app_version,
        "environment": settings.environment,
        "region": settings.gcp_region
    }


@app.on_event("startup")
async def startup_event() -> None:
    """Initialise services on application startup."""
    # Future: Initialise Firestore client
    # Future: Initialise Storage client
    # Future: Verify GCP connectivity
    pass


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on application shutdown."""
    # Future: Close database connections
    # Future: Close storage clients
    pass


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=not settings.is_production,
        log_level=settings.log_level.lower()
    )