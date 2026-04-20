from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from tci.api.schemas.repository_connection import serialize_repository_connection_detail
from tci.domain.services.get_repository_connection_detail import (
    get_repository_connection_detail,
)

from ._common import build_template_context, extract_workspace_id_from_query


router = APIRouter(tags=["RepositoryConnectionDetailWeb"], include_in_schema=False)


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

    template = request.app.state.templates
    return template.TemplateResponse(
        request=request,
        name="connections/detail.html",
        context=build_template_context(
            request,
            workspace_id=workspace_id,
            connection=serialize_repository_connection_detail(connection),
        ),
        status_code=200,
    )
