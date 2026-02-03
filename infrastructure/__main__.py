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
"""

import json
import os

import pulumi
import pulumi_gcp as gcp

# Application constants (same across all environments)
APP_NAME = "personal-diary"
IMAGE_NAME = APP_NAME
SIGNED_URL_EXPIRATION = 3600
CONTAINER_PORT = 8080
MEMORY_LIMIT = "512Mi"
CPU_LIMIT = "1"
MIN_INSTANCES = 0
MAX_INSTANCES = 10
PHOTO_RETENTION_DAYS = 3650  # 10 years

# Get GCP configuration
config = pulumi.Config("gcp")
project_id = config.require("project")
region = config.get("region") or "australia-southeast1"

# Get application configuration (all required)
config_app = pulumi.Config()
environment = config_app.require("environment")
log_level = config_app.require("log_level")
cors_origins = config_app.require("cors_origins")
rate_limit_per_minute = config_app.require("rate_limit_per_minute")
image_tag = config_app.require("image_tag")

# Validate configuration
if rate_limit_per_minute and not rate_limit_per_minute.isdigit():
    raise pulumi.RunError("rate_limit_per_minute must be a numeric string")
if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
    raise pulumi.RunError(f"Invalid log_level: {log_level}")

# Resource labels for consistency
labels = {
    "app": APP_NAME,
    "environment": environment,
    "managed-by": "pulumi",
}

# Enable GCP APIs
required_apis = [
    "firestore.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
]

api_services = []
for svc in required_apis:
    res_name = svc.replace(".", "-")
    api_services.append(
        gcp.projects.Service(
            f"api-{res_name}",
            project=project_id,
            service=svc,
            disable_on_destroy=False,
        )
    )

# Cloud Storage bucket for photo storage
bucket = gcp.storage.Bucket(
    "bucket",
    name=f"{APP_NAME}-photos",
    location=region.upper(),
    labels=labels,
    uniform_bucket_level_access=True,
    force_destroy=(environment == "development"),
    public_access_prevention="enforced",
    lifecycle_rules=[
        gcp.storage.BucketLifecycleRuleArgs(
            action=gcp.storage.BucketLifecycleRuleActionArgs(type="Delete"),
            condition=gcp.storage.BucketLifecycleRuleConditionArgs(age=PHOTO_RETENTION_DAYS),
        ),
    ],
    versioning=gcp.storage.BucketVersioningArgs(enabled=False),
)

# Artifact Registry repository for Docker images
artifact_registry = gcp.artifactregistry.Repository(
    "registry",
    repository_id=APP_NAME,
    location=region,
    format="DOCKER",
    description="Docker images for Personal Diary REST API",
    labels=labels,
    cleanup_policy_dry_run=False,
    cleanup_policies=[
        gcp.artifactregistry.RepositoryCleanupPolicyArgs(
            id="keep-recent",
            action="KEEP",
            most_recent_versions=gcp.artifactregistry.RepositoryCleanupPolicyMostRecentVersionsArgs(
                keep_count=10,
            ),
        ),
    ],
)

# Firestore database in Firestore mode
firestore_database = gcp.firestore.Database(
    "database",
    name=APP_NAME,
    project=project_id,
    location_id=region,
    type="FIRESTORE_NATIVE",
    concurrency_mode="OPTIMISTIC",
    app_engine_integration_mode="DISABLED",
    opts=pulumi.ResourceOptions(
        depends_on=api_services,
        protect=True,
    ),
)

# Read Firestore index configuration
index_config_path = os.path.join(os.path.dirname(__file__), "firestore.indexes.json")
try:
    with open(index_config_path) as f:
        index_config = json.load(f)
except FileNotFoundError:
    pulumi.log.warn(f"No index config at {index_config_path}, skipping indexes")
    index_config = {"indexes": []}
except json.JSONDecodeError as e:
    raise pulumi.RunError(f"Invalid JSON in {index_config_path}: {e}") from e

# Create composite indexes for complex queries
firestore_indexes = []
for idx_num, idx_def in enumerate(index_config.get("indexes", [])):
    fields = []
    for field in idx_def["fields"]:
        if "order" in field:
            fields.append(
                gcp.firestore.IndexFieldArgs(
                    field_path=field["fieldPath"],
                    order=field["order"],
                )
            )
        elif "arrayConfig" in field:
            fields.append(
                gcp.firestore.IndexFieldArgs(
                    field_path=field["fieldPath"],
                    array_config=field["arrayConfig"],
                )
            )

    collection_name = idx_def["collectionGroup"]
    index = gcp.firestore.Index(
        f"index-{collection_name}-{idx_num}",
        database=firestore_database.name,
        collection=collection_name,
        fields=fields,
        query_scope=idx_def["queryScope"],
        project=project_id,
    )
    firestore_indexes.append(index)

# Service account for the application
service_account = gcp.serviceaccount.Account(
    "sa",
    account_id=f"{APP_NAME}-sa",
    display_name="Personal Diary API Service Account",
    description="Service account for Personal Diary REST API with minimal permissions",
    project=project_id,
)

service_account_member = service_account.email.apply(lambda email: f"serviceAccount:{email}")

# IAM bindings
firestore_iam_binding = gcp.projects.IAMMember(
    "iam-firestore",
    project=project_id,
    role="roles/datastore.user",
    member=service_account_member,
)

storage_iam_binding = gcp.storage.BucketIAMMember(
    "iam-storage",
    bucket=bucket.name,
    role="roles/storage.objectAdmin",
    member=service_account_member,
)

artifact_registry_iam_binding = gcp.artifactregistry.RepositoryIamMember(
    "iam-registry",
    repository=artifact_registry.name,
    location=region,
    role="roles/artifactregistry.reader",
    member=service_account_member,
)

# Secret Manager for API keys
api_keys_secret = gcp.secretmanager.Secret(
    "api-keys",
    secret_id=f"{APP_NAME}-keys",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
    opts=pulumi.ResourceOptions(protect=True),
)

# Initial secret version with placeholder
api_keys_secret_version = gcp.secretmanager.SecretVersion(
    "api-keys-version",
    secret=api_keys_secret.id,
    secret_data="CHANGE_ME",
)

secret_iam_binding = gcp.secretmanager.SecretIamMember(
    "iam-secret",
    secret_id=api_keys_secret.id,
    role="roles/secretmanager.secretAccessor",
    member=service_account_member,
)

# Construct the full image URL
image_url = pulumi.Output.concat(
    region,
    "-docker.pkg.dev/",
    project_id,
    "/",
    artifact_registry.repository_id,
    "/",
    IMAGE_NAME,
    ":",
    image_tag,
)

# Cloud Run service
cloud_run_service = gcp.cloudrunv2.Service(
    "service",
    name=APP_NAME,
    location=region,
    labels=labels,
    deletion_protection=False,
    ingress="INGRESS_TRAFFIC_ALL",
    template=gcp.cloudrunv2.ServiceTemplateArgs(
        service_account=service_account.email,
        scaling=gcp.cloudrunv2.ServiceTemplateScalingArgs(
            min_instance_count=MIN_INSTANCES,
            max_instance_count=MAX_INSTANCES,
        ),
        containers=[
            gcp.cloudrunv2.ServiceTemplateContainerArgs(
                image=image_url,
                ports=gcp.cloudrunv2.ServiceTemplateContainerPortsArgs(
                    container_port=CONTAINER_PORT,
                ),
                resources=gcp.cloudrunv2.ServiceTemplateContainerResourcesArgs(
                    limits={
                        "cpu": CPU_LIMIT,
                        "memory": MEMORY_LIMIT,
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
                        name="FIRESTORE_DATABASE",
                        value=firestore_database.name,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="ENVIRONMENT",
                        value=environment,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="LOG_LEVEL",
                        value=log_level,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="RATE_LIMIT_PER_MINUTE",
                        value=rate_limit_per_minute,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="SIGNED_URL_EXPIRATION",
                        value=str(SIGNED_URL_EXPIRATION),
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="CORS_ORIGINS",
                        value=cors_origins,
                    ),
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
            *api_services,
            firestore_database,
            bucket,
            artifact_registry,
            api_keys_secret_version,
            secret_iam_binding,
            firestore_iam_binding,
            storage_iam_binding,
            artifact_registry_iam_binding,
        ]
    ),
)

# Allow unauthenticated access to Cloud Run service
# Authentication is handled by the application via API keys
cloud_run_iam_binding = gcp.cloudrunv2.ServiceIamMember(
    "iam-invoker",
    name=cloud_run_service.name,
    location=region,
    role="roles/run.invoker",
    member="allUsers",
)

# Exports
pulumi.export("project_id", project_id)
pulumi.export("region", region)
pulumi.export("bucket_name", bucket.name)
pulumi.export("bucket_url", bucket.url)
pulumi.export("service_account_email", service_account.email)
pulumi.export("firestore_database_name", firestore_database.name)
pulumi.export("firestore_indexes_count", len(firestore_indexes))
pulumi.export("artifact_registry_repository", artifact_registry.name)
pulumi.export(
    "artifact_registry_url",
    pulumi.Output.concat(
        region,
        "-docker.pkg.dev/",
        project_id,
        "/",
        artifact_registry.repository_id,
    ),
)
pulumi.export("secret_id", api_keys_secret.secret_id)
pulumi.export("cloud_run_service_name", cloud_run_service.name)
pulumi.export("cloud_run_service_url", cloud_run_service.uri)
