from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import uuid

from tci.api.problem_details import ProblemCode, problem_details_for
from tci.api.schemas.repository_connection import (
    CreateRepositoryConnectionRequest,
    UpdateRepositoryConnectionRequest,
    serialize_repository_connection,
    serialize_repository_connection_detail,
    serialize_verification_accepted,
)
from tci.infrastructure.queue.repository_ingestion_tasks import (
    VERIFY_REPOSITORY_CONNECTION_TASK_NAME,
)
from tci.workers.celery_app import create_celery_app
from tci.domain.services.create_repository_connection import (
    CreateRepositoryConnectionCommand,
    create_repository_connection,
)
from tci.domain.services.get_repository_connection_detail import (
    get_repository_connection_detail,
)
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.domain.services.update_default_ref import (
    UpdateDefaultRefCommand,
    update_default_ref,
)


router = APIRouter(prefix="/api/repository-connections", tags=["RepositoryConnections"])


@router.post("")
def create_repository_connection_route(
    payload: CreateRepositoryConnectionRequest, request: Request
):
    workspace_id = _extract_workspace_id(request)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    try:
        connection = create_repository_connection(
            CreateRepositoryConnectionCommand(
                workspace_id=workspace_id,
                planning_input_reference_id=payload.planning_input_reference_id,
                provider=payload.provider,
                remote_url=payload.remote_url,
                transport=payload.transport,
                default_ref_type=payload.default_ref_type,
                default_ref_name=payload.default_ref_name,
                credential_type=payload.credential.credential_type,
                credential_secret=payload.credential.secret,
                credential_fingerprint=payload.credential.fingerprint,
            ),
            dependencies=request.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        return _problem_response(error)

    return JSONResponse(status_code=201, content=serialize_repository_connection(connection))


@router.get("/{connection_id}")
def get_repository_connection_route(connection_id: uuid.UUID, request: Request):
    workspace_id = _extract_workspace_id(request)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    try:
        connection = get_repository_connection_detail(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return JSONResponse(status_code=404, content={"detail": "저장소 연결을 찾을 수 없습니다."})

    return serialize_repository_connection_detail(connection)


@router.patch("/{connection_id}")
def update_repository_connection_route(
    connection_id: uuid.UUID,
    payload: UpdateRepositoryConnectionRequest,
    request: Request,
):
    workspace_id = _extract_workspace_id(request)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    if payload.default_ref_type is None or payload.default_ref_name is None:
        return _problem_response(
            RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "기본 ref를 수정하려면 defaultRefType과 defaultRefName이 모두 필요합니다.",
            )
        )

    try:
        connection = update_default_ref(
            UpdateDefaultRefCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                default_ref_type=payload.default_ref_type,
                default_ref_name=payload.default_ref_name,
            ),
            dependencies=request.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        return _problem_response(error)
    except LookupError:
        return JSONResponse(status_code=404, content={"detail": "저장소 연결을 찾을 수 없습니다."})

    return serialize_repository_connection(connection)


@router.post("/{connection_id}/verify")
def verify_repository_connection_route(connection_id: uuid.UUID, request: Request):
    workspace_id = _extract_workspace_id(request)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    try:
        get_repository_connection_detail(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return JSONResponse(status_code=404, content={"detail": "저장소 연결을 찾을 수 없습니다."})

    settings = request.app.state.settings
    if settings.redis_url:
        try:
            create_celery_app(settings).send_task(
                VERIFY_REPOSITORY_CONNECTION_TASK_NAME,
                kwargs={"connection_id": str(connection_id)},
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"detail": "검증 작업 큐에 연결할 수 없습니다."},
            )

    return JSONResponse(
        status_code=202,
        content=serialize_verification_accepted(connection_id=connection_id),
    )


def _problem_response(error: RepositoryConnectionProblem) -> JSONResponse:
    definition = problem_details_for(error.problem_code)
    return JSONResponse(
        status_code=definition.status_code,
        content={
            "code": error.problem_code.value,
            "message": error.detail or definition.message,
        },
    )


def _extract_workspace_id(request: Request) -> uuid.UUID | JSONResponse:
    raw_workspace_id = request.headers.get("X-TCI-Workspace-Id")
    if not raw_workspace_id:
        return JSONResponse(
            status_code=400,
            content={
                "code": ProblemCode.INVALID_INPUT.value,
                "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
            },
        )

    try:
        return uuid.UUID(raw_workspace_id)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={
                "code": ProblemCode.INVALID_INPUT.value,
                "message": "X-TCI-Workspace-Id는 UUID 형식이어야 합니다.",
            },
        )
