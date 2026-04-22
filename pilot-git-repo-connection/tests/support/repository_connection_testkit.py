from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
import uuid

from fastapi.testclient import TestClient

from tci.app import AppDependencies, create_app
from tci.domain.services.build_traceability_reference import (
    build_snapshot_traceability_reference,
)
from tci.infrastructure.git.git_mirror_manager import (
    ManagedGitMirror,
    MaterializedGitSnapshot,
)
from tci.infrastructure.git.git_readonly_validator import ReadonlyProbeResult
from tci.infrastructure.git.git_ref_resolver import (
    GitConnectionAuthError,
    GitRefNotFoundError,
    ResolvedGitRef,
)
from tci.infrastructure.persistence.code_snapshot_repository import CodeSnapshotRepository
from tci.infrastructure.persistence.credential_revision_repository import (
    CredentialRevisionRepository,
)
from tci.infrastructure.persistence.models import (
    CodeSnapshot,
    CodeSnapshotFile,
    CollectionScopeRuleVersion,
    CredentialRevisionStatus,
    CredentialType,
    DefaultRefType,
    PlanningInputReference,
    PlanningInputSourceType,
    RefType,
    RepositoryConnection,
    RepositoryConnectionStatus,
    RepositoryCredentialRevision,
    RepositoryProvider,
    RepositoryTransport,
    RepositorySyncRun,
    ScopeRuleWarningState,
    SnapshotInclusionReason,
    SyncFailureCode,
    SyncRunStatus,
    SyncTriggerType,
    WebhookHealthState,
    WebhookRejectionReason,
)
from tci.infrastructure.persistence.repository_connection_repository import (
    RepositoryConnectionRepository,
)
from tci.infrastructure.persistence.repository_event_cursor_repository import (
    RepositoryEventCursorRepository,
)
from tci.infrastructure.persistence.repository_event_repository import (
    RepositoryEventRepository,
)
from tci.infrastructure.persistence.planning_input_reference_repository import (
    PlanningInputReferenceRepository,
)
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunRepository,
)
from tci.infrastructure.persistence.scope_rule_repository import ScopeRuleRepository
from tci.infrastructure.persistence.session import build_session_factory
from tci.infrastructure.persistence.webhook_secret_repository import (
    WebhookSecretRepository,
)
from tci.infrastructure.snapshots.snapshot_archive_store import (
    SnapshotArchiveEntryDraft,
    SnapshotArchiveStore,
)
from tci.infrastructure.snapshots.snapshot_manifest_writer import SnapshotManifestWriter
from tci.settings import load_settings


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class TestWebhookSecretRevision:
    id: uuid.UUID
    connection_id: uuid.UUID
    secret: str | None
    status: str
    created_at: datetime
    encrypted_secret: str | None = None
    grace_until: datetime | None = None


@dataclass(slots=True)
class TestRepositoryEventCursor:
    id: uuid.UUID
    connection_id: uuid.UUID
    target_key: str
    latest_head_sha: str
    latest_event_id: uuid.UUID
    updated_at: datetime


@dataclass(slots=True)
class TestRepositoryEvent:
    id: uuid.UUID
    connection_id: uuid.UUID
    provider_delivery_id: str
    provider_event_type: str
    provider_action: str | None
    target_key: str
    target_head_sha: str | None
    signature_status: str
    processing_decision: str
    processing_status: str
    received_at: datetime
    domain_event_type: str | None = None
    target_kind: str | None = None
    target_ref_name: str | None = None
    occurred_at: datetime | None = None
    payload_hash: str | None = None
    verified_secret_revision_id: uuid.UUID | None = None
    verified_secret_revision_status: str | None = None
    rejection_reason: str | None = None
    sync_run_id: uuid.UUID | None = None
    snapshot_id: uuid.UUID | None = None
    processed_at: datetime | None = None


@dataclass(slots=True)
class InMemoryRepositoryStore:
    planning_input_references: dict[uuid.UUID, PlanningInputReference] = field(
        default_factory=dict
    )
    connections: dict[uuid.UUID, RepositoryConnection] = field(default_factory=dict)
    scope_rule_versions: dict[uuid.UUID, CollectionScopeRuleVersion] = field(
        default_factory=dict
    )
    credentials: dict[uuid.UUID, RepositoryCredentialRevision] = field(
        default_factory=dict
    )
    webhook_secret_revisions: dict[uuid.UUID, TestWebhookSecretRevision] = field(
        default_factory=dict
    )
    repository_events: dict[uuid.UUID, TestRepositoryEvent] = field(default_factory=dict)
    event_cursors: dict[tuple[uuid.UUID, str], TestRepositoryEventCursor] = field(
        default_factory=dict
    )
    sync_runs: dict[uuid.UUID, RepositorySyncRun] = field(default_factory=dict)
    snapshots: dict[uuid.UUID, CodeSnapshot] = field(default_factory=dict)
    webhook_rotation_lock_calls: int = 0
    resolver_requires_bound_credential: bool = False
    auth_failure_ref_names: set[str] = field(default_factory=set)
    missing_ref_names: set[str] = field(default_factory=set)
    last_resolved_remote_url: str | None = None
    resolved_ref_commits: dict[str, str] = field(default_factory=dict)
    mirror_sync_error: Exception | None = None
    mirror_tree_sha: str = "b" * 40
    mirror_snapshot_entries: tuple[tuple[str, bytes], ...] = field(
        default_factory=lambda: (("src/main.py", b"print('hello')\n"),)
    )


class FakePlanningInputReferenceRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def create(self, draft) -> PlanningInputReference:
        PlanningInputReferenceRepository._validate_feature_paths(
            spec_path=draft.approved_spec_path,
            plan_path=draft.approved_plan_path,
        )
        reference = PlanningInputReference(
            id=uuid.uuid4(),
            workspace_id=draft.workspace_id,
            source_type=draft.source_type,
            source_title=draft.source_title,
            source_reference=draft.source_reference,
            approved_spec_path=draft.approved_spec_path,
            approved_plan_path=draft.approved_plan_path,
            created_at=now_utc(),
        )
        self._store.planning_input_references[reference.id] = reference
        return reference

    def get(
        self, *, workspace_id: uuid.UUID, reference_id: uuid.UUID
    ) -> PlanningInputReference | None:
        reference = self._store.planning_input_references.get(reference_id)
        if reference is None or reference.workspace_id != workspace_id:
            return None
        return reference

    def get_any(self, *, reference_id: uuid.UUID) -> PlanningInputReference | None:
        return self._store.planning_input_references.get(reference_id)


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


class FakeRepositoryConnectionRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

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
            last_successful_snapshot_at=None,
            last_failed_sync_at=None,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        self._store.connections[connection.id] = connection
        return connection

    def get(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection | None:
        connection = self._store.connections.get(connection_id)
        if connection is None or connection.workspace_id != workspace_id:
            return None
        return connection

    def get_for_update(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection | None:
        self._store.webhook_rotation_lock_calls += 1
        return self.get(workspace_id=workspace_id, connection_id=connection_id)

    def get_any(self, *, connection_id: uuid.UUID) -> RepositoryConnection | None:
        return self._store.connections.get(connection_id)

    def list_for_workspace(
        self, *, workspace_id: uuid.UUID
    ) -> list[RepositoryConnection]:
        return sorted(
            [
                connection
                for connection in self._store.connections.values()
                if connection.workspace_id == workspace_id
            ],
            key=lambda connection: (connection.created_at, connection.id),
            reverse=True,
        )

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
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.default_ref_type = default_ref_type
        connection.default_ref_name = default_ref_name
        connection.status = status
        connection.last_verified_at = last_verified_at
        connection.updated_at = now_utc()
        return connection

    def set_active_credential_revision(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        credential_revision_id: uuid.UUID,
    ) -> RepositoryConnection:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.active_credential_revision_id = credential_revision_id
        connection.active_credential_revision = self._store.credentials[credential_revision_id]
        connection.updated_at = now_utc()
        return connection

    def set_active_webhook_secret_revision(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        webhook_secret_revision_id: uuid.UUID,
    ) -> RepositoryConnection:
        connection = self.get(workspace_id=workspace_id, connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        connection.active_webhook_secret_revision_id = webhook_secret_revision_id
        connection.webhook_health_state = WebhookHealthState.HEALTHY
        connection.last_webhook_rejection_reason = None
        connection.last_webhook_rejected_at = None
        connection.updated_at = now_utc()
        return connection

    def update_verification(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        status: RepositoryConnectionStatus,
        last_verified_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.status = status
        connection.last_verified_at = last_verified_at
        connection.updated_at = now_utc()
        return connection

    def ensure_default_scope_rule_version(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> CollectionScopeRuleVersion:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection.active_scope_rule_version_id is not None:
            return self._store.scope_rule_versions[connection.active_scope_rule_version_id]

        scope_rule = CollectionScopeRuleVersion(
            id=uuid.uuid4(),
            connection_id=connection.id,
            planning_input_reference_id=connection.planning_input_reference_id,
            include_paths=[],
            exclude_paths=[],
            allowed_file_types=[],
            blocked_file_types=[],
            max_file_size_bytes=5 * 1024 * 1024,
            exclude_binary=True,
            warning_state=ScopeRuleWarningState.OK,
            created_at=now_utc(),
            created_by=created_by,
        )
        self._store.scope_rule_versions[scope_rule.id] = scope_rule
        connection.active_scope_rule_version_id = scope_rule.id
        connection.active_scope_rule_version = scope_rule
        connection.updated_at = now_utc()
        return scope_rule

    def record_sync_failure(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        failed_at: datetime,
        status: RepositoryConnectionStatus | None = None,
    ) -> RepositoryConnection:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.last_failed_sync_at = failed_at
        if status is not None:
            connection.status = status
        connection.updated_at = now_utc()
        return connection

    def record_snapshot_success(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        succeeded_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.last_successful_snapshot_at = succeeded_at
        connection.updated_at = now_utc()
        return connection

    def record_webhook_rejection(
        self,
        *,
        connection_id: uuid.UUID,
        health_state: WebhookHealthState,
        rejection_reason: WebhookRejectionReason,
        rejected_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require_any(connection_id=connection_id)
        connection.webhook_health_state = health_state
        connection.last_webhook_rejection_reason = rejection_reason
        connection.last_webhook_rejected_at = rejected_at
        connection.updated_at = now_utc()
        return connection

    def record_processed_event(
        self,
        *,
        connection_id: uuid.UUID,
        event_id: uuid.UUID,
        processed_at: datetime,
        health_state: WebhookHealthState,
    ) -> RepositoryConnection:
        connection = self._require_any(connection_id=connection_id)
        connection.last_processed_event_id = event_id
        connection.last_processed_event_at = processed_at
        connection.webhook_health_state = health_state
        if health_state is WebhookHealthState.HEALTHY:
            connection.last_webhook_rejection_reason = None
            connection.last_webhook_rejected_at = None
        connection.updated_at = now_utc()
        return connection

    def _require_connection(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection:
        connection = self.get(workspace_id=workspace_id, connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection

    def _require_any(self, *, connection_id: uuid.UUID) -> RepositoryConnection:
        connection = self.get_any(connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection


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


class FakeScopeRuleRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def get_active_for_connection(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> CollectionScopeRuleVersion | None:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection.active_scope_rule_version_id is None:
            return None
        return self._store.scope_rule_versions[connection.active_scope_rule_version_id]

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
            id=uuid.uuid4(),
            connection_id=connection.id,
            planning_input_reference_id=connection.planning_input_reference_id,
            include_paths=list(draft.include_paths),
            exclude_paths=list(draft.exclude_paths),
            allowed_file_types=list(draft.allowed_file_types),
            blocked_file_types=list(draft.blocked_file_types),
            max_file_size_bytes=draft.max_file_size_bytes,
            exclude_binary=draft.exclude_binary,
            warning_state=draft.warning_state,
            created_at=now_utc(),
            created_by=draft.created_by,
        )
        self._store.scope_rule_versions[scope_rule.id] = scope_rule
        connection.active_scope_rule_version_id = scope_rule.id
        connection.active_scope_rule_version = scope_rule
        connection.updated_at = now_utc()
        return scope_rule

    def _require_connection(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection:
        connection = self._store.connections.get(connection_id)
        if connection is None or connection.workspace_id != workspace_id:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection


@dataclass(frozen=True, slots=True)
class CredentialRevisionDraft:
    connection_id: uuid.UUID
    credential_type: CredentialType
    encrypted_secret: str
    display_fingerprint: str
    read_only_validated: bool
    status: CredentialRevisionStatus


class FakeCredentialRevisionRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def create(self, draft: CredentialRevisionDraft) -> RepositoryCredentialRevision:
        revision = RepositoryCredentialRevision(
            id=uuid.uuid4(),
            connection_id=draft.connection_id,
            credential_type=draft.credential_type,
            encrypted_secret=draft.encrypted_secret,
            display_fingerprint=draft.display_fingerprint,
            read_only_validated=draft.read_only_validated,
            status=draft.status,
            created_at=now_utc(),
        )
        self._store.credentials[revision.id] = revision
        return revision

    def get_active_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> RepositoryCredentialRevision | None:
        connection = self._store.connections.get(connection_id)
        if connection is None or connection.active_credential_revision_id is None:
            return None
        return self._store.credentials.get(connection.active_credential_revision_id)


class FakeWebhookSecretRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def create(
        self,
        *,
        connection_id: uuid.UUID,
        encrypted_secret: str,
        status: str | object,
        grace_until: datetime | None = None,
        created_at: datetime | None = None,
    ) -> TestWebhookSecretRevision:
        revision = TestWebhookSecretRevision(
            id=uuid.uuid4(),
            connection_id=connection_id,
            secret=None,
            encrypted_secret=encrypted_secret,
            status=getattr(status, "value", status),
            created_at=created_at or now_utc(),
            grace_until=grace_until,
        )
        self._store.webhook_secret_revisions[revision.id] = revision
        return revision

    def list_verification_candidates(
        self, *, connection_id: uuid.UUID, as_of: datetime
    ) -> list[TestWebhookSecretRevision]:
        candidates = [
            revision
            for revision in self._store.webhook_secret_revisions.values()
            if revision.connection_id == connection_id
            and (
                getattr(revision.status, "value", revision.status) == "active"
                or (
                    getattr(revision.status, "value", revision.status) == "previous_grace"
                    and revision.grace_until is not None
                    and revision.grace_until >= as_of
                )
            )
        ]
        return sorted(candidates, key=lambda revision: (revision.created_at, revision.id), reverse=True)

    def get_active_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> TestWebhookSecretRevision | None:
        for revision in self._store.webhook_secret_revisions.values():
            if (
                revision.connection_id == connection_id
                and getattr(revision.status, "value", revision.status) == "active"
            ):
                return revision
        return None

    def get_latest_previous_grace_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> TestWebhookSecretRevision | None:
        revisions = [
            revision
            for revision in self._store.webhook_secret_revisions.values()
            if revision.connection_id == connection_id
            and getattr(revision.status, "value", revision.status) == "previous_grace"
        ]
        if not revisions:
            return None
        return max(revisions, key=lambda revision: (revision.created_at, revision.id))

    def mark_previous_grace(
        self, *, revision_id: uuid.UUID, grace_until: datetime
    ) -> TestWebhookSecretRevision:
        revision = self._store.webhook_secret_revisions[revision_id]
        revision.status = "previous_grace"
        revision.grace_until = grace_until
        return revision

    def revoke_previous_grace_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> list[TestWebhookSecretRevision]:
        revisions = [
            revision
            for revision in self._store.webhook_secret_revisions.values()
            if revision.connection_id == connection_id
            and getattr(revision.status, "value", revision.status) == "previous_grace"
        ]
        for revision in revisions:
            revision.status = "revoked"
            revision.grace_until = None
        return revisions


class FakeRepositoryEventRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def create(self, draft) -> TestRepositoryEvent:
        event = TestRepositoryEvent(
            id=draft.id,
            connection_id=draft.connection_id,
            provider_delivery_id=draft.provider_delivery_id,
            provider_event_type=draft.provider_event_type.value,
            provider_action=draft.provider_action,
            domain_event_type=draft.domain_event_type.value,
            target_kind=draft.target_kind.value,
            target_key=draft.target_key,
            target_ref_name=draft.target_ref_name,
            target_head_sha=draft.target_head_sha,
            occurred_at=draft.occurred_at,
            signature_status=draft.signature_status.value,
            processing_decision=draft.processing_decision.value,
            processing_status=draft.processing_status.value,
            received_at=draft.received_at,
            payload_hash=draft.payload_hash,
            verified_secret_revision_id=draft.verified_secret_revision_id,
            verified_secret_revision_status=(
                None
                if draft.verified_secret_revision_status is None
                else draft.verified_secret_revision_status.value
            ),
            rejection_reason=(
                None
                if draft.rejection_reason is None
                else draft.rejection_reason.value
            ),
            sync_run_id=draft.sync_run_id,
            snapshot_id=draft.snapshot_id,
            processed_at=draft.processed_at,
        )
        self._store.repository_events[event.id] = event
        return event

    def get_by_delivery_id(
        self, *, connection_id: uuid.UUID, provider_delivery_id: str
    ) -> TestRepositoryEvent | None:
        for event in self._store.repository_events.values():
            if (
                event.connection_id == connection_id
                and event.provider_delivery_id == provider_delivery_id
            ):
                return event
        return None

    def get(self, *, event_id: uuid.UUID) -> TestRepositoryEvent | None:
        return self._store.repository_events.get(event_id)

    def list_for_connection(self, *, connection_id: uuid.UUID) -> list[TestRepositoryEvent]:
        events = [
            event
            for event in self._store.repository_events.values()
            if event.connection_id == connection_id
        ]
        return sorted(
            events,
            key=lambda event: (event.received_at, event.id),
            reverse=True,
        )

    def update_processing(
        self,
        *,
        event_id: uuid.UUID,
        processing_decision,
        processing_status,
        processed_at: datetime,
        sync_run_id: uuid.UUID | None = None,
        snapshot_id: uuid.UUID | None = None,
        clear_sync_run_id: bool = False,
    ) -> TestRepositoryEvent:
        event = self._store.repository_events[event_id]
        event.processing_decision = processing_decision.value
        event.processing_status = processing_status.value
        event.processed_at = processed_at
        if clear_sync_run_id:
            event.sync_run_id = None
        if sync_run_id is not None:
            event.sync_run_id = sync_run_id
        if snapshot_id is not None:
            event.snapshot_id = snapshot_id
        return event


class FakeRepositoryEventCursorRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def get(
        self, *, connection_id: uuid.UUID, target_key: str
    ) -> TestRepositoryEventCursor | None:
        return self._store.event_cursors.get((connection_id, target_key))

    def upsert(self, draft) -> TestRepositoryEventCursor:
        cursor = self._store.event_cursors.get((draft.connection_id, draft.target_key))
        if cursor is None:
            cursor = TestRepositoryEventCursor(
                id=draft.id,
                connection_id=draft.connection_id,
                target_key=draft.target_key,
                latest_head_sha=draft.latest_head_sha,
                latest_event_id=draft.latest_event_id,
                updated_at=draft.updated_at,
            )
            self._store.event_cursors[(draft.connection_id, draft.target_key)] = cursor
            return cursor
        cursor.latest_head_sha = draft.latest_head_sha
        cursor.latest_event_id = draft.latest_event_id
        cursor.updated_at = draft.updated_at
        return cursor

    def delete_if_latest_event(
        self, *, connection_id: uuid.UUID, target_key: str, latest_event_id: uuid.UUID
    ) -> None:
        cursor = self._store.event_cursors.get((connection_id, target_key))
        if cursor is None or cursor.latest_event_id != latest_event_id:
            return
        del self._store.event_cursors[(connection_id, target_key)]


class FakeGitRefResolver:
    def __init__(
        self,
        *,
        store: InMemoryRepositoryStore,
        resolved_sha: str = "a" * 40,
    ) -> None:
        self._store = store
        self._resolved_sha = resolved_sha

    def resolve(
        self, *, remote_url: str, ref_type: DefaultRefType, ref_name: str
    ) -> ResolvedGitRef:
        self._store.last_resolved_remote_url = remote_url
        if (
            self._store.resolver_requires_bound_credential
            and "x-access-token:" not in remote_url
        ):
            raise GitConnectionAuthError()
        if ref_name in self._store.auth_failure_ref_names:
            raise GitConnectionAuthError()
        if ref_name in self._store.missing_ref_names:
            raise GitRefNotFoundError(ref_name)
        return ResolvedGitRef(
            ref_type=ref_type,
            ref_name=ref_name,
            commit_sha=self._store.resolved_ref_commits.get(ref_name, self._resolved_sha),
        )


class FakeGitReadonlyValidator:
    def probe(self, *, remote_url: str) -> ReadonlyProbeResult:
        return ReadonlyProbeResult(
            is_read_only=True,
            problem_code=None,
            detail="읽기 전용 자격 증명입니다.",
        )


class FakeGitMirrorManager:
    def __init__(self, *, project_root: Path) -> None:
        self._project_root = project_root

    def ensure_synced_mirror(
        self,
        *,
        connection_id: uuid.UUID,
        remote_url: str,
        restore_remote_url: str | None = None,
    ) -> ManagedGitMirror:
        if getattr(self, "_store", None) is not None and self._store.mirror_sync_error:
            raise self._store.mirror_sync_error
        relative_path = Path(".runtime") / "git-mirrors" / f"{connection_id}.git"
        absolute_path = self._project_root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.mkdir(parents=True, exist_ok=True)
        return ManagedGitMirror(
            connection_id=connection_id,
            mirror_path=relative_path.as_posix(),
            absolute_path=absolute_path,
        )

    def reset_origin_url(self, *, mirror: ManagedGitMirror, remote_url: str) -> None:
        return None

    def bind_store(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def read_snapshot_entries(
        self, *, mirror: ManagedGitMirror, commit_sha: str
    ) -> MaterializedGitSnapshot:
        return MaterializedGitSnapshot(
            tree_sha=self._store.mirror_tree_sha,
            entries=tuple(
                SnapshotArchiveEntryDraft(
                    path=path,
                    content=content,
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=Path(path).suffix or None,
                    language_hint=None,
                )
                for path, content in self._store.mirror_snapshot_entries
            ),
        )


@dataclass(frozen=True, slots=True)
class RepositorySyncRunDraft:
    id: uuid.UUID
    connection_id: uuid.UUID
    trigger_event_id: uuid.UUID | None
    trigger_type: SyncTriggerType
    requested_ref_type: RefType
    requested_ref_name: str


class FakeRepositorySyncRunRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

    def create_pending(self, draft: RepositorySyncRunDraft) -> RepositorySyncRun:
        sync_run = RepositorySyncRun(
            id=draft.id,
            connection_id=draft.connection_id,
            trigger_event_id=draft.trigger_event_id,
            trigger_type=draft.trigger_type,
            requested_ref_type=draft.requested_ref_type,
            requested_ref_name=draft.requested_ref_name,
            status=SyncRunStatus.PENDING,
            started_at=now_utc(),
        )
        self._store.sync_runs[sync_run.id] = sync_run
        return sync_run

    def get(
        self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID
    ) -> RepositorySyncRun | None:
        sync_run = self._store.sync_runs.get(sync_run_id)
        if sync_run is None or sync_run.connection_id != connection_id:
            return None
        return sync_run

    def get_latest_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> RepositorySyncRun | None:
        sync_runs = [
            sync_run
            for sync_run in self._store.sync_runs.values()
            if sync_run.connection_id == connection_id
        ]
        if not sync_runs:
            return None
        return max(sync_runs, key=lambda sync_run: (sync_run.started_at, sync_run.id))

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
        sync_run.completed_at = None
        sync_run.failure_code = None
        sync_run.failure_message = None
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
        sync_run.completed_at = completed_at
        sync_run.failure_code = None
        sync_run.failure_message = None
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
        return sync_run

    def delete_pending(self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID) -> None:
        sync_run = self._require(connection_id=connection_id, sync_run_id=sync_run_id)
        if sync_run.status is not SyncRunStatus.PENDING:
            raise ValueError("대기 중인 스냅샷 실행만 취소할 수 있습니다.")
        del self._store.sync_runs[sync_run.id]

    def _require(
        self, *, connection_id: uuid.UUID, sync_run_id: uuid.UUID
    ) -> RepositorySyncRun:
        sync_run = self.get(connection_id=connection_id, sync_run_id=sync_run_id)
        if sync_run is None:
            raise LookupError("스냅샷 실행 이력을 찾을 수 없습니다.")
        return sync_run


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


class FakeCodeSnapshotRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

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
            created_at=now_utc(),
        )
        snapshot.files = [
            CodeSnapshotFile(
                id=uuid.uuid4(),
                snapshot_id=snapshot.id,
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
        self._store.snapshots[snapshot.id] = snapshot
        return snapshot

    def get(self, *, connection_id: uuid.UUID, snapshot_id: uuid.UUID) -> CodeSnapshot | None:
        snapshot = self._store.snapshots.get(snapshot_id)
        if snapshot is None or snapshot.connection_id != connection_id:
            return None
        return snapshot

    def get_latest_for_connection(self, *, connection_id: uuid.UUID) -> CodeSnapshot | None:
        snapshots = [
            snapshot
            for snapshot in self._store.snapshots.values()
            if snapshot.connection_id == connection_id
        ]
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: (snapshot.created_at, snapshot.id))

    def get_by_sync_run_id(self, *, sync_run_id: uuid.UUID) -> CodeSnapshot | None:
        for snapshot in self._store.snapshots.values():
            if snapshot.sync_run_id == sync_run_id:
                return snapshot
        return None


@contextmanager
def fake_session_factory():
    yield object()


def seed_planning_input_reference(
    store: InMemoryRepositoryStore,
    *,
    workspace_id: uuid.UUID,
    reference_id: uuid.UUID | None = None,
) -> PlanningInputReference:
    reference = PlanningInputReference(
        id=reference_id or uuid.uuid4(),
        workspace_id=workspace_id,
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="저장소 연결 준비",
        source_reference="chat://test",
        approved_spec_path="specs/001-git-repo-connection/spec.md",
        approved_plan_path="specs/001-git-repo-connection/plan.md",
        created_at=now_utc(),
    )
    store.planning_input_references[reference.id] = reference
    return reference


def seed_active_scope_rule_version(
    store: InMemoryRepositoryStore,
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    allowed_file_types: list[str] | None = None,
    blocked_file_types: list[str] | None = None,
    max_file_size_bytes: int = 5 * 1024 * 1024,
    exclude_binary: bool = True,
    warning_state: ScopeRuleWarningState = ScopeRuleWarningState.OK,
    created_by: uuid.UUID | None = None,
) -> CollectionScopeRuleVersion:
    connection = store.connections.get(connection_id)
    if connection is None or connection.workspace_id != workspace_id:
        raise LookupError("저장소 연결을 찾을 수 없습니다.")

    scope_rule = CollectionScopeRuleVersion(
        id=uuid.uuid4(),
        connection_id=connection.id,
        planning_input_reference_id=connection.planning_input_reference_id,
        include_paths=list(include_paths or []),
        exclude_paths=list(exclude_paths or []),
        allowed_file_types=list(allowed_file_types or []),
        blocked_file_types=list(blocked_file_types or []),
        max_file_size_bytes=max_file_size_bytes,
        exclude_binary=exclude_binary,
        warning_state=warning_state,
        created_at=now_utc(),
        created_by=created_by or workspace_id,
    )
    store.scope_rule_versions[scope_rule.id] = scope_rule
    connection.active_scope_rule_version_id = scope_rule.id
    connection.active_scope_rule_version = scope_rule
    connection.updated_at = now_utc()
    return scope_rule


def create_test_client(
    *,
    tmp_path: Path,
    workspace_id: uuid.UUID,
    store: InMemoryRepositoryStore | None = None,
    use_real_repositories: bool = False,
    database_url: str | None = None,
) -> tuple[TestClient, InMemoryRepositoryStore]:
    store = store or InMemoryRepositoryStore()
    settings = _load_test_settings(tmp_path, database_url=database_url)
    fake_mirror_manager = FakeGitMirrorManager(project_root=settings.project_root)
    fake_mirror_manager.bind_store(store)
    if use_real_repositories:
        if settings.database_url is None:
            raise ValueError("실DB 테스트에는 database_url이 필요합니다.")
        dependencies = AppDependencies(
            settings=settings,
            git_ref_resolver=FakeGitRefResolver(store=store),
            git_readonly_validator=FakeGitReadonlyValidator(),
            git_mirror_manager=fake_mirror_manager,
            snapshot_archive_store=SnapshotArchiveStore(settings=settings),
            snapshot_manifest_writer=SnapshotManifestWriter(),
            planning_input_reference_repository_factory=PlanningInputReferenceRepository,
            snapshot_traceability_builder=build_snapshot_traceability_reference,
            session_factory=build_session_factory(settings),
            repository_connection_repository_factory=RepositoryConnectionRepository,
            scope_rule_repository_factory=ScopeRuleRepository,
            credential_revision_repository_factory=CredentialRevisionRepository,
            webhook_secret_repository_factory=WebhookSecretRepository,
            repository_event_repository_factory=RepositoryEventRepository,
            repository_event_cursor_repository_factory=RepositoryEventCursorRepository,
            repository_sync_run_repository_factory=RepositorySyncRunRepository,
            code_snapshot_repository_factory=CodeSnapshotRepository,
        )
    else:
        dependencies = AppDependencies(
            settings=settings,
            git_ref_resolver=FakeGitRefResolver(store=store),
            git_readonly_validator=FakeGitReadonlyValidator(),
            git_mirror_manager=fake_mirror_manager,
            snapshot_archive_store=SnapshotArchiveStore(settings=settings),
            snapshot_manifest_writer=SnapshotManifestWriter(),
            planning_input_reference_repository_factory=lambda session: FakePlanningInputReferenceRepository(
                store
            ),
            snapshot_traceability_builder=build_snapshot_traceability_reference,
            session_factory=fake_session_factory,
            repository_connection_repository_factory=lambda session: FakeRepositoryConnectionRepository(
                store
            ),
            scope_rule_repository_factory=lambda session: FakeScopeRuleRepository(store),
            credential_revision_repository_factory=lambda session: FakeCredentialRevisionRepository(
                store
            ),
            webhook_secret_repository_factory=lambda session: FakeWebhookSecretRepository(
                store
            ),
            repository_event_repository_factory=lambda session: FakeRepositoryEventRepository(
                store
            ),
            repository_event_cursor_repository_factory=lambda session: FakeRepositoryEventCursorRepository(
                store
            ),
            repository_sync_run_repository_factory=lambda session: FakeRepositorySyncRunRepository(
                store
            ),
            code_snapshot_repository_factory=lambda session: FakeCodeSnapshotRepository(store),
        )
    app = create_app(settings=settings, dependencies=dependencies)
    client = TestClient(app)
    client.headers.update({"X-TCI-Workspace-Id": str(workspace_id)})
    return client, store


def create_connection_payload(
    *,
    planning_input_reference_id: uuid.UUID,
    provider: str = "github_cloud",
    default_ref_name: str = "main",
) -> dict[str, Any]:
    return {
        "planningInputReferenceId": str(planning_input_reference_id),
        "provider": provider,
        "remoteUrl": "https://github.com/acme/sample-repo.git",
        "transport": "https",
        "defaultRefType": "branch",
        "defaultRefName": default_ref_name,
        "credential": {
            "type": "https_pat",
            "secret": "readonly-token-value",
            "fingerprint": "pat-01",
        },
    }


def create_planning_input_reference_payload(
    *,
    workspace_id: uuid.UUID,
    source_type: str = "user_request",
    source_title: str = "저장소 연결 준비",
    source_reference: str = "manual://docs",
    approved_spec_path: str = "specs/001-git-repo-connection/spec.md",
    approved_plan_path: str = "specs/001-git-repo-connection/plan.md",
) -> dict[str, str]:
    return {
        "workspaceId": str(workspace_id),
        "sourceType": source_type,
        "sourceTitle": source_title,
        "sourceReference": source_reference,
        "approvedSpecPath": approved_spec_path,
        "approvedPlanPath": approved_plan_path,
    }


def build_github_push_payload(
    *,
    ref_name: str = "main",
    after_sha: str = "a" * 40,
    repository_full_name: str = "acme/sample-repo",
    commits: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "ref": f"refs/heads/{ref_name}",
        "after": after_sha,
        "repository": {"full_name": repository_full_name},
        "commits": commits
        or [
            {
                "id": after_sha,
                "message": "update repository snapshot",
            }
        ],
    }


def build_github_pull_request_payload(
    *,
    action: str = "opened",
    number: int = 101,
    head_ref: str = "feature/us3",
    head_sha: str = "b" * 40,
    base_ref: str = "main",
    repository_full_name: str = "acme/sample-repo",
) -> dict[str, Any]:
    return {
        "action": action,
        "number": number,
        "repository": {"full_name": repository_full_name},
        "pull_request": {
            "head": {"ref": head_ref, "sha": head_sha},
            "base": {"ref": base_ref},
        },
    }


def build_github_webhook_headers(
    *,
    secret: str,
    payload: dict[str, Any],
    delivery_id: str,
    event_name: str,
) -> dict[str, str]:
    body = serialize_github_webhook_payload(payload)
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {
        "X-GitHub-Delivery": delivery_id,
        "X-GitHub-Event": event_name,
        "X-Hub-Signature-256": f"sha256={signature}",
    }


def seed_active_webhook_secret(
    store: InMemoryRepositoryStore,
    *,
    connection_id: uuid.UUID,
    secret: str = "webhook-secret",
) -> TestWebhookSecretRevision:
    revision = TestWebhookSecretRevision(
        id=uuid.uuid4(),
        connection_id=connection_id,
        secret=secret,
        encrypted_secret=None,
        status="active",
        created_at=now_utc(),
    )
    store.webhook_secret_revisions[revision.id] = revision
    connection = store.connections.get(connection_id)
    if connection is not None:
        connection.active_webhook_secret_revision_id = revision.id
        connection.webhook_health_state = WebhookHealthState.HEALTHY
        connection.updated_at = now_utc()
    return revision


def seed_rotated_webhook_secret_with_grace(
    store: InMemoryRepositoryStore,
    *,
    connection_id: uuid.UUID,
    active_secret: str = "current-secret",
    previous_secret: str = "previous-secret",
    grace_until: datetime | None = None,
) -> tuple[TestWebhookSecretRevision, TestWebhookSecretRevision]:
    previous_revision = TestWebhookSecretRevision(
        id=uuid.uuid4(),
        connection_id=connection_id,
        secret=previous_secret,
        encrypted_secret=None,
        status="previous_grace",
        created_at=now_utc(),
        grace_until=grace_until or now_utc(),
    )
    active_revision = TestWebhookSecretRevision(
        id=uuid.uuid4(),
        connection_id=connection_id,
        secret=active_secret,
        encrypted_secret=None,
        status="active",
        created_at=now_utc(),
    )
    store.webhook_secret_revisions[previous_revision.id] = previous_revision
    store.webhook_secret_revisions[active_revision.id] = active_revision
    connection = store.connections.get(connection_id)
    if connection is not None:
        connection.active_webhook_secret_revision_id = active_revision.id
        connection.webhook_health_state = WebhookHealthState.HEALTHY
        connection.updated_at = now_utc()
    return active_revision, previous_revision


def seed_repository_event_cursor(
    store: InMemoryRepositoryStore,
    *,
    connection_id: uuid.UUID,
    target_key: str,
    latest_head_sha: str,
    latest_event_id: uuid.UUID | None = None,
) -> TestRepositoryEventCursor:
    cursor = TestRepositoryEventCursor(
        id=uuid.uuid4(),
        connection_id=connection_id,
        target_key=target_key,
        latest_head_sha=latest_head_sha,
        latest_event_id=latest_event_id or uuid.uuid4(),
        updated_at=now_utc(),
    )
    store.event_cursors[(connection_id, target_key)] = cursor
    return cursor


def serialize_github_webhook_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _load_test_settings(tmp_path: Path, *, database_url: str | None = None):
    import os

    from cryptography.fernet import Fernet

    original_root = os.environ.get("TCI_PROJECT_ROOT")
    original_key = os.environ.get("TCI_CREDENTIAL_ENCRYPTION_KEY")
    original_template_root = os.environ.get("TCI_TEMPLATE_ROOT")
    original_database_url = os.environ.get("TCI_DATABASE_URL")
    template_root = Path(__file__).resolve().parents[2] / "src" / "tci" / "web" / "templates"
    os.environ["TCI_PROJECT_ROOT"] = str(tmp_path)
    os.environ["TCI_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
    os.environ["TCI_TEMPLATE_ROOT"] = str(template_root)
    if database_url is None:
        os.environ.pop("TCI_DATABASE_URL", None)
    else:
        os.environ["TCI_DATABASE_URL"] = database_url
    try:
        return load_settings()
    finally:
        if original_root is None:
            os.environ.pop("TCI_PROJECT_ROOT", None)
        else:
            os.environ["TCI_PROJECT_ROOT"] = original_root
        if original_key is None:
            os.environ.pop("TCI_CREDENTIAL_ENCRYPTION_KEY", None)
        else:
            os.environ["TCI_CREDENTIAL_ENCRYPTION_KEY"] = original_key
        if original_template_root is None:
            os.environ.pop("TCI_TEMPLATE_ROOT", None)
        else:
            os.environ["TCI_TEMPLATE_ROOT"] = original_template_root
        if original_database_url is None:
            os.environ.pop("TCI_DATABASE_URL", None)
        else:
            os.environ["TCI_DATABASE_URL"] = original_database_url
