from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True, slots=True)
class CodeSnapshotDetail:
    snapshot: object
    planning_input_reference: object | None
    trigger_event_id: uuid.UUID | None = None


def get_code_snapshot_detail(
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    dependencies,
):
    if dependencies.session_factory is None:
        raise RuntimeError("스냅샷을 조회하려면 데이터베이스 세션이 필요합니다.")

    with dependencies.session_factory() as session:
        if not _workspace_is_active(
            workspace_id=workspace_id,
            dependencies=dependencies,
            session=session,
        ):
            raise LookupError("코드 스냅샷을 찾을 수 없습니다.")
        connection_repository = dependencies.repository_connection_repository_factory(
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
        snapshot = snapshot_repository.get(
            connection_id=connection_id,
            snapshot_id=snapshot_id,
        )
        if snapshot is None:
            raise LookupError("코드 스냅샷을 찾을 수 없습니다.")
        sync_run = sync_run_repository.get(
            connection_id=connection_id,
            sync_run_id=snapshot.sync_run_id,
        )
        return CodeSnapshotDetail(
            snapshot=snapshot,
            planning_input_reference=_matching_workspace_planning_input_reference(
                connection
            ),
            trigger_event_id=None if sync_run is None else sync_run.trigger_event_id,
        )


def _matching_workspace_planning_input_reference(connection):
    planning_input_reference = getattr(connection, "planning_input_reference", None)
    if planning_input_reference is None:
        return None
    if getattr(planning_input_reference, "workspace_id", None) != getattr(
        connection, "workspace_id", None
    ):
        return None
    return planning_input_reference


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
