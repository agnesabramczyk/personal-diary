"""Main FastAPI application entry point for Personal Diary REST API.

This module initialises the FastAPI application with configuration,
middleware, and routes.
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any, AsyncGenerator

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.routes import entries_router, photos_router


# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "correlation_id": "%(correlation_id)s", "message": "%(message)s", "module": "%(module)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S%z"
)
logger = logging.getLogger(__name__)


# Initialise rate limiter with API key-based limiting
def get_api_key_for_rate_limit(request: Request) -> str:
    """Extract API key from request for rate limiting.

    Uses the X-API-Key header to key rate limits per API key rather than
    per IP address. This ensures each API key has its own rate limit bucket.

    Args:
        request: FastAPI request object.

    Returns:
        API key from X-API-Key header, or "anonymous" if not provided.
    """
    api_key = request.headers.get("X-API-Key", "anonymous")
    return api_key


limiter = Limiter(key_func=get_api_key_for_rate_limit)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle events.

    Initialises services on startup and cleans up on shutdown.
    """
    # Startup: Verify Firestore connectivity
    from app.services import FirestoreService

    try:
        firestore_service = FirestoreService(
            project_id=settings.gcp_project_id,
            credentials_path=settings.google_application_credentials,
        )
        # Test connection by accessing collections (doesn't retrieve data)
        list(firestore_service.client.collections())

        creds_info = "with service account key" if settings.google_application_credentials else "with Workload Identity"
        logger.info(f"Firestore connected to project: {settings.gcp_project_id} {creds_info}")
    except Exception as e:
        logger.warning(f"Failed to initialise Firestore: {e}")
        logger.warning("Application will continue but Firestore operations may fail")
    
    yield
    
    # Shutdown: Clean up resources
    # Future: Close database connections
    # Future: Close storage clients
    pass


# Create FastAPI application
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add rate limiting state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# Request logging and correlation ID middleware
@app.middleware("http")
async def add_correlation_id_and_logging(request: Request, call_next):
    """Add correlation ID to all requests and log request/response details.
    
    Generates a unique correlation ID for each request to enable request tracing
    across logs. Logs request start, completion, and timing information.
    """
    correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    
    # Log request start
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={"correlation_id": correlation_id}
    )
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        # Log request completion
        logger.info(
            f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {process_time:.3f}s",
            extra={"correlation_id": correlation_id}
        )
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url.path} - Error: {str(e)} - Duration: {process_time:.3f}s",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )
        raise


# Error handling middleware
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent error response format.
    
    Args:
        request: FastAPI request object.
        exc: HTTPException raised during request processing.
    
    Returns:
        JSONResponse with standardised error format.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "correlation_id": correlation_id
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with safe error messages.
    
    Logs the full exception details but returns a generic error message
    to the client to avoid exposing internal implementation details.
    
    Args:
        request: FastAPI request object.
        exc: Exception raised during request processing.
    
    Returns:
        JSONResponse with generic error message.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={"correlation_id": correlation_id},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "An internal server error occurred. Please try again later.",
                "correlation_id": correlation_id
            }
        }
    )


# Configure CORS middleware
# Use settings.cors_origins for flexible configuration
# Default: "*" for development, configure specific origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(entries_router)
app.include_router(photos_router)


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
            "entries": "/api/entries",
            "photos": "/api/photos"
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


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=not settings.is_production,
        log_level=settings.log_level.lower()
    )