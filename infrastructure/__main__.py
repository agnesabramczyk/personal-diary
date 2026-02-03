"""Personal Diary REST API Infrastructure

Provisions GCP resources for the Personal Diary REST API:
- Cloud Firestore database (Firestore mode)
- Firestore composite indexes for complex queries
- Cloud Storage bucket (private, with lifecycle rules)
- Artifact Registry repository for Docker images
- Secret Manager for API keys
- Cloud Run service
- Service account with minimal permissions
- IAM bindings for service account
- Exports service account key (for local dev), bucket name, and service URL
"""

import json
import os
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

# Create Artifact Registry repository for Docker images
artifact_registry = gcp.artifactregistry.Repository(
    "diary-api-registry",
    repository_id="diary-api",
    location=region,
    format="DOCKER",
    description="Docker images for Personal Diary REST API",
    # Optional: configure cleanup policies for old images
    cleanup_policy_dry_run=False,
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

# Read Firestore index configuration from firestore.indexes.json
index_config_path = os.path.join(os.path.dirname(__file__), "firestore.indexes.json")
with open(index_config_path) as f:
    index_config = json.load(f)

# Create composite indexes for complex queries
firestore_indexes = []
for idx_num, idx_def in enumerate(index_config.get("indexes", [])):
    # Build field configuration for the index
    fields = []
    for field in idx_def["fields"]:
        # Map order values to Pulumi format
        order_value = field.get("order", "ASCENDING")
        fields.append(
            gcp.firestore.IndexFieldArgs(
                field_path=field["fieldPath"],
                order=order_value,
            )
        )
    
    # Create the composite index
    collection_name = idx_def["collectionGroup"]
    index = gcp.firestore.Index(
        f"firestore-index-{collection_name}-{idx_num}",
        database=firestore_database.name,
        collection=collection_name,
        fields=fields,
        query_scope=idx_def["queryScope"],
        project=project_id,
        opts=pulumi.ResourceOptions(depends_on=[firestore_database]),
    )
    firestore_indexes.append(index)

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

# Grant Artifact Registry Reader role for pulling images
artifact_registry_iam_binding = gcp.artifactregistry.RepositoryIamMember(
    "artifact-registry-reader-binding",
    repository=artifact_registry.name,
    location=region,
    role="roles/artifactregistry.reader",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Create Secret Manager secret for API keys
api_keys_secret = gcp.secretmanager.Secret(
    "api-keys-secret",
    secret_id="diary-api-keys",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
)

# Create initial secret version with placeholder
# User should update this with actual API keys after deployment
api_keys_secret_version = gcp.secretmanager.SecretVersion(
    "api-keys-secret-version",
    secret=api_keys_secret.id,
    secret_data="PLACEHOLDER-UPDATE-AFTER-DEPLOYMENT",
)

# Grant Secret Manager accessor role to service account
secret_iam_binding = gcp.secretmanager.SecretIamMember(
    "secret-accessor-binding",
    secret_id=api_keys_secret.id,
    role="roles/secretmanager.secretAccessor",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Create service account key for local development
service_account_key = gcp.serviceaccount.Key(
    "diary-api-service-account-key",
    service_account_id=service_account.name,
    # Use JSON format for easier local development setup
    public_key_type="TYPE_X509_PEM_FILE",
)

# Get image tag from config or use 'latest' as default
config_app = pulumi.Config()
image_tag = config_app.get("image_tag") or "latest"

# Construct the full image URL
image_url = pulumi.Output.concat(
    region,
    "-docker.pkg.dev/",
    project_id,
    "/diary-api/personal-diary:",
    image_tag,
)

# Create Cloud Run service
cloud_run_service = gcp.cloudrunv2.Service(
    "diary-api-service",
    name="diary-api",
    location=region,
    ingress="INGRESS_TRAFFIC_ALL",
    template=gcp.cloudrunv2.ServiceTemplateArgs(
        service_account=service_account.email,
        scaling=gcp.cloudrunv2.ServiceTemplateScalingArgs(
            min_instance_count=0,
            max_instance_count=10,
        ),
        containers=[
            gcp.cloudrunv2.ServiceTemplateContainerArgs(
                image=image_url,
                ports=[
                    gcp.cloudrunv2.ServiceTemplateContainerPortArgs(
                        container_port=8080,
                    ),
                ],
                resources=gcp.cloudrunv2.ServiceTemplateContainerResourcesArgs(
                    limits={
                        "cpu": "1",
                        "memory": "512Mi",
                    },
                    cpu_idle=True,
                    startup_cpu_boost=True,
                ),
                envs=[
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="GCP_PROJECT_ID",
                        value=project_id,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="GCP_REGION",
                        value=region,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="STORAGE_BUCKET",
                        value=bucket.name,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="ENVIRONMENT",
                        value="production",
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="LOG_LEVEL",
                        value="INFO",
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="RATE_LIMIT_PER_MINUTE",
                        value="100",
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="SIGNED_URL_EXPIRATION",
                        value="3600",
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="CORS_ORIGINS",
                        # Empty string for production = no CORS (API only, no web frontend)
                        # Or set specific origins: "https://example.com,https://app.example.com"
                        value="",
                    ),
                    # API keys from Secret Manager
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="API_KEYS",
                        value_source=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceArgs(
                            secret_key_ref=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceSecretKeyRefArgs(
                                secret=api_keys_secret.secret_id,
                                version="latest",
                            ),
                        ),
                    ),
                ],
            ),
        ],
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[
            firestore_database,
            bucket,
            artifact_registry,
            api_keys_secret_version,
            secret_iam_binding,
        ]
    ),
)

# Allow unauthenticated access to Cloud Run service
# Authentication is handled by the application via API keys
cloud_run_iam_binding = gcp.cloudrunv2.ServiceIamMember(
    "cloud-run-invoker-binding",
    name=cloud_run_service.name,
    location=region,
    role="roles/run.invoker",
    member="allUsers",
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
pulumi.export(
    "firestore_indexes_count",
    len(firestore_indexes)
)
pulumi.export(
    "artifact_registry_repository",
    artifact_registry.name,
)
pulumi.export(
    "artifact_registry_url",
    pulumi.Output.concat(
        region,
        "-docker.pkg.dev/",
        project_id,
        "/diary-api",
    ),
)
pulumi.export("secret_id", api_keys_secret.secret_id)
pulumi.export("cloud_run_service_name", cloud_run_service.name)
pulumi.export("cloud_run_service_url", cloud_run_service.uri)

# Export instructions for using the service account key
pulumi.export(
    "setup_instructions",
    pulumi.Output.all(
        bucket.name,
        service_account.email,
        artifact_registry.name,
        api_keys_secret.secret_id,
        cloud_run_service.uri,
    ).apply(
        lambda args: f"""
Infrastructure provisioned successfully!

=== Cloud Run Service ===
Service URL: {args[4]}

IMPORTANT: The Cloud Run service is deployed but will fail until you:
1. Build and push a Docker image to Artifact Registry
2. Update the Secret Manager secret with actual API keys

=== For Local Development ===
1. Authenticate with Application Default Credentials (recommended):
   gcloud auth application-default login

2. Add to .env file:
   GCP_PROJECT_ID={project_id}
   GCP_REGION={region}
   STORAGE_BUCKET={args[0]}
   API_KEYS=<your-generated-api-keys>

   Note: GOOGLE_APPLICATION_CREDENTIALS is not needed when using ADC.

   Alternative (not recommended): Use service account key
   pulumi stack output service_account_key --show-secrets > ../gcp-key.json.b64
   base64 -d ../gcp-key.json.b64 > ../gcp-key.json
   rm ../gcp-key.json.b64
   Then add: GOOGLE_APPLICATION_CREDENTIALS=./gcp-key.json

=== Deploy Application to Cloud Run ===
1. Configure Docker for Artifact Registry:
   gcloud auth configure-docker {region}-docker.pkg.dev

2. Build and push image:
   docker build -t {region}-docker.pkg.dev/{project_id}/diary-api/personal-diary:latest .
   docker push {region}-docker.pkg.dev/{project_id}/diary-api/personal-diary:latest

3. Update Secret Manager with actual API keys:
   echo -n "your-api-key-1,your-api-key-2" | gcloud secrets versions add {args[3]} --data-file=-

4. Trigger new Cloud Run deployment:
   pulumi up

=== Verify Resources ===
- Firestore: https://console.cloud.google.com/firestore/databases?project={project_id}
- Storage: https://console.cloud.google.com/storage/browser/{args[0]}?project={project_id}
- Artifact Registry: https://console.cloud.google.com/artifacts/docker/{project_id}/{region}/{args[2]}
- Secret Manager: https://console.cloud.google.com/security/secret-manager/secret/{args[3]}?project={project_id}
- Cloud Run: https://console.cloud.google.com/run/detail/{region}/diary-api?project={project_id}

Note: Firestore indexes may take 5-15 minutes to build.
"""
    ),
)
