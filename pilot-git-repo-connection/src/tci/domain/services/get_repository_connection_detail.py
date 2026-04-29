from __future__ import annotations

import uuid

from tci.domain.services.rotate_webhook_secret import (
    build_webhook_secret_rotation_projection,
)


def get_repository_connection_detail(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies
):
    if dependencies.session_factory is None:
        raise RuntimeError("저장소 연결을 조회하려면 데이터베이스 세션이 필요합니다.")

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        event_repository = dependencies.repository_event_repository_factory(session)
        webhook_secret_repository = dependencies.webhook_secret_repository_factory(
            session
        )
        snapshot_repository = dependencies.code_snapshot_repository_factory(session)
        sync_run_repository = dependencies.repository_sync_run_repository_factory(
            session
        )
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
        connection.last_processed_event = (
            None
            if getattr(connection, "last_processed_event_id", None) is None
            else event_repository.get(event_id=connection.last_processed_event_id)
        )
        rotation_projection = build_webhook_secret_rotation_projection(
            connection_id=connection_id,
            webhook_secret_repository=webhook_secret_repository,
            event_repository=event_repository,
        )
        connection.last_previous_secret_accepted_at = (
            rotation_projection.last_previous_secret_accepted_at
        )
        connection.previous_secret_deliveries_during_grace = (
            rotation_projection.previous_secret_deliveries_during_grace
        )
        connection.webhook_secret_grace_until = rotation_projection.grace_until
        return connection
