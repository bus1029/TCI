from __future__ import annotations

import uuid


def list_repository_connections(*, workspace_id: uuid.UUID, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("저장소 연결 목록을 조회하려면 데이터베이스 세션이 필요합니다.")

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        return connection_repository.list_for_workspace(workspace_id=workspace_id)
