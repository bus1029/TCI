from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
import uuid

from tci.api.operator_auth import require_operator_auth
from tci.api.problem_details import ProblemCode
from tci.api.schemas.repository_candidate import RepositoryCandidateListResponse
from tci.domain.services.list_repository_candidates import list_repository_candidates
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    parse_provider,
)


router = APIRouter(
    prefix="/api/repository-candidates",
    tags=["RepositoryCandidates"],
    dependencies=[Depends(require_operator_auth)],
)


@router.get("", responses={200: {"model": RepositoryCandidateListResponse}})
def list_repository_candidates_route(
    request: Request,
    provider: str | None = None,
    workspace_header: str | None = Header(
        default=None,
        alias="X-TCI-Workspace-Id",
        description="워크스페이스 UUID",
    ),
):
    workspace_id = _extract_workspace_id(workspace_header)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    try:
        parsed_provider = None if provider is None else parse_provider(provider)
        return list_repository_candidates(
            workspace_id=workspace_id,
            provider=parsed_provider,
            dependencies=request.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        return JSONResponse(
            status_code=400,
            content={
                "code": error.problem_code.value,
                "message": error.detail or "저장소 후보 조회 요청이 올바르지 않습니다.",
            },
        )


def _extract_workspace_id(raw_workspace_id: str | None) -> uuid.UUID | JSONResponse:
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
