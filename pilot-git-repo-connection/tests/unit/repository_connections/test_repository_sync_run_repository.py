from __future__ import annotations

from datetime import datetime, timedelta
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import (
    Base,
    RefType,
    RepositorySyncRun,
    SyncRunStatus,
    SyncTriggerType,
)
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunRepository,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.tables["repository_sync_runs"].create(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX ix_sync_run_one_active_per_requested_ref"))
        connection.execute(text("DROP INDEX ix_sync_run_one_blocked_per_requested_ref"))
    return Session(engine)


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
    connection_id = uuid.uuid4()
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


def test_repository_sync_run_release_blocked_if_no_active_uses_ref_key() -> None:
    session = _session()
    repository = RepositorySyncRunRepository(session)
    connection_id = uuid.uuid4()
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
