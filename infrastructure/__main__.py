"""Personal Diary REST API Infrastructure

Provisions GCP resources for the Personal Diary REST API:
- Cloud Firestore database (Firestore mode)
- Cloud Storage bucket (private, with lifecycle rules)
- Service account with minimal permissions
- IAM bindings for service account
- Exports service account key, bucket name, and project ID
"""

import pulumi
import pulumi_gcp as gcp

# Get GCP configuration
config = pulumi.Config("gcp")
project_id = config.require("project")
region = config.get("region") or "australia-southeast1"

# Create Cloud Storage bucket for photo storage
bucket = gcp.storage.Bucket(
    "diary-photos-bucket",
    name=f"{project_id}-diary-photos",
    location=region.upper(),
    uniform_bucket_level_access=True,
    # Private bucket - access via signed URLs only
    public_access_prevention="enforced",
    # Lifecycle rules for cost optimisation
    lifecycle_rules=[
        gcp.storage.BucketLifecycleRuleArgs(
            action=gcp.storage.BucketLifecycleRuleActionArgs(
                type="Delete",
            ),
            condition=gcp.storage.BucketLifecycleRuleConditionArgs(
                # Delete photos older than 10 years
                age=3650,
            ),
        ),
    ],
    versioning=gcp.storage.BucketVersioningArgs(
        enabled=False,
    ),
)

# Enable Cloud Firestore API
firestore_api = gcp.projects.Service(
    "firestore-api",
    service="firestore.googleapis.com",
    project=project_id,
    disable_on_destroy=False,
)

# Create Firestore database in Firestore mode (not Datastore mode)
firestore_database = gcp.firestore.Database(
    "diary-database",
    name="(default)",
    project=project_id,
    location_id=region,
    type="FIRESTORE_NATIVE",
    # Use GOOGLE_STANDARD_SQL concurrency mode for better query support
    concurrency_mode="OPTIMISTIC",
    app_engine_integration_mode="DISABLED",
    opts=pulumi.ResourceOptions(depends_on=[firestore_api]),
)

# Create service account for the application
service_account = gcp.serviceaccount.Account(
    "diary-api-service-account",
    account_id=f"{project_id}-diary-api",
    display_name="Personal Diary API Service Account",
    description="Service account for Personal Diary REST API with minimal permissions",
    project=project_id,
)

# Grant Cloud Datastore User role for Firestore access
firestore_iam_binding = gcp.projects.IAMMember(
    "firestore-user-binding",
    project=project_id,
    role="roles/datastore.user",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Storage Object Admin role for bucket access
storage_iam_binding = gcp.storage.BucketIAMMember(
    "storage-admin-binding",
    bucket=bucket.name,
    role="roles/storage.objectAdmin",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Create service account key for local development
service_account_key = gcp.serviceaccount.Key(
    "diary-api-service-account-key",
    service_account_id=service_account.name,
    # Use JSON format for easier local development setup
    public_key_type="TYPE_X509_PEM_FILE",
)

# Export outputs for use in application configuration
pulumi.export("project_id", project_id)
pulumi.export("region", region)
pulumi.export("bucket_name", bucket.name)
pulumi.export("bucket_url", bucket.url)
pulumi.export("service_account_email", service_account.email)
pulumi.export(
    "service_account_key",
    service_account_key.private_key.apply(
        lambda key: pulumi.Output.secret(key)
    ),
)
pulumi.export("firestore_database_name", firestore_database.name)

# Export instructions for using the service account key
pulumi.export(
    "setup_instructions",
    pulumi.Output.all(bucket.name, service_account.email).apply(
        lambda args: f"""
Infrastructure provisioned successfully!

Next steps:
1. Export the service account key (you'll be prompted for your Pulumi passphrase):
   pulumi stack output service_account_key --show-secrets > ../gcp-key.json.b64
   base64 -d ../gcp-key.json.b64 > ../gcp-key.json
   rm ../gcp-key.json.b64

   Note: If you get a passphrase error, set: export PULUMI_CONFIG_PASSPHRASE="your-passphrase"

2. Add to .env file:
   GCP_PROJECT_ID={project_id}
   GCP_REGION={region}
   STORAGE_BUCKET={args[0]}
   GOOGLE_APPLICATION_CREDENTIALS=./gcp-key.json

3. Verify Firestore database in GCP Console:
   https://console.cloud.google.com/firestore/databases?project={project_id}

4. Verify Storage bucket in GCP Console:
   https://console.cloud.google.com/storage/browser/{args[0]}?project={project_id}
"""
    ),
)
