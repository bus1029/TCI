from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tci.api.schemas.repository_connection import serialize_repository_event
from tci.domain.services.list_repository_events import list_repository_events

from .repository_connections import _extract_workspace_id


router = APIRouter(
    prefix="/api/repository-connections/{connection_id}/events",
    tags=["RepositoryEvents"],
)


@router.get("")
def list_repository_events_route(connection_id: uuid.UUID, request: Request):
    workspace_id = _extract_workspace_id(request)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id

    try:
        events = list_repository_events(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError as error:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    return JSONResponse(
        status_code=200,
        content={"items": [serialize_repository_event(event) for event in events]},
    )
