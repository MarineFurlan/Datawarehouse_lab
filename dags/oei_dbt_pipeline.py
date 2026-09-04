from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator


IMAGE = (
    "europe-west9-docker.pkg.dev/"
    "oei-data-platform-lab-dev/"
    "oei-dbt-images/oei-dbt"
    "@sha256:6f75c3b53ac319fb6aa96996f20b341a76129efbb9812075913304a2ee0a7eab"
)

ENV_VARS = {
    "DBT_PROJECT": "oei-data-platform-lab-dev",
    "DBT_DATASET": "oei_staging",
    "DBT_LOCATION": "europe-west9",
}


with DAG(
    dag_id="oei_dbt_pipeline",
    description="Build and test BigQuery staging and marts with dbt",
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    default_args={
        "owner": "oei-lab",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["oei", "dbt", "staging", "marts"],
) as dag:
    dbt_build_staging = KubernetesPodOperator(
        task_id="dbt_build_staging",
        name="dbt-build-staging",
        namespace="composer-user-workloads",
        image=IMAGE,
        image_pull_policy="IfNotPresent",
        arguments=[
            "build",
            "--profiles-dir",
            "/app/profiles",
            "--select",
            "stg_orders",
            "--fail-fast",
            "--no-partial-parse",
        ],
        env_vars=ENV_VARS,
        config_file="/home/airflow/composer_kube_config",
        kubernetes_conn_id="kubernetes_default",
        get_logs=True,
        log_events_on_failure=True,
        do_xcom_push=False,
        on_finish_action="delete_pods",
        startup_timeout_seconds=600,
        execution_timeout=timedelta(minutes=15),
    )

    dbt_build_marts = KubernetesPodOperator(
        task_id="dbt_build_marts",
        name="dbt-build-marts",
        namespace="composer-user-workloads",
        image=IMAGE,
        image_pull_policy="IfNotPresent",
        arguments=[
            "build",
            "--profiles-dir",
            "/app/profiles",
            "--select",
            "orders",
            "order_reconciliation_feed",
            "--fail-fast",
            "--no-partial-parse",
        ],
        env_vars=ENV_VARS,
        config_file="/home/airflow/composer_kube_config",
        kubernetes_conn_id="kubernetes_default",
        get_logs=True,
        log_events_on_failure=True,
        do_xcom_push=False,
        on_finish_action="delete_pod",
        startup_timeout_seconds=600,
        execution_timeout=timedelta(minutes=15),
    )

    dbt_build_staging >> dbt_build_marts