from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tci.domain.services.failure_messages import bounded_failure_message
from tci.infrastructure.persistence.models import (
    Workspace,
    WorkspaceDeletionPurgeStatus,
    WorkspaceDeletionRecord,
    WorkspaceStatus,
)


@dataclass(frozen=True, slots=True)
class WorkspaceDraft:
    id: uuid.UUID
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class WorkspaceDeletionRecordDraft:
    id: uuid.UUID
    workspace_id: uuid.UUID
    deleted_by: str
    repository_connection_count: int
    local_upload_count: int
    snapshot_count: int
    purged_archive_count: int = 0
    purge_status: WorkspaceDeletionPurgeStatus = WorkspaceDeletionPurgeStatus.PENDING
    requested_at: datetime | None = None
    completed_at: datetime | None = None
    failure_message: str | None = None


class WorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, draft: WorkspaceDraft) -> Workspace:
        workspace = Workspace(id=draft.id, status=draft.status)
        self._session.add(workspace)
        self._session.flush()
        self._session.refresh(workspace)
        return workspace

    def get(self, *, workspace_id: uuid.UUID) -> Workspace | None:
        return self._session.get(Workspace, workspace_id)

    def get_for_update(self, *, workspace_id: uuid.UUID) -> Workspace | None:
        statement = (
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def list_active(self) -> list[Workspace]:
        statement = (
            select(Workspace)
            .where(Workspace.status == WorkspaceStatus.ACTIVE)
            .order_by(Workspace.created_at.desc(), Workspace.id.desc())
        )
        return list(self._session.scalars(statement))

    def transition_status(
        self,
        *,
        workspace_id: uuid.UUID,
        status: WorkspaceStatus,
        deleted_by: str | None = None,
        delete_reason: str | None = None,
        transitioned_at: datetime | None = None,
    ) -> Workspace:
        workspace = self.get(workspace_id=workspace_id)
        if workspace is None:
            raise LookupError("워크스페이스를 찾을 수 없습니다.")
        if workspace.status is status:
            return workspace
        if status is WorkspaceStatus.DELETED and not deleted_by:
            raise ValueError("deleted_by is required when deleting a workspace.")
        if workspace.status is WorkspaceStatus.DELETED:
            raise ValueError("deleted workspace is terminal.")
        if (
            workspace.status is WorkspaceStatus.ACTIVE
            and status is not WorkspaceStatus.DELETING
        ) or (
            workspace.status is WorkspaceStatus.DELETING
            and status is not WorkspaceStatus.DELETED
        ):
            raise ValueError(
                "Workspace lifecycle must move active -> deleting -> deleted."
            )
        values: dict[str, object] = {"status": status}
        if status is WorkspaceStatus.DELETED:
            values.update(
                {
                    "deleted_at": transitioned_at or datetime.now(tz=UTC),
                    "deleted_by": deleted_by,
                    "delete_reason": bounded_failure_message(delete_reason, limit=255),
                }
            )
        statement = (
            update(Workspace)
            .where(
                Workspace.id == workspace_id,
                Workspace.status == workspace.status,
            )
            .values(**values)
        )
        result = self._session.execute(statement)
        if result.rowcount != 1:
            raise ValueError("Workspace lifecycle transition lost a state race.")
        self._session.refresh(workspace)
        return workspace

    def create_deletion_record(
        self, draft: WorkspaceDeletionRecordDraft
    ) -> WorkspaceDeletionRecord:
        record = WorkspaceDeletionRecord(
            id=draft.id,
            workspace_id=draft.workspace_id,
            deleted_by=draft.deleted_by,
            requested_at=draft.requested_at,
            completed_at=draft.completed_at,
            purge_status=draft.purge_status,
            repository_connection_count=draft.repository_connection_count,
            local_upload_count=draft.local_upload_count,
            snapshot_count=draft.snapshot_count,
            purged_archive_count=draft.purged_archive_count,
            failure_message=bounded_failure_message(draft.failure_message),
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record

    def get_latest_deletion_record(
        self, *, workspace_id: uuid.UUID
    ) -> WorkspaceDeletionRecord | None:
        statement = (
            select(WorkspaceDeletionRecord)
            .where(WorkspaceDeletionRecord.workspace_id == workspace_id)
            .order_by(
                WorkspaceDeletionRecord.requested_at.desc(),
                WorkspaceDeletionRecord.id.desc(),
            )
            .limit(1)
        )
        return self._session.scalar(statement)

    def update_deletion_record(
        self,
        *,
        record_id: uuid.UUID,
        purge_status: WorkspaceDeletionPurgeStatus,
        purged_archive_count: int,
        completed_at: datetime,
        failure_message: str | None = None,
    ) -> WorkspaceDeletionRecord:
        record = self._session.get(WorkspaceDeletionRecord, record_id)
        if record is None:
            raise LookupError("워크스페이스 삭제 기록을 찾을 수 없습니다.")
        record.purge_status = purge_status
        record.purged_archive_count = purged_archive_count
        record.completed_at = completed_at
        record.failure_message = bounded_failure_message(failure_message)
        self._session.flush()
        self._session.refresh(record)
        return record
