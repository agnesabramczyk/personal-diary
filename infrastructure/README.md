# Personal Diary Infrastructure

This directory contains the Pulumi infrastructure-as-code for the Personal Diary REST API, provisioning all necessary Google Cloud Platform resources.

## Architecture Overview

The infrastructure provisions a complete serverless application stack:

```
┌─────────────────┐
│   Cloud Run     │ ← Serverless container platform
│   (diary-api)   │
└────────┬────────┘
         │
         ├─────────────┬─────────────┬─────────────┐
         │             │             │             │
         ▼             ▼             ▼             ▼
┌────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│ Firestore  │  │  Cloud   │  │  Secret  │  │   Artifact   │
│  Database  │  │  Storage │  │  Manager │  │   Registry   │
└────────────┘  └──────────┘  └──────────┘  └──────────────┘
         │             │             │             │
         └─────────────┴─────────────┴─────────────┘
                       │
                       ▼
               ┌───────────────┐
               │Service Account│
               │  (diary-api)  │
               └───────────────┘
```

## Provisioned Resources

### 1. Cloud Firestore Database
- **Type**: FIRESTORE_NATIVE (not Datastore mode)
- **Concurrency**: OPTIMISTIC
- **Region**: australia-southeast1
- **Indexes**: Composite indexes from `firestore.indexes.json`
- **Purpose**: Store diary entries and photo metadata

### 2. Cloud Storage Bucket
- **Name**: `{project_id}-diary-photos`
- **Location**: australia-southeast1
- **Access**: Private (enforced)
- **Lifecycle**: Auto-delete photos older than 10 years
- **Features**: Uniform bucket-level access enabled
- **Purpose**: Store diary entry photos

### 3. Artifact Registry
- **Repository ID**: `diary-api`
- **Format**: DOCKER
- **Location**: australia-southeast1
- **Purpose**: Store container images for Cloud Run deployment
- **URL**: `{region}-docker.pkg.dev/{project_id}/diary-api`

### 4. Secret Manager
- **Secret ID**: `diary-api-keys`
- **Purpose**: Securely store API keys
- **Replication**: Automatic across regions
- **Access**: Service account only (via IAM)

### 5. Cloud Run Service
- **Name**: `diary-api`
- **Region**: australia-southeast1
- **Image**: From Artifact Registry
- **Memory**: 512Mi
- **CPU**: 1 vCPU
- **Scaling**: 0-10 instances (scale-to-zero enabled)
- **Port**: 8080
- **Ingress**: All traffic (authentication via application API keys)
- **Workload Identity**: Uses service account (no keys needed)

### 6. Service Account & IAM
- **Account**: `{project_id}-diary-api`
- **Roles**:
  - `roles/datastore.user` (Firestore access)
  - `roles/storage.objectAdmin` (Storage bucket access)
  - `roles/artifactregistry.reader` (Pull images from Artifact Registry)
  - `roles/secretmanager.secretAccessor` (Read API keys from Secret Manager)
- **Key**: Service account key exported for local development only
- **Purpose**: Minimal permissions for application runtime

## Prerequisites

### Required Tools

```bash
# Install Pulumi CLI
curl -fsSL https://get.pulumi.com | sh

# Install Google Cloud SDK
brew install google-cloud-sdk

# Install Colima (lightweight container runtime for macOS)
brew install colima docker docker-compose docker-buildx
colima start
```

### GCP Authentication

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID
```

### Python Dependencies

```bash
cd infrastructure

# Install dependencies (uv automatically creates .venv and installs locked versions)
uv sync

# Activate the environment to use the installed packages
source .venv/bin/activate
```

The infrastructure uses `pyproject.toml` and `uv.lock` for reproducible dependency management. Running `uv sync`:
1. Creates a `.venv` directory (if it doesn't exist)
2. Installs exact versions from `uv.lock` (Pulumi and dependencies)
3. You then activate the environment to use those packages

## Configuration Philosophy

Configuration is split between static values (Pulumi code) and required stack settings:

**Static values** (in `__main__.py`):
- Application name, image name
- Resource limits (CPU, memory)
- Photo retention policy
- Signed URL expiration

**Required stack configuration** (set via `pulumi config set` or in `Pulumi.dev.yaml`):
- GCP project and region
- Environment name (development/production)
- Log level (DEBUG/INFO/WARNING/ERROR)
- CORS origins
- Rate limit per minute
- Docker image tag
  - YAML default: `latest` (used by `make bootstrap` for first deployment)
  - Makefile override: Git commit hash (used by `make deploy` for traceability)
  - Manual operations: Must be explicitly set via `--config image_tag=...`

## Makefile Targets

The project includes a Makefile for both local development and cloud deployment:

**Local Development** (Docker):
```bash
make dev-up          # Start application in Docker (http://localhost:8080)
make dev-down        # Stop application
make dev-logs        # View application logs
make dev-shell       # Open shell in app container
make dev-rebuild     # Rebuild image and restart
```

**Cloud Infrastructure**:
```bash
make bootstrap       # First-time setup: create registry, build image, deploy
make build-push      # Build and push Docker image to Artifact Registry
make deploy          # Regular deployment: build, push, update infrastructure
make preview         # Preview infrastructure changes
make destroy         # Destroy all infrastructure (requires confirmation)
```

**Quality**:
```bash
make lint            # Run linting checks
make test            # Run tests
```

## Local Development

### Setup

```bash
# Copy the environment template to create your local configuration
cp .env.example .env

# Edit .env with your GCP credentials and settings
# Required: GCP_PROJECT_ID, STORAGE_BUCKET, FIRESTORE_DATABASE, API_KEYS
```

### Run Application Locally

```bash
# Start the application in Docker
make dev-up

# View logs
make dev-logs

# Open shell for debugging
make dev-shell

# Rebuild after code changes
make dev-rebuild

# Stop the application
make dev-down
```

The application will be available at `http://localhost:8080` and configured with:
- `ENVIRONMENT=development` (DEBUG logging)
- Hot reload enabled (if FastAPI is configured with `--reload`)
- GCP credentials mounted from `~/.config/gcloud/` (Application Default Credentials)
- Local CORS origins: `http://localhost:3000,http://localhost:8080`

### Local Testing Against GCP

The docker-compose configuration automatically uses your local GCP credentials:

```bash
# Ensure you're authenticated with GCP
gcloud auth application-default login

# Start the app (it will use your credentials)
make dev-up

# Test against real GCP services
curl -X POST http://localhost:8080/api/entries \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-test-api-key-1" \
  -d '{"title": "Test", "content": "Hello"}'
```

## Deployment Guide

### Initial Setup

```bash
cd infrastructure

# Log in to local Pulumi backend (stores state in ~/.pulumi)
pulumi login file://~

# Initialise stack
pulumi stack init dev

# Set stack configuration (all values required)
pulumi config set gcp:project YOUR_PROJECT_ID
pulumi config set gcp:region australia-southeast1
pulumi config set environment development
pulumi config set log_level DEBUG
pulumi config set cors_origins "http://localhost:3000"
pulumi config set rate_limit_per_minute "100"
pulumi config set image_tag latest
```

**About Pulumi backends:**

Local filesystem (used above) stores state in `~/.pulumi` on your machine. Simple and works offline, but you're responsible for backing up the state directory.

**Alternatives:**
- **Pulumi Cloud**: `pulumi login` - Managed service with automatic backups (free tier: 200 resources)
- **Cloud Storage**: `pulumi login gs://bucket-name` - Store state in Google Cloud Storage (or S3, Azure Blob, etc.)

### First-Time Deployment

Cloud Run requires a container image to deploy, creating a dependency order:
1. Artifact Registry must exist before you can push images
2. An image must exist before Cloud Run can deploy

The `make bootstrap` target handles this automatically:

```bash
cd infrastructure

# Create registry, build image, and deploy everything
make bootstrap
```

This runs in the correct order:
1. Creates Artifact Registry (so we have somewhere to push)
2. Builds and pushes Docker image (so Cloud Run has something to deploy)
3. Deploys remaining infrastructure (Firestore, Storage, Secret Manager, Cloud Run)

### Subsequent Deployments

For updates to the running service:

```bash
# Build, push, and update infrastructure with new image tag
make deploy

# Or manually:
make build-push
pulumi up --config image_tag=$(git rev-parse --short HEAD)
```

### Preview Changes

Before deploying:

```bash
make preview
```

### Get Infrastructure Outputs

```bash
# View all outputs
pulumi stack output

# Get specific values
export PROJECT_ID=$(pulumi stack output project_id)
export REGION=$(pulumi stack output region)
export BUCKET_NAME=$(pulumi stack output bucket_name)
export SERVICE_ACCOUNT_EMAIL=$(pulumi stack output service_account_email)
export CLOUD_RUN_URL=$(pulumi stack output cloud_run_service_url)
```

## Application Deployment

### Initial Setup

After provisioning infrastructure with `make bootstrap`, you need to:
1. Update API keys in Secret Manager
2. The Docker image is already built and deployed to Cloud Run

### Update API Keys in Secret Manager

```bash
# Generate secure API keys
# Example: openssl rand -hex 32

# Get the secret ID
export SECRET_ID=$(pulumi stack output secret_id)

# Update the secret with your actual API keys (comma-separated)
echo -n "your-api-key-1,your-api-key-2,your-api-key-3" | \
  gcloud secrets versions add ${SECRET_ID} --data-file=-
```

### Deploy Updated Service

To deploy a new version of the application:

```bash
# Build, push image, and update Cloud Run
make deploy

# Or manually:
cd ../..  # Back to project root
docker build -t $(cd infrastructure && pulumi stack output artifact_registry_url)/personal-diary:$(git rev-parse --short HEAD) .
docker push $(cd infrastructure && pulumi stack output artifact_registry_url)/personal-diary:$(git rev-parse --short HEAD)
cd infrastructure
pulumi up --config image_tag=$(git rev-parse --short HEAD)
```

The Cloud Run service automatically uses the latest image from Artifact Registry.

## Verify Infrastructure

### Check Firestore Database

```bash
# List Firestore databases
gcloud firestore databases list --project=${PROJECT_ID}

# Check index status (may take 5-15 minutes to build)
gcloud firestore indexes list --database="(default)" --project=${PROJECT_ID}
```

### Check Storage Bucket

```bash
# List buckets
gsutil ls -b gs://${BUCKET_NAME}

# Check bucket permissions
gsutil iam get gs://${BUCKET_NAME}
```

## Updating Infrastructure

When infrastructure changes are needed (e.g., modifying Firestore indexes), update the Pulumi code:

```bash
cd infrastructure

# Edit __main__.py or firestore.indexes.json as needed

# Preview changes
make preview

# Apply changes
pulumi up
```

To update the deployed application with a new image:

```bash
# Build, push image, and update infrastructure with new tag
make deploy

# Or step by step:
make build-push
pulumi up --config image_tag=$(git rev-parse --short HEAD)
```

## Rolling Back Infrastructure Changes

If you need to rollback infrastructure changes:

```bash
cd infrastructure

# View stack history
pulumi stack history

# Preview rollback to a specific version
pulumi stack select <version>
pulumi preview

# Rollback infrastructure
pulumi up
```

## Outputs

After successful deployment, the following values are exported:

| Output | Description |
|--------|-------------|
| `project_id` | GCP project ID |
| `region` | Deployment region |
| `bucket_name` | Storage bucket name for photos |
| `bucket_url` | Storage bucket URL |
| `artifact_registry_repository` | Artifact Registry repository name |
| `artifact_registry_url` | Full Artifact Registry URL for Docker push/pull |
| `secret_id` | Secret Manager secret ID for API keys |
| `cloud_run_service_name` | Cloud Run service name |
| `cloud_run_service_url` | Live API endpoint URL |
| `service_account_email` | Service account email |
| `firestore_database_name` | Firestore database name |
| `firestore_indexes_count` | Number of composite indexes created |
| `setup_instructions` | Complete setup instructions for next steps |

Access outputs:
```bash
pulumi stack output <output_name>
```

## Security Best Practices

### 1. API Keys Management
- Store API keys in environment variables (not committed to version control)
- Rotate keys regularly
- Use different keys for different environments (dev, staging, production)

### 2. Service Account
- The service account has minimal required permissions (Firestore + Storage only)
- For Cloud Run production deployment, uses Workload Identity (no keys needed)
- For local development, use Application Default Credentials: `gcloud auth application-default login`

### 3. Data Security
- Storage bucket enforces private access
- Firestore uses service account authentication
- Signed URLs for photo access (time-limited)
- User data isolation via user_id field in Firestore

## Cost Optimisation

### Cloud Run
- Scales to zero when not in use (no cost)
- 512Mi memory is sufficient for FastAPI
- Monitor usage and adjust max instances if needed

### Storage
- Lifecycle policy deletes old photos (10 years)
- Consider Standard vs Nearline storage class

### Firestore
- Monitor document reads/writes
- Optimise queries to minimise operations

## Monitoring and Alerts

Set up monitoring in Google Cloud Console:

### Cloud Run Metrics
- Request count
- Request latency
- Error rate
- Instance count

### Storage Metrics
- Total size
- Request count
- Bandwidth usage

### Firestore Metrics
- Document reads/writes
- Query performance
- Storage usage

## Troubleshooting

### Authentication Issues

Use Application Default Credentials:
```bash
# Authenticate with your user account
gcloud auth application-default login

# Verify authentication works
gcloud auth application-default print-access-token

# Test Firestore access
python -c "from google.cloud import firestore; client = firestore.Client(); print('Success')"
```

### Firestore Permission Issues

```bash
# Check service account permissions
gcloud projects get-iam-policy $(pulumi stack output project_id) \
  --flatten="bindings[].members" \
  --filter="bindings.members:$(pulumi stack output service_account_email)"
```

## State Management

Pulumi state is stored in `~/.pulumi` and contains critical information about your infrastructure (resource IDs, configuration, dependencies). Without this state, you cannot update or destroy your infrastructure through Pulumi.

**Backup options:**

**1. Time Machine (recommended for macOS)**
- Ensure Time Machine is enabled - it automatically backs up `~/.pulumi`
- Restore from Time Machine if needed

**2. Export state to version control**
```bash
# Export current state
cd infrastructure
pulumi stack export --file stack-state.json

# Commit to git (ensure repo is private!)
git add stack-state.json
git commit -m "Backup Pulumi state"

# Restore from file
pulumi stack import --file stack-state.json
```

**3. Backup to Google Cloud Storage**
```bash
# One-time backup
pulumi stack export | gsutil cp - gs://your-backup-bucket/pulumi-state-$(date +%Y%m%d).json

# Restore from GCS
gsutil cat gs://your-backup-bucket/pulumi-state-YYYYMMDD.json | pulumi stack import
```

## Clean Up

To destroy all infrastructure:

```bash
cd infrastructure

# Destroy infrastructure (requires confirmation)
make destroy

# Or manually:
pulumi destroy

# Remove Pulumi stack
pulumi stack rm dev
```

**Warning**: This will permanently delete all data including Firestore documents and storage bucket photos!

**Protected resources**: The Firestore database and Secret Manager secret have Pulumi protection enabled. To force deletion, use `pulumi destroy --target` or `-f` flag.

## Infrastructure Improvements

### Resource Protection

The infrastructure includes built-in protections against accidental deletion:

- **Firestore database**: Protected with `protect=True` in Pulumi and `deletion_protection=True` in non-development environments
- **Secret Manager secret**: Protected with `protect=True` in Pulumi
- **Storage bucket**: `force_destroy=True` only in development environment

To delete protected resources, use `pulumi destroy -f`.

### Resource Labels

All resources are tagged with labels for organisation:
- `app: personal-diary`
- `environment: development|production`
- `managed-by: pulumi`

These appear in GCP Console for easy filtering and cost tracking.

### Artifact Registry Cleanup

The Artifact Registry automatically maintains only the 10 most recent image versions, preventing storage bloat from repeated deployments.

### Configuration Simplification

Static values (like memory limits, timeouts) are constants in the code. Environment-specific values (like log level, rate limits) go in stack configuration files. Deployment-specific values (like image tag) are passed at deploy time.

## Development Notes

### Firestore Indexes
- Composite indexes are defined in `firestore.indexes.json`
- Indexes may take 5-15 minutes to build after deployment
- Check status: https://console.cloud.google.com/firestore/indexes

### Local Development Authentication

Use Application Default Credentials (no key files needed):
```bash
gcloud auth application-default login
```

### Environment Variables
The following environment variables are configured in Cloud Run:
- `GCP_PROJECT_ID` - Project ID
- `GCP_REGION` - Deployment region
- `STORAGE_BUCKET` - Photos bucket name
- `FIRESTORE_DATABASE` - Firestore database name
- `ENVIRONMENT` - Environment (development/production)
- `LOG_LEVEL` - Log level (DEBUG/INFO/WARNING/ERROR)
- `RATE_LIMIT_PER_MINUTE` - API rate limit (from required config)
- `SIGNED_URL_EXPIRATION` - Signed URL expiration in seconds (static value: 3600)
- `CORS_ORIGINS` - CORS allowed origins (from config)
- `API_KEYS` - From Secret Manager (set via gcloud secrets versions add)

## File Structure

```
infrastructure/
├── __main__.py              # Main Pulumi program
├── pyproject.toml           # Python project metadata and dependencies
├── uv.lock                  # Locked dependency versions
├── firestore.indexes.json   # Firestore composite index definitions
├── README.md                # This file
├── Pulumi.yaml              # Pulumi project config
├── Pulumi.dev.yaml          # Development stack configuration
└── .gitignore               # Git ignore rules

../
├── Makefile                 # Deployment and local dev targets
├── docker-compose.yml       # Local development environment
├── .env.example             # Environment variables template (commit to git)
├── .env                     # Local environment values (in .gitignore)
├── Dockerfile               # Container image definition
├── .gitignore               # Git ignore rules
└── ...
```

## Additional Resources

- [Pulumi GCP Documentation](https://www.pulumi.com/docs/clouds/gcp/)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Firestore Documentation](https://cloud.google.com/firestore/docs)