from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from tci.domain.services.delete_workspace import (
    DeleteWorkspaceCommand,
    WorkspaceDeleteProblem,
    delete_workspace,
    get_workspace_deletion_impact,
)
from tci.infrastructure.persistence.models import (
    CodeSnapshot,
    CodeSnapshotSourceKind,
    DefaultRefType,
    LocalUpload,
    LocalUploadStatus,
    RepositoryConnection,
    RepositoryConnectionStatus,
    RepositoryProvider,
    RepositoryTransport,
    WebhookAuthMode,
    Workspace,
    WorkspaceDeletionRecord,
    WorkspaceDeletionPurgeStatus,
    WorkspaceStatus,
    PlanningInputReference,
    PlanningInputSourceType,
    RefType,
)
from tests.support.repository_connection_testkit import (
    InMemoryRepositoryStore,
    TestRepositoryEvent,
    TestRepositoryEventCursor,
    create_test_client,
    now_utc,
)


def test_get_workspace_deletion_impact_counts_sources(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)
    _seed_snapshot(store, workspace_id=workspace_id)

    impact = get_workspace_deletion_impact(
        workspace_id=workspace_id,
        operator_role="owner",
        dependencies=cast(Any, client.app).state.dependencies,
    )

    assert impact.workspace_id == workspace_id
    assert impact.snapshot_count == 1
    assert impact.project_content_will_be_removed is True
    assert impact.audit_metadata_will_remain is True
    assert impact.confirmation == f"DELETE {workspace_id}"


def test_get_workspace_deletion_impact_rejects_deleted_workspace(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)
    store.workspaces[workspace_id].status = WorkspaceStatus.DELETED
    store.workspaces[workspace_id].deleted_at = now_utc()
    store.workspaces[workspace_id].deleted_by = "owner-a"

    with pytest.raises(WorkspaceDeleteProblem) as exc_info:
        get_workspace_deletion_impact(
            workspace_id=workspace_id,
            operator_role="owner",
            dependencies=cast(Any, client.app).state.dependencies,
        )

    assert exc_info.value.code == "workspace_deleted"
    assert exc_info.value.status_code == 409


def test_delete_workspace_rejects_non_owner_or_admin(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)

    with pytest.raises(WorkspaceDeleteProblem) as exc_info:
        delete_workspace(
            DeleteWorkspaceCommand(
                workspace_id=workspace_id,
                confirmation=f"DELETE {workspace_id}",
                deleted_by="viewer-a",
                operator_role="viewer",
            ),
            dependencies=cast(Any, client.app).state.dependencies,
        )

    assert exc_info.value.code == "workspace_delete_forbidden"
    assert exc_info.value.status_code == 403
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE


def test_delete_workspace_rejects_wrong_confirmation(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)

    with pytest.raises(WorkspaceDeleteProblem) as exc_info:
        delete_workspace(
            DeleteWorkspaceCommand(
                workspace_id=workspace_id,
                confirmation="delete",
                deleted_by="owner-a",
                operator_role="owner",
            ),
            dependencies=cast(Any, client.app).state.dependencies,
        )

    assert exc_info.value.code == "workspace_delete_confirmation_required"
    assert exc_info.value.status_code == 400
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE


def test_delete_workspace_soft_deletes_purges_content_and_records_audit(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)
    snapshot = _seed_snapshot(store, workspace_id=workspace_id)
    assert snapshot.local_upload_id is not None
    store.local_uploads[snapshot.local_upload_id] = _local_upload(
        workspace_id=workspace_id,
        local_upload_id=snapshot.local_upload_id,
    )
    archive_root = cast(Any, client.app).state.settings.code_snapshot_root / str(
        snapshot.id
    )
    archive_root.mkdir(parents=True)
    (archive_root / "manifest.json").write_text("{}", encoding="utf-8")
    queue_root = (
        cast(Any, client.app).state.settings.runtime_root / "local-upload-queue"
    )
    queue_root.mkdir(parents=True)
    queue_zip = queue_root / f"{snapshot.local_upload_id}.zip"
    queue_zip.write_bytes(b"zip")
    connection = _seed_connection(store, workspace_id=workspace_id)
    repository_snapshot = _seed_repository_snapshot(
        store, workspace_id=workspace_id, connection_id=connection.id
    )
    event_id = _seed_repository_event(
        store, connection_id=connection.id, snapshot_id=repository_snapshot.id
    ).id
    _seed_event_cursor(store, connection_id=connection.id, event_id=event_id)
    mirror_root = (
        cast(Any, client.app).state.settings.project_root / connection.mirror_path
    )
    mirror_root.mkdir(parents=True)
    (mirror_root / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    planning_reference_id = _seed_planning_input_reference(
        store, workspace_id=workspace_id
    ).id

    response = delete_workspace(
        DeleteWorkspaceCommand(
            workspace_id=workspace_id,
            confirmation=f"DELETE {workspace_id}",
            deleted_by="owner-a",
            operator_role="owner",
            reason="/private/path.zip token=secret",
        ),
        dependencies=cast(Any, client.app).state.dependencies,
    )

    record = next(iter(store.workspace_deletion_records.values()))
    assert response.workspace_id == workspace_id
    assert response.status == "deleted"
    assert response.project_content_removed is True
    assert response.deletion_record_id == record.id
    assert store.workspaces[workspace_id].status is WorkspaceStatus.DELETED
    assert store.workspaces[workspace_id].deleted_by == "owner-a"
    assert "token=secret" not in (store.workspaces[workspace_id].delete_reason or "")
    assert "private" not in (store.workspaces[workspace_id].delete_reason or "")
    assert archive_root.exists() is False
    assert queue_zip.exists() is False
    assert mirror_root.exists() is False
    assert store.snapshots == {}
    assert store.local_uploads == {}
    assert store.connections == {}
    assert store.repository_events == {}
    assert store.event_cursors == {}
    assert planning_reference_id not in store.planning_input_references
    assert record.snapshot_count == 2
    assert record.purged_archive_count == 1
    assert record.purge_status is WorkspaceDeletionPurgeStatus.SUCCEEDED
    assert record.completed_at is not None


def test_delete_workspace_reports_existing_deleted_state_without_new_record(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)
    store.workspaces[workspace_id].status = WorkspaceStatus.DELETED
    store.workspaces[workspace_id].deleted_at = now_utc()
    store.workspaces[workspace_id].deleted_by = "owner-a"

    response = delete_workspace(
        DeleteWorkspaceCommand(
            workspace_id=workspace_id,
            confirmation=f"DELETE {workspace_id}",
            deleted_by="owner-a",
            operator_role="owner",
        ),
        dependencies=cast(Any, client.app).state.dependencies,
    )

    assert response.status == "deleted"
    assert response.project_content_removed is True
    assert response.deletion_record_id is None
    assert store.workspace_deletion_records == {}


def test_delete_workspace_records_failed_purge_without_success_claim(
    monkeypatch, tmp_path
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)
    snapshot = _seed_snapshot(store, workspace_id=workspace_id)
    assert snapshot.local_upload_id is not None
    store.local_uploads[snapshot.local_upload_id] = _local_upload(
        workspace_id=workspace_id,
        local_upload_id=snapshot.local_upload_id,
    )
    queue_root = (
        cast(Any, client.app).state.settings.runtime_root / "local-upload-queue"
    )
    queue_root.mkdir(parents=True)
    queue_zip = queue_root / f"{snapshot.local_upload_id}.zip"
    queue_zip.write_bytes(b"zip")

    def fail_purge(*, snapshots):
        raise OSError("disk still busy")

    monkeypatch.setattr(
        cast(Any, client.app).state.dependencies.snapshot_archive_store,
        "purge_workspace_snapshots",
        fail_purge,
    )

    response = delete_workspace(
        DeleteWorkspaceCommand(
            workspace_id=workspace_id,
            confirmation=f"DELETE {workspace_id}",
            deleted_by="owner-a",
            operator_role="owner",
        ),
        dependencies=cast(Any, client.app).state.dependencies,
    )

    record = next(iter(store.workspace_deletion_records.values()))
    assert response.status == "deleting"
    assert response.project_content_removed is False
    assert store.workspaces[workspace_id].status is WorkspaceStatus.DELETING
    assert store.snapshots[snapshot.id] is snapshot
    assert store.local_uploads[snapshot.local_upload_id].id == snapshot.local_upload_id
    assert queue_zip.exists() is False
    assert record.purge_status is WorkspaceDeletionPurgeStatus.FAILED
    assert record.failure_message == "snapshot archives: disk still busy"


def test_delete_workspace_redacts_purge_failure_metadata(monkeypatch, tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)
    _seed_snapshot(store, workspace_id=workspace_id)

    def fail_purge(*, snapshots):
        raise OSError("/Users/operator/private.zip token=secret")

    monkeypatch.setattr(
        cast(Any, client.app).state.dependencies.snapshot_archive_store,
        "purge_workspace_snapshots",
        fail_purge,
    )

    delete_workspace(
        DeleteWorkspaceCommand(
            workspace_id=workspace_id,
            confirmation=f"DELETE {workspace_id}",
            deleted_by="owner-a",
            operator_role="owner",
        ),
        dependencies=cast(Any, client.app).state.dependencies,
    )

    record = next(iter(store.workspace_deletion_records.values()))
    assert record.failure_message is not None
    assert "/Users" not in record.failure_message
    assert "private.zip" not in record.failure_message
    assert "secret" not in record.failure_message


def test_delete_workspace_resumes_deleting_workspace_and_reuses_audit_record(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id)
    snapshot = _seed_snapshot(store, workspace_id=workspace_id)
    record_id = uuid.uuid4()
    store.workspaces[workspace_id].status = WorkspaceStatus.DELETING
    store.workspace_deletion_records[record_id] = WorkspaceDeletionRecord(
        id=record_id,
        workspace_id=workspace_id,
        deleted_by="owner-a",
        repository_connection_count=0,
        local_upload_count=0,
        snapshot_count=1,
        purge_status=WorkspaceDeletionPurgeStatus.FAILED,
        failure_message="snapshot archives: disk still busy",
        requested_at=now_utc(),
        completed_at=now_utc(),
    )
    archive_root = cast(Any, client.app).state.settings.code_snapshot_root / str(
        snapshot.id
    )
    archive_root.mkdir(parents=True)

    response = delete_workspace(
        DeleteWorkspaceCommand(
            workspace_id=workspace_id,
            confirmation=f"DELETE {workspace_id}",
            deleted_by="owner-a",
            operator_role="owner",
        ),
        dependencies=cast(Any, client.app).state.dependencies,
    )

    assert response.status == "deleted"
    assert response.deletion_record_id == record_id
    assert store.workspaces[workspace_id].status is WorkspaceStatus.DELETED
    assert store.workspace_deletion_records[record_id].purge_status is (
        WorkspaceDeletionPurgeStatus.SUCCEEDED
    )
    assert archive_root.exists() is False


def _seed_workspace(store: InMemoryRepositoryStore, *, workspace_id: uuid.UUID) -> None:
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE,
        created_at=now_utc(),
        updated_at=now_utc(),
    )


def _seed_snapshot(
    store: InMemoryRepositoryStore, *, workspace_id: uuid.UUID
) -> CodeSnapshot:
    snapshot = CodeSnapshot(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        source_kind=CodeSnapshotSourceKind.LOCAL_UPLOAD,
        connection_id=None,
        local_upload_id=uuid.uuid4(),
        sync_run_id=None,
        scope_rule_version_id=None,
        requested_ref_type=None,
        requested_ref_name=None,
        resolved_commit_sha=None,
        tree_sha=None,
        archive_path=f".runtime/code-snapshots/{uuid.uuid4()}",
        file_count=1,
        total_bytes=10,
        created_at=now_utc(),
    )
    store.snapshots[snapshot.id] = snapshot
    return snapshot


def _seed_connection(
    store: InMemoryRepositoryStore, *, workspace_id: uuid.UUID
) -> RepositoryConnection:
    connection_id = uuid.uuid4()
    connection = RepositoryConnection(
        id=connection_id,
        workspace_id=workspace_id,
        planning_input_reference_id=None,
        provider=RepositoryProvider.GITHUB_CLOUD,
        remote_url="https://github.com/acme/project.git",
        provider_instance_url=None,
        transport=RepositoryTransport.HTTPS,
        repository_owner="acme",
        repository_name="project",
        provider_project_path="acme/project",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=f".runtime/git-mirrors/{connection_id}.git",
        webhook_auth_mode=WebhookAuthMode.HMAC_SHA256,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    store.connections[connection_id] = connection
    return connection


def _seed_repository_snapshot(
    store: InMemoryRepositoryStore,
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> CodeSnapshot:
    snapshot = CodeSnapshot(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        source_kind=CodeSnapshotSourceKind.REPOSITORY_CONNECTION,
        connection_id=connection_id,
        local_upload_id=None,
        sync_run_id=uuid.uuid4(),
        scope_rule_version_id=uuid.uuid4(),
        requested_ref_type=RefType.BRANCH,
        requested_ref_name="main",
        resolved_commit_sha="a" * 40,
        tree_sha="b" * 40,
        archive_path=f".runtime/code-snapshots/{uuid.uuid4()}",
        file_count=1,
        total_bytes=10,
        created_at=now_utc(),
    )
    store.snapshots[snapshot.id] = snapshot
    return snapshot


def _seed_repository_event(
    store: InMemoryRepositoryStore,
    *,
    connection_id: uuid.UUID,
    snapshot_id: uuid.UUID,
) -> TestRepositoryEvent:
    event = TestRepositoryEvent(
        id=uuid.uuid4(),
        connection_id=connection_id,
        provider_delivery_id="delivery-1",
        provider_event_idempotency_source="delivery_header",
        provider_event_type="push",
        provider_action=None,
        target_key="branch:main",
        target_head_sha="a" * 40,
        signature_status="valid",
        processing_decision="processed",
        processing_status="succeeded",
        received_at=now_utc(),
        snapshot_id=snapshot_id,
    )
    store.repository_events[event.id] = event
    return event


def _seed_event_cursor(
    store: InMemoryRepositoryStore,
    *,
    connection_id: uuid.UUID,
    event_id: uuid.UUID,
) -> TestRepositoryEventCursor:
    cursor = TestRepositoryEventCursor(
        id=uuid.uuid4(),
        connection_id=connection_id,
        target_key="branch:main",
        latest_head_sha="a" * 40,
        latest_event_id=event_id,
        updated_at=now_utc(),
    )
    store.event_cursors[(connection_id, cursor.target_key)] = cursor
    return cursor


def _seed_planning_input_reference(
    store: InMemoryRepositoryStore, *, workspace_id: uuid.UUID
) -> PlanningInputReference:
    reference = PlanningInputReference(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="Private planning title",
        source_reference="manual://private/reference",
        approved_spec_path="specs/004-zip-upload-workspace-delete/spec.md",
        approved_plan_path="specs/004-zip-upload-workspace-delete/plan.md",
        created_at=now_utc(),
    )
    store.planning_input_references[reference.id] = reference
    return reference


def _local_upload(
    *, workspace_id: uuid.UUID, local_upload_id: uuid.UUID
) -> LocalUpload:
    return LocalUpload(
        id=local_upload_id,
        workspace_id=workspace_id,
        status=LocalUploadStatus.SUCCEEDED,
        original_filename_display="project.zip",
        upload_sha256="a" * 64,
        compressed_size_bytes=3,
        uncompressed_size_bytes=10,
        file_count=1,
        directory_count=0,
        latest_snapshot_id=None,
        created_by="operator",
        created_at=now_utc(),
    )
