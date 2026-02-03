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

# Install Google Cloud SDK (if not already installed)
brew install google-cloud-sdk

# Install Docker
brew install docker
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

# Using uv (recommended - faster)
uv pip install -r requirements.txt

# Or using pip
pip install -r requirements.txt
```

## Deployment Guide

### Step 1: Configure Pulumi Stack

```bash
cd infrastructure

# Initialise Pulumi stack (if not already done)
pulumi login

# Set stack configuration
pulumi config set gcp:project YOUR_PROJECT_ID
pulumi config set gcp:region australia-southeast1
```

### Step 2: Deploy Infrastructure

```bash
# Preview changes
pulumi preview

# Deploy infrastructure
pulumi up
```

This provisions all resources including:
- Firestore database with composite indexes
- Cloud Storage bucket for photos
- Artifact Registry repository for Docker images
- Secret Manager secret for API keys
- Cloud Run service (requires image to be pushed first)
- Service account with appropriate IAM roles
- Service account key for local development

### Step 3: Get Infrastructure Outputs

```bash
# View all outputs
pulumi stack output

# Get specific values
export PROJECT_ID=$(pulumi stack output project_id)
export REGION=$(pulumi stack output region)
export BUCKET_NAME=$(pulumi stack output bucket_name)
export SERVICE_ACCOUNT_EMAIL=$(pulumi stack output service_account_email)
```

## Application Deployment

### Initial Setup

After provisioning infrastructure, you need to:
1. Build and push a Docker image to Artifact Registry
2. Set API keys in Secret Manager
3. Pulumi will automatically deploy the image to Cloud Run

### Step 1: Configure Docker Authentication

```bash
# Get the Artifact Registry URL
export AR_URL=$(pulumi stack output artifact_registry_url)
export REGION=$(pulumi stack output region)

# Configure Docker to authenticate with Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### Step 2: Build and Push Container Image

```bash
# Navigate to project root
cd ..

# Build Docker image
docker build -t ${AR_URL}/personal-diary:latest .

# Push to Artifact Registry
docker push ${AR_URL}/personal-diary:latest
```

### Step 3: Update API Keys in Secret Manager

```bash
# Generate secure API keys
# Example: openssl rand -hex 32

# Get the secret ID
export SECRET_ID=$(pulumi stack output secret_id)

# Update the secret with your actual API keys (comma-separated)
echo -n "your-api-key-1,your-api-key-2,your-api-key-3" | \
  gcloud secrets versions add ${SECRET_ID} --data-file=-
```

### Step 4: Deploy to Cloud Run

```bash
# Return to infrastructure directory
cd infrastructure

# Deploy updated configuration
pulumi up
```

The Cloud Run service will automatically use the latest image from Artifact Registry and pull API keys from Secret Manager.

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
pulumi preview

# Apply changes
pulumi up
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
| `service_account_key` | Service account key (base64 encoded, secret) |
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
- For Cloud Run production deployment, use Workload Identity (no keys needed)
- For local development, use Application Default Credentials: `gcloud auth application-default login`
- Service account keys are available via Pulumi output but not recommended for regular use
- Never commit service account keys to version control

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

**Recommended approach** - Use Application Default Credentials:
```bash
# Authenticate with your user account
gcloud auth application-default login

# Verify authentication works
gcloud auth application-default print-access-token

# Test Firestore access
python -c "from google.cloud import firestore; client = firestore.Client(); print('Success')"
```

**Alternative** - Service account key (if needed):
```bash
# Export service account key
pulumi stack output service_account_key --show-secrets | base64 -d > ../gcp-key.json

# Verify the key is valid JSON
cat ../gcp-key.json | python -m json.tool

# Test authentication
export GOOGLE_APPLICATION_CREDENTIALS=../gcp-key.json
gcloud auth activate-service-account --key-file=../gcp-key.json
```

### Firestore Permission Issues

```bash
# Check service account permissions
gcloud projects get-iam-policy $(pulumi stack output project_id) \
  --flatten="bindings[].members" \
  --filter="bindings.members:$(pulumi stack output service_account_email)"
```

## Clean Up

To destroy all infrastructure:

```bash
cd infrastructure

# Preview what will be destroyed
pulumi destroy --preview

# Destroy infrastructure
pulumi destroy

# Remove Pulumi stack
pulumi stack rm dev
```

**Warning**: This will permanently delete all data including Firestore documents and storage bucket photos!

## Development Notes

### Firestore Indexes
- Composite indexes are defined in `firestore.indexes.json`
- Indexes may take 5-15 minutes to build after deployment
- Check status: https://console.cloud.google.com/firestore/indexes

### Local Development Authentication

**Recommended**: Use Application Default Credentials (no key files needed):
```bash
gcloud auth application-default login
```

**Alternative**: Export service account key (less secure, not recommended):
```bash
pulumi stack output service_account_key --show-secrets > ../gcp-key.json.b64
base64 -d ../gcp-key.json.b64 > ../gcp-key.json
rm ../gcp-key.json.b64
```

### Environment Variables
The following environment variables are configured in Cloud Run:
- `GCP_PROJECT_ID` - Project ID
- `GCP_REGION` - Deployment region
- `STORAGE_BUCKET` - Photos bucket name
- `API_KEYS` - From Secret Manager
- `RATE_LIMIT_PER_MINUTE` - 100 requests
- `SIGNED_URL_EXPIRATION` - 3600 seconds
- `ENVIRONMENT` - production
- `LOG_LEVEL` - INFO

## File Structure

```
infrastructure/
├── __main__.py              # Main Pulumi program
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── Pulumi.yaml             # Pulumi project config
├── Pulumi.dev.yaml         # Dev stack config
└── .gitignore              # Git ignore rules
```

## Additional Resources

- [Pulumi GCP Documentation](https://www.pulumi.com/docs/clouds/gcp/)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Firestore Documentation](https://cloud.google.com/firestore/docs)