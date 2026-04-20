from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import (
    RefType,
    RepositorySyncRun,
    SyncFailureCode,
    SyncRunStatus,
    SyncTriggerType,
)


@dataclass(frozen=True, slots=True)
class RepositorySyncRunDraft:
    id: uuid.UUID
    connection_id: uuid.UUID
    trigger_type: SyncTriggerType
    requested_ref_type: RefType
    requested_ref_name: str


class RepositorySyncRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_pending(self, draft: RepositorySyncRunDraft) -> RepositorySyncRun:
        sync_run = RepositorySyncRun(
            id=draft.id,
            connection_id=draft.connection_id,
            trigger_type=draft.trigger_type,
            requested_ref_type=draft.requested_ref_type,
            requested_ref_name=draft.requested_ref_name,
            status=SyncRunStatus.PENDING,
        )
        self._session.add(sync_run)
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def get(
        self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID
    ) -> RepositorySyncRun | None:
        statement = select(RepositorySyncRun).where(
            RepositorySyncRun.connection_id == connection_id,
            RepositorySyncRun.id == sync_run_id,
        )
        return self._session.scalar(statement)

    def get_latest_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> RepositorySyncRun | None:
        statement = (
            select(RepositorySyncRun)
            .where(RepositorySyncRun.connection_id == connection_id)
            .order_by(RepositorySyncRun.started_at.desc(), RepositorySyncRun.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def mark_running(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        started_at: datetime,
    ) -> RepositorySyncRun:
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
        if sync_run.status is not SyncRunStatus.PENDING:
            raise ValueError("대기 중인 스냅샷 실행만 시작할 수 있습니다.")
        sync_run.status = SyncRunStatus.RUNNING
        sync_run.started_at = started_at
        sync_run.failure_code = None
        sync_run.failure_message = None
        sync_run.completed_at = None
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def mark_succeeded(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        resolved_commit_sha: str,
        completed_at: datetime,
    ) -> RepositorySyncRun:
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
        sync_run.status = SyncRunStatus.SUCCEEDED
        sync_run.resolved_commit_sha = resolved_commit_sha
        sync_run.failure_code = None
        sync_run.failure_message = None
        sync_run.completed_at = completed_at
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def mark_failed(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        failure_code: SyncFailureCode,
        failure_message: str,
        completed_at: datetime,
    ) -> RepositorySyncRun:
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
        sync_run.status = SyncRunStatus.FAILED
        sync_run.failure_code = failure_code
        sync_run.failure_message = failure_message
        sync_run.completed_at = completed_at
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def delete_pending(self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID) -> None:
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
        if sync_run.status is not SyncRunStatus.PENDING:
            raise ValueError("대기 중인 스냅샷 실행만 취소할 수 있습니다.")
        self._session.delete(sync_run)
        self._session.flush()

    def _require(
        self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID
    ) -> RepositorySyncRun:
        sync_run = self.get(connection_id=connection_id, sync_run_id=sync_run_id)
        if sync_run is None:
            raise LookupError("스냅샷 실행 이력을 찾을 수 없습니다.")
        return sync_run
