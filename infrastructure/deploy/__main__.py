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

pulumi.export("postgresInstanceName", postgres_instance.name)
pulumi.export(
    "datasetIds",
    {name: dataset.dataset_id for name, dataset in datasets.items()},
)
pulumi.export("dbtRepositoryName", dbt_repository.name)
pulumi.export("composerServiceAccountEmail", composer_service_account.email)
