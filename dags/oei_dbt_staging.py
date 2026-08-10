from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator


IMAGE = (
    "europe-west9-docker.pkg.dev/"
    "oei-data-platform-lab-dev/"
    "oei-dbt-images/oei-dbt:v1"
)


with DAG(
    dag_id="oei_dbt_staging",
    description="Build and test the BigQuery staging layer with dbt",
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    default_args={
        "owner": "oei-lab",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["oei", "dbt", "staging"],
) as dag:
    dbt_build_staging = KubernetesPodOperator(
        task_id="dbt_build_staging",
        name="dbt-build-staging",
        namespace="composer-user-workloads",
        image=IMAGE,
        arguments=[
            "build",
            "--profiles-dir",
            "/app/profiles",
            "--select",
            "stg_orders",
        ],
        env_vars={
            "DBT_PROJECT": "oei-data-platform-lab-dev",
            "DBT_DATASET": "oei_staging",
            "DBT_LOCATION": "europe-west9",
        },
        config_file="/home/airflow/composer_kube_config",
        kubernetes_conn_id="kubernetes_default",
        get_logs=True,
        log_events_on_failure=True,
        do_xcom_push=False,
        on_finish_action="delete_pod",
        startup_timeout_seconds=600,
        execution_timeout=timedelta(minutes=15),
    )
