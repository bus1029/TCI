from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
import uuid

from tci.domain.services.failure_messages import bounded_failure_message
from tci.infrastructure.persistence.models import (
    WorkspaceDeletionPurgeStatus,
    WorkspaceStatus,
)
from tci.infrastructure.persistence.workspace_repository import (
    WorkspaceDeletionRecordDraft,
)


AUTHORIZED_DELETE_ROLES = {"owner", "admin"}


@dataclass(frozen=True, slots=True)
class WorkspaceDeleteProblem(Exception):
    code: str
    message: str
    remediation_action: str
    status_code: int

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class WorkspaceDeletionImpact:
    workspace_id: uuid.UUID
    repository_connection_count: int
    local_upload_count: int
    snapshot_count: int
    project_content_will_be_removed: bool
    audit_metadata_will_remain: bool
    confirmation: str


@dataclass(frozen=True, slots=True)
class DeleteWorkspaceCommand:
    workspace_id: uuid.UUID
    confirmation: str
    deleted_by: str
    operator_role: str | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceDeletionResult:
    workspace_id: uuid.UUID
    status: str
    deletion_record_id: uuid.UUID | None
    audit_metadata_retained: bool
    project_content_removed: bool
    message: str
    status_code: int = 202


def get_workspace_deletion_impact(
    *,
    workspace_id: uuid.UUID,
    operator_role: str | None,
    dependencies,
) -> WorkspaceDeletionImpact:
    _ensure_delete_role(operator_role)
    workspace, counts = _workspace_and_counts(
        workspace_id=workspace_id,
        dependencies=dependencies,
    )
    _ensure_impact_workspace_status(workspace)
    return WorkspaceDeletionImpact(
        workspace_id=workspace_id,
        repository_connection_count=counts.repository_connection_count,
        local_upload_count=counts.local_upload_count,
        snapshot_count=counts.snapshot_count,
        project_content_will_be_removed=True,
        audit_metadata_will_remain=True,
        confirmation=_confirmation_phrase(workspace_id),
    )


def get_deleted_workspace_status(
    *,
    workspace_id: uuid.UUID,
    dependencies,
) -> WorkspaceDeletionResult:
    if dependencies.session_factory is None:
        raise RuntimeError("워크스페이스 상태 조회에는 데이터베이스 세션이 필요합니다.")
    with dependencies.session_factory() as session:
        workspace_repository = dependencies.workspace_repository_factory(session)
        workspace = workspace_repository.get(workspace_id=workspace_id)
        latest_record = (
            None
            if workspace is None
            else workspace_repository.get_latest_deletion_record(
                workspace_id=workspace_id
            )
        )
    if workspace is None:
        raise WorkspaceDeleteProblem(
            code="invalid_request",
            message="워크스페이스를 찾을 수 없습니다.",
            remediation_action="choose_active_workspace",
            status_code=404,
        )
    if getattr(workspace, "status") is not WorkspaceStatus.DELETED:
        raise WorkspaceDeleteProblem(
            code="workspace_not_deleted",
            message="삭제된 워크스페이스가 아닙니다.",
            remediation_action="confirm_workspace_state",
            status_code=409,
        )
    return WorkspaceDeletionResult(
        workspace_id=workspace_id,
        status="deleted",
        deletion_record_id=None if latest_record is None else latest_record.id,
        audit_metadata_retained=True,
        project_content_removed=True,
        message="이미 삭제된 워크스페이스입니다.",
        status_code=200,
    )


def delete_workspace(
    command: DeleteWorkspaceCommand,
    *,
    dependencies,
) -> WorkspaceDeletionResult:
    _ensure_delete_role(command.operator_role)
    _ensure_confirmation(
        workspace_id=command.workspace_id,
        supplied_confirmation=command.confirmation,
    )
    if dependencies.session_factory is None:
        raise RuntimeError("워크스페이스 삭제에는 데이터베이스 세션이 필요합니다.")

    requested_at = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        workspace_repository = dependencies.workspace_repository_factory(session)
        workspace = workspace_repository.get_for_update(
            workspace_id=command.workspace_id
        )
        if workspace is None:
            raise WorkspaceDeleteProblem(
                code="invalid_request",
                message="워크스페이스를 찾을 수 없습니다.",
                remediation_action="choose_active_workspace",
                status_code=404,
            )
        if workspace.status is WorkspaceStatus.DELETED:
            return WorkspaceDeletionResult(
                workspace_id=command.workspace_id,
                status="deleted",
                deletion_record_id=None,
                audit_metadata_retained=True,
                project_content_removed=True,
                message="이미 삭제된 워크스페이스입니다.",
                status_code=409,
            )
        if workspace.status is WorkspaceStatus.DELETING:
            latest_record = workspace_repository.get_latest_deletion_record(
                workspace_id=command.workspace_id
            )
            counts = _workspace_counts_in_session(
                workspace_id=command.workspace_id,
                dependencies=dependencies,
                session=session,
            )
            if latest_record is None:
                record = workspace_repository.create_deletion_record(
                    WorkspaceDeletionRecordDraft(
                        id=uuid.uuid4(),
                        workspace_id=command.workspace_id,
                        deleted_by=command.deleted_by,
                        repository_connection_count=counts.repository_connection_count,
                        local_upload_count=counts.local_upload_count,
                        snapshot_count=counts.snapshot_count,
                        purge_status=WorkspaceDeletionPurgeStatus.PENDING,
                        requested_at=requested_at,
                    )
                )
            else:
                record = latest_record
        else:
            counts = _workspace_counts_in_session(
                workspace_id=command.workspace_id,
                dependencies=dependencies,
                session=session,
            )
            workspace_repository.transition_status(
                workspace_id=command.workspace_id,
                status=WorkspaceStatus.DELETING,
            )
            record = workspace_repository.create_deletion_record(
                WorkspaceDeletionRecordDraft(
                    id=uuid.uuid4(),
                    workspace_id=command.workspace_id,
                    deleted_by=command.deleted_by,
                    repository_connection_count=counts.repository_connection_count,
                    local_upload_count=counts.local_upload_count,
                    snapshot_count=counts.snapshot_count,
                    purge_status=WorkspaceDeletionPurgeStatus.PENDING,
                    requested_at=requested_at,
                )
            )
        record_id = record.id

    purge_status = WorkspaceDeletionPurgeStatus.SUCCEEDED
    purged_archive_count = 0
    failure_message = None
    purge_failures: list[str] = []
    for purge_label, count_as_archive, purge_operation in (
        (
            "snapshot archives",
            True,
            lambda: dependencies.snapshot_archive_store.purge_workspace_snapshots(
                snapshots=counts.snapshots
            ),
        ),
        (
            "local upload queue",
            False,
            lambda: dependencies.snapshot_archive_store.purge_local_upload_queue_files(
                uploads=counts.local_uploads
            ),
        ),
        (
            "git mirrors",
            False,
            lambda: dependencies.snapshot_archive_store.purge_git_mirrors(
                connections=counts.connections
            ),
        ),
    ):
        try:
            purged_count = purge_operation()
            if count_as_archive:
                purged_archive_count += purged_count
        except Exception as error:
            purge_failures.append(
                f"{purge_label}: {_sanitize_purge_failure(str(error))}"
            )
    if purge_failures:
        purge_status = WorkspaceDeletionPurgeStatus.FAILED
        failure_message = bounded_failure_message("; ".join(purge_failures))

    completed_at = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        workspace_repository = dependencies.workspace_repository_factory(session)
        if purge_status is WorkspaceDeletionPurgeStatus.FAILED:
            record = workspace_repository.update_deletion_record(
                record_id=record_id,
                purge_status=purge_status,
                purged_archive_count=purged_archive_count,
                completed_at=completed_at,
                failure_message=failure_message,
            )
            return WorkspaceDeletionResult(
                workspace_id=command.workspace_id,
                status="deleting",
                deletion_record_id=record.id,
                audit_metadata_retained=True,
                project_content_removed=False,
                message="워크스페이스 삭제 중 일부 프로젝트 내용 제거에 실패했습니다.",
            )
        dependencies.repository_connection_repository_factory(
            session
        ).delete_for_workspace(workspace_id=command.workspace_id)
        dependencies.code_snapshot_repository_factory(session).delete_for_workspace(
            workspace_id=command.workspace_id
        )
        dependencies.local_upload_repository_factory(session).delete_for_workspace(
            workspace_id=command.workspace_id
        )
        dependencies.planning_input_reference_repository_factory(
            session
        ).delete_for_workspace(workspace_id=command.workspace_id)
        workspace_repository.transition_status(
            workspace_id=command.workspace_id,
            status=WorkspaceStatus.DELETED,
            deleted_by=command.deleted_by,
            delete_reason=_sanitize_reason(command.reason),
            transitioned_at=completed_at,
        )
        record = workspace_repository.update_deletion_record(
            record_id=record_id,
            purge_status=purge_status,
            purged_archive_count=purged_archive_count,
            completed_at=completed_at,
            failure_message=failure_message,
        )
        return WorkspaceDeletionResult(
            workspace_id=command.workspace_id,
            status="deleted",
            deletion_record_id=record.id,
            audit_metadata_retained=True,
            project_content_removed=True,
            message="워크스페이스 삭제가 완료되었습니다.",
        )


@dataclass(frozen=True, slots=True)
class _WorkspaceCounts:
    repository_connection_count: int
    local_upload_count: int
    snapshot_count: int
    connections: tuple[object, ...]
    local_uploads: tuple[object, ...]
    snapshots: tuple[object, ...]


def _workspace_and_counts(
    *, workspace_id: uuid.UUID, dependencies
) -> tuple[object, _WorkspaceCounts]:
    if dependencies.session_factory is None:
        raise RuntimeError(
            "워크스페이스 삭제 영향 조회에는 데이터베이스 세션이 필요합니다."
        )
    with dependencies.session_factory() as session:
        workspace_repository = dependencies.workspace_repository_factory(session)
        workspace = workspace_repository.get(workspace_id=workspace_id)
        if workspace is None:
            raise WorkspaceDeleteProblem(
                code="invalid_request",
                message="워크스페이스를 찾을 수 없습니다.",
                remediation_action="choose_active_workspace",
                status_code=404,
            )
        counts = _workspace_counts_in_session(
            workspace_id=workspace_id,
            dependencies=dependencies,
            session=session,
        )
        return workspace, counts


def _workspace_counts_in_session(
    *, workspace_id: uuid.UUID, dependencies, session
) -> _WorkspaceCounts:
    connection_repository = dependencies.repository_connection_repository_factory(
        session
    )
    local_upload_repository = dependencies.local_upload_repository_factory(session)
    snapshot_repository = dependencies.code_snapshot_repository_factory(session)
    connections = connection_repository.list_for_workspace(workspace_id=workspace_id)
    uploads = tuple(
        local_upload_repository.list_for_workspace(workspace_id=workspace_id)
    )
    snapshots = tuple(snapshot_repository.list_for_workspace(workspace_id=workspace_id))
    return _WorkspaceCounts(
        repository_connection_count=len(connections),
        local_upload_count=len(uploads),
        snapshot_count=len(snapshots),
        connections=tuple(connections),
        local_uploads=uploads,
        snapshots=snapshots,
    )


def _ensure_impact_workspace_status(workspace: object) -> None:
    status = getattr(workspace, "status")
    if status is WorkspaceStatus.ACTIVE:
        return
    if status is WorkspaceStatus.DELETING:
        raise WorkspaceDeleteProblem(
            code="workspace_deleting",
            message="워크스페이스 삭제가 이미 진행 중입니다.",
            remediation_action="none",
            status_code=409,
        )
    raise WorkspaceDeleteProblem(
        code="workspace_deleted",
        message="이미 삭제된 워크스페이스입니다.",
        remediation_action="none",
        status_code=409,
    )


def _ensure_delete_role(operator_role: str | None) -> None:
    if (operator_role or "").lower() in AUTHORIZED_DELETE_ROLES:
        return
    raise WorkspaceDeleteProblem(
        code="workspace_delete_forbidden",
        message="워크스페이스 소유자 또는 관리자만 삭제할 수 있습니다.",
        remediation_action="request_owner_or_admin",
        status_code=403,
    )


def _ensure_confirmation(
    *, workspace_id: uuid.UUID, supplied_confirmation: str
) -> None:
    expected = _confirmation_phrase(workspace_id)
    if supplied_confirmation == expected:
        return
    raise WorkspaceDeleteProblem(
        code="workspace_delete_confirmation_required",
        message=f"삭제하려면 확인 문구 '{expected}'를 입력해야 합니다.",
        remediation_action="confirm_workspace_delete",
        status_code=400,
    )


def _confirmation_phrase(workspace_id: uuid.UUID) -> str:
    return f"DELETE {workspace_id}"


def _sanitize_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    redacted = bounded_failure_message(reason, limit=255) or ""
    sanitized = re.sub(
        r"(?i)(token|secret|password|credential|cookie)=\S+",
        r"\1=[redacted]",
        redacted,
    )
    sanitized = re.sub(r"https?://\S+", "[redacted-url]", sanitized)
    sanitized = re.sub(r"(?i)[A-Za-z]:\\[^\s]+", "[redacted-path]", sanitized)
    sanitized = re.sub(r"/[^\s]+", "[redacted-path]", sanitized)
    sanitized = sanitized.replace("/", " ")
    return bounded_failure_message(sanitized, limit=255)


def _sanitize_purge_failure(message: str) -> str:
    return _sanitize_reason(message) or "purge failed"
