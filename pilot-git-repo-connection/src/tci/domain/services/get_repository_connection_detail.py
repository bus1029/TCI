from __future__ import annotations

import uuid


def get_repository_connection_detail(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies
):
    if dependencies.session_factory is None:
        raise RuntimeError("저장소 연결을 조회하려면 데이터베이스 세션이 필요합니다.")

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        snapshot_repository = dependencies.code_snapshot_repository_factory(session)
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)
        connection = connection_repository.get(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        connection.latest_snapshot = snapshot_repository.get_latest_for_connection(
            connection_id=connection_id
        )
        connection.latest_sync_run = sync_run_repository.get_latest_for_connection(
            connection_id=connection_id
        )
        connection.latest_scope_rule = connection.active_scope_rule_version
        return connection
