from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from tci.infrastructure.persistence.models import (
    CodeSnapshot,
    CodeSnapshotFile,
    RefType,
    SnapshotInclusionReason,
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


class CodeSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        draft: CodeSnapshotDraft,
        files: tuple[CodeSnapshotFileDraft, ...],
    ) -> CodeSnapshot:
        snapshot = CodeSnapshot(
            id=draft.id,
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

    def get_latest_for_connection(self, *, connection_id: uuid.UUID) -> CodeSnapshot | None:
        statement = (
            select(CodeSnapshot)
            .where(CodeSnapshot.connection_id == connection_id)
            .order_by(CodeSnapshot.created_at.desc(), CodeSnapshot.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def get_by_sync_run_id(self, *, sync_run_id: uuid.UUID) -> CodeSnapshot | None:
        statement = select(CodeSnapshot).where(CodeSnapshot.sync_run_id == sync_run_id)
        return self._session.scalar(statement)
