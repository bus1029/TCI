from __future__ import annotations

import uuid

from tci.domain.services.repository_connection_support import build_connection_origin


def list_repository_connections(*, workspace_id: uuid.UUID, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError(
            "저장소 연결 목록을 조회하려면 데이터베이스 세션이 필요합니다."
        )

    with dependencies.session_factory() as session:
        if not _workspace_is_active(
            workspace_id=workspace_id,
            dependencies=dependencies,
            session=session,
        ):
            return []
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        connections = connection_repository.list_for_workspace(
            workspace_id=workspace_id
        )
        for connection in connections:
            connection.origin = build_connection_origin(connection)
        return connections


def _workspace_is_active(*, workspace_id: uuid.UUID, dependencies, session) -> bool:
    workspace_repository_factory = getattr(
        dependencies, "workspace_repository_factory", None
    )
    if workspace_repository_factory is None:
        return True
    workspace = workspace_repository_factory(session).get(workspace_id=workspace_id)
    if workspace is None:
        return True
    status = getattr(getattr(workspace, "status", None), "value", workspace.status)
    return status == "active"
