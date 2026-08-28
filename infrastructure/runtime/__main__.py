"""Runtime ingestion infrastructure for the OEI data platform."""

import pulumi
import pulumi_gcp as gcp


gcp_config = pulumi.Config("gcp")
runtime_config = pulumi.Config()

project = gcp_config.require("project")
region = gcp_config.require("region")
postgres_password = runtime_config.require_secret("postgresPassword")
deploy_stack_name = runtime_config.require("deployStack")
composer_enabled = runtime_config.get_bool("composerEnabled") or False

deploy_stack = pulumi.StackReference(deploy_stack_name)
composer_service_account_email = deploy_stack.require_output(
    "composerServiceAccountEmail"
)

source_profile_id = "oei-postgres-source-dev"
destination_profile_id = "oei-bigquery-destination-dev"

source_connection_profile = gcp.datastream.ConnectionProfile(
    source_profile_id,
    connection_profile_id=source_profile_id,
    display_name=source_profile_id,
    project=project,
    location=region,
    postgresql_profile={
        "hostname": "34.155.201.32",
        "port": 5432,
        "username": "datastream_user",
        "password": postgres_password,
        "database": "oei_source",
    },
    opts=pulumi.ResourceOptions(
        import_=(
            f"projects/{project}/locations/{region}/"
            f"connectionProfiles/{source_profile_id}"
        ),
        protect=True,
        retain_on_delete=True,
        # Preserve the password already stored in Datastream during import.
        # Remove this ignore rule only for an intentional password rotation.
        ignore_changes=["postgresqlProfile.password"],
    ),
)

destination_connection_profile = gcp.datastream.ConnectionProfile(
    destination_profile_id,
    connection_profile_id=destination_profile_id,
    display_name=destination_profile_id,
    project=project,
    location=region,
    bigquery_profile={},
    opts=pulumi.ResourceOptions(
        import_=(
            f"projects/{project}/locations/{region}/"
            f"connectionProfiles/{destination_profile_id}"
        ),
        protect=True,
        retain_on_delete=True,
    ),
)

stream_id = "oei-orders-to-bigquery-dev"

orders_stream = gcp.datastream.Stream(
    stream_id,
    stream_id=stream_id,
    display_name=stream_id,
    project=project,
    location=region,
    source_config={
        "source_connection_profile": source_connection_profile.id,
        "postgresql_source_config": {
            "publication": "datastream_pub",
            "replication_slot": "datastream_slot",
            "max_concurrent_backfill_tasks": 16,
            "include_objects": {
                "postgresql_schemas": [
                    {
                        "schema": "public",
                        "postgresql_tables": [
                            {
                                "table": "orders",
                            },
                        ],
                    },
                ],
            },
        },
    },
    destination_config={
        "destination_connection_profile": (
            destination_connection_profile.id
        ),
        "bigquery_destination_config": {
            "data_freshness": "900s",
            "merge": {},
            "single_target_dataset": {
                "dataset_id": f"{project}:oei_einvoice",
            },
        },
    },
    backfill_all={},
    opts=pulumi.ResourceOptions(
        import_=(
            f"projects/{project}/locations/{region}/streams/{stream_id}"
        ),
        protect=True,
        retain_on_delete=True,
         # Preserve the stream's existing operational state during import.
        ignore_changes=["desiredState"],
    ),
)

composer_environment = None

if composer_enabled:
    composer_environment = gcp.composer.Environment(
        "oei-composer-dev",
        name="oei-composer-dev",
        project=project,
        region=region,
        labels={
            "environment": "dev",
            "purpose": "oei-lab",
        },
        config={
            "environment_size": "ENVIRONMENT_SIZE_SMALL",
            "node_config": {
                "service_account": composer_service_account_email,
            },
            "software_config": {
                "image_version": (
                    "composer-3-airflow-2.11.1-build.17"
                ),
            },
        },
        # Composer cannot be paused. It is intentionally removable when
        # composerEnabled is set to false to control lab costs.
        opts=pulumi.ResourceOptions(
            protect=False,
            retain_on_delete=False,
        ),
    )

    pulumi.export(
        "composerEnvironmentName",
        composer_environment.name,
    )

pulumi.export(
    "sourceConnectionProfileName",
    source_connection_profile.name,
)
pulumi.export(
    "destinationConnectionProfileName",
    destination_connection_profile.name,
)
pulumi.export("ordersStreamName", orders_stream.name)
pulumi.export("ordersStreamState", orders_stream.state)
