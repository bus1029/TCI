from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from tci.infrastructure.persistence.models import (
    CodeSnapshot,
    CodeSnapshotFile,
    CodeSnapshotSourceKind,
    LocalUpload,
    LocalUploadStatus,
    RefType,
    RepositoryConnection,
    SnapshotInclusionReason,
    Workspace,
    WorkspaceStatus,
)


@dataclass(frozen=True, slots=True)
class CodeSnapshotFileDraft:
    path: str
    extension: str | None
    language_hint: str | None
    size_bytes: int
    content_sha256: str
    archive_blob_path: str
    included_by: SnapshotInclusionReason


@dataclass(frozen=True, slots=True)
class CodeSnapshotDraft:
    id: uuid.UUID
    connection_id: uuid.UUID
    sync_run_id: uuid.UUID
    scope_rule_version_id: uuid.UUID
    requested_ref_type: RefType
    requested_ref_name: str
    resolved_commit_sha: str
    tree_sha: str
    archive_path: str
    file_count: int
    total_bytes: int
    workspace_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class CodeSnapshotLocalUploadDraft:
    id: uuid.UUID
    workspace_id: uuid.UUID
    local_upload_id: uuid.UUID
    archive_path: str
    file_count: int
    total_bytes: int
    created_at: datetime | None = None


class CodeSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        draft: CodeSnapshotDraft,
        files: tuple[CodeSnapshotFileDraft, ...],
    ) -> CodeSnapshot:
        workspace_id = self._workspace_id_for_connection(
            connection_id=draft.connection_id
        )
        if draft.workspace_id is not None and draft.workspace_id != workspace_id:
            raise ValueError(
                "CodeSnapshotDraft.workspace_id must match the repository connection."
            )
        snapshot = CodeSnapshot(
            id=draft.id,
            workspace_id=workspace_id,
            source_kind=CodeSnapshotSourceKind.REPOSITORY_CONNECTION,
            connection_id=draft.connection_id,
            sync_run_id=draft.sync_run_id,
            scope_rule_version_id=draft.scope_rule_version_id,
            requested_ref_type=draft.requested_ref_type,
            requested_ref_name=draft.requested_ref_name,
            resolved_commit_sha=draft.resolved_commit_sha,
            tree_sha=draft.tree_sha,
            archive_path=draft.archive_path,
            file_count=draft.file_count,
            total_bytes=draft.total_bytes,
        )
        snapshot.files = [
            CodeSnapshotFile(
                path=file.path,
                extension=file.extension,
                language_hint=file.language_hint,
                size_bytes=file.size_bytes,
                content_sha256=file.content_sha256,
                archive_blob_path=file.archive_blob_path,
                included_by=file.included_by,
            )
            for file in files
        ]
        self._session.add(snapshot)
        self._session.flush()
        self._session.refresh(snapshot)
        return snapshot

    def create_for_local_upload(
        self,
        *,
        draft: CodeSnapshotLocalUploadDraft,
        files: tuple[CodeSnapshotFileDraft, ...],
    ) -> CodeSnapshot:
        upload = self._local_upload_for_snapshot(local_upload_id=draft.local_upload_id)
        if draft.workspace_id != upload.workspace_id:
            raise ValueError(
                "CodeSnapshotLocalUploadDraft.workspace_id must match the local upload."
            )
        snapshot_kwargs = {}
        if draft.created_at is not None:
            snapshot_kwargs["created_at"] = draft.created_at
        snapshot = CodeSnapshot(
            id=draft.id,
            workspace_id=draft.workspace_id,
            source_kind=CodeSnapshotSourceKind.LOCAL_UPLOAD,
            connection_id=None,
            local_upload_id=draft.local_upload_id,
            sync_run_id=None,
            scope_rule_version_id=None,
            requested_ref_type=None,
            requested_ref_name=None,
            resolved_commit_sha=None,
            tree_sha=None,
            archive_path=draft.archive_path,
            file_count=draft.file_count,
            total_bytes=draft.total_bytes,
            **snapshot_kwargs,
        )
        snapshot.files = [
            CodeSnapshotFile(
                path=file.path,
                extension=file.extension,
                language_hint=file.language_hint,
                size_bytes=file.size_bytes,
                content_sha256=file.content_sha256,
                archive_blob_path=file.archive_blob_path,
                included_by=file.included_by,
            )
            for file in files
        ]
        self._session.add(snapshot)
        self._session.flush()
        self._session.refresh(snapshot)
        return snapshot

    def _workspace_id_for_connection(self, *, connection_id: uuid.UUID) -> uuid.UUID:
        if not hasattr(self._session, "execute"):
            workspace_id = self._session.scalar(
                select(RepositoryConnection.workspace_id).where(
                    RepositoryConnection.id == connection_id
                )
            )
            if workspace_id is None:
                raise ValueError(
                    "CodeSnapshotDraft.workspace_id is required for snapshots."
                )
            return workspace_id
        workspace_id = self._session.scalar(
            select(RepositoryConnection.workspace_id).where(
                RepositoryConnection.id == connection_id
            )
        )
        if workspace_id is None:
            raise ValueError(
                "CodeSnapshotDraft.workspace_id is required for snapshots."
            )
        workspace_status = self._session.scalar(
            select(Workspace.status)
            .where(Workspace.id == workspace_id)
            .with_for_update(of=Workspace)
        )
        if workspace_status is not WorkspaceStatus.ACTIVE:
            raise ValueError("Repository snapshot requires an active workspace.")
        return workspace_id

    def _local_upload_for_snapshot(self, *, local_upload_id: uuid.UUID) -> LocalUpload:
        workspace_id = self._session.scalar(
            select(LocalUpload.workspace_id).where(LocalUpload.id == local_upload_id)
        )
        if workspace_id is None:
            raise ValueError("CodeSnapshotLocalUploadDraft.local_upload_id must exist.")
        workspace_status = self._session.scalar(
            select(Workspace.status)
            .where(Workspace.id == workspace_id)
            .with_for_update(of=Workspace)
        )
        if workspace_status is not WorkspaceStatus.ACTIVE:
            raise ValueError("Local Upload snapshot requires an active workspace.")
        upload = self._session.scalar(
            select(LocalUpload)
            .where(LocalUpload.id == local_upload_id)
            .with_for_update(of=LocalUpload)
        )
        if upload is None:
            raise ValueError("CodeSnapshotLocalUploadDraft.local_upload_id must exist.")
        if upload.status is not LocalUploadStatus.PROCESSING:
            raise ValueError("Local Upload snapshot requires a processing upload.")
        return upload

    def get(
        self, *, connection_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> CodeSnapshot | None:
        statement = (
            select(CodeSnapshot)
            .options(joinedload(CodeSnapshot.files))
            .where(
                CodeSnapshot.connection_id == connection_id,
                CodeSnapshot.id == snapshot_id,
            )
        )
        return self._session.execute(statement).unique().scalar_one_or_none()

    def get_latest_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> CodeSnapshot | None:
        statement = (
            select(CodeSnapshot)
            .where(
                CodeSnapshot.connection_id == connection_id,
                CodeSnapshot.source_kind
                == CodeSnapshotSourceKind.REPOSITORY_CONNECTION,
            )
            .order_by(CodeSnapshot.created_at.desc(), CodeSnapshot.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def get_for_local_upload(
        self,
        *,
        workspace_id: uuid.UUID,
        local_upload_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> CodeSnapshot | None:
        statement = (
            select(CodeSnapshot)
            .options(joinedload(CodeSnapshot.files))
            .where(
                CodeSnapshot.workspace_id == workspace_id,
                CodeSnapshot.local_upload_id == local_upload_id,
                CodeSnapshot.id == snapshot_id,
                CodeSnapshot.source_kind == CodeSnapshotSourceKind.LOCAL_UPLOAD,
            )
        )
        return self._session.execute(statement).unique().scalar_one_or_none()

    def get_latest_local_upload_for_workspace(
        self, *, workspace_id: uuid.UUID
    ) -> CodeSnapshot | None:
        statement = (
            select(CodeSnapshot)
            .join(LocalUpload, CodeSnapshot.local_upload_id == LocalUpload.id)
            .where(
                CodeSnapshot.workspace_id == workspace_id,
                LocalUpload.workspace_id == workspace_id,
                CodeSnapshot.source_kind == CodeSnapshotSourceKind.LOCAL_UPLOAD,
                LocalUpload.status == LocalUploadStatus.SUCCEEDED,
                LocalUpload.latest_snapshot_id == CodeSnapshot.id,
            )
            .order_by(CodeSnapshot.created_at.desc(), CodeSnapshot.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def list_for_workspace(self, *, workspace_id: uuid.UUID) -> list[CodeSnapshot]:
        statement = (
            select(CodeSnapshot)
            .where(CodeSnapshot.workspace_id == workspace_id)
            .order_by(CodeSnapshot.created_at.desc(), CodeSnapshot.id.desc())
        )
        return list(self._session.scalars(statement))

    def delete_for_workspace(self, *, workspace_id: uuid.UUID) -> int:
        snapshots = self.list_for_workspace(workspace_id=workspace_id)
        for snapshot in snapshots:
            self._session.delete(snapshot)
        self._session.flush()
        return len(snapshots)

    def get_by_sync_run_id(self, *, sync_run_id: uuid.UUID) -> CodeSnapshot | None:
        statement = select(CodeSnapshot).where(CodeSnapshot.sync_run_id == sync_run_id)
        return self._session.scalar(statement)
