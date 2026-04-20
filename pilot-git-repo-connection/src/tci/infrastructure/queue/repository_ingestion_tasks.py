from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
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


def _run_manual_snapshot_sync_task(
    *, workspace_id: str = "", connection_id: str = "", sync_run_id: str = ""
) -> dict[str, str]:
    result = _registered_task_result(
        task_name=RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
        connection_id=connection_id,
        sync_run_id=sync_run_id,
    )
    if not workspace_id or not connection_id or not sync_run_id:
        return result

    dependencies = _build_snapshot_dependencies()
    build_command_type, build_service = _load_build_snapshot_service()
    build_service(
        build_command_type(
            workspace_id=uuid.UUID(workspace_id),
            connection_id=uuid.UUID(connection_id),
            sync_run_id=uuid.UUID(sync_run_id),
        ),
        dependencies=dependencies,
    )
    result["status"] = "completed"
    return result


def _run_webhook_sync_task(
    *, connection_id: str = "", event_id: str = "", sync_run_id: str = ""
) -> dict[str, str]:
    result = _registered_task_result(
        task_name=RUN_WEBHOOK_SYNC_TASK_NAME,
        connection_id=connection_id,
    )
    if event_id:
        result["event_id"] = event_id
    if sync_run_id:
        result["sync_run_id"] = sync_run_id
    if not connection_id or not sync_run_id:
        return result

    dependencies = _build_snapshot_dependencies()
    build_command_type, build_service = _load_build_snapshot_service()
    connection_uuid = uuid.UUID(connection_id)
    sync_run_uuid = uuid.UUID(sync_run_id)
    snapshot = None

    try:
        if dependencies.session_factory is not None:
            with dependencies.session_factory() as session:
                connection_repository = dependencies.repository_connection_repository_factory(
                    session
                )
                connection = connection_repository.get_any(connection_id=connection_uuid)
                if connection is None:
                    return result
                snapshot = build_service(
                    build_command_type(
                        workspace_id=connection.workspace_id,
                        connection_id=connection_uuid,
                        sync_run_id=sync_run_uuid,
                    ),
                    dependencies=dependencies,
                )
                if event_id:
                    event_repository = dependencies.repository_event_repository_factory(session)
                    from tci.infrastructure.persistence.models import (
                        EventProcessingStatus,
                        ProcessingDecision,
                    )

                    event_repository.update_processing(
                        event_id=uuid.UUID(event_id),
                        processing_decision=ProcessingDecision.QUEUED,
                        processing_status=EventProcessingStatus.COMPLETED,
                        processed_at=snapshot.created_at,
                        snapshot_id=snapshot.id,
                    )
    except Exception:
        if event_id and dependencies.session_factory is not None:
            with dependencies.session_factory() as session:
                event_repository = dependencies.repository_event_repository_factory(session)
                from tci.infrastructure.persistence.models import (
                    EventProcessingStatus,
                    ProcessingDecision,
                )

                event_repository.update_processing(
                    event_id=uuid.UUID(event_id),
                    processing_decision=ProcessingDecision.QUEUED,
                    processing_status=EventProcessingStatus.FAILED,
                    processed_at=datetime.now(tz=UTC),
                )
        raise
    if snapshot is not None:
        result["status"] = "completed"
        result["snapshot_id"] = str(snapshot.id)
    return result


def _registered_task_result(
    *, task_name: str, connection_id: str, sync_run_id: str = ""
) -> dict[str, str]:
    result = {
        "status": "registered",
        "task_name": task_name,
        "connection_id": connection_id,
    }
    if sync_run_id:
        result["sync_run_id"] = sync_run_id
    return result


def _build_verify_dependencies():
    from tci.app import build_app_dependencies
    from tci.settings import get_settings

    return build_app_dependencies(get_settings())


def _build_snapshot_dependencies():
    from tci.app import build_app_dependencies
    from tci.settings import get_settings

    return build_app_dependencies(get_settings())


def _load_verify_service():
    from tci.domain.services.verify_repository_connection import (
        VerifyRepositoryConnectionCommand,
        verify_repository_connection,
    )

    return VerifyRepositoryConnectionCommand, verify_repository_connection


def _load_build_snapshot_service():
    from tci.domain.services.build_code_snapshot import (
        BuildCodeSnapshotCommand,
        build_code_snapshot,
    )

    return BuildCodeSnapshotCommand, build_code_snapshot
