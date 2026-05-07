from __future__ import annotations

import json
from pathlib import Path
import hashlib
from typing import cast
import uuid


from tests.support.local_upload_testkit import (
    ZipFixtureEntry,
    build_project_zip,
    build_zip_bytes,
    build_zip_with_traversal_path,
)
from tests.support.repository_connection_testkit import (
    FakeCodeSnapshotRepository,
    FakeLocalUploadRepository,
    InMemoryRepositoryStore,
    fake_session_factory,
)
from tci.app import AppDependencies
from tci.infrastructure.persistence.code_snapshot_repository import (
    CodeSnapshotRepository,
)
from tci.infrastructure.persistence.local_upload_repository import LocalUploadDraft
from tci.infrastructure.persistence.local_upload_repository import LocalUploadRepository
from tci.infrastructure.persistence.models import (
    CodeSnapshotSourceKind,
    LocalUploadStatus,
    Workspace,
    WorkspaceStatus,
)
from tci.infrastructure.snapshots.snapshot_archive_store import SnapshotArchiveStore
from tci.infrastructure.snapshots.snapshot_manifest_writer import SnapshotManifestWriter
from tci.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    runtime_root = tmp_path / ".runtime"
    return Settings(
        project_root=tmp_path,
        environment="test",
        runtime_root=runtime_root,
        git_mirror_root=runtime_root / "git-mirrors",
        code_snapshot_root=runtime_root / "code-snapshots",
        template_root=tmp_path / "src" / "tci" / "web" / "templates",
        database_url=None,
        redis_url=None,
        credential_encryption_key=None,
        operator_api_token="test-operator-token",
        gitlab_self_managed_allowed_hosts=(),
        gitlab_webhook_trusted_proxy_hosts=(),
        allow_insecure_gitlab_http=False,
        local_upload_max_compressed_bytes=10_000,
        local_upload_max_uncompressed_bytes=10_000,
        local_upload_max_file_count=100,
        local_upload_max_file_bytes=10_000,
        local_upload_max_path_segments=50,
        local_upload_max_in_memory_bytes=10_000,
    )


def _dependencies(
    settings: Settings, store: InMemoryRepositoryStore
) -> AppDependencies:
    return AppDependencies(
        settings=settings,
        git_ref_resolver=None,  # type: ignore[arg-type]
        git_readonly_validator=None,  # type: ignore[arg-type]
        git_mirror_manager=None,  # type: ignore[arg-type]
        snapshot_archive_store=SnapshotArchiveStore(settings=settings),
        snapshot_manifest_writer=SnapshotManifestWriter(),
        planning_input_reference_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        snapshot_traceability_builder=lambda **kwargs: None,
        session_factory=fake_session_factory,
        repository_connection_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        scope_rule_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        credential_revision_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        webhook_secret_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        repository_event_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        repository_event_cursor_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        repository_sync_run_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        code_snapshot_repository_factory=lambda session: cast(
            CodeSnapshotRepository,
            FakeCodeSnapshotRepository(store),
        ),
        workspace_repository_factory=lambda session: None,  # type: ignore[arg-type,return-value]
        local_upload_repository_factory=lambda session: cast(
            LocalUploadRepository,
            FakeLocalUploadRepository(store),
        ),
    )


def _workspace(store: InMemoryRepositoryStore) -> uuid.UUID:
    workspace_id = uuid.uuid4()
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE,
    )
    return workspace_id


def _local_upload(
    store: InMemoryRepositoryStore,
    *,
    workspace_id: uuid.UUID,
    zip_bytes: bytes,
    original_filename: str = "project.zip",
    upload_id: uuid.UUID | None = None,
) -> uuid.UUID:
    upload = FakeLocalUploadRepository(store).create(
        LocalUploadDraft(
            id=upload_id or uuid.uuid4(),
            workspace_id=workspace_id,
            original_filename_display=original_filename,
            upload_sha256=hashlib.sha256(zip_bytes).hexdigest(),
            compressed_size_bytes=len(zip_bytes),
            created_by="operator@example.com",
        )
    )
    return upload.id


def test_create_local_upload_snapshot_persists_archive_manifest_and_latest(
    tmp_path: Path,
) -> None:
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    store = InMemoryRepositoryStore()
    workspace_id = _workspace(store)
    zip_bytes = build_project_zip()
    local_upload_id = _local_upload(
        store, workspace_id=workspace_id, zip_bytes=zip_bytes
    )
    dependencies = _dependencies(_settings(tmp_path), store)

    result = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=zip_bytes,
        ),
        dependencies=dependencies,
    )

    upload = store.local_uploads[local_upload_id]
    assert result.snapshot_id is not None
    snapshot = store.snapshots[result.snapshot_id]
    assert result.succeeded is True
    assert upload.status is LocalUploadStatus.SUCCEEDED
    assert upload.latest_snapshot_id == snapshot.id
    assert upload.file_count == 3
    assert upload.directory_count == 2
    assert snapshot.source_kind is CodeSnapshotSourceKind.LOCAL_UPLOAD
    assert snapshot.local_upload_id == local_upload_id
    assert [file.path for file in snapshot.files] == [
        "project/.env.example",
        "project/README.md",
        "project/src/main.py",
    ]
    manifest_path = (
        dependencies.settings.project_root / snapshot.archive_path / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"]["kind"] == "local_upload"
    assert manifest["source"]["localUploadId"] == str(local_upload_id)
    assert manifest["source"]["originalFilename"] == "project.zip"
    assert manifest["source"]["directories"] == [
        "project",
        "project/src",
    ]


def test_create_local_upload_snapshot_uses_latest_snapshot_for_repeated_uploads(
    tmp_path: Path,
) -> None:
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    store = InMemoryRepositoryStore()
    workspace_id = _workspace(store)
    dependencies = _dependencies(_settings(tmp_path), store)
    first_zip = build_zip_bytes((ZipFixtureEntry("first.txt", b"first"),))
    second_zip = build_zip_bytes((ZipFixtureEntry("second.txt", b"second"),))
    first_upload_id = _local_upload(
        store, workspace_id=workspace_id, zip_bytes=first_zip
    )
    second_upload_id = _local_upload(
        store, workspace_id=workspace_id, zip_bytes=second_zip
    )

    first = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=first_upload_id,
            zip_bytes=first_zip,
        ),
        dependencies=dependencies,
    )
    second = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=second_upload_id,
            zip_bytes=second_zip,
        ),
        dependencies=dependencies,
    )

    assert first.snapshot_id != second.snapshot_id
    latest = FakeCodeSnapshotRepository(store).get_latest_local_upload_for_workspace(
        workspace_id=workspace_id
    )
    assert latest is not None
    assert latest.id == second.snapshot_id


def test_create_local_upload_snapshot_failure_leaves_no_active_snapshot(
    tmp_path: Path,
) -> None:
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    store = InMemoryRepositoryStore()
    workspace_id = _workspace(store)
    zip_bytes = build_zip_with_traversal_path()
    local_upload_id = _local_upload(
        store, workspace_id=workspace_id, zip_bytes=zip_bytes
    )
    dependencies = _dependencies(_settings(tmp_path), store)

    result = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=zip_bytes,
        ),
        dependencies=dependencies,
    )

    upload = store.local_uploads[local_upload_id]
    assert result.succeeded is False
    assert result.failure_code == "unsafe_zip_path"
    assert upload.status is LocalUploadStatus.FAILED
    assert upload.latest_snapshot_id is None
    assert store.snapshots == {}
    assert not dependencies.settings.code_snapshot_root.exists()


def test_create_local_upload_snapshot_rejects_upload_hash_mismatch(
    tmp_path: Path,
) -> None:
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    store = InMemoryRepositoryStore()
    workspace_id = _workspace(store)
    local_upload_id = _local_upload(
        store,
        workspace_id=workspace_id,
        zip_bytes=build_zip_bytes((ZipFixtureEntry("other.txt", b"other"),)),
    )
    dependencies = _dependencies(_settings(tmp_path), store)

    result = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=build_project_zip(),
        ),
        dependencies=dependencies,
    )

    upload = store.local_uploads[local_upload_id]
    assert result.succeeded is False
    assert result.failure_code == "upload_hash_mismatch"
    assert upload.status is LocalUploadStatus.FAILED
    assert upload.latest_snapshot_id is None
    assert store.snapshots == {}
    assert not dependencies.settings.code_snapshot_root.exists()


def test_create_local_upload_snapshot_preserves_empty_directory_manifest_metadata(
    tmp_path: Path,
) -> None:
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    store = InMemoryRepositoryStore()
    workspace_id = _workspace(store)
    zip_bytes = build_zip_bytes(
        (
            ZipFixtureEntry("project/empty/", is_directory=True),
            ZipFixtureEntry("project/src/main.py", b"print('hello')\n"),
        )
    )
    local_upload_id = _local_upload(
        store, workspace_id=workspace_id, zip_bytes=zip_bytes
    )
    dependencies = _dependencies(_settings(tmp_path), store)

    result = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=zip_bytes,
        ),
        dependencies=dependencies,
    )

    assert result.snapshot_id is not None
    snapshot = store.snapshots[result.snapshot_id]
    manifest_path = (
        dependencies.settings.project_root / snapshot.archive_path / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert store.local_uploads[local_upload_id].directory_count == 3
    assert manifest["source"]["directories"] == [
        "project",
        "project/empty",
        "project/src",
    ]


class _FailingArchiveStore:
    def store(self, *, snapshot_id: uuid.UUID, entries: object) -> object:
        archive_root = self.settings.code_snapshot_root / str(snapshot_id)
        archive_root.mkdir(parents=True, exist_ok=True)
        (archive_root / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("disk full")

    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings


def test_create_local_upload_snapshot_storage_failure_cleans_partial_archive(
    tmp_path: Path,
) -> None:
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    store = InMemoryRepositoryStore()
    workspace_id = _workspace(store)
    zip_bytes = build_project_zip()
    local_upload_id = _local_upload(
        store, workspace_id=workspace_id, zip_bytes=zip_bytes
    )
    settings = _settings(tmp_path)
    dependencies = _dependencies(settings, store)
    dependencies = AppDependencies(
        **{
            field: getattr(dependencies, field)
            for field in dependencies.__dataclass_fields__
            if field != "snapshot_archive_store"
        },
        snapshot_archive_store=_FailingArchiveStore(settings=settings),  # type: ignore[arg-type]
    )

    result = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=zip_bytes,
        ),
        dependencies=dependencies,
    )

    assert result.succeeded is False
    assert result.failure_code == "snapshot_write_failed"
    assert result.failure_message == "Local Upload 스냅샷 저장에 실패했습니다."
    assert store.local_uploads[local_upload_id].latest_snapshot_id is None
    assert store.local_uploads[local_upload_id].failure_message == "disk full"
    assert store.snapshots == {}
    assert list(settings.code_snapshot_root.glob("*")) == []


class _LeakyArchiveStore:
    def store(self, *, snapshot_id: uuid.UUID, entries: object) -> object:
        raise OSError("/Users/operator/private/project.zip token=secret")


def test_create_local_upload_snapshot_sanitizes_failure_result_message(
    tmp_path: Path,
) -> None:
    from tci.domain.services.create_local_upload_snapshot import (
        CreateLocalUploadSnapshotCommand,
        create_local_upload_snapshot,
    )

    store = InMemoryRepositoryStore()
    workspace_id = _workspace(store)
    zip_bytes = build_project_zip()
    local_upload_id = _local_upload(
        store, workspace_id=workspace_id, zip_bytes=zip_bytes
    )
    dependencies = _dependencies(_settings(tmp_path), store)
    dependencies = AppDependencies(
        **{
            field: getattr(dependencies, field)
            for field in dependencies.__dataclass_fields__
            if field != "snapshot_archive_store"
        },
        snapshot_archive_store=_LeakyArchiveStore(),  # type: ignore[arg-type]
    )

    result = create_local_upload_snapshot(
        CreateLocalUploadSnapshotCommand(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=zip_bytes,
        ),
        dependencies=dependencies,
    )

    assert result.succeeded is False
    assert "/Users" not in (result.failure_message or "")
    assert "token=secret" not in (result.failure_message or "")
