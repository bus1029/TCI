from __future__ import annotations

from datetime import datetime, timedelta
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import (
    Base,
    RefType,
    RepositorySyncRun,
    SyncFailureCode,
    SyncRunStatus,
    SyncTriggerType,
    WorkspaceStatus,
)
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunRepository,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE workspaces (id CHAR(32) PRIMARY KEY, status VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE repository_connections ("
                "id CHAR(32) PRIMARY KEY, "
                "workspace_id CHAR(32) NOT NULL"
                ")"
            )
        )
        Base.metadata.tables["repository_sync_runs"].create(connection)
        connection.execute(
            text(
                "CREATE TABLE code_snapshots ("
                "id CHAR(32) PRIMARY KEY, "
                "workspace_id CHAR(32), "
                "source_kind VARCHAR, "
                "connection_id CHAR(32), "
                "local_upload_id CHAR(32), "
                "sync_run_id CHAR(32), "
                "scope_rule_version_id CHAR(32), "
                "requested_ref_type VARCHAR, "
                "requested_ref_name VARCHAR, "
                "resolved_commit_sha VARCHAR, "
                "tree_sha VARCHAR, "
                "archive_path VARCHAR, "
                "file_count INTEGER, "
                "total_bytes INTEGER, "
                "created_at DATETIME"
                ")"
            )
        )
        connection.execute(text("DROP INDEX ix_sync_run_one_active_per_requested_ref"))
        connection.execute(text("DROP INDEX ix_sync_run_one_blocked_per_requested_ref"))
    return Session(engine)


def _connection(
    session: Session, *, workspace_status: WorkspaceStatus = WorkspaceStatus.ACTIVE
) -> uuid.UUID:
    workspace_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    session.execute(
        text("INSERT INTO workspaces (id, status) VALUES (:id, :status)"),
        {"id": workspace_id.hex, "status": workspace_status.value},
    )
    session.execute(
        text(
            "INSERT INTO repository_connections (id, workspace_id) VALUES (:id, :workspace_id)"
        ),
        {"id": connection_id.hex, "workspace_id": workspace_id.hex},
    )
    return connection_id


def _sync_run(
    *,
    connection_id: uuid.UUID,
    requested_ref_name: str,
    requested_ref_key: str,
    status: SyncRunStatus,
    dispatch_enqueued_at: datetime | None = None,
) -> RepositorySyncRun:
    return RepositorySyncRun(
        id=uuid.uuid4(),
        connection_id=connection_id,
        trigger_event_id=None,
        trigger_type=SyncTriggerType.WEBHOOK_PUSH,
        requested_ref_type=RefType.BRANCH,
        requested_ref_name=requested_ref_name,
        requested_ref_key=requested_ref_key,
        status=status,
        started_at=datetime.now(),
        dispatch_enqueued_at=dispatch_enqueued_at,
    )


def test_repository_sync_run_claim_dispatch_enqueued_respects_stale_marker() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session)
    now = datetime.now()
    fresh = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.PENDING,
        dispatch_enqueued_at=now - timedelta(minutes=1),
    )
    stale = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="stale-main",
        status=SyncRunStatus.PENDING,
        dispatch_enqueued_at=now - timedelta(minutes=16),
    )
    session.add_all((fresh, stale))
    session.commit()

    assert not repository.claim_dispatch_enqueued(
        connection_id=connection_id,
        sync_run_id=fresh.id,
        enqueued_at=now,
        stale_before=now - timedelta(minutes=15),
    )
    assert repository.claim_dispatch_enqueued(
        connection_id=connection_id,
        sync_run_id=stale.id,
        enqueued_at=now,
        stale_before=now - timedelta(minutes=15),
    )


def test_repository_sync_run_claim_dispatch_enqueued_requires_active_workspace() -> (
    None
):
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session, workspace_status=WorkspaceStatus.DELETING)
    pending = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.PENDING,
    )
    session.add(pending)
    session.commit()

    with pytest.raises(ValueError, match="활성 워크스페이스"):
        repository.claim_dispatch_enqueued(
            connection_id=connection_id,
            sync_run_id=pending.id,
            enqueued_at=datetime.now(),
        )


def test_repository_sync_run_release_blocked_if_no_active_uses_ref_key() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session)
    active = _sync_run(
        connection_id=connection_id,
        requested_ref_name="feature/shared",
        requested_ref_key="pr:101",
        status=SyncRunStatus.PENDING,
    )
    blocked_same_branch_different_pr = _sync_run(
        connection_id=connection_id,
        requested_ref_name="feature/shared",
        requested_ref_key="pr:102",
        status=SyncRunStatus.BLOCKED,
    )
    blocked_same_pr = _sync_run(
        connection_id=connection_id,
        requested_ref_name="feature/shared",
        requested_ref_key="pr:101",
        status=SyncRunStatus.BLOCKED,
    )
    session.add_all((active, blocked_same_branch_different_pr, blocked_same_pr))
    session.commit()

    released = repository.release_blocked_if_no_active(
        connection_id=connection_id,
        sync_run_id=blocked_same_branch_different_pr.id,
        released_at=datetime.now(),
    )
    blocked = repository.release_blocked_if_no_active(
        connection_id=connection_id,
        sync_run_id=blocked_same_pr.id,
        released_at=datetime.now(),
    )

    assert released is not None
    assert released.status is SyncRunStatus.PENDING
    assert blocked is None


def test_repository_sync_run_release_blocked_requires_active_workspace() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session, workspace_status=WorkspaceStatus.DELETING)
    blocked = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.BLOCKED,
    )
    session.add(blocked)
    session.commit()

    with pytest.raises(ValueError, match="활성 워크스페이스"):
        repository.release_blocked_if_no_active(
            connection_id=connection_id,
            sync_run_id=blocked.id,
            released_at=datetime.now(),
        )


def test_repository_sync_run_mark_running_requires_active_workspace() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session, workspace_status=WorkspaceStatus.DELETING)
    pending = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.PENDING,
    )
    session.add(pending)
    session.commit()

    with pytest.raises(ValueError, match="활성 워크스페이스"):
        repository.mark_running(
            connection_id=connection_id,
            sync_run_id=pending.id,
            started_at=datetime.now(),
        )


def test_repository_sync_run_allows_terminal_cleanup_when_workspace_deleting() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session, workspace_status=WorkspaceStatus.DELETING)
    succeeded = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.RUNNING,
    )
    failed = _sync_run(
        connection_id=connection_id,
        requested_ref_name="feature",
        requested_ref_key="feature",
        status=SyncRunStatus.RUNNING,
    )
    session.add_all((succeeded, failed))
    session.commit()

    marked_succeeded = repository.mark_succeeded(
        connection_id=connection_id,
        sync_run_id=succeeded.id,
        resolved_commit_sha="a" * 40,
        completed_at=datetime.now(),
    )
    marked_failed = repository.mark_failed(
        connection_id=connection_id,
        sync_run_id=failed.id,
        failure_code=SyncFailureCode.SNAPSHOT_WRITE_FAILED,
        failure_message="path=.runtime/code-snapshots/abc",
        completed_at=datetime.now(),
    )

    assert marked_succeeded.status is SyncRunStatus.SUCCEEDED
    assert marked_failed.status is SyncRunStatus.FAILED
    assert marked_failed.failure_message is not None
    assert ".runtime" not in marked_failed.failure_message


def test_repository_sync_run_mark_succeeded_rejects_non_running_run() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session)
    pending = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.PENDING,
    )
    session.add(pending)
    session.commit()

    with pytest.raises(ValueError, match="실행 중인 활성 워크스페이스 스냅샷"):
        repository.mark_succeeded(
            connection_id=connection_id,
            sync_run_id=pending.id,
            resolved_commit_sha="a" * 40,
            completed_at=datetime.now(),
        )

    assert pending.status is SyncRunStatus.PENDING


def test_repository_sync_run_mark_failed_returns_already_succeeded_run() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session)
    sync_run = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.SUCCEEDED,
    )
    session.add(sync_run)
    session.commit()

    marked_failed = repository.mark_failed(
        connection_id=connection_id,
        sync_run_id=sync_run.id,
        failure_code=SyncFailureCode.SNAPSHOT_WRITE_FAILED,
        failure_message="late failure",
        completed_at=datetime.now(),
    )

    assert marked_failed.status is SyncRunStatus.SUCCEEDED


def test_repository_sync_run_mark_failed_refreshes_concurrently_succeeded_run() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session)
    sync_run = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.RUNNING,
    )
    session.add(sync_run)
    session.commit()
    stale_sync_run = repository.get(
        connection_id=connection_id, sync_run_id=sync_run.id
    )
    assert stale_sync_run is not None
    assert stale_sync_run.status is SyncRunStatus.RUNNING
    session.execute(
        text("UPDATE repository_sync_runs SET status = :status WHERE id = :id"),
        {"status": SyncRunStatus.SUCCEEDED.value, "id": sync_run.id.hex},
    )

    marked_failed = repository.mark_failed(
        connection_id=connection_id,
        sync_run_id=sync_run.id,
        failure_code=SyncFailureCode.SNAPSHOT_WRITE_FAILED,
        failure_message="late failure",
        completed_at=datetime.now(),
    )

    assert marked_failed.status is SyncRunStatus.SUCCEEDED


def test_repository_sync_run_delete_pending_allows_deleting_workspace_cleanup() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = _connection(session, workspace_status=WorkspaceStatus.DELETING)
    pending = _sync_run(
        connection_id=connection_id,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.PENDING,
    )
    session.add(pending)
    session.commit()

    repository.delete_pending(connection_id=connection_id, sync_run_id=pending.id)

    assert repository.get(connection_id=connection_id, sync_run_id=pending.id) is None


def test_repository_sync_run_requested_ref_lookups_use_ref_key() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = uuid.uuid4()
    pr_101 = _sync_run(
        connection_id=connection_id,
        requested_ref_name="feature/shared",
        requested_ref_key="pr:101",
        status=SyncRunStatus.PENDING,
    )
    pr_102 = _sync_run(
        connection_id=connection_id,
        requested_ref_name="feature/shared",
        requested_ref_key="pr:102",
        status=SyncRunStatus.PENDING,
    )
    session.add_all((pr_101, pr_102))
    session.commit()

    found = repository.get_active_for_requested_ref(
        connection_id=connection_id,
        trigger_type=SyncTriggerType.WEBHOOK_PULL_REQUEST,
        requested_ref_type=RefType.BRANCH,
        requested_ref_name="feature/shared",
        requested_ref_key="pr:102",
    )

    assert found is not None
    assert found.id == pr_102.id
