from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from tci.infrastructure.persistence.models import (
    CollectionScopeRuleVersion,
    RepositoryConnection,
    ScopeRuleWarningState,
)


@dataclass(frozen=True, slots=True)
class ScopeRuleVersionDraft:
    include_paths: list[str]
    exclude_paths: list[str]
    allowed_file_types: list[str]
    blocked_file_types: list[str]
    max_file_size_bytes: int
    exclude_binary: bool
    warning_state: ScopeRuleWarningState
    created_by: uuid.UUID


class ScopeRuleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_for_connection(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> CollectionScopeRuleVersion | None:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        return connection.active_scope_rule_version

    def create_active_version(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        draft: ScopeRuleVersionDraft,
    ) -> CollectionScopeRuleVersion:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        scope_rule = CollectionScopeRuleVersion(
            connection_id=connection.id,
            planning_input_reference_id=connection.planning_input_reference_id,
            include_paths=draft.include_paths,
            exclude_paths=draft.exclude_paths,
            allowed_file_types=draft.allowed_file_types,
            blocked_file_types=draft.blocked_file_types,
            max_file_size_bytes=draft.max_file_size_bytes,
            exclude_binary=draft.exclude_binary,
            warning_state=draft.warning_state,
            created_by=draft.created_by,
        )
        self._session.add(scope_rule)
        self._session.flush()
        connection.active_scope_rule_version_id = scope_rule.id
        connection.active_scope_rule_version = scope_rule
        self._session.flush()
        self._session.refresh(scope_rule)
        self._session.refresh(connection)
        return scope_rule

    def _require_connection(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection:
        statement = (
            select(RepositoryConnection)
            .options(joinedload(RepositoryConnection.active_scope_rule_version))
            .where(
                RepositoryConnection.id == connection_id,
                RepositoryConnection.workspace_id == workspace_id,
            )
        )
        connection = self._session.scalar(statement)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection
