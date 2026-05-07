from __future__ import annotations

from datetime import datetime, timedelta
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.code_snapshot_repository import (
    CodeSnapshotFileDraft,
    CodeSnapshotLocalUploadDraft,
    CodeSnapshotRepository,
)
from tci.infrastructure.persistence.models import (
    Base,
    CodeSnapshotSourceKind,
    LocalUpload,
    LocalUploadStatus,
    SnapshotInclusionReason,
    Workspace,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table_name in (
        "workspaces",
        "local_uploads",
        "code_snapshots",
        "code_snapshot_files",
    ):
        Base.metadata.tables[table_name].create(engine)
    return Session(engine)


def _file(path: str = "src/app.py") -> CodeSnapshotFileDraft:
    return CodeSnapshotFileDraft(
        path=path,
        extension=".py",
        language_hint="python",
        size_bytes=12,
        content_sha256="a" * 64,
        archive_blob_path=path,
        included_by=SnapshotInclusionReason.DEFAULT_POLICY,
    )


def _workspace_with_upload(
    session: Session,
    *,
    workspace_id: uuid.UUID | None = None,
    upload_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    resolved_workspace_id = workspace_id or uuid.uuid4()
    resolved_upload_id = upload_id or uuid.uuid4()
    if session.get(Workspace, resolved_workspace_id) is None:
        session.add(Workspace(id=resolved_workspace_id))
    session.add(
        LocalUpload(
            id=resolved_upload_id,
            workspace_id=resolved_workspace_id,
            status=LocalUploadStatus.PROCESSING,
            original_filename_display="project.zip",
            upload_sha256="b" * 64,
            compressed_size_bytes=128,
            created_by="operator@example.com",
        )
    )
    session.commit()
    return resolved_workspace_id, resolved_upload_id


def test_create_for_local_upload_persists_source_owner_and_files() -> None:
    session = _session()
    workspace_id, upload_id = _workspace_with_upload(session)
    snapshot_id = uuid.uuid4()

    snapshot = CodeSnapshotRepository(session).create_for_local_upload(
        draft=CodeSnapshotLocalUploadDraft(
            id=snapshot_id,
            workspace_id=workspace_id,
            local_upload_id=upload_id,
            archive_path=f".runtime/code-snapshots/{snapshot_id}",
            file_count=1,
            total_bytes=12,
        ),
        files=(_file(),),
    )

    assert snapshot.source_kind is CodeSnapshotSourceKind.LOCAL_UPLOAD
    assert snapshot.workspace_id == workspace_id
    assert snapshot.local_upload_id == upload_id
    assert snapshot.connection_id is None
    assert snapshot.sync_run_id is None
    assert snapshot.scope_rule_version_id is None
    assert [file.path for file in snapshot.files] == ["src/app.py"]


def test_create_for_local_upload_requires_processing_upload() -> None:
    session = _session()
    workspace_id, upload_id = _workspace_with_upload(session)
    upload = session.get(LocalUpload, upload_id)
    assert upload is not None
    upload.status = LocalUploadStatus.SUCCEEDED
    upload.latest_snapshot_id = uuid.uuid4()
    upload.completed_at = datetime(2026, 5, 6, 12, 0, 0)
    session.commit()

    with pytest.raises(ValueError, match="processing"):
        CodeSnapshotRepository(session).create_for_local_upload(
            draft=CodeSnapshotLocalUploadDraft(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                local_upload_id=upload_id,
                archive_path=".runtime/code-snapshots/not-processing",
                file_count=1,
                total_bytes=12,
            ),
            files=(_file(),),
        )


def test_create_for_local_upload_rejects_workspace_mismatch() -> None:
    session = _session()
    _, upload_id = _workspace_with_upload(session)

    with pytest.raises(ValueError, match="must match"):
        CodeSnapshotRepository(session).create_for_local_upload(
            draft=CodeSnapshotLocalUploadDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                local_upload_id=upload_id,
                archive_path=".runtime/code-snapshots/mismatch",
                file_count=1,
                total_bytes=12,
            ),
            files=(_file(),),
        )


def test_get_for_local_upload_scopes_lookup_to_workspace_and_upload() -> None:
    session = _session()
    workspace_id, upload_id = _workspace_with_upload(session)
    other_workspace_id, _ = _workspace_with_upload(session)
    snapshot_id = uuid.uuid4()
    repository = CodeSnapshotRepository(session)
    repository.create_for_local_upload(
        draft=CodeSnapshotLocalUploadDraft(
            id=snapshot_id,
            workspace_id=workspace_id,
            local_upload_id=upload_id,
            archive_path=f".runtime/code-snapshots/{snapshot_id}",
            file_count=1,
            total_bytes=12,
        ),
        files=(_file(),),
    )

    assert (
        repository.get_for_local_upload(
            workspace_id=workspace_id,
            local_upload_id=upload_id,
            snapshot_id=snapshot_id,
        )
        is not None
    )
    assert (
        repository.get_for_local_upload(
            workspace_id=other_workspace_id,
            local_upload_id=upload_id,
            snapshot_id=snapshot_id,
        )
        is None
    )


def test_get_latest_local_upload_for_workspace_uses_snapshot_created_at_then_id() -> (
    None
):
    session = _session()
    workspace_id, older_upload_id = _workspace_with_upload(session)
    _, newer_upload_id = _workspace_with_upload(
        session,
        workspace_id=workspace_id,
    )
    base_time = datetime(2026, 5, 6, 12, 0, 0)
    older_snapshot_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    newer_snapshot_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    repository = CodeSnapshotRepository(session)
    repository.create_for_local_upload(
        draft=CodeSnapshotLocalUploadDraft(
            id=older_snapshot_id,
            workspace_id=workspace_id,
            local_upload_id=older_upload_id,
            archive_path=f".runtime/code-snapshots/{older_snapshot_id}",
            file_count=1,
            total_bytes=12,
            created_at=base_time - timedelta(minutes=1),
        ),
        files=(_file("src/old.py"),),
    )
    older_upload = session.get(LocalUpload, older_upload_id)
    assert older_upload is not None
    older_upload.status = LocalUploadStatus.SUCCEEDED
    older_upload.latest_snapshot_id = older_snapshot_id
    older_upload.completed_at = base_time + timedelta(minutes=5)
    repository.create_for_local_upload(
        draft=CodeSnapshotLocalUploadDraft(
            id=newer_snapshot_id,
            workspace_id=workspace_id,
            local_upload_id=newer_upload_id,
            archive_path=f".runtime/code-snapshots/{newer_snapshot_id}",
            file_count=1,
            total_bytes=12,
            created_at=base_time,
        ),
        files=(_file("src/new.py"),),
    )
    newer_upload = session.get(LocalUpload, newer_upload_id)
    assert newer_upload is not None
    newer_upload.status = LocalUploadStatus.SUCCEEDED
    newer_upload.latest_snapshot_id = newer_snapshot_id
    newer_upload.completed_at = base_time - timedelta(minutes=5)
    session.commit()

    latest = repository.get_latest_local_upload_for_workspace(workspace_id=workspace_id)

    assert latest is not None
    assert latest.id == newer_snapshot_id


def test_get_latest_local_upload_for_workspace_ignores_failed_uploads() -> None:
    session = _session()
    workspace_id, upload_id = _workspace_with_upload(session)
    snapshot_id = uuid.uuid4()
    repository = CodeSnapshotRepository(session)
    repository.create_for_local_upload(
        draft=CodeSnapshotLocalUploadDraft(
            id=snapshot_id,
            workspace_id=workspace_id,
            local_upload_id=upload_id,
            archive_path=f".runtime/code-snapshots/{snapshot_id}",
            file_count=1,
            total_bytes=12,
        ),
        files=(_file(),),
    )
    upload = session.get(LocalUpload, upload_id)
    assert upload is not None
    upload.status = LocalUploadStatus.FAILED
    upload.failure_code = "unsafe_zip_path"
    upload.completed_at = datetime(2026, 5, 6, 12, 0, 0)
    session.commit()

    assert (
        repository.get_latest_local_upload_for_workspace(workspace_id=workspace_id)
        is None
    )


def test_get_latest_local_upload_for_workspace_uses_upload_latest_snapshot_id() -> None:
    session = _session()
    workspace_id, upload_id = _workspace_with_upload(session)
    repository = CodeSnapshotRepository(session)
    stale_snapshot_id = uuid.UUID("00000000-0000-0000-0000-000000000011")
    latest_snapshot_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
    repository.create_for_local_upload(
        draft=CodeSnapshotLocalUploadDraft(
            id=latest_snapshot_id,
            workspace_id=workspace_id,
            local_upload_id=upload_id,
            archive_path=f".runtime/code-snapshots/{latest_snapshot_id}",
            file_count=1,
            total_bytes=12,
            created_at=datetime(2026, 5, 6, 12, 0, 0),
        ),
        files=(_file("src/latest.py"),),
    )
    upload = session.get(LocalUpload, upload_id)
    assert upload is not None
    upload.status = LocalUploadStatus.PROCESSING
    repository.create_for_local_upload(
        draft=CodeSnapshotLocalUploadDraft(
            id=stale_snapshot_id,
            workspace_id=workspace_id,
            local_upload_id=upload_id,
            archive_path=f".runtime/code-snapshots/{stale_snapshot_id}",
            file_count=1,
            total_bytes=12,
            created_at=datetime(2026, 5, 6, 12, 1, 0),
        ),
        files=(_file("src/stale.py"),),
    )
    upload.status = LocalUploadStatus.SUCCEEDED
    upload.latest_snapshot_id = latest_snapshot_id
    upload.completed_at = datetime(2026, 5, 6, 12, 2, 0)
    session.commit()

    latest = repository.get_latest_local_upload_for_workspace(workspace_id=workspace_id)

    assert latest is not None
    assert latest.id == latest_snapshot_id
