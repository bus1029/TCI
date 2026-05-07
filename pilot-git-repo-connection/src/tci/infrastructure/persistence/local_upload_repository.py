from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tci.domain.services.failure_messages import (
    bounded_display_filename,
    bounded_failure_message,
)
from tci.infrastructure.persistence.models import (
    CodeSnapshot,
    CodeSnapshotSourceKind,
    LocalUpload,
    LocalUploadStatus,
    Workspace,
    WorkspaceStatus,
)


@dataclass(frozen=True, slots=True)
class LocalUploadDraft:
    id: uuid.UUID
    workspace_id: uuid.UUID
    original_filename_display: str
    upload_sha256: str
    compressed_size_bytes: int
    created_by: str


class LocalUploadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, draft: LocalUploadDraft) -> LocalUpload:
        self._ensure_active_workspace(workspace_id=draft.workspace_id)
        upload = LocalUpload(
            id=draft.id,
            workspace_id=draft.workspace_id,
            status=LocalUploadStatus.PENDING,
            original_filename_display=bounded_display_filename(
                draft.original_filename_display
            ),
            upload_sha256=draft.upload_sha256,
            compressed_size_bytes=draft.compressed_size_bytes,
            created_by=draft.created_by,
        )
        self._session.add(upload)
        self._session.flush()
        self._session.refresh(upload)
        return upload

    def get(
        self, *, workspace_id: uuid.UUID, local_upload_id: uuid.UUID
    ) -> LocalUpload | None:
        statement = select(LocalUpload).where(
            LocalUpload.workspace_id == workspace_id,
            LocalUpload.id == local_upload_id,
        )
        return self._session.scalar(statement)

    def mark_processing(
        self, *, workspace_id: uuid.UUID, local_upload_id: uuid.UUID
    ) -> LocalUpload:
        return self._apply_status_update(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            allowed=(LocalUploadStatus.PENDING,),
            target=LocalUploadStatus.PROCESSING,
            values={"status": LocalUploadStatus.PROCESSING},
            workspace_statuses=(WorkspaceStatus.ACTIVE,),
        )

    def mark_succeeded(
        self,
        *,
        workspace_id: uuid.UUID,
        local_upload_id: uuid.UUID,
        latest_snapshot_id: uuid.UUID,
        uncompressed_size_bytes: int,
        file_count: int,
        directory_count: int,
        completed_at: datetime | None = None,
    ) -> LocalUpload:
        return self._apply_status_update(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            allowed=(LocalUploadStatus.PROCESSING,),
            target=LocalUploadStatus.SUCCEEDED,
            values={
                "status": LocalUploadStatus.SUCCEEDED,
                "latest_snapshot_id": latest_snapshot_id,
                "uncompressed_size_bytes": uncompressed_size_bytes,
                "file_count": file_count,
                "directory_count": directory_count,
                "failure_code": None,
                "failure_message": None,
                "completed_at": completed_at or datetime.now(tz=UTC),
            },
            workspace_statuses=(WorkspaceStatus.ACTIVE, WorkspaceStatus.DELETING),
        )

    def mark_failed(
        self,
        *,
        workspace_id: uuid.UUID,
        local_upload_id: uuid.UUID,
        failure_code: str,
        failure_message: str,
        completed_at: datetime | None = None,
    ) -> LocalUpload:
        return self._apply_status_update(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            allowed=(LocalUploadStatus.PENDING, LocalUploadStatus.PROCESSING),
            target=LocalUploadStatus.FAILED,
            values={
                "status": LocalUploadStatus.FAILED,
                "failure_code": failure_code[:64],
                "failure_message": bounded_failure_message(failure_message),
                "latest_snapshot_id": None,
                "completed_at": completed_at or datetime.now(tz=UTC),
            },
            workspace_statuses=(WorkspaceStatus.ACTIVE, WorkspaceStatus.DELETING),
        )

    def get_latest_succeeded_for_workspace(
        self, *, workspace_id: uuid.UUID
    ) -> LocalUpload | None:
        statement = (
            select(LocalUpload)
            .join(CodeSnapshot, LocalUpload.latest_snapshot_id == CodeSnapshot.id)
            .where(
                LocalUpload.workspace_id == workspace_id,
                LocalUpload.status == LocalUploadStatus.SUCCEEDED,
                CodeSnapshot.workspace_id == workspace_id,
                CodeSnapshot.source_kind == CodeSnapshotSourceKind.LOCAL_UPLOAD,
            )
            .order_by(CodeSnapshot.created_at.desc(), CodeSnapshot.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def list_for_workspace(self, *, workspace_id: uuid.UUID) -> list[LocalUpload]:
        statement = (
            select(LocalUpload)
            .where(LocalUpload.workspace_id == workspace_id)
            .order_by(LocalUpload.created_at.desc(), LocalUpload.id.desc())
        )
        return list(self._session.scalars(statement))

    def _require(
        self, *, workspace_id: uuid.UUID, local_upload_id: uuid.UUID
    ) -> LocalUpload:
        upload = self.get(workspace_id=workspace_id, local_upload_id=local_upload_id)
        if upload is None:
            raise LookupError("Local Upload을 찾을 수 없습니다.")
        return upload

    def _ensure_active_workspace(self, *, workspace_id: uuid.UUID) -> None:
        self._lock_workspace(
            workspace_id=workspace_id,
            statuses=(WorkspaceStatus.ACTIVE,),
            message="Local Upload requires an active workspace.",
        )

    def _lock_workspace(
        self,
        *,
        workspace_id: uuid.UUID,
        statuses: tuple[WorkspaceStatus, ...],
        message: str,
    ) -> None:
        workspace = self._session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        if workspace is None or workspace.status not in statuses:
            raise ValueError(message)

    @staticmethod
    def _workspace_status_exists(
        *, workspace_id: uuid.UUID, statuses: tuple[WorkspaceStatus, ...]
    ):
        return (
            select(Workspace.id)
            .where(
                Workspace.id == workspace_id,
                Workspace.status.in_(statuses),
            )
            .exists()
        )

    def _apply_status_update(
        self,
        *,
        workspace_id: uuid.UUID,
        local_upload_id: uuid.UUID,
        allowed: tuple[LocalUploadStatus, ...],
        target: LocalUploadStatus,
        values: dict[str, object],
        workspace_statuses: tuple[WorkspaceStatus, ...],
    ) -> LocalUpload:
        self._lock_workspace(
            workspace_id=workspace_id,
            statuses=workspace_statuses,
            message="Local Upload transition requires an active or deleting workspace.",
        )
        statement = (
            update(LocalUpload)
            .where(
                LocalUpload.workspace_id == workspace_id,
                LocalUpload.id == local_upload_id,
                LocalUpload.status.in_(allowed),
                self._workspace_status_exists(
                    workspace_id=workspace_id,
                    statuses=workspace_statuses,
                ),
            )
            .values(**values)
        )
        result = self._session.execute(statement)
        if result.rowcount != 1:
            self._raise_transition_problem(
                workspace_id=workspace_id,
                local_upload_id=local_upload_id,
                allowed=allowed,
                target=target,
                workspace_statuses=workspace_statuses,
            )
        upload = self._require(
            workspace_id=workspace_id, local_upload_id=local_upload_id
        )
        self._session.refresh(upload)
        return upload

    def _raise_transition_problem(
        self,
        *,
        workspace_id: uuid.UUID,
        local_upload_id: uuid.UUID,
        allowed: tuple[LocalUploadStatus, ...],
        target: LocalUploadStatus,
        workspace_statuses: tuple[WorkspaceStatus, ...],
    ) -> None:
        self._lock_workspace(
            workspace_id=workspace_id,
            statuses=workspace_statuses,
            message="Local Upload transition requires an active or deleting workspace.",
        )
        upload = self._require(
            workspace_id=workspace_id, local_upload_id=local_upload_id
        )
        if upload.status in (LocalUploadStatus.SUCCEEDED, LocalUploadStatus.FAILED):
            raise ValueError("Local Upload terminal status cannot transition.")
        if upload.status not in allowed:
            allowed_values = ", ".join(status.value for status in allowed)
            raise ValueError(
                f"Local Upload status must be one of {allowed_values} before {target.value}."
            )
        raise RuntimeError("Local Upload status transition did not update a row.")
