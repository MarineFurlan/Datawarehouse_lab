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

pulumi.export(
    "datasetIds",
    {name: dataset.dataset_id for name, dataset in datasets.items()},
)
pulumi.export("dbtRepositoryName", dbt_repository.name)
pulumi.export("composerServiceAccountEmail", composer_service_account.email)
