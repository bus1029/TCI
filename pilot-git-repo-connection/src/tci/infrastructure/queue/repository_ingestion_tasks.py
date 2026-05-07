from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import inspect
from pathlib import Path
import uuid

from celery import Celery  # type: ignore[import-untyped]
from celery.utils.log import get_task_logger  # type: ignore[import-untyped]
from kombu import Queue  # type: ignore[import-untyped]
from sqlalchemy.exc import IntegrityError

from tci.infrastructure.persistence.repository_event_cursor_repository import (
    RepositoryEventCursorDraft,
)

REPOSITORY_INGESTION_QUEUE_NAME = "repository_ingestion"

VERIFY_REPOSITORY_CONNECTION_TASK_NAME = (
    "tci.repository_ingestion.verify_repository_connection"
)
RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME = "tci.repository_ingestion.run_manual_snapshot_sync"
RUN_WEBHOOK_SYNC_TASK_NAME = "tci.repository_ingestion.run_webhook_sync"
RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME = (
    "tci.repository_ingestion.run_local_upload_snapshot"
)

REPOSITORY_INGESTION_TASK_ROUTES = {
    VERIFY_REPOSITORY_CONNECTION_TASK_NAME: {"queue": REPOSITORY_INGESTION_QUEUE_NAME},
    RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME: {"queue": REPOSITORY_INGESTION_QUEUE_NAME},
    RUN_WEBHOOK_SYNC_TASK_NAME: {"queue": REPOSITORY_INGESTION_QUEUE_NAME},
    RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME: {"queue": REPOSITORY_INGESTION_QUEUE_NAME},
}

logger = get_task_logger(__name__)
WEBHOOK_SYNC_RUNNING_REPLAY_STALE_AFTER = timedelta(minutes=15)
WEBHOOK_SYNC_PENDING_DISPATCH_STALE_AFTER = timedelta(minutes=15)


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
    _register_task_if_missing(
        app,
        task_name=RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME,
        func=_run_local_upload_snapshot_task,
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

    logger.info(
        "starting manual snapshot sync workspace_id=%s connection_id=%s sync_run_id=%s",
        workspace_id,
        connection_id,
        sync_run_id,
    )
    connection_uuid: uuid.UUID | None = None
    sync_run_uuid: uuid.UUID | None = None
    workspace_uuid: uuid.UUID | None = None
    dependencies = None
    try:
        workspace_uuid = uuid.UUID(workspace_id)
        connection_uuid = uuid.UUID(connection_id)
        sync_run_uuid = uuid.UUID(sync_run_id)
        dependencies = _build_snapshot_dependencies()
        build_command_type, build_service = _load_build_snapshot_service()
        build_service(
            build_command_type(
                workspace_id=workspace_uuid,
                connection_id=connection_uuid,
                sync_run_id=sync_run_uuid,
            ),
            dependencies=dependencies,
        )
    except Exception as error:
        _mark_manual_snapshot_sync_failed(
            dependencies=dependencies,
            workspace_id=workspace_uuid,
            connection_id=connection_uuid,
            sync_run_id=sync_run_uuid,
            error=error,
        )
        logger.exception(
            "manual snapshot sync failed workspace_id=%s connection_id=%s sync_run_id=%s error=%s",
            workspace_id,
            connection_id,
            sync_run_id,
            error,
        )
        if (
            dependencies is not None
            and connection_uuid is not None
            and sync_run_uuid is not None
        ):
            _dispatch_next_pending_sync_for_ref(
                dependencies=dependencies,
                connection_id=connection_uuid,
                completed_sync_run_id=sync_run_uuid,
            )
        raise
    _dispatch_next_pending_sync_for_ref(
        dependencies=dependencies,
        connection_id=connection_uuid,
        completed_sync_run_id=sync_run_uuid,
    )
    result["status"] = "completed"
    return result


def _mark_manual_snapshot_sync_failed(
    *,
    dependencies,
    workspace_id: uuid.UUID | None,
    connection_id: uuid.UUID | None,
    sync_run_id: uuid.UUID | None,
    error: Exception,
) -> None:
    if workspace_id is None or connection_id is None or sync_run_id is None:
        return

    if dependencies is None:
        try:
            dependencies = _build_manual_snapshot_failure_dependencies()
        except Exception:
            logger.exception(
                "manual snapshot failure fallback init failed "
                "workspace_id=%s connection_id=%s sync_run_id=%s",
                workspace_id,
                connection_id,
                sync_run_id,
            )
            return

    if getattr(dependencies, "session_factory", None) is None:
        return

    failure_message = (
        str(error) or "수동 스냅샷 동기화 준비 중 예기치 못한 오류가 발생했습니다."
    )
    failed_at = datetime.now(tz=UTC)
    try:
        with dependencies.session_factory() as session:
            sync_run_repository = dependencies.repository_sync_run_repository_factory(
                session
            )
            connection_repository = (
                dependencies.repository_connection_repository_factory(session)
            )
            sync_run = sync_run_repository.get(
                connection_id=connection_id,
                sync_run_id=sync_run_id,
            )
            if (
                sync_run is None
                or sync_run.status is not None
                and sync_run.status.value == "failed"
            ):
                return
            sync_run_repository.mark_failed(
                connection_id=connection_id,
                sync_run_id=sync_run_id,
                failure_code=_manual_snapshot_failure_code(error),
                failure_message=failure_message,
                completed_at=failed_at,
            )
            connection_repository.record_sync_failure(
                workspace_id=workspace_id,
                connection_id=connection_id,
                failed_at=failed_at,
                status=None,
            )
    except Exception:
        logger.warning(
            "best-effort manual snapshot failure bookkeeping failed "
            "workspace_id=%s connection_id=%s sync_run_id=%s",
            workspace_id,
            connection_id,
            sync_run_id,
        )


def _manual_snapshot_failure_code(error: Exception):
    from tci.infrastructure.persistence.models import SyncFailureCode

    problem_code = getattr(error, "problem_code", None)
    if (
        problem_code is not None
        and getattr(problem_code, "value", None) == "DEFAULT_REF_NOT_FOUND"
    ):
        return SyncFailureCode.REF_NOT_FOUND
    if (
        problem_code is not None
        and getattr(problem_code, "value", None) == "CONNECTION_AUTH_FAILED"
    ):
        return SyncFailureCode.AUTH_FAILED
    return SyncFailureCode.SNAPSHOT_WRITE_FAILED


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
    allow_running_retry = False

    try:
        if dependencies.session_factory is not None:
            with dependencies.session_factory() as session:
                connection_repository = (
                    dependencies.repository_connection_repository_factory(session)
                )
                connection = connection_repository.get_any(
                    connection_id=connection_uuid
                )
                if connection is None:
                    return result
                sync_run_repository = (
                    dependencies.repository_sync_run_repository_factory(session)
                )
                sync_run = sync_run_repository.get(
                    connection_id=connection_uuid,
                    sync_run_id=sync_run_uuid,
                )
                if (
                    getattr(getattr(sync_run, "status", None), "value", None)
                    == "running"
                ):
                    if not _running_sync_run_is_stale(sync_run):
                        result["status"] = "in_progress"
                        return result
                    allow_running_retry = True
                workspace_id = connection.workspace_id
            snapshot = _build_snapshot_for_worker(
                build_service,
                build_command_type(
                    workspace_id=workspace_id,
                    connection_id=connection_uuid,
                    sync_run_id=sync_run_uuid,
                ),
                dependencies=dependencies,
                allow_running_retry=allow_running_retry,
            )
            with dependencies.session_factory() as session:
                if event_id:
                    event_repository = dependencies.repository_event_repository_factory(
                        session
                    )
                    from tci.infrastructure.persistence.models import (
                        EventProcessingStatus,
                        ProcessingDecision,
                    )

                    event = event_repository.get(event_id=uuid.UUID(event_id))
                    if event is not None and event.sync_run_id == sync_run_uuid:
                        event_repository.update_processing(
                            event_id=uuid.UUID(event_id),
                            processing_decision=ProcessingDecision.QUEUED,
                            processing_status=EventProcessingStatus.COMPLETED,
                            processed_at=snapshot.created_at,
                            snapshot_id=snapshot.id,
                        )
    except Exception:
        if event_id and dependencies.session_factory is not None:
            failed_at = datetime.now(tz=UTC)
            with dependencies.session_factory() as session:
                event_repository = dependencies.repository_event_repository_factory(
                    session
                )
                event_cursor_repository = (
                    dependencies.repository_event_cursor_repository_factory(session)
                )
                sync_run_repository = (
                    dependencies.repository_sync_run_repository_factory(session)
                )
                connection_repository = (
                    dependencies.repository_connection_repository_factory(session)
                )
                from tci.infrastructure.persistence.models import (
                    EventProcessingStatus,
                    ProcessingDecision,
                    SyncFailureCode,
                    SyncRunStatus,
                    WebhookHealthState,
                )

                failed_event = event_repository.get(event_id=uuid.UUID(event_id))
                connection = connection_repository.get_any(
                    connection_id=connection_uuid
                )
                sync_run = sync_run_repository.get(
                    connection_id=connection_uuid,
                    sync_run_id=sync_run_uuid,
                )
                sync_run_succeeded = (
                    sync_run is not None and sync_run.status is SyncRunStatus.SUCCEEDED
                )
                if sync_run is not None and sync_run.status not in {
                    SyncRunStatus.FAILED,
                    SyncRunStatus.SUCCEEDED,
                }:
                    sync_run_repository.mark_failed(
                        connection_id=connection_uuid,
                        sync_run_id=sync_run_uuid,
                        failure_code=SyncFailureCode.SNAPSHOT_WRITE_FAILED,
                        failure_message="웹훅 스냅샷 처리 중 예기치 못한 오류가 발생했습니다.",
                        completed_at=failed_at,
                    )
                if (
                    failed_event is not None
                    and failed_event.sync_run_id == sync_run_uuid
                    and not sync_run_succeeded
                ):
                    event_repository.update_processing(
                        event_id=uuid.UUID(event_id),
                        processing_decision=ProcessingDecision.QUEUED,
                        processing_status=EventProcessingStatus.FAILED,
                        processed_at=failed_at,
                    )
                    _restore_event_cursor_after_failure(
                        connection_id=connection_uuid,
                        failed_event=failed_event,
                        event_repository=event_repository,
                        event_cursor_repository=event_cursor_repository,
                        restored_at=failed_at,
                    )
                    if connection is not None:
                        connection_repository.record_sync_failure(
                            workspace_id=connection.workspace_id,
                            connection_id=connection_uuid,
                            failed_at=failed_at,
                        )
                        connection_repository.record_processed_event(
                            connection_id=connection_uuid,
                            event_id=failed_event.id,
                            processed_at=failed_at,
                            health_state=WebhookHealthState.HEALTHY,
                        )
        _dispatch_next_pending_sync_for_ref(
            dependencies=dependencies,
            connection_id=connection_uuid,
            completed_sync_run_id=sync_run_uuid,
            event_id=uuid.UUID(event_id) if event_id else None,
        )
        raise
    if snapshot is not None:
        _dispatch_next_pending_sync_for_ref(
            dependencies=dependencies,
            connection_id=connection_uuid,
            completed_sync_run_id=sync_run_uuid,
            event_id=uuid.UUID(event_id) if event_id else None,
        )
        result["status"] = "completed"
        result["snapshot_id"] = str(snapshot.id)
    return result


def _run_local_upload_snapshot_task(
    *, workspace_id: str = "", local_upload_id: str = "", zip_path: str = ""
) -> dict[str, str]:
    result = _registered_task_result(
        task_name=RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME,
        connection_id="",
    )
    if local_upload_id:
        result["local_upload_id"] = local_upload_id
    if not workspace_id or not local_upload_id:
        return result

    workspace_uuid = uuid.UUID(workspace_id)
    local_upload_uuid = uuid.UUID(local_upload_id)
    dependencies = _build_snapshot_dependencies()
    zip_file: Path | None = None
    try:
        zip_file = _local_upload_queue_zip_path(
            runtime_root=dependencies.settings.runtime_root,
            local_upload_id=local_upload_uuid,
        )
        zip_bytes = zip_file.read_bytes()
        command_type, service = _load_create_local_upload_snapshot_service()
        snapshot_result = service(
            command_type(
                workspace_id=workspace_uuid,
                local_upload_id=local_upload_uuid,
                zip_bytes=zip_bytes,
            ),
            dependencies=dependencies,
        )
    except Exception as error:
        _mark_local_upload_task_failed(
            dependencies=dependencies,
            workspace_id=workspace_uuid,
            local_upload_id=local_upload_uuid,
            failure_code="local_upload_task_failed",
            failure_message="Local Upload 스냅샷 작업을 완료하지 못했습니다.",
        )
        logger.exception(
            "local upload snapshot task failed workspace_id=%s local_upload_id=%s error=%s",
            workspace_id,
            local_upload_id,
            error,
        )
        result["status"] = "failed"
        result["failure_code"] = "local_upload_task_failed"
        return result
    finally:
        if zip_file is not None:
            zip_file.unlink(missing_ok=True)

    result["status"] = "completed" if snapshot_result.succeeded else "failed"
    if snapshot_result.snapshot_id is not None:
        result["snapshot_id"] = str(snapshot_result.snapshot_id)
    if snapshot_result.failure_code is not None:
        result["failure_code"] = snapshot_result.failure_code
    return result


def _local_upload_queue_zip_path(
    *, runtime_root: Path, local_upload_id: uuid.UUID
) -> Path:
    queue_dir = (runtime_root / "local-upload-queue").resolve()
    candidate = (queue_dir / f"{local_upload_id}.zip").resolve()
    candidate.relative_to(queue_dir)
    if candidate.is_symlink():
        raise ValueError("Local Upload queue ZIP path must not be a symlink.")
    return candidate


def _mark_local_upload_task_failed(
    *,
    dependencies,
    workspace_id: uuid.UUID,
    local_upload_id: uuid.UUID,
    failure_code: str,
    failure_message: str,
) -> None:
    if getattr(dependencies, "session_factory", None) is None:
        return
    try:
        with dependencies.session_factory() as session:
            repository = dependencies.local_upload_repository_factory(session)
            upload = repository.get(
                workspace_id=workspace_id,
                local_upload_id=local_upload_id,
            )
            if upload is None:
                return
            if getattr(getattr(upload, "status", None), "value", upload.status) in {
                "succeeded",
                "failed",
            }:
                return
            repository.mark_failed(
                workspace_id=workspace_id,
                local_upload_id=local_upload_id,
                failure_code=failure_code,
                failure_message=failure_message,
            )
    except Exception:
        logger.warning(
            "best-effort Local Upload failure bookkeeping failed "
            "workspace_id=%s local_upload_id=%s",
            workspace_id,
            local_upload_id,
        )


def _dispatch_next_pending_sync_for_ref(
    *,
    dependencies,
    connection_id: uuid.UUID,
    completed_sync_run_id: uuid.UUID,
    event_id: uuid.UUID | None = None,
) -> None:
    if getattr(dependencies, "session_factory", None) is None or not getattr(
        dependencies.settings, "redis_url", None
    ):
        return

    with dependencies.session_factory() as session:
        sync_run_repository = dependencies.repository_sync_run_repository_factory(
            session
        )
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        completed_sync_run = sync_run_repository.get(
            connection_id=connection_id,
            sync_run_id=completed_sync_run_id,
        )
        connection = connection_repository.get_any(connection_id=connection_id)
        if completed_sync_run is None or connection is None:
            return
        if event_id is not None:
            event_repository = dependencies.repository_event_repository_factory(session)
            event = event_repository.get(event_id=event_id)
            if event is not None and event.sync_run_id != completed_sync_run_id:
                return
        if getattr(completed_sync_run.status, "value", None) not in {
            "succeeded",
            "failed",
        }:
            return
        from tci.infrastructure.persistence.models import (
            EventProcessingStatus,
            ProcessingDecision,
        )

        event_repository = dependencies.repository_event_repository_factory(session)
        pending_sync_run = sync_run_repository.get_active_for_requested_ref(
            connection_id=connection_id,
            trigger_type=completed_sync_run.trigger_type,
            requested_ref_type=completed_sync_run.requested_ref_type,
            requested_ref_name=completed_sync_run.requested_ref_name,
            requested_ref_key=completed_sync_run.requested_ref_key,
        )
        if (
            pending_sync_run is not None
            and pending_sync_run.id != completed_sync_run_id
            and pending_sync_run.trigger_event_id is not None
        ):
            if (
                pending_sync_run.dispatch_enqueued_at is not None
                and not _pending_dispatch_is_stale(
                    pending_sync_run.dispatch_enqueued_at
                )
            ):
                return
            pending_event = event_repository.get(
                event_id=pending_sync_run.trigger_event_id,
                for_update=True,
            )
            if (
                pending_event is not None
                and pending_event.sync_run_id == pending_sync_run.id
                and getattr(
                    pending_event.processing_status,
                    "value",
                    pending_event.processing_status,
                )
                == EventProcessingStatus.QUEUED.value
            ):
                task_name, task_kwargs = _pending_sync_task_payload(
                    workspace_id=connection.workspace_id,
                    connection_id=connection_id,
                    pending_sync_run=pending_sync_run,
                )
            else:
                return
        else:
            pending_sync_run = None

        if pending_sync_run is None:
            running_sync_run = sync_run_repository.get_running_for_requested_ref(
                connection_id=connection_id,
                requested_ref_type=completed_sync_run.requested_ref_type,
                requested_ref_name=completed_sync_run.requested_ref_name,
                requested_ref_key=completed_sync_run.requested_ref_key,
            )
            if (
                running_sync_run is not None
                and running_sync_run.id != completed_sync_run_id
            ):
                return
            blocked_sync_run = sync_run_repository.get_blocked_for_requested_ref(
                connection_id=connection_id,
                requested_ref_type=completed_sync_run.requested_ref_type,
                requested_ref_name=completed_sync_run.requested_ref_name,
                requested_ref_key=completed_sync_run.requested_ref_key,
            )
            if blocked_sync_run is None or blocked_sync_run.id == completed_sync_run_id:
                return
            if blocked_sync_run.trigger_event_id is None:
                return
            pending_event = event_repository.get(
                event_id=blocked_sync_run.trigger_event_id,
                for_update=True,
            )
            if (
                pending_event is None
                or pending_event.sync_run_id != blocked_sync_run.id
                or getattr(
                    pending_event.processing_status,
                    "value",
                    pending_event.processing_status,
                )
                != EventProcessingStatus.VALIDATED.value
            ):
                return
            released_at = datetime.now(tz=UTC)
            try:
                pending_sync_run = sync_run_repository.release_blocked_if_no_active(
                    connection_id=connection_id,
                    sync_run_id=blocked_sync_run.id,
                    released_at=released_at,
                )
            except (IntegrityError, ValueError):
                return
            if pending_sync_run is None:
                return
            event_repository.update_processing(
                event_id=blocked_sync_run.trigger_event_id,
                processing_decision=ProcessingDecision.QUEUED,
                processing_status=EventProcessingStatus.QUEUED,
                processed_at=released_at,
                sync_run_id=pending_sync_run.id,
            )
            task_name, task_kwargs = _pending_sync_task_payload(
                workspace_id=connection.workspace_id,
                connection_id=connection_id,
                pending_sync_run=pending_sync_run,
            )
        if not sync_run_repository.claim_dispatch_enqueued(
            connection_id=connection_id,
            sync_run_id=pending_sync_run.id,
            enqueued_at=datetime.now(tz=UTC),
            stale_before=datetime.now(tz=UTC)
            - WEBHOOK_SYNC_PENDING_DISPATCH_STALE_AFTER,
        ):
            return

    from tci.workers.celery_app import create_celery_app

    try:
        create_celery_app(dependencies.settings).send_task(
            task_name, kwargs=task_kwargs
        )
    except Exception:
        _mark_pending_sync_dispatch_failed(
            dependencies=dependencies,
            connection_id=connection_id,
            sync_run_id=pending_sync_run.id,
        )
        logger.error(
            "follow-up sync dispatch failed connection_id=%s sync_run_id=%s",
            connection_id,
            pending_sync_run.id,
        )
    else:
        return


def _build_snapshot_for_worker(
    build_service,
    command,
    *,
    dependencies,
    allow_running_retry: bool = False,
):
    if allow_running_retry:
        parameters = inspect.signature(build_service).parameters.values()
        if (
            any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters
            )
            or "_allow_running_retry" in inspect.signature(build_service).parameters
        ):
            return build_service(
                command,
                dependencies=dependencies,
                _allow_running_retry=True,
            )
    return build_service(command, dependencies=dependencies)


def _running_sync_run_is_stale(sync_run) -> bool:
    started_at = getattr(sync_run, "started_at", None)
    if started_at is None:
        return False
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    return datetime.now(tz=UTC) - started_at > WEBHOOK_SYNC_RUNNING_REPLAY_STALE_AFTER


def _pending_dispatch_is_stale(dispatch_enqueued_at: datetime) -> bool:
    if dispatch_enqueued_at.tzinfo is None:
        dispatch_enqueued_at = dispatch_enqueued_at.replace(tzinfo=UTC)
    return (
        datetime.now(tz=UTC) - dispatch_enqueued_at
        > WEBHOOK_SYNC_PENDING_DISPATCH_STALE_AFTER
    )


def _pending_sync_task_payload(
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    pending_sync_run,
) -> tuple[str, dict[str, str]]:
    trigger_type = getattr(pending_sync_run.trigger_type, "value", None)
    if trigger_type in {"manual_initial", "manual_refresh"}:
        return RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME, {
            "workspace_id": str(workspace_id),
            "connection_id": str(connection_id),
            "sync_run_id": str(pending_sync_run.id),
        }

    task_kwargs = {
        "connection_id": str(connection_id),
        "sync_run_id": str(pending_sync_run.id),
    }
    if pending_sync_run.trigger_event_id is not None:
        task_kwargs["event_id"] = str(pending_sync_run.trigger_event_id)
    return RUN_WEBHOOK_SYNC_TASK_NAME, task_kwargs


def _mark_pending_sync_dispatch_failed(
    *,
    dependencies,
    connection_id: uuid.UUID,
    sync_run_id: uuid.UUID,
) -> None:
    try:
        with dependencies.session_factory() as session:
            sync_run_repository = dependencies.repository_sync_run_repository_factory(
                session
            )
            connection_repository = (
                dependencies.repository_connection_repository_factory(session)
            )
            sync_run = sync_run_repository.get(
                connection_id=connection_id,
                sync_run_id=sync_run_id,
            )
            connection = connection_repository.get_any(connection_id=connection_id)
            if sync_run is None or connection is None:
                return
            from tci.infrastructure.persistence.models import (
                EventProcessingStatus,
                ProcessingDecision,
                SyncFailureCode,
            )

            failed_at = datetime.now(tz=UTC)
            sync_run_repository.mark_failed(
                connection_id=connection_id,
                sync_run_id=sync_run_id,
                failure_code=SyncFailureCode.QUEUE_DISPATCH_FAILED,
                failure_message="후속 스냅샷 작업 큐에 연결할 수 없습니다.",
                completed_at=failed_at,
            )
            if sync_run.trigger_event_id is not None:
                event_repository = dependencies.repository_event_repository_factory(
                    session
                )
                event_repository.update_processing(
                    event_id=sync_run.trigger_event_id,
                    processing_decision=ProcessingDecision.QUEUED,
                    processing_status=EventProcessingStatus.FAILED,
                    processed_at=failed_at,
                    sync_run_id=sync_run_id,
                )
                event_cursor_repository = (
                    dependencies.repository_event_cursor_repository_factory(session)
                )
                failed_event = event_repository.get(event_id=sync_run.trigger_event_id)
                if failed_event is not None:
                    _restore_event_cursor_after_failure(
                        connection_id=connection_id,
                        failed_event=failed_event,
                        event_repository=event_repository,
                        event_cursor_repository=event_cursor_repository,
                        restored_at=failed_at,
                    )
            connection_repository.record_sync_failure(
                workspace_id=connection.workspace_id,
                connection_id=connection_id,
                failed_at=failed_at,
                status=None,
            )
    except Exception:
        logger.warning(
            "best-effort follow-up sync dispatch failure bookkeeping failed "
            "connection_id=%s sync_run_id=%s",
            connection_id,
            sync_run_id,
        )


def _mark_pending_sync_dispatch_enqueued(
    *,
    dependencies,
    connection_id: uuid.UUID,
    sync_run_id: uuid.UUID,
) -> None:
    try:
        with dependencies.session_factory() as session:
            sync_run_repository = dependencies.repository_sync_run_repository_factory(
                session
            )
            sync_run = sync_run_repository.get(
                connection_id=connection_id,
                sync_run_id=sync_run_id,
            )
            if sync_run is None:
                return
            sync_run_repository.mark_dispatch_enqueued(
                connection_id=connection_id,
                sync_run_id=sync_run_id,
                enqueued_at=datetime.now(tz=UTC),
            )
    except Exception:
        logger.warning(
            "best-effort follow-up sync dispatch marker failed "
            "connection_id=%s sync_run_id=%s",
            connection_id,
            sync_run_id,
        )


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


def _build_manual_snapshot_failure_dependencies():
    from types import SimpleNamespace

    from tci.infrastructure.persistence.repository_connection_repository import (
        RepositoryConnectionRepository,
    )
    from tci.infrastructure.persistence.repository_sync_run_repository import (
        RepositorySyncRunRepository,
    )
    from tci.infrastructure.persistence.session import build_session_factory
    from tci.settings import get_settings

    settings = get_settings()
    return SimpleNamespace(
        session_factory=build_session_factory(settings),
        repository_connection_repository_factory=RepositoryConnectionRepository,
        repository_sync_run_repository_factory=RepositorySyncRunRepository,
    )


def _restore_event_cursor_after_failure(
    *,
    connection_id: uuid.UUID,
    failed_event,
    event_repository,
    event_cursor_repository,
    restored_at: datetime,
) -> None:
    fallback_event = next(
        (
            candidate
            for candidate in event_repository.list_for_connection(
                connection_id=connection_id
            )
            if candidate.id != failed_event.id
            and candidate.target_key == failed_event.target_key
            and candidate.target_head_sha is not None
            and getattr(
                candidate.processing_decision, "value", candidate.processing_decision
            )
            == "queued"
            and getattr(
                candidate.processing_status, "value", candidate.processing_status
            )
            != "failed"
            and getattr(candidate, "sync_run_id", None) is not None
        ),
        None,
    )
    if fallback_event is None:
        event_cursor_repository.delete_if_latest_event(
            connection_id=connection_id,
            target_key=failed_event.target_key,
            latest_event_id=failed_event.id,
        )
        return
    event_cursor_repository.upsert(
        RepositoryEventCursorDraft(
            id=uuid.uuid4(),
            connection_id=connection_id,
            target_key=fallback_event.target_key,
            latest_head_sha=fallback_event.target_head_sha,
            latest_event_id=fallback_event.id,
            updated_at=restored_at,
        )
    )


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


def _load_create_local_upload_snapshot_service():
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    return CreateLocalUploadSnapshotCommand, create_local_upload_snapshot
