from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import uuid

from tci.api.problem_details import ProblemCode
from tci.api.schemas.repository_connection import (
    CreateRepositorySnapshotRequest,
    serialize_code_snapshot_detail,
    serialize_sync_run_accepted,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    cancel_initial_snapshot,
    create_initial_snapshot,
    validate_initial_snapshot_request,
)
from tci.domain.services.get_code_snapshot_detail import get_code_snapshot_detail
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.infrastructure.queue.repository_ingestion_tasks import (
    RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
)
from tci.workers.celery_app import create_celery_app

from .repository_connections import _extract_workspace_id, _problem_response


router = APIRouter(
    prefix="/api/repository-connections/{connection_id}/snapshots",
    tags=["RepositorySnapshots"],
)


@router.post("")
def create_repository_snapshot_route(
    connection_id: uuid.UUID,
    request: Request,
    payload: CreateRepositorySnapshotRequest | None = None,
):
    workspace_id = _extract_workspace_id(request)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    try:
        command = CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            reason="manual_initial" if payload is None else payload.reason,
        )
        prepared_request = validate_initial_snapshot_request(
            command,
            dependencies=request.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        return _snapshot_problem_response(error)
    except LookupError:
        return JSONResponse(status_code=404, content={"detail": "저장소 연결을 찾을 수 없습니다."})

    settings = request.app.state.settings
    if not settings.redis_url:
        return JSONResponse(
            status_code=503,
            content={"detail": "스냅샷 작업 큐가 설정되지 않았습니다."},
        )

    sync_run = create_initial_snapshot(
        command,
        dependencies=request.app.state.dependencies,
        prepared_request=prepared_request,
    )
    try:
        create_celery_app(settings).send_task(
            RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
            kwargs={
                "workspace_id": str(workspace_id),
                "connection_id": str(connection_id),
                "sync_run_id": str(sync_run.id),
            },
        )
    except Exception:
        cancel_initial_snapshot(
            connection_id=connection_id,
            sync_run_id=sync_run.id,
            dependencies=request.app.state.dependencies,
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "스냅샷 작업 큐에 연결할 수 없습니다."},
        )

    return JSONResponse(
        status_code=202,
        content=serialize_sync_run_accepted(sync_run_id=sync_run.id),
    )


@router.get("/{snapshot_id}")
def get_repository_snapshot_route(
    connection_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    request: Request,
):
    workspace_id = _extract_workspace_id(request)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    try:
        detail = get_code_snapshot_detail(
            workspace_id=workspace_id,
            connection_id=connection_id,
            snapshot_id=snapshot_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError as error:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    return JSONResponse(status_code=200, content=serialize_code_snapshot_detail(detail))


def _snapshot_problem_response(error: RepositoryConnectionProblem) -> JSONResponse:
    if error.problem_code in {
        ProblemCode.CONNECTION_AUTH_FAILED,
        ProblemCode.DEFAULT_REF_NOT_FOUND,
    }:
        return JSONResponse(
            status_code=409,
            content={
                "code": error.problem_code.value,
                "message": error.detail,
            },
        )
    return _problem_response(error)
