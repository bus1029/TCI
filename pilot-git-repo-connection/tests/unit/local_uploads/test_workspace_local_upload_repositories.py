from __future__ import annotations

from datetime import datetime
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.local_upload_repository import (
    LocalUploadDraft,
    LocalUploadRepository,
)
from tci.infrastructure.persistence.models import (
    Base,
    LocalUploadStatus,
    Workspace,
    WorkspaceStatus,
)
from tci.infrastructure.persistence.workspace_repository import (
    WorkspaceDeletionRecordDraft,
    WorkspaceDraft,
    WorkspaceRepository,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table_name in (
        "workspaces",
        "local_uploads",
        "workspace_deletion_records",
    ):
        Base.metadata.tables[table_name].create(engine)
    return Session(engine)


def _workspace(
    session: Session,
    *,
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE,
) -> uuid.UUID:
    if status is WorkspaceStatus.DELETED:
        workspace = Workspace(
            id=uuid.uuid4(),
            status=WorkspaceStatus.DELETED,
            deleted_at=datetime(2026, 5, 6, 11, 0, 0),
            deleted_by="operator@example.com",
        )
        session.add(workspace)
        session.commit()
        return workspace.id
    workspace = WorkspaceRepository(session).create(
        WorkspaceDraft(id=uuid.uuid4(), status=status)
    )
    session.commit()
    return workspace.id


def _local_upload_draft(workspace_id: uuid.UUID) -> LocalUploadDraft:
    return LocalUploadDraft(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        original_filename_display="project.zip",
        upload_sha256="c" * 64,
        compressed_size_bytes=128,
        created_by="operator@example.com",
    )


def test_workspace_repository_create_list_and_deletion_record_lookup() -> None:
    session = _session()
    repository = WorkspaceRepository(session)
    active = repository.create(WorkspaceDraft(id=uuid.uuid4()))
    deleted = Workspace(
        id=uuid.uuid4(),
        status=WorkspaceStatus.DELETED,
        deleted_at=datetime(2026, 5, 6, 11, 0, 0),
        deleted_by="operator@example.com",
    )
    session.add(deleted)
    session.flush()
    first_record = repository.create_deletion_record(
        WorkspaceDeletionRecordDraft(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            workspace_id=deleted.id,
            deleted_by="operator@example.com",
            repository_connection_count=1,
            local_upload_count=2,
            snapshot_count=3,
            requested_at=datetime(2026, 5, 6, 12, 0, 0),
        )
    )
    latest_record = repository.create_deletion_record(
        WorkspaceDeletionRecordDraft(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            workspace_id=deleted.id,
            deleted_by="operator@example.com",
            repository_connection_count=1,
            local_upload_count=2,
            snapshot_count=3,
            requested_at=datetime(2026, 5, 6, 12, 1, 0),
        )
    )
    session.commit()

    assert repository.get(workspace_id=active.id) is active
    assert [workspace.id for workspace in repository.list_active()] == [active.id]
    assert first_record.id != latest_record.id
    loaded_record = repository.get_latest_deletion_record(workspace_id=deleted.id)
    assert loaded_record is not None
    assert loaded_record.id == latest_record.id


def test_workspace_repository_enforces_forward_only_lifecycle() -> None:
    session = _session()
    repository = WorkspaceRepository(session)
    workspace = repository.create(WorkspaceDraft(id=uuid.uuid4()))

    with pytest.raises(ValueError, match="active -> deleting -> deleted"):
        repository.transition_status(
            workspace_id=workspace.id,
            status=WorkspaceStatus.DELETED,
            deleted_by="operator@example.com",
        )

    assert workspace.status is WorkspaceStatus.ACTIVE
    repository.transition_status(
        workspace_id=workspace.id,
        status=WorkspaceStatus.DELETING,
    )
    repository.transition_status(
        workspace_id=workspace.id,
        status=WorkspaceStatus.DELETED,
        deleted_by="operator@example.com",
    )
    with pytest.raises(ValueError, match="deleted workspace is terminal"):
        repository.transition_status(
            workspace_id=workspace.id,
            status=WorkspaceStatus.ACTIVE,
        )
    assert workspace.status is WorkspaceStatus.DELETED


def test_workspace_repository_validates_delete_audit_before_mutating() -> None:
    session = _session()
    repository = WorkspaceRepository(session)
    workspace = repository.create(WorkspaceDraft(id=uuid.uuid4()))
    repository.transition_status(
        workspace_id=workspace.id,
        status=WorkspaceStatus.DELETING,
    )

    with pytest.raises(ValueError, match="deleted_by"):
        repository.transition_status(
            workspace_id=workspace.id,
            status=WorkspaceStatus.DELETED,
        )

    assert workspace.status is WorkspaceStatus.DELETING


def test_workspace_repository_sanitizes_delete_reason() -> None:
    session = _session()
    repository = WorkspaceRepository(session)
    workspace = repository.create(WorkspaceDraft(id=uuid.uuid4()))
    repository.transition_status(
        workspace_id=workspace.id,
        status=WorkspaceStatus.DELETING,
    )

    deleted = repository.transition_status(
        workspace_id=workspace.id,
        status=WorkspaceStatus.DELETED,
        deleted_by="operator@example.com",
        delete_reason=(
            "cleanup /Users/operator/private.zip "
            "https://token@example.com/Private%20Project/archive.zip?secret=1 "
            "%2FUsers%2Foperator%2FEncoded%20Project%2Fsecret.zip "
            "encoded_token%3Dplain-secret "
            "https://token@example.com/repo.git path=.runtime/code-snapshots/abc "
            "/Users/operator/Private Project/archive.zip "
            "C:\\Users\\operator\\Private Project\\archive.zip "
            "'/Users/operator/Private Project/archive.zip' "
            '"C:\\Users\\operator\\Private Project\\archive.zip" '
            "Authorization: Basic base64-secret"
        ),
    )

    assert deleted.delete_reason is not None
    assert "/Users" not in deleted.delete_reason
    assert "https://" not in deleted.delete_reason
    assert ".runtime" not in deleted.delete_reason
    assert "Private Project" not in deleted.delete_reason
    assert "Encoded Project" not in deleted.delete_reason
    assert "encoded_token" not in deleted.delete_reason
    assert "Authorization:" not in deleted.delete_reason
    assert "base64-secret" not in deleted.delete_reason


def test_local_upload_repository_requires_active_workspace_on_create() -> None:
    session = _session()
    workspace_id = _workspace(session, status=WorkspaceStatus.DELETED)

    with pytest.raises(ValueError, match="active workspace"):
        LocalUploadRepository(session).create(_local_upload_draft(workspace_id))


@pytest.mark.parametrize(
    ("raw_filename", "display_filename"),
    (
        ("/Users/operator/private/project.zip", "project.zip"),
        ("C:\\Users\\operator\\secret\\workspace.zip", "workspace.zip"),
        ("https://example.com/uploads/private.zip?token=secret", "private.zip"),
        ("https://token@example.com?secret=1", "upload.zip"),
        ("archive.zip?token=secret#private", "archive.zip"),
        ("token=secret.zip", "upload.zip"),
        ("token%3Dsecret.zip", "upload.zip"),
        ("Users%2Foperator%2Fprivate%2Fencoded.zip", "encoded.zip"),
        ("nested\nfolder\tarchive.zip", "nested folder archive.zip"),
    ),
)
def test_local_upload_repository_sanitizes_display_filename(
    raw_filename: str, display_filename: str
) -> None:
    session = _session()
    workspace_id = _workspace(session)
    draft = _local_upload_draft(workspace_id)
    draft = LocalUploadDraft(
        id=draft.id,
        workspace_id=draft.workspace_id,
        original_filename_display=raw_filename,
        upload_sha256=draft.upload_sha256,
        compressed_size_bytes=draft.compressed_size_bytes,
        created_by=draft.created_by,
    )

    upload = LocalUploadRepository(session).create(draft)

    assert upload.original_filename_display == display_filename


def test_local_upload_repository_enforces_processing_terminal_transitions() -> None:
    session = _session()
    workspace_id = _workspace(session)
    repository = LocalUploadRepository(session)
    upload = repository.create(_local_upload_draft(workspace_id))

    repository.mark_processing(workspace_id=workspace_id, local_upload_id=upload.id)
    succeeded = repository.mark_succeeded(
        workspace_id=workspace_id,
        local_upload_id=upload.id,
        latest_snapshot_id=uuid.uuid4(),
        uncompressed_size_bytes=256,
        file_count=2,
        directory_count=1,
        completed_at=datetime(2026, 5, 6, 12, 0, 0),
    )
    with pytest.raises(ValueError, match="terminal"):
        repository.mark_failed(
            workspace_id=workspace_id,
            local_upload_id=upload.id,
            failure_code="unsafe_zip_path",
            failure_message="late worker failure",
        )

    assert succeeded.status is LocalUploadStatus.SUCCEEDED
    assert succeeded.latest_snapshot_id is not None


def test_local_upload_repository_blocks_terminal_cleanup_when_workspace_deleting() -> (
    None
):
    session = _session()
    workspace_id = _workspace(session)
    repository = LocalUploadRepository(session)
    upload = repository.create(_local_upload_draft(workspace_id))
    repository.mark_processing(workspace_id=workspace_id, local_upload_id=upload.id)
    WorkspaceRepository(session).transition_status(
        workspace_id=workspace_id,
        status=WorkspaceStatus.DELETING,
    )

    with pytest.raises(ValueError, match="active"):
        repository.mark_succeeded(
            workspace_id=workspace_id,
            local_upload_id=upload.id,
            latest_snapshot_id=uuid.uuid4(),
            uncompressed_size_bytes=256,
            file_count=2,
            directory_count=1,
        )

    assert upload.status is LocalUploadStatus.PROCESSING


def test_local_upload_repository_blocks_new_processing_when_workspace_deleting() -> (
    None
):
    session = _session()
    workspace_id = _workspace(session)
    repository = LocalUploadRepository(session)
    upload = repository.create(_local_upload_draft(workspace_id))
    WorkspaceRepository(session).transition_status(
        workspace_id=workspace_id,
        status=WorkspaceStatus.DELETING,
    )

    with pytest.raises(ValueError, match="active"):
        repository.mark_processing(workspace_id=workspace_id, local_upload_id=upload.id)


def test_local_upload_repository_sanitizes_failure_messages() -> None:
    session = _session()
    workspace_id = _workspace(session)
    repository = LocalUploadRepository(session)
    upload = repository.create(_local_upload_draft(workspace_id))
    raw_message = (
        "failed /Users/operator/private/project.zip\n"
        "see https://token@example.com/Private%20Project/archive.zip?secret=1 "
        "see https://token@example.com/acme/repo.git?secret=1 "
        "%2FUsers%2Foperator%2FEncoded%20Project%2Fsecret.zip "
        "encoded_token%3Dplain-secret "
        "/home/tci/private.zip /tmp/upload.zip path=.runtime/code-snapshots/abc "
        "/Users/operator/Private Project/archive.zip "
        "C:\\Users\\operator\\Private Project\\archive.zip "
        "'/Users/operator/Private Project/archive.zip' "
        '"C:\\Users\\operator\\Private Project\\archive.zip" '
        "git@gitlab.example.com:group/repo.git C:\\Users\\operator\\repo "
        "token=plain-secret api_key = abc access_token: def password: xyz "
        "Authorization: Bearer secret-token\n"
        "Authorization: Basic base64-secret\n"
        "Authorization: token plain-secret"
    )

    failed = repository.mark_failed(
        workspace_id=workspace_id,
        local_upload_id=upload.id,
        failure_code="unsafe_zip_path",
        failure_message=raw_message,
    )

    assert failed.failure_message is not None
    assert "/Users" not in failed.failure_message
    assert "/home" not in failed.failure_message
    assert "/tmp" not in failed.failure_message
    assert ".runtime" not in failed.failure_message
    assert "Private Project" not in failed.failure_message
    assert "Encoded Project" not in failed.failure_message
    assert "encoded_token" not in failed.failure_message
    assert "https://" not in failed.failure_message
    assert "git@" not in failed.failure_message
    assert "token=" not in failed.failure_message
    assert "api_key" not in failed.failure_message
    assert "access_token" not in failed.failure_message
    assert "password:" not in failed.failure_message
    assert "Authorization:" not in failed.failure_message
    assert "base64-secret" not in failed.failure_message
    assert "C:\\Users" not in failed.failure_message
    assert "\n" not in failed.failure_message
