from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from tci.infrastructure.persistence.models import (
    CollectionScopeRuleVersion,
    DefaultRefType,
    RepositoryConnection,
    RepositoryConnectionStatus,
    RepositoryProvider,
    RepositoryTransport,
    ScopeRuleWarningState,
)


@dataclass(frozen=True, slots=True)
class RepositoryConnectionDraft:
    id: uuid.UUID
    workspace_id: uuid.UUID
    planning_input_reference_id: uuid.UUID
    provider: RepositoryProvider
    remote_url: str
    transport: RepositoryTransport
    repository_owner: str
    repository_name: str
    default_ref_type: DefaultRefType
    default_ref_name: str
    status: RepositoryConnectionStatus
    mirror_path: str
    last_verified_at: datetime | None


class RepositoryConnectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, draft: RepositoryConnectionDraft) -> RepositoryConnection:
        connection = RepositoryConnection(
            id=draft.id,
            workspace_id=draft.workspace_id,
            planning_input_reference_id=draft.planning_input_reference_id,
            provider=draft.provider,
            remote_url=draft.remote_url,
            transport=draft.transport,
            repository_owner=draft.repository_owner,
            repository_name=draft.repository_name,
            default_ref_type=draft.default_ref_type,
            default_ref_name=draft.default_ref_name,
            status=draft.status,
            mirror_path=draft.mirror_path,
            last_verified_at=draft.last_verified_at,
        )
        self._session.add(connection)
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def get(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection | None:
        statement = (
            select(RepositoryConnection)
            .options(joinedload(RepositoryConnection.planning_input_reference))
            .where(
                RepositoryConnection.id == connection_id,
                RepositoryConnection.workspace_id == workspace_id,
            )
        )
        return self._session.scalar(statement)

    def list_for_workspace(
        self, *, workspace_id: uuid.UUID
    ) -> list[RepositoryConnection]:
        statement = (
            select(RepositoryConnection)
            .options(joinedload(RepositoryConnection.planning_input_reference))
            .where(RepositoryConnection.workspace_id == workspace_id)
            .order_by(RepositoryConnection.created_at.desc(), RepositoryConnection.id.desc())
        )
        return list(self._session.scalars(statement).unique())

    def set_active_credential_revision(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        credential_revision_id: uuid.UUID,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.active_credential_revision_id = credential_revision_id
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def update_default_ref(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        default_ref_type: DefaultRefType,
        default_ref_name: str,
        status: RepositoryConnectionStatus,
        last_verified_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.default_ref_type = default_ref_type
        connection.default_ref_name = default_ref_name
        connection.status = status
        connection.last_verified_at = last_verified_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def update_verification(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        status: RepositoryConnectionStatus,
        last_verified_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.status = status
        connection.last_verified_at = last_verified_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def ensure_default_scope_rule_version(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> CollectionScopeRuleVersion:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection.active_scope_rule_version is not None:
            return connection.active_scope_rule_version

        scope_rule = CollectionScopeRuleVersion(
            connection_id=connection.id,
            planning_input_reference_id=connection.planning_input_reference_id,
            include_paths=[],
            exclude_paths=[],
            allowed_file_types=[],
            blocked_file_types=[],
            max_file_size_bytes=5 * 1024 * 1024,
            exclude_binary=True,
            warning_state=ScopeRuleWarningState.OK,
            created_by=created_by,
        )
        self._session.add(scope_rule)
        self._session.flush()
        connection.active_scope_rule_version_id = scope_rule.id
        connection.active_scope_rule_version = scope_rule
        self._session.flush()
        self._session.refresh(scope_rule)
        self._session.refresh(connection)
        return scope_rule

    def record_sync_failure(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        failed_at: datetime,
        status: RepositoryConnectionStatus | None = None,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.last_failed_sync_at = failed_at
        if status is not None:
            connection.status = status
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def record_snapshot_success(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        succeeded_at: datetime,
        scope_rule_version_id: uuid.UUID,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.last_successful_snapshot_at = succeeded_at
        connection.active_scope_rule_version_id = scope_rule_version_id
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def _require(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection:
        connection = self.get(workspace_id=workspace_id, connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection
