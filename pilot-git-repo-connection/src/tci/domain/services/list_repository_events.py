from __future__ import annotations

import uuid


def list_repository_events(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies
):
    if dependencies.session_factory is None:
        raise RuntimeError("저장소 이벤트를 조회하려면 데이터베이스 세션이 필요합니다.")

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        connection = connection_repository.get(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        event_repository = dependencies.repository_event_repository_factory(session)
        return event_repository.list_for_connection(connection_id=connection_id)
