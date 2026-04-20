from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    sync_runs: dict[uuid.UUID, RepositorySyncRun] = field(default_factory=dict)
    snapshots: dict[uuid.UUID, CodeSnapshot] = field(default_factory=dict)
    resolver_requires_bound_credential: bool = False
    auth_failure_ref_names: set[str] = field(default_factory=set)
    missing_ref_names: set[str] = field(default_factory=set)
    last_resolved_remote_url: str | None = None
    mirror_sync_error: Exception | None = None
    mirror_tree_sha: str = "b" * 40
    mirror_snapshot_entries: tuple[tuple[str, bytes], ...] = field(
        default_factory=lambda: (("src/main.py", b"print('hello')\n"),)
    )


class FakePlanningInputReferenceRepository:
    def __init__(self, store: InMemoryRepositoryStore) -> None:
        self._store = store

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
        scope_rule_version_id: uuid.UUID,
    ) -> RepositoryConnection:
        connection = self._require_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.last_successful_snapshot_at = succeeded_at
        connection.active_scope_rule_version_id = scope_rule_version_id
        connection.active_scope_rule_version = self._store.scope_rule_versions[
            scope_rule_version_id
        ]
        connection.updated_at = now_utc()
        return connection

    def _require_connection(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection:
        connection = self.get(workspace_id=workspace_id, connection_id=connection_id)
        if connection is None:
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
            commit_sha=self._resolved_sha,
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


def create_test_client(
    *,
    tmp_path: Path,
    workspace_id: uuid.UUID,
    store: InMemoryRepositoryStore | None = None,
) -> tuple[TestClient, InMemoryRepositoryStore]:
    store = store or InMemoryRepositoryStore()
    settings = _load_test_settings(tmp_path)
    fake_mirror_manager = FakeGitMirrorManager(project_root=settings.project_root)
    fake_mirror_manager.bind_store(store)
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
        credential_revision_repository_factory=lambda session: FakeCredentialRevisionRepository(
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


def _load_test_settings(tmp_path: Path):
    import os

    from cryptography.fernet import Fernet

    original_root = os.environ.get("TCI_PROJECT_ROOT")
    original_key = os.environ.get("TCI_CREDENTIAL_ENCRYPTION_KEY")
    os.environ["TCI_PROJECT_ROOT"] = str(tmp_path)
    os.environ["TCI_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
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
