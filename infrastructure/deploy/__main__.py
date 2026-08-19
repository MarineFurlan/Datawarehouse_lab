"""Stable infrastructure for the OEI data platform."""

import pulumi
import pulumi_gcp as gcp


gcp_config = pulumi.Config("gcp")
project = gcp_config.require("project")
region = gcp_config.require("region")

dataset_ids = (
    "oei_einvoice",
    "oei_staging",
    "oei_mart",
    "osre_mart",
)

datasets = {}

for dataset_id in dataset_ids:
    datasets[dataset_id] = gcp.bigquery.Dataset(
        dataset_id,
        dataset_id=dataset_id,
        project=project,
        location=region,
        delete_contents_on_destroy=False,
        opts=pulumi.ResourceOptions(
            import_=f"projects/{project}/datasets/{dataset_id}",
            protect=True,
            ignore_changes=["accesses"],
        ),
    )

dbt_repository = gcp.artifactregistry.Repository(
    "oei-dbt-images",
    repository_id="oei-dbt-images",
    project=project,
    location=region,
    description="dbt images for the OEI data pipeline",
    format="DOCKER",
    mode="STANDARD_REPOSITORY",
    opts=pulumi.ResourceOptions(
        import_=(
            f"projects/{project}/locations/{region}"
            "/repositories/oei-dbt-images"
        ),
        protect=True,
    ),
)

composer_service_account = gcp.serviceaccount.Account(
    "oei-composer-sa",
    account_id="oei-composer-sa",
    project=project,
    display_name="OEI Composer runtime",
    disabled=False,
    opts=pulumi.ResourceOptions(
        import_=(
            f"projects/{project}/serviceAccounts/"
            f"oei-composer-sa@{project}.iam.gserviceaccount.com"
        ),
        protect=True,
    ),
)

composer_member = (
    f"serviceAccount:oei-composer-sa@{project}.iam.gserviceaccount.com"
)

composer_project_roles = {
    "bigquery-job-user": "roles/bigquery.jobUser",
    "worker": "roles/composer.worker",
}

composer_project_role_members = {}

for grant_name, role in composer_project_roles.items():
    composer_project_role_members[grant_name] = gcp.projects.IAMMember(
        f"oei-composer-{grant_name}",
        project=project,
        role=role,
        member=composer_member,
        opts=pulumi.ResourceOptions(
            import_=f"{project} {role} {composer_member}",
            protect=True,
            depends_on=[composer_service_account],
        ),
    )

composer_artifact_reader = gcp.artifactregistry.RepositoryIamMember(
    "oei-dbt-images-composer-reader",
    project=project,
    location=region,
    repository=dbt_repository.repository_id,
    role="roles/artifactregistry.reader",
    member=composer_member,
    opts=pulumi.ResourceOptions(
        import_=(
            f"projects/{project}/locations/{region}/repositories/"
            f"oei-dbt-images roles/artifactregistry.reader {composer_member}"
        ),
        protect=True,
        depends_on=[
            dbt_repository,
            composer_service_account,
        ],
    ),
)

# The landing and staging permissions predate Pulumi and are preserved through
# ignore_changes. These mart grants complete the permissions required by dbt.
mart_writer_accesses = {}

for dataset_id in ("oei_mart", "osre_mart"):
    mart_writer_accesses[dataset_id] = gcp.bigquery.DatasetAccess(
        f"{dataset_id}-composer-writer",
        project=project,
        dataset_id=datasets[dataset_id].dataset_id,
        role="WRITER",
        user_by_email=composer_service_account.email,
        opts=pulumi.ResourceOptions(
            protect=True,
            depends_on=[
                datasets[dataset_id],
                composer_service_account,
            ],
        ),
    )

postgres_instance = gcp.sql.DatabaseInstance(
    "oei-postgres-dev",
    name="oei-postgres-dev",
    project=project,
    region=region,
    database_version="POSTGRES_18",
    deletion_protection=True,
    settings={
        "tier": "db-perf-optimized-N-8",
        "edition": "ENTERPRISE_PLUS",
        "activation_policy": "NEVER",
        # Preserve the settings detected during the import preview.
        "enable_dataplex_integration": True,
        "final_backup_config": {
            "enabled": False,
        },

        "availability_type": "ZONAL",
        "disk_type": "PD_SSD",
        "disk_size": 100,
        "disk_autoresize": False,
        "disk_autoresize_limit": 0,
        "pricing_plan": "PER_USE",
        "database_flags": [
            {
                "name": "cloudsql.iam_authentication",
                "value": "on",
            },
            {
                "name": "cloudsql.logical_decoding",
                "value": "on",
            },
        ],
        "backup_configuration": {
            "enabled": False,
            "point_in_time_recovery_enabled": False,
            "start_time": "17:00",
            "transaction_log_retention_days": 14,
            "backup_retention_settings": {
                "retained_backups": 15,
                "retention_unit": "COUNT",
            },
        },
        "ip_configuration": {
            "ipv4_enabled": True,
            "ssl_mode": "ALLOW_UNENCRYPTED_AND_ENCRYPTED",
            "enable_private_path_for_google_cloud_services": False,
        },
        "location_preference": {
            "zone": "europe-west9-a",
        },
    },
    opts=pulumi.ResourceOptions(
        import_=f"projects/{project}/instances/oei-postgres-dev",
        protect=True,
        retain_on_delete=True,
        ignore_changes=[
            "settings.ipConfiguration.authorizedNetworks",
            "settings.maintenanceWindow",
            "settings.diskSize",
        ],
    ),
)

# GitHub Actions authenticates without stored GCP keys. The immutable numeric
# IDs prevent a renamed or recreated repository from inheriting this trust.
github_repository_id = "1328145264"
github_repository_owner_id = "34574120"

sts_api = gcp.projects.Service(
    "sts-api",
    project=project,
    service="sts.googleapis.com",
    disable_on_destroy=False,
    opts=pulumi.ResourceOptions(
        protect=True,
    ),
)

github_preview_service_account = gcp.serviceaccount.Account(
    "oei-github-preview",
    account_id="oei-github-preview",
    project=project,
    display_name="OEI GitHub preview",
    description="Read-only identity for GitHub Actions Pulumi previews",
    opts=pulumi.ResourceOptions(
        protect=True,
    ),
)

github_identity_pool = gcp.iam.WorkloadIdentityPool(
    "oei-github-actions",
    workload_identity_pool_id="oei-github-actions",
    project=project,
    display_name="OEI GitHub Actions",
    description="Federates GitHub Actions identities for OEI CI",
    disabled=False,
    opts=pulumi.ResourceOptions(
        protect=True,
        depends_on=[sts_api],
    ),
)

github_identity_provider = gcp.iam.WorkloadIdentityPoolProvider(
    "oei-dbt-lab",
    workload_identity_pool_id=github_identity_pool.workload_identity_pool_id,
    workload_identity_pool_provider_id="oei-dbt-lab",
    project=project,
    display_name="OEI dbt lab",
    description="GitHub OIDC provider for the OEI dbt lab repository",
    disabled=False,
    attribute_mapping={
        "google.subject": "assertion.sub",
        "attribute.repository": "assertion.repository",
        "attribute.repository_id": "assertion.repository_id",
        "attribute.repository_owner_id": "assertion.repository_owner_id",
    },
    attribute_condition=(
        f'assertion.repository_owner_id == "{github_repository_owner_id}" && '
        f'assertion.repository_id == "{github_repository_id}"'
    ),
    oidc={
        "issuer_uri": "https://token.actions.githubusercontent.com",
    },
    opts=pulumi.ResourceOptions(
        protect=True,
        depends_on=[github_identity_pool],
    ),
)

github_workload_identity_member = github_identity_pool.name.apply(
    lambda pool_name: (
        f"principalSet://iam.googleapis.com/{pool_name}"
        f"/attribute.repository_id/{github_repository_id}"
    )
)

github_preview_identity_user = gcp.serviceaccount.IAMMember(
    "oei-github-preview-workload-identity-user",
    service_account_id=github_preview_service_account.name,
    role="roles/iam.workloadIdentityUser",
    member=github_workload_identity_member,
    opts=pulumi.ResourceOptions(
        protect=True,
        depends_on=[
            github_identity_provider,
            github_preview_service_account,
        ],
    ),
)

github_preview_member = github_preview_service_account.email.apply(
    lambda email: f"serviceAccount:{email}"
)

github_preview_roles = {
    "artifact-reader": "roles/artifactregistry.reader",
    "bigquery-metadata-viewer": "roles/bigquery.metadataViewer",
    "cloudsql-viewer": "roles/cloudsql.viewer",
    "datastream-viewer": "roles/datastream.viewer",
    "security-reviewer": "roles/iam.securityReviewer",
    "service-account-viewer": "roles/iam.serviceAccountViewer",
    "workload-identity-pool-viewer": (
        "roles/iam.workloadIdentityPoolViewer"
    ),
    "service-usage-viewer": "roles/serviceusage.serviceUsageViewer",
}

github_preview_role_members = {}

for grant_name, role in github_preview_roles.items():
    github_preview_role_members[grant_name] = gcp.projects.IAMMember(
        f"oei-github-preview-{grant_name}",
        project=project,
        role=role,
        member=github_preview_member,
        opts=pulumi.ResourceOptions(
            protect=True,
            depends_on=[github_preview_service_account],
        ),
    )

pulumi.export("postgresInstanceName", postgres_instance.name)
pulumi.export(
    "datasetIds",
    {name: dataset.dataset_id for name, dataset in datasets.items()},
)
pulumi.export("dbtRepositoryName", dbt_repository.name)
pulumi.export("composerServiceAccountEmail", composer_service_account.email)
pulumi.export(
    "githubWorkloadIdentityProvider",
    github_identity_provider.name,
)
pulumi.export(
    "githubPreviewServiceAccountEmail",
    github_preview_service_account.email,
)
