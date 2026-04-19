from __future__ import annotations

from collections.abc import Callable
import uuid

from celery import Celery
from kombu import Queue


REPOSITORY_INGESTION_QUEUE_NAME = "repository_ingestion"

VERIFY_REPOSITORY_CONNECTION_TASK_NAME = (
    "tci.repository_ingestion.verify_repository_connection"
)
RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME = (
    "tci.repository_ingestion.run_manual_snapshot_sync"
)
RUN_WEBHOOK_SYNC_TASK_NAME = "tci.repository_ingestion.run_webhook_sync"

REPOSITORY_INGESTION_TASK_ROUTES = {
    VERIFY_REPOSITORY_CONNECTION_TASK_NAME: {
        "queue": REPOSITORY_INGESTION_QUEUE_NAME
    },
    RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME: {
        "queue": REPOSITORY_INGESTION_QUEUE_NAME
    },
    RUN_WEBHOOK_SYNC_TASK_NAME: {"queue": REPOSITORY_INGESTION_QUEUE_NAME},
}


def build_repository_ingestion_queues() -> tuple[Queue, ...]:
    return (Queue(REPOSITORY_INGESTION_QUEUE_NAME),)


def register_repository_ingestion_tasks(app: Celery) -> None:
    # Phase 2에서는 실제 서비스 로직보다 stable task name을 worker에 먼저 고정하는 것이 목적이다.
    _register_task_if_missing(
        app,
        task_name=VERIFY_REPOSITORY_CONNECTION_TASK_NAME,
        func=_verify_repository_connection_task,
    )
    _register_task_if_missing(
        app,
        task_name=RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
        func=_run_manual_snapshot_sync_task,
    )
    _register_task_if_missing(
        app,
        task_name=RUN_WEBHOOK_SYNC_TASK_NAME,
        func=_run_webhook_sync_task,
    )


def _register_task_if_missing(
    app: Celery,
    *,
    task_name: str,
    func: Callable[..., dict[str, str]],
) -> None:
    if task_name in app.tasks:
        return
    app.task(name=task_name)(func)


def _verify_repository_connection_task(
    *, workspace_id: str = "", connection_id: str = ""
) -> dict[str, str]:
    result = _registered_task_result(
        task_name=VERIFY_REPOSITORY_CONNECTION_TASK_NAME,
        connection_id=connection_id,
    )
    if not workspace_id or not connection_id:
        return result

    dependencies = _build_verify_dependencies()
    verify_command_type, verify_service = _load_verify_service()

    verified_connection = verify_service(
        verify_command_type(
            workspace_id=uuid.UUID(workspace_id),
            connection_id=uuid.UUID(connection_id),
        ),
        dependencies=dependencies,
    )
    result["status"] = verified_connection.status.value
    return result


def _run_manual_snapshot_sync_task(*, connection_id: str = "") -> dict[str, str]:
    return _registered_task_result(
        task_name=RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
        connection_id=connection_id,
    )


def _run_webhook_sync_task(*, connection_id: str = "") -> dict[str, str]:
    return _registered_task_result(
        task_name=RUN_WEBHOOK_SYNC_TASK_NAME,
        connection_id=connection_id,
    )


def _registered_task_result(*, task_name: str, connection_id: str) -> dict[str, str]:
    return {
        "status": "registered",
        "task_name": task_name,
        "connection_id": connection_id,
    }


def _build_verify_dependencies():
    from tci.app import build_app_dependencies
    from tci.settings import get_settings

    return build_app_dependencies(get_settings())


def _load_verify_service():
    from tci.domain.services.verify_repository_connection import (
        VerifyRepositoryConnectionCommand,
        verify_repository_connection,
    )

    return VerifyRepositoryConnectionCommand, verify_repository_connection
