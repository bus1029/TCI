from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
import uuid

from tci.api.schemas.repository_scope import (
    SaveScopeRulesRequest,
    ScopeRuleResponse,
    serialize_scope_rule,
)
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.save_scope_rules import SaveScopeRulesCommand, save_scope_rules

from .repository_connections import _extract_workspace_id, _problem_response


router = APIRouter(
    prefix="/api/repository-connections/{connection_id}/scope-rules",
    tags=["RepositoryConnections"],
)


@router.post("", responses={200: {"model": ScopeRuleResponse}})
def save_scope_rules_route(
    connection_id: uuid.UUID,
    payload: SaveScopeRulesRequest,
    request: Request,
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
        scope_rule = save_scope_rules(
            SaveScopeRulesCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                include_paths=tuple(payload.include_paths),
                exclude_paths=tuple(payload.exclude_paths),
                allowed_file_types=tuple(payload.allowed_file_types),
                blocked_file_types=tuple(payload.blocked_file_types),
                max_file_size_bytes=payload.max_file_size_bytes,
                exclude_binary=payload.exclude_binary,
            ),
            dependencies=request.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        return _problem_response(error)
    except LookupError:
        return JSONResponse(
            status_code=404, content={"detail": "저장소 연결을 찾을 수 없습니다."}
        )

    return JSONResponse(status_code=200, content=serialize_scope_rule(scope_rule))
