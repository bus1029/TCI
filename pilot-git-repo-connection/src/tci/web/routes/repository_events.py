from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from tci.api.operator_auth import require_operator_auth
from tci.api.schemas.repository_connection import (
    serialize_repository_connection_detail,
    serialize_repository_event,
)
from tci.domain.services.get_repository_connection_detail import (
    get_repository_connection_detail,
)
from tci.domain.services.list_repository_events import list_repository_events
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)

from ._common import build_template_context, extract_workspace_id_from_query


router = APIRouter(
    tags=["RepositoryEventsWeb"],
    include_in_schema=False,
    dependencies=[Depends(require_operator_auth)],
)


@router.get("/connections/{connection_id}/events")
def repository_events_page(connection_id: uuid.UUID, request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id

    try:
        connection = get_repository_connection_detail(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
        events = list_repository_events(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return PlainTextResponse("저장소 연결을 찾을 수 없습니다.", status_code=404)
    except RepositoryConnectionProblem as error:
        return PlainTextResponse(str(error.detail), status_code=400)

    template = request.app.state.templates
    return template.TemplateResponse(
        request=request,
        name="connections/events.html",
        context=build_template_context(
            request,
            workspace_id=workspace_id,
            connection=serialize_repository_connection_detail(connection),
            events=[serialize_repository_event(event) for event in events],
        ),
        status_code=200,
    )
