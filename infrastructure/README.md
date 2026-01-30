# Diary Application Infrastructure

This directory contains Pulumi Infrastructure as Code (IaC) for provisioning Google Cloud Platform resources for the diary application.

## Resources Provisioned

- **Cloud Storage Bucket**: Stores diary entry photos with 10-year lifecycle policy
- **Firestore Database**: Native mode database for diary entries (OPTIMISTIC concurrency control)
- **Service Account**: Dedicated service account with appropriate IAM permissions
  - `roles/datastore.user` - Firestore read/write access
  - `roles/storage.objectAdmin` - Cloud Storage full access

## Prerequisites

1. **GCP Project**: Active Google Cloud Platform project
2. **GCP CLI**: `gcloud` CLI installed and authenticated
3. **Pulumi CLI**: Pulumi installed (see https://www.pulumi.com/docs/get-started/install/)
4. **Python**: Python 3.11+ with pip
5. **GCP Authentication**: Application Default Credentials configured

## Initial Setup

### 1. Authenticate with GCP

```bash
# Authenticate gcloud CLI
gcloud auth login

# Set default project
gcloud config set project YOUR_PROJECT_ID

# Configure application default credentials
gcloud auth application-default login
```

### 2. Install Dependencies

```bash
cd infrastructure
pip install -r requirements.txt
```

### 3. Configure Pulumi Stack

The project uses a local state backend (configured in Pulumi.dev.yaml).

```bash
# Select the development stack
pulumi stack select dev

# Set required configuration values
pulumi config set gcp:project YOUR_PROJECT_ID
pulumi config set gcp:region australia-southeast1
```

## Deployment Commands

### Preview Changes

View what resources will be created/modified without applying changes:

```bash
pulumi preview
```

### Deploy Infrastructure

Provision or update all GCP resources:

```bash
pulumi up
```

Review the preview, then confirm with 'yes' when prompted.

### View Current Stack Outputs

Display exported values (project ID, bucket name, service account email, etc.):

```bash
pulumi stack output
```

### Export Service Account Key

After deployment, export the service account key for application use.

**Note**: Pulumi encrypts secrets with a passphrase. You'll need to provide it when exporting.

**Option 1: Set passphrase environment variable**
```bash
# Export with passphrase (enter your stack's passphrase)
export PULUMI_CONFIG_PASSPHRASE="your-passphrase-here"

# Get the service account key (base64 encoded)
pulumi stack output service_account_key --show-secrets > ../gcp-key.json.b64
```

**Option 2: Enter passphrase interactively**
```bash
# Pulumi will prompt for passphrase
pulumi stack output service_account_key --show-secrets > ../gcp-key.json.b64
# Enter passphrase when prompted
```

**Decode and verify the key**:
```bash
# Decode to JSON
base64 -d ../gcp-key.json.b64 > ../gcp-key.json

# Remove base64 file
rm ../gcp-key.json.b64

# Verify key is valid JSON
cat ../gcp-key.json | jq .
```

### Destroy Infrastructure

Remove all provisioned resources (use with caution):

```bash
pulumi destroy
```

## Configuration Reference

Key configuration values in `Pulumi.dev.yaml`:

| Config Key | Description | Example |
|------------|-------------|---------|
| `gcp:project` | GCP project ID | `my-diary-app-123456` |
| `gcp:region` | GCP region for resources | `australia-southeast1` |

## Stack Outputs

After successful deployment, these values are exported:

| Output | Description | Usage |
|--------|-------------|-------|
| `project_id` | GCP project ID | Set as `GCP_PROJECT_ID` in .env |
| `region` | GCP region | Set as `GCP_REGION` in .env |
| `bucket_name` | Cloud Storage bucket name | Set as `STORAGE_BUCKET` in .env |
| `service_account_email` | Service account email | For IAM configuration |
| `service_account_key` | Service account JSON key | Save as gcp-key.json |

## Environment Variable Configuration

After deployment, update the application's `.env` file:

```bash
# Copy outputs to .env
cd ..
cp .env.example .env

# Set values from Pulumi outputs
GCP_PROJECT_ID=$(cd infrastructure && pulumi stack output project_id)
GCP_REGION=$(cd infrastructure && pulumi stack output region)
STORAGE_BUCKET=$(cd infrastructure && pulumi stack output bucket_name)
GOOGLE_APPLICATION_CREDENTIALS=./gcp-key.json
```

## Troubleshooting

### Authentication Issues

**Problem**: `Error: gcp:projects/Project: google: could not find default credentials`

**Solution**:
```bash
gcloud auth application-default login
```

### Permission Denied

**Problem**: `Error: googleapi: Error 403: Permission denied`

**Solution**: Ensure your GCP user has the following roles:
- `roles/owner` OR
- `roles/editor` + `roles/iam.serviceAccountAdmin`

### State File Issues

**Problem**: `error: could not load plugin`

**Solution**: Reinstall Pulumi plugins:
```bash
pulumi plugin install resource gcp v9.0.0
```

### Firestore Already Exists

**Problem**: `Error: resource already exists`

**Solution**: If Firestore database already exists in default mode:
1. Delete existing database from GCP Console (cannot be done via API)
2. Wait 5-10 minutes for deletion to complete
3. Run `pulumi up` again

### Service Account Key Not Exported

**Problem**: Can't retrieve service account key

**Solution**:
```bash
# View key in terminal (base64 encoded)
pulumi stack output service_account_key --show-secrets

# Or export again following "Export Service Account Key" instructions above
```

## State Management

This project uses **local state backend** stored in:
- Location: `.pulumi/` directory (gitignored)
- Stack files: Individual JSON files per stack

For team collaboration, consider migrating to Pulumi Cloud or S3 backend.

## Updating Infrastructure

1. Modify `__main__.py` with required changes
2. Preview changes: `pulumi preview`
3. Review the diff carefully
4. Apply changes: `pulumi up`
5. Verify in GCP Console

## Security Notes

- **Service Account Keys**: Never commit `gcp-key.json` to version control
- **State Files**: Local state contains sensitive data - keep `.pulumi/` directory secure
- **Principle of Least Privilege**: Service account has minimal required permissions
- **Secrets**: Use `pulumi config set --secret` for sensitive configuration

## Useful Commands Summary

```bash
# View help
pulumi --help

# List all stacks
pulumi stack ls

# View stack information
pulumi stack

# Refresh state from actual cloud resources
pulumi refresh

# View recent stack operations
pulumi stack history

# Export stack state
pulumi stack export > stack-backup.json

# Import stack state
pulumi stack import < stack-backup.json
```

## Resources

- [Pulumi GCP Documentation](https://www.pulumi.com/docs/clouds/gcp/)
- [GCP Cloud Storage](https://cloud.google.com/storage/docs)
- [GCP Firestore](https://cloud.google.com/firestore/docs)
- [GCP Service Accounts](https://cloud.google.com/iam/docs/service-accounts)