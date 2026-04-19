from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import uuid

from fastapi.testclient import TestClient

from tci.app import AppDependencies, create_app
from tci.infrastructure.git.git_mirror_manager import ManagedGitMirror
from tci.infrastructure.git.git_readonly_validator import ReadonlyProbeResult
from tci.infrastructure.git.git_ref_resolver import (
    GitConnectionAuthError,
    GitRefNotFoundError,
    ResolvedGitRef,
)
from tci.infrastructure.persistence.models import (
    CredentialRevisionStatus,
    CredentialType,
    DefaultRefType,
    PlanningInputReference,
    PlanningInputSourceType,
    RepositoryConnection,
    RepositoryConnectionStatus,
    RepositoryCredentialRevision,
    RepositoryProvider,
    RepositoryTransport,
)
from tci.settings import load_settings


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class InMemoryRepositoryStore:
    planning_input_references: dict[uuid.UUID, PlanningInputReference] = field(
        default_factory=dict
    )
    connections: dict[uuid.UUID, RepositoryConnection] = field(default_factory=dict)
    credentials: dict[uuid.UUID, RepositoryCredentialRevision] = field(
        default_factory=dict
    )
    resolver_requires_bound_credential: bool = False
    auth_failure_ref_names: set[str] = field(default_factory=set)
    missing_ref_names: set[str] = field(default_factory=set)
    last_resolved_remote_url: str | None = None


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
        self, *, connection_id: uuid.UUID, remote_url: str
    ) -> ManagedGitMirror:
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
    dependencies = AppDependencies(
        settings=settings,
        git_ref_resolver=FakeGitRefResolver(store=store),
        git_readonly_validator=FakeGitReadonlyValidator(),
        git_mirror_manager=FakeGitMirrorManager(project_root=settings.project_root),
        snapshot_archive_store=object(),
        snapshot_manifest_writer=object(),
        planning_input_reference_repository_factory=lambda session: FakePlanningInputReferenceRepository(
            store
        ),
        snapshot_traceability_builder=lambda **kwargs: kwargs,
        session_factory=fake_session_factory,
        repository_connection_repository_factory=lambda session: FakeRepositoryConnectionRepository(
            store
        ),
        credential_revision_repository_factory=lambda session: FakeCredentialRevisionRepository(
            store
        ),
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
