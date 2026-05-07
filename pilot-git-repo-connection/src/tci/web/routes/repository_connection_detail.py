from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from tci.api.operator_auth import require_operator_auth
from tci.api.schemas.repository_connection import serialize_repository_connection_detail
from tci.domain.services.get_repository_connection_detail import (
    get_repository_connection_detail,
)
from tci.domain.services.workspace_lifecycle import (
    WorkspaceLifecycleProblem,
    ensure_active_workspace,
)

from ._common import build_template_context, extract_workspace_id_from_query


router = APIRouter(
    tags=["RepositoryConnectionDetailWeb"],
    include_in_schema=False,
    dependencies=[Depends(require_operator_auth)],
)


@router.get("/connections/{connection_id}")
def repository_connection_detail_page(connection_id: uuid.UUID, request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id

    try:
        connection = get_repository_connection_detail(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return PlainTextResponse("저장소 연결을 찾을 수 없습니다.", status_code=404)

    local_uploads = _list_local_uploads(request=request, workspace_id=workspace_id)
    template = request.app.state.templates
    return template.TemplateResponse(
        request=request,
        name="connections/detail.html",
        context=build_template_context(
            request,
            workspace_id=workspace_id,
            connection=serialize_repository_connection_detail(connection),
            local_uploads=local_uploads,
        ),
        status_code=200,
    )


def _list_local_uploads(*, request: Request, workspace_id: uuid.UUID) -> list[object]:
    with request.app.state.dependencies.session_factory() as session:
        workspace_repository_factory = getattr(
            request.app.state.dependencies, "workspace_repository_factory", None
        )
        if workspace_repository_factory is not None:
            try:
                ensure_active_workspace(
                    workspace_id=workspace_id,
                    workspace_repository=workspace_repository_factory(session),
                )
            except WorkspaceLifecycleProblem:
                return []
        repository = request.app.state.dependencies.local_upload_repository_factory(
            session
        )
        return repository.list_for_workspace(workspace_id=workspace_id)
