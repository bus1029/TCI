from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from tci.domain.services.failure_messages import bounded_failure_message
from tci.infrastructure.persistence.models import (
    RefType,
    RepositoryConnection,
    RepositorySyncRun,
    SyncFailureCode,
    SyncRunStatus,
    SyncTriggerType,
    Workspace,
    WorkspaceStatus,
)


@dataclass(frozen=True, slots=True)
class RepositorySyncRunDraft:
    id: uuid.UUID
    connection_id: uuid.UUID
    trigger_event_id: uuid.UUID | None
    trigger_type: SyncTriggerType
    requested_ref_type: RefType
    requested_ref_name: str
    requested_ref_key: str | None = None


class RepositorySyncRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_pending(self, draft: RepositorySyncRunDraft) -> RepositorySyncRun:
        return self._create(draft=draft, status=SyncRunStatus.PENDING)

    def create_blocked(self, draft: RepositorySyncRunDraft) -> RepositorySyncRun:
        return self._create(draft=draft, status=SyncRunStatus.BLOCKED)

    def _create(
        self, *, draft: RepositorySyncRunDraft, status: SyncRunStatus
    ) -> RepositorySyncRun:
        self._lock_active_connection_workspace(connection_id=draft.connection_id)
        sync_run = RepositorySyncRun(
            id=draft.id,
            connection_id=draft.connection_id,
            trigger_event_id=draft.trigger_event_id,
            trigger_type=draft.trigger_type,
            requested_ref_type=draft.requested_ref_type,
            requested_ref_name=draft.requested_ref_name,
            requested_ref_key=draft.requested_ref_key or draft.requested_ref_name,
            status=status,
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

    def get_active_for_trigger_event(
        self, *, connection_id: uuid.UUID, trigger_event_id: uuid.UUID
    ) -> RepositorySyncRun | None:
        statement = (
            select(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.trigger_event_id == trigger_event_id,
                RepositorySyncRun.status.in_(
                    (SyncRunStatus.PENDING, SyncRunStatus.RUNNING)
                ),
            )
            .order_by(RepositorySyncRun.started_at.desc(), RepositorySyncRun.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def get_active_for_requested_ref(
        self,
        *,
        connection_id: uuid.UUID,
        trigger_type: SyncTriggerType,
        requested_ref_type: RefType,
        requested_ref_name: str,
        requested_ref_key: str | None = None,
    ) -> RepositorySyncRun | None:
        requested_ref_key = requested_ref_key or requested_ref_name
        statement = (
            select(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.requested_ref_type == requested_ref_type,
                RepositorySyncRun.requested_ref_key == requested_ref_key,
                RepositorySyncRun.status == SyncRunStatus.PENDING,
            )
            .order_by(RepositorySyncRun.started_at.desc(), RepositorySyncRun.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def get_running_for_requested_ref(
        self,
        *,
        connection_id: uuid.UUID,
        requested_ref_type: RefType,
        requested_ref_name: str,
        requested_ref_key: str | None = None,
    ) -> RepositorySyncRun | None:
        requested_ref_key = requested_ref_key or requested_ref_name
        statement = (
            select(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.requested_ref_type == requested_ref_type,
                RepositorySyncRun.requested_ref_key == requested_ref_key,
                RepositorySyncRun.status == SyncRunStatus.RUNNING,
            )
            .order_by(RepositorySyncRun.started_at.desc(), RepositorySyncRun.id.desc())
            .limit(1)
        )
        return self._session.scalar(statement)

    def get_blocked_for_requested_ref(
        self,
        *,
        connection_id: uuid.UUID,
        requested_ref_type: RefType,
        requested_ref_name: str,
        requested_ref_key: str | None = None,
    ) -> RepositorySyncRun | None:
        requested_ref_key = requested_ref_key or requested_ref_name
        statement = (
            select(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.requested_ref_type == requested_ref_type,
                RepositorySyncRun.requested_ref_key == requested_ref_key,
                RepositorySyncRun.status == SyncRunStatus.BLOCKED,
            )
            .order_by(RepositorySyncRun.started_at.asc(), RepositorySyncRun.id.asc())
            .with_for_update(of=RepositorySyncRun)
            .limit(1)
        )
        return self._session.scalar(statement)

    def update_blocked_trigger_event(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        trigger_event_id: uuid.UUID,
        updated_at: datetime,
    ) -> RepositorySyncRun:
        self._lock_active_connection_workspace(connection_id=connection_id)
        sync_run = self._require_for_update(
            connection_id=connection_id, sync_run_id=sync_run_id
        )
        if sync_run.status is not SyncRunStatus.BLOCKED:
            raise ValueError("차단된 스냅샷 실행만 최신 이벤트로 교체할 수 있습니다.")
        sync_run.trigger_event_id = trigger_event_id
        sync_run.started_at = updated_at
        sync_run.dispatch_enqueued_at = None
        sync_run.completed_at = None
        sync_run.failure_code = None
        sync_run.failure_message = None
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def release_blocked(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        released_at: datetime,
    ) -> RepositorySyncRun:
        self._lock_active_connection_workspace(connection_id=connection_id)
        sync_run = self._require_for_update(
            connection_id=connection_id, sync_run_id=sync_run_id
        )
        if sync_run.status is not SyncRunStatus.BLOCKED:
            raise ValueError("차단된 스냅샷 실행만 대기 상태로 전환할 수 있습니다.")
        sync_run.status = SyncRunStatus.PENDING
        sync_run.started_at = released_at
        sync_run.dispatch_enqueued_at = None
        sync_run.completed_at = None
        sync_run.failure_code = None
        sync_run.failure_message = None
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def release_blocked_if_no_active(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        released_at: datetime,
    ) -> RepositorySyncRun | None:
        self._lock_active_connection_workspace(connection_id=connection_id)
        blocked = RepositorySyncRun.__table__
        active = RepositorySyncRun.__table__.alias("active_sync_run")
        active_exists = (
            select(active.c.id)
            .where(
                active.c.connection_id == connection_id,
                active.c.id != sync_run_id,
                active.c.requested_ref_type == blocked.c.requested_ref_type,
                active.c.requested_ref_key == blocked.c.requested_ref_key,
                active.c.status.in_(
                    (SyncRunStatus.PENDING.value, SyncRunStatus.RUNNING.value)
                ),
            )
            .exists()
        )
        statement = (
            update(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.id == sync_run_id,
                RepositorySyncRun.status == SyncRunStatus.BLOCKED,
                self._active_connection_workspace_exists(connection_id=connection_id),
                ~active_exists,
            )
            .values(
                status=SyncRunStatus.PENDING,
                started_at=released_at,
                dispatch_enqueued_at=None,
                completed_at=None,
                failure_code=None,
                failure_message=None,
            )
            .returning(RepositorySyncRun.id)
        )
        released_id = self._session.scalar(statement)
        self._session.flush()
        if released_id is None:
            return None
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
        self._session.refresh(sync_run)
        return sync_run

    def mark_dispatch_enqueued(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        enqueued_at: datetime,
    ) -> RepositorySyncRun:
        self._lock_active_connection_workspace(connection_id=connection_id)
        sync_run = self._require_for_update(
            connection_id=connection_id, sync_run_id=sync_run_id
        )
        sync_run.dispatch_enqueued_at = enqueued_at
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def clear_dispatch_enqueued(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
    ) -> RepositorySyncRun:
        self._lock_connection_workspace(
            connection_id=connection_id,
            statuses=(WorkspaceStatus.ACTIVE, WorkspaceStatus.DELETING),
            message="워크스페이스 스냅샷 실행만 큐 표시를 정리할 수 있습니다.",
        )
        sync_run = self._require_for_update(
            connection_id=connection_id, sync_run_id=sync_run_id
        )
        sync_run.dispatch_enqueued_at = None
        self._session.flush()
        self._session.refresh(sync_run)
        return sync_run

    def claim_dispatch_enqueued(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        enqueued_at: datetime,
        stale_before: datetime | None = None,
    ) -> bool:
        self._lock_active_connection_workspace(connection_id=connection_id)
        dispatch_predicate: ColumnElement[bool] = (
            RepositorySyncRun.dispatch_enqueued_at.is_(None)
        )
        if stale_before is not None:
            dispatch_predicate = or_(
                RepositorySyncRun.dispatch_enqueued_at.is_(None),
                RepositorySyncRun.dispatch_enqueued_at <= stale_before,
            )
        statement = (
            update(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.id == sync_run_id,
                RepositorySyncRun.status == SyncRunStatus.PENDING,
                self._active_connection_workspace_exists(connection_id=connection_id),
                dispatch_predicate,
            )
            .values(dispatch_enqueued_at=enqueued_at)
            .returning(RepositorySyncRun.id)
        )
        claimed_id = self._session.scalar(statement)
        self._session.flush()
        return claimed_id is not None

    def mark_running(
        self,
        *,
        connection_id: uuid.UUID,
        sync_run_id: uuid.UUID,
        started_at: datetime,
    ) -> RepositorySyncRun:
        self._lock_active_connection_workspace(connection_id=connection_id)
        statement = (
            update(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.id == sync_run_id,
                RepositorySyncRun.status == SyncRunStatus.PENDING,
                self._active_connection_workspace_exists(connection_id=connection_id),
            )
            .values(
                status=SyncRunStatus.RUNNING,
                started_at=started_at,
                failure_code=None,
                failure_message=None,
                completed_at=None,
            )
            .returning(RepositorySyncRun.id)
        )
        if self._session.scalar(statement) is None:
            raise ValueError("대기 중인 스냅샷 실행만 시작할 수 있습니다.")
        self._session.flush()
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
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
        terminal_statuses = (WorkspaceStatus.ACTIVE, WorkspaceStatus.DELETING)
        self._lock_connection_workspace(
            connection_id=connection_id,
            statuses=terminal_statuses,
            message="실행 중인 워크스페이스 스냅샷만 성공 처리할 수 있습니다.",
        )
        statement = (
            update(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.id == sync_run_id,
                RepositorySyncRun.status == SyncRunStatus.RUNNING,
                self._connection_workspace_exists(
                    connection_id=connection_id,
                    statuses=terminal_statuses,
                ),
            )
            .values(
                status=SyncRunStatus.SUCCEEDED,
                resolved_commit_sha=resolved_commit_sha,
                failure_code=None,
                failure_message=None,
                completed_at=completed_at,
            )
            .returning(RepositorySyncRun.id)
        )
        if self._session.scalar(statement) is None:
            raise ValueError(
                "실행 중인 활성 워크스페이스 스냅샷만 성공 처리할 수 있습니다."
            )
        self._session.flush()
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
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
        terminal_statuses = (WorkspaceStatus.ACTIVE, WorkspaceStatus.DELETING)
        self._lock_connection_workspace(
            connection_id=connection_id,
            statuses=terminal_statuses,
            message="워크스페이스 스냅샷 실행만 실패 처리할 수 있습니다.",
        )
        statement = (
            update(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.id == sync_run_id,
                RepositorySyncRun.status != SyncRunStatus.SUCCEEDED,
                self._connection_workspace_exists(
                    connection_id=connection_id,
                    statuses=terminal_statuses,
                ),
            )
            .values(
                status=SyncRunStatus.FAILED,
                failure_code=failure_code,
                failure_message=bounded_failure_message(failure_message),
                completed_at=completed_at,
            )
            .returning(RepositorySyncRun.id)
        )
        if self._session.scalar(statement) is None:
            sync_run = self._require_fresh(
                connection_id=connection_id,
                sync_run_id=sync_run_id,
            )
            if sync_run.status is SyncRunStatus.SUCCEEDED:
                return sync_run
            raise ValueError("활성 워크스페이스 스냅샷 실행만 실패 처리할 수 있습니다.")
        self._session.flush()
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
        self._session.refresh(sync_run)
        return sync_run

    @staticmethod
    def _active_connection_workspace_exists(*, connection_id: uuid.UUID):
        return RepositorySyncRunRepository._connection_workspace_exists(
            connection_id=connection_id,
            statuses=(WorkspaceStatus.ACTIVE,),
        )

    @staticmethod
    def _connection_workspace_exists(
        *, connection_id: uuid.UUID, statuses: tuple[WorkspaceStatus, ...]
    ):
        return (
            select(RepositoryConnection.id)
            .join(Workspace, RepositoryConnection.workspace_id == Workspace.id)
            .where(
                RepositoryConnection.id == connection_id,
                Workspace.status.in_(statuses),
            )
            .exists()
        )

    def _lock_active_connection_workspace(self, *, connection_id: uuid.UUID) -> None:
        self._lock_connection_workspace(
            connection_id=connection_id,
            statuses=(WorkspaceStatus.ACTIVE,),
            message="활성 워크스페이스 저장소 연결만 스냅샷 실행을 생성할 수 있습니다.",
        )

    def _lock_connection_workspace(
        self,
        *,
        connection_id: uuid.UUID,
        statuses: tuple[WorkspaceStatus, ...],
        message: str,
    ) -> None:
        workspace_id = self._session.scalar(
            select(RepositoryConnection.workspace_id).where(
                RepositoryConnection.id == connection_id
            )
        )
        if workspace_id is None:
            raise ValueError(message)
        workspace_status = self._session.scalar(
            select(Workspace.status)
            .where(Workspace.id == workspace_id)
            .with_for_update(of=Workspace)
        )
        if workspace_status not in statuses:
            raise ValueError(message)

    def delete_pending(
        self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID
    ) -> None:
        self._lock_connection_workspace(
            connection_id=connection_id,
            statuses=(WorkspaceStatus.ACTIVE, WorkspaceStatus.DELETING),
            message="워크스페이스 스냅샷 실행만 취소할 수 있습니다.",
        )
        sync_run = self._require_for_update(
            connection_id=connection_id, sync_run_id=sync_run_id
        )
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

    def _require_for_update(
        self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID
    ) -> RepositorySyncRun:
        statement = (
            select(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.id == sync_run_id,
            )
            .with_for_update(of=RepositorySyncRun)
        )
        sync_run = self._session.scalar(statement)
        if sync_run is None:
            raise LookupError("스냅샷 실행 이력을 찾을 수 없습니다.")
        return sync_run

    def _require_fresh(
        self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID
    ) -> RepositorySyncRun:
        statement = (
            select(RepositorySyncRun)
            .where(
                RepositorySyncRun.connection_id == connection_id,
                RepositorySyncRun.id == sync_run_id,
            )
            .execution_options(populate_existing=True)
        )
        sync_run = self._session.scalar(statement)
        if sync_run is None:
            raise LookupError("스냅샷 실행 이력을 찾을 수 없습니다.")
        return sync_run
