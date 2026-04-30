from __future__ import annotations

import uuid

from tci.domain.services.repository_connection_support import build_connection_origin


def list_repository_connections(*, workspace_id: uuid.UUID, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError(
            "저장소 연결 목록을 조회하려면 데이터베이스 세션이 필요합니다."
        )

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        connections = connection_repository.list_for_workspace(
            workspace_id=workspace_id
        )
        for connection in connections:
            connection.origin = build_connection_origin(connection)
        return connections
