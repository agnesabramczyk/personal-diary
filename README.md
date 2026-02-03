# Personal Diary REST API

A personal diary REST API built with FastAPI that enables creating daily entries with photos, retrieving entries by date, and searching across entries. Designed for technical users to interact via CLI tools (curl, httpie) without requiring a frontend interface.

## Features

- **Entry Management**: Create, read, update, and delete diary entries with rich metadata (title, body, tags, mood, location, weather)
- **Photo Storage**: Upload unlimited photos per entry with EXIF preservation and automatic thumbnail generation
- **Search & Filtering**: Text search, tag filtering, and date range queries with pagination
- **Authentication**: API key-based authentication for secure access
- **Rate Limiting**: Configurable rate limiting to prevent API abuse
- **Cloud Native**: Serverless architecture using Google Cloud Platform (Cloud Run, Firestore, Cloud Storage)
- **Cost Effective**: Optimised for personal use (~$0.01/month)

## Architecture

- **Framework**: FastAPI 0.128.0 with Pydantic 2.12.5 for data validation
- **Database**: Cloud Firestore (NoSQL, serverless)
- **Storage**: Cloud Storage with signed URLs for photo access
- **Deployment**: Docker containers on Cloud Run
- **Infrastructure**: Pulumi (Infrastructure as Code)
- **Timezone**: AEST (Australian Eastern Standard Time)

## Prerequisites

### Required Tools

1. **Python 3.11+**
   ```bash
   python --version
   ```

2. **uv** (Fast Python package manager)
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Or with Homebrew
   brew install uv

   # Verify installation
   uv --version
   ```

3. **Docker**
   ```bash
   docker --version
   ```

4. **Google Cloud CLI**
   ```bash
   gcloud --version
   # If not installed: https://cloud.google.com/sdk/docs/install
   ```

5. **Pulumi CLI**
   ```bash
   pulumi version
   # If not installed on macOS: brew install pulumi
   ```

### GCP Setup

1. **Create GCP Project**
   ```bash
   export PROJECT_ID="personal-diary-$(openssl rand -hex 4)"
   gcloud projects create $PROJECT_ID --name="Personal Diary"
   gcloud config set project $PROJECT_ID
   ```

2. **Enable Required APIs**
   ```bash
   gcloud services enable \
     firestore.googleapis.com \
     storage-api.googleapis.com \
     artifactregistry.googleapis.com \
     secretmanager.googleapis.com \
     run.googleapis.com \
     cloudbuild.googleapis.com
   ```

3. **Initialise Firestore**
   ```bash
   gcloud firestore databases create --region=australia-southeast1
   ```

4. **Authenticate**
   ```bash
   gcloud auth application-default login
   ```

## Infrastructure Deployment

Deploy GCP infrastructure using Pulumi:

```bash
cd infrastructure

# Install Pulumi dependencies
pip install -r requirements.txt

# Configure Pulumi stack
pulumi stack init dev

# Set GCP project
pulumi config set gcp:project $PROJECT_ID
pulumi config set gcp:region australia-southeast1

# Preview changes
pulumi preview

# Deploy infrastructure
pulumi up

# View outputs (bucket name, service account key)
pulumi stack output
```

The Pulumi program creates:
- Cloud Firestore database (Firestore mode)
- Cloud Storage bucket (private with lifecycle rules)
- Artifact Registry repository for Docker images
- Secret Manager for API keys
- Cloud Run service
- Service account with minimal permissions
- IAM bindings and service account key (for local development)

### Infrastructure Management

```bash
# View current stack state
pulumi stack

# Update infrastructure
pulumi up

# Destroy all resources
pulumi destroy

# Export stack outputs to .env
pulumi stack output bucketName > .env
```

## Local Development Setup

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd personal-diary
   ```

2. **Create Virtual Environment and Install Dependencies**
   ```bash
   # Create virtual environment with uv (faster than venv)
   uv venv

   # Activate virtual environment
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

   # Install dependencies (much faster than pip)
   uv pip install -r requirements.txt

   # Or install with dev dependencies
   uv pip install -e ".[dev]"
   ```

   **Alternative (using pip):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure Environment**

   Copy `.env.example` to `.env` and update values:
   ```bash
   cp .env.example .env
   ```

   Required environment variables:
   ```bash
   # GCP Configuration
   GCP_PROJECT_ID=your-gcp-project-id
   GCP_REGION=australia-southeast1
   STORAGE_BUCKET=your-storage-bucket-name

   # API Keys (generate secure keys)
   # Note: For local development, use environment variables
   # For production (Cloud Run), API keys are stored in Secret Manager
   API_KEYS=your-api-key-here,another-api-key-here

   # Rate Limiting
   RATE_LIMIT_PER_MINUTE=100

   # Signed URL Expiration (seconds)
   SIGNED_URL_EXPIRATION=3600

   # Environment
   ENVIRONMENT=development
   LOG_LEVEL=INFO
   ```

   Generate secure API keys:
   ```bash
   openssl rand -hex 32
   ```

   **Note**: For local development, use Application Default Credentials instead of service account keys:
   ```bash
   gcloud auth application-default login
   ```
   This is more secure than using service account key files.

5. **Run Development Server**
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
   ```

6. **Access API Documentation**
   - Swagger UI: http://localhost:8080/docs
   - ReDoc: http://localhost:8080/redoc
   - OpenAPI JSON: http://localhost:8080/openapi.json

## Docker Build & Run

### Build Docker Image

```bash
docker build -t personal-diary:latest .
```

### Run Container Locally

Using Application Default Credentials (recommended):
```bash
docker run -d \
  --name personal-diary \
  -p 8080:8080 \
  --env-file .env \
  -v ~/.config/gcloud/application_default_credentials.json:/tmp/adc.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json \
  personal-diary:latest
```

Or use docker-compose (simpler):
```bash
docker-compose up
```

### View Logs

```bash
docker logs -f personal-diary
```

### Stop Container

```bash
docker stop personal-diary
docker rm personal-diary
```

## API Documentation

### Authentication

All API endpoints (except `/health` and `/docs`) require authentication using the `X-API-Key` header:

```bash
export API_KEY="your-api-key-here"
```

### Multi-User Support

The API supports multiple users through API key-based isolation:

- Each API key represents a unique user
- All diary entries and photos are isolated by `user_id` (derived from the API key)
- Users can only access their own entries and photos
- Firestore composite indexes include `user_id` for efficient filtering
- Each API request is automatically scoped to the authenticated user

This design allows:
- Multiple people to use the same deployment
- Complete data isolation between users
- Simple authentication without user account management
- Easy migration to proper user authentication later (API keys can be mapped to actual user IDs)

### Base URL

- Local: `http://localhost:8080`
- Production: `https://your-service-url.run.app`

### Endpoints

#### Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-02T04:02:26.123456+00:00",
  "service": "Personal Diary REST API",
  "version": "1.0.0",
  "environment": "development",
  "region": "australia-southeast1"
}
```

#### Create Entry

```bash
curl -X POST http://localhost:8080/api/entries \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Morning Reflection",
    "body": "Beautiful sunrise today. Feeling energised and ready for the day.",
    "tags": ["morning", "reflection"],
    "mood": "happy",
    "location": "Brisbane, QLD",
    "weather": "Sunny, 24°C"
  }'
```

Response:
```json
{
  "id": "abc123",
  "timestamp": "2026-02-02T14:02:26+10:00",
  "title": "Morning Reflection",
  "body": "Beautiful sunrise today. Feeling energised and ready for the day.",
  "tags": ["morning", "reflection"],
  "mood": "happy",
  "location": "Brisbane, QLD",
  "weather": "Sunny, 24°C",
  "created_at": "2026-02-02T14:02:26+10:00",
  "updated_at": "2026-02-02T14:02:26+10:00",
  "photos": []
}
```

#### Get Entry by ID

```bash
curl http://localhost:8080/api/entries/abc123 \
  -H "X-API-Key: $API_KEY"
```

#### Update Entry

```bash
curl -X PUT http://localhost:8080/api/entries/abc123 \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Morning Reflection (Updated)",
    "body": "Beautiful sunrise today. Added some thoughts about the day ahead.",
    "tags": ["morning", "reflection", "planning"]
  }'
```

#### Delete Entry

```bash
curl -X DELETE http://localhost:8080/api/entries/abc123 \
  -H "X-API-Key: $API_KEY"
```

#### List Entries

```bash
# Get all entries (paginated)
curl "http://localhost:8080/api/entries?limit=20&offset=0" \
  -H "X-API-Key: $API_KEY"

# Filter by tags
curl "http://localhost:8080/api/entries?tags=morning&tags=reflection" \
  -H "X-API-Key: $API_KEY"

# Search by text
curl "http://localhost:8080/api/entries?search=sunrise" \
  -H "X-API-Key: $API_KEY"

# Date range
curl "http://localhost:8080/api/entries?start_date=2026-01-01&end_date=2026-02-01" \
  -H "X-API-Key: $API_KEY"
```

#### Get Entries by Date

```bash
curl http://localhost:8080/api/entries/date/2026-02-02 \
  -H "X-API-Key: $API_KEY"
```

#### Upload Photo

```bash
curl -X POST http://localhost:8080/api/entries/abc123/photos \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/photo.jpg"
```

Response:
```json
{
  "id": "photo123",
  "entry_id": "abc123",
  "filename": "photo.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 2048000,
  "storage_path": "photos/abc123/photo123.jpg",
  "thumbnail_path": "photos/abc123/photo123_thumb.jpg",
  "original_url": "https://storage.googleapis.com/...",
  "thumbnail_url": "https://storage.googleapis.com/...",
  "exif_data": {
    "Make": "Apple",
    "Model": "iPhone 13 Pro",
    "DateTime": "2026:02:02 14:02:26"
  },
  "created_at": "2026-02-02T14:02:26+10:00"
}
```

#### Get Photo Details

```bash
curl http://localhost:8080/api/photos/photo123 \
  -H "X-API-Key: $API_KEY"
```

#### Delete Photo

```bash
curl -X DELETE http://localhost:8080/api/photos/photo123 \
  -H "X-API-Key: $API_KEY"
```

### Error Responses

- `400 Bad Request`: Invalid input data
- `401 Unauthorised`: Missing or invalid API key
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html --cov-report=term
```

View coverage report:
```bash
open htmlcov/index.html
```

### Run Specific Tests

```bash
# Unit tests only
pytest tests/test_firestore_service.py

# Integration tests only
pytest tests/test_entries_api.py

# Specific test
pytest tests/test_entries_api.py::test_create_entry
```

### Linting

```bash
ruff check .
ruff format .
```

## Cloud Run Deployment

The Cloud Run service is automatically provisioned via Pulumi. Follow these steps to deploy your application:

### Build and Push Container

```bash
# Navigate to infrastructure directory and get outputs
cd infrastructure
export AR_URL=$(pulumi stack output artifact_registry_url)
export REGION=$(pulumi stack output region)
cd ..

# Configure Docker for Artifact Registry
gcloud auth configure-docker $REGION-docker.pkg.dev

# Build and tag image
docker build -t $AR_URL/personal-diary:latest .

# Push to Artifact Registry
docker push $AR_URL/personal-diary:latest
```

### Update API Keys in Secret Manager

```bash
# Generate secure API keys (example)
export API_KEY_1=$(openssl rand -hex 32)
export API_KEY_2=$(openssl rand -hex 32)

# Get secret ID from Pulumi
cd infrastructure
export SECRET_ID=$(pulumi stack output secret_id)

# Update the secret with actual API keys
echo -n "$API_KEY_1,$API_KEY_2" | \
  gcloud secrets versions add $SECRET_ID --data-file=-
```

### Deploy to Cloud Run

```bash
# Cloud Run service is already created by Pulumi
# Deploy the new image by running:
pulumi up

# This will update the Cloud Run service with the latest configuration
```

### View Deployment

```bash
# Get service URL
pulumi stack output cloud_run_service_url

# Or view in GCP Console
gcloud run services describe diary-api \
  --region australia-southeast1 \
  --format 'value(status.url)'

# View logs
gcloud run services logs read diary-api --region australia-southeast1 --limit=50
```

### Continuous Deployment

For subsequent deployments, simply:

```bash
# Build and push new image
docker build -t $AR_URL/personal-diary:latest .
docker push $AR_URL/personal-diary:latest

# Update Cloud Run (this triggers automatic deployment)
cd infrastructure
pulumi up
```

## Project Structure

```
personal-diary/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── entry.py         # Entry Pydantic models
│   │   ├── photo.py         # Photo Pydantic models
│   │   └── pagination.py    # Pagination models
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── entries.py       # Entry endpoints
│   │   └── photos.py        # Photo endpoints
│   └── services/
│       ├── __init__.py
│       ├── firestore_service.py  # Firestore operations
│       ├── storage_service.py    # Cloud Storage operations
│       └── timezone_utils.py     # AEST timezone handling
├── infrastructure/
│   ├── __main__.py          # Pulumi infrastructure definition
│   ├── firestore.indexes.json  # Firestore composite indexes
│   ├── requirements.txt
│   ├── README.md            # Infrastructure documentation
│   ├── Pulumi.yaml
│   ├── Pulumi.dev.yaml
│   └── .gitignore
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   ├── test_entries_api.py
│   ├── test_photos_api.py
│   ├── test_firestore_service.py
│   ├── test_storage_service.py
│   ├── test_e2e.py          # End-to-end tests
│   └── test_rate_limiting.py
├── docs/
│   └── DEVELOPMENT_PLAN.md
├── .claude/
│   ├── CLAUDE.md            # Project memory for Claude Code
│   └── settings.json
├── .env.example
├── .gitignore
├── .mcp.json                # MCP server configuration
├── Dockerfile
├── requirements.txt
└── README.md
```

## Development Workflow

1. **Feature Development**
   - Create feature branch
   - Implement changes with tests
   - Run tests locally
   - Lint code
   - Build Docker image
   - Test in Docker container

2. **Testing**
   - Unit tests for services
   - Integration tests for API endpoints
   - Verify coverage >80%
   - Manual API testing with curl

3. **Deployment**
   - Build and push Docker image
   - Deploy to Cloud Run
   - Verify health check
   - Test production endpoints

## Cost Optimisation

Estimated monthly cost for personal use: ~$0.01

- **Cloud Run**: Generous free tier (2 million requests/month)
- **Firestore**: Free tier covers ~20K writes/day
- **Cloud Storage**: First 5GB free
- **Network**: Within Australia region minimises egress costs

Tips:
- Use signed URLs for photo access (no Cloud Run bandwidth charges)
- Implement pagination to reduce query costs
- Use lifecycle policies on Cloud Storage for old photos
- Monitor usage in GCP console

## Troubleshooting

### Application Won't Start

```bash
# Check environment variables
cat .env

# Verify Application Default Credentials
gcloud auth application-default print-access-token

# Check Firestore connectivity
gcloud firestore databases describe --database=(default)
```

### Authentication Errors

```bash
# Regenerate application credentials
gcloud auth application-default login

# Verify API key in request
curl -v -H "X-API-Key: $API_KEY" http://localhost:8080/api/entries
```

### Photo Upload Fails

```bash
# Check bucket permissions
gsutil iam get gs://your-bucket-name

# Verify storage client authentication
python -c "from google.cloud import storage; storage.Client()"
```

### Rate Limiting Issues

Adjust in `.env`:
```bash
RATE_LIMIT_PER_MINUTE=200
```

## Security Considerations

- **API Keys**: Store securely, never commit to version control
- **Service Account**: Use minimal permissions (Firestore + Storage only)
- **Cloud Storage**: Bucket is private, access via signed URLs only
- **CORS**: Restricted in production (wildcard allowed only in development)
- **Rate Limiting**: Prevents API abuse
- **Input Validation**: All requests validated with Pydantic models

## Contributing

This is a personal project, but feedback and suggestions are welcome via issues.

## Licence

Private project - All rights reserved

## Support

For issues or questions, create an issue in the repository.