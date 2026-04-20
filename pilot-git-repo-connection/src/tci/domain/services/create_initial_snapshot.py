from __future__ import annotations

from dataclasses import dataclass
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.infrastructure.persistence.models import RefType, RepositoryConnectionStatus, SyncTriggerType
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunDraft,
)


@dataclass(frozen=True, slots=True)
class CreateInitialSnapshotCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    reason: str = "manual_initial"


@dataclass(frozen=True, slots=True)
class PreparedInitialSnapshotRequest:
    connection_id: uuid.UUID
    trigger_type: SyncTriggerType
    requested_ref_type: RefType
    requested_ref_name: str


def create_initial_snapshot(command, *, dependencies, prepared_request=None):
    if dependencies.session_factory is None:
        raise RuntimeError("초기 스냅샷을 생성하려면 데이터베이스 세션이 필요합니다.")

    prepared = prepared_request or validate_initial_snapshot_request(
        command,
        dependencies=dependencies,
    )
    with dependencies.session_factory() as session:
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)
        return sync_run_repository.create_pending(
            RepositorySyncRunDraft(
                id=uuid.uuid4(),
                connection_id=prepared.connection_id,
                trigger_type=prepared.trigger_type,
                requested_ref_type=prepared.requested_ref_type,
                requested_ref_name=prepared.requested_ref_name,
            )
        )


def validate_initial_snapshot_request(command, *, dependencies) -> PreparedInitialSnapshotRequest:
    if dependencies.session_factory is None:
        raise RuntimeError("초기 스냅샷을 검증하려면 데이터베이스 세션이 필요합니다.")

    trigger_type = _parse_trigger_type(command.reason)
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        connection = connection_repository.get(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        if connection.status is RepositoryConnectionStatus.REAUTH_REQUIRED:
            raise RepositoryConnectionProblem(
                ProblemCode.CONNECTION_AUTH_FAILED,
                "재인증이 필요한 연결은 새 스냅샷을 시작할 수 없습니다.",
            )
        if connection.status is RepositoryConnectionStatus.REF_MISSING:
            raise RepositoryConnectionProblem(
                ProblemCode.DEFAULT_REF_NOT_FOUND,
                "기본 ref가 유효하지 않아 새 스냅샷을 시작할 수 없습니다.",
            )
        return PreparedInitialSnapshotRequest(
            connection_id=connection.id,
            trigger_type=trigger_type,
            requested_ref_type=RefType(connection.default_ref_type.value),
            requested_ref_name=connection.default_ref_name,
        )


def cancel_initial_snapshot(
    *, connection_id: uuid.UUID, sync_run_id: uuid.UUID, dependencies
) -> None:
    if dependencies.session_factory is None:
        raise RuntimeError("초기 스냅샷을 취소하려면 데이터베이스 세션이 필요합니다.")

    with dependencies.session_factory() as session:
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)
        sync_run_repository.delete_pending(
            connection_id=connection_id,
            sync_run_id=sync_run_id,
        )


def _parse_trigger_type(raw_reason: str) -> SyncTriggerType:
    if raw_reason == "manual_initial":
        return SyncTriggerType.MANUAL_INITIAL
    if raw_reason == "manual_refresh":
        return SyncTriggerType.MANUAL_REFRESH
    raise RepositoryConnectionProblem(
        ProblemCode.INVALID_INPUT,
        "reason은 manual_initial 또는 manual_refresh여야 합니다.",
    )
