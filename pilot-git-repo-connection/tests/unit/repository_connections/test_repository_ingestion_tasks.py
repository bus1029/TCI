from __future__ import annotations


def test_repository_ingestion_tasks_expose_stable_task_names_and_queue_names() -> None:
    from tci.infrastructure.queue.repository_ingestion_tasks import (
        REPOSITORY_INGESTION_QUEUE_NAME,
        REPOSITORY_INGESTION_TASK_ROUTES,
        RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
        RUN_WEBHOOK_SYNC_TASK_NAME,
        VERIFY_REPOSITORY_CONNECTION_TASK_NAME,
    )

    assert REPOSITORY_INGESTION_QUEUE_NAME == "repository_ingestion"
    assert VERIFY_REPOSITORY_CONNECTION_TASK_NAME == (
        "tci.repository_ingestion.verify_repository_connection"
    )
    assert RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME == (
        "tci.repository_ingestion.run_manual_snapshot_sync"
    )
    assert RUN_WEBHOOK_SYNC_TASK_NAME == "tci.repository_ingestion.run_webhook_sync"
    assert REPOSITORY_INGESTION_TASK_ROUTES == {
        VERIFY_REPOSITORY_CONNECTION_TASK_NAME: {
            "queue": REPOSITORY_INGESTION_QUEUE_NAME
        },
        RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME: {
            "queue": REPOSITORY_INGESTION_QUEUE_NAME
        },
        RUN_WEBHOOK_SYNC_TASK_NAME: {
            "queue": REPOSITORY_INGESTION_QUEUE_NAME
        },
    }
