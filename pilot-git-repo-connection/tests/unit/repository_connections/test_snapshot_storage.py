from __future__ import annotations

import hashlib
import json
from pathlib import Path
import uuid

import pytest


def _build_test_settings(project_root: Path):
    from tci.settings import Settings

    runtime_root = project_root / ".runtime"
    return Settings(
        project_root=project_root,
        environment="test",
        runtime_root=runtime_root,
        git_mirror_root=runtime_root / "git-mirrors",
        code_snapshot_root=runtime_root / "code-snapshots",
        template_root=project_root / "src" / "tci" / "web" / "templates",
        database_url=None,
        redis_url=None,
        credential_encryption_key=None,
        operator_api_token="test-operator-token",
        gitlab_self_managed_allowed_hosts=(),
        gitlab_webhook_trusted_proxy_hosts=(),
        allow_insecure_gitlab_http=False,
    )


def test_snapshot_archive_store_creates_canonical_archive_and_writes_files(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    snapshot_id = uuid.uuid4()
    store = SnapshotArchiveStore(settings=settings)
    drafts = (
        SnapshotArchiveEntryDraft(
            path="src/app.py",
            content=b"print('hello')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
            language_hint="python",
        ),
        SnapshotArchiveEntryDraft(
            path="docs/guide.md",
            content=b"# guide\n",
            included_by=SnapshotInclusionReason.USER_INCLUDE,
            extension=".md",
            language_hint="markdown",
        ),
    )

    archive = store.store(snapshot_id=snapshot_id, entries=drafts)

    assert archive.archive_path == f".runtime/code-snapshots/{snapshot_id}"
    assert archive.absolute_path == settings.code_snapshot_root / str(snapshot_id)
    assert (
        archive.absolute_path / "src" / "app.py"
    ).read_bytes() == b"print('hello')\n"
    assert (archive.absolute_path / "docs" / "guide.md").read_bytes() == b"# guide\n"
    assert archive.files[0].archive_blob_path == "src/app.py"
    assert (
        archive.files[0].content_sha256
        == hashlib.sha256(b"print('hello')\n").hexdigest()
    )
    assert archive.files[1].archive_blob_path == "docs/guide.md"
    assert archive.files[1].content_sha256 == hashlib.sha256(b"# guide\n").hexdigest()


def test_snapshot_manifest_writer_serializes_null_planning_reference(
    tmp_path: Path,
) -> None:
    from tci.domain.services.build_traceability_reference import (
        build_snapshot_traceability_reference,
    )
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )
    from tci.infrastructure.snapshots.snapshot_manifest_writer import (
        SnapshotManifestWriter,
    )

    settings = _build_test_settings(tmp_path)
    snapshot_id = uuid.uuid4()
    archive = SnapshotArchiveStore(settings=settings).store(
        snapshot_id=snapshot_id,
        entries=(
            SnapshotArchiveEntryDraft(
                path="src/app.py",
                content=b"print('hello')\n",
                included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            ),
        ),
    )
    traceability = build_snapshot_traceability_reference(
        planning_input_reference_id=None,
        connection_id=uuid.uuid4(),
        scope_rule_version_id=uuid.uuid4(),
        sync_run_id=uuid.uuid4(),
        snapshot_id=snapshot_id,
    )

    manifest_path = SnapshotManifestWriter().write(
        archive=archive,
        traceability=traceability,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["traceability"]["planningInputReferenceId"] is None


def test_snapshot_archive_store_rejects_empty_entry_set(tmp_path: Path) -> None:
    from tci.infrastructure.snapshots.snapshot_archive_store import SnapshotArchiveStore

    settings = _build_test_settings(tmp_path)
    store = SnapshotArchiveStore(settings=settings)

    with pytest.raises(ValueError, match="최소 한 개"):
        store.store(snapshot_id=uuid.uuid4(), entries=())


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "",
        "../outside.py",
        "/absolute/path.py",
        "src/../../escape.py",
    ),
)
def test_snapshot_archive_store_rejects_unsafe_relative_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    store = SnapshotArchiveStore(settings=settings)
    drafts = (
        SnapshotArchiveEntryDraft(
            path=unsafe_path,
            content=b"print('oops')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
            language_hint="python",
        ),
    )

    with pytest.raises(ValueError, match="상대 경로"):
        store.store(snapshot_id=uuid.uuid4(), entries=drafts)


def test_snapshot_archive_store_rejects_root_manifest_filename(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    store = SnapshotArchiveStore(settings=settings)

    with pytest.raises(ValueError, match="manifest.json"):
        store.store(
            snapshot_id=uuid.uuid4(),
            entries=(
                SnapshotArchiveEntryDraft(
                    path="manifest.json",
                    content=b"{}",
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=".json",
                    language_hint="json",
                ),
            ),
        )


def test_snapshot_archive_store_allows_root_manifest_with_reserved_blob_path(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    store = SnapshotArchiveStore(settings=settings)
    snapshot_id = uuid.uuid4()

    archive = store.store(
        snapshot_id=snapshot_id,
        entries=(
            SnapshotArchiveEntryDraft(
                path="manifest.json",
                content=b'{"name":"repo-manifest"}',
                included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                extension=".json",
                language_hint="json",
                archive_blob_path="__tci_snapshot_reserved__/root-manifest.json",
            ),
        ),
    )

    assert archive.files[0].path == "manifest.json"
    assert (
        archive.absolute_path / "__tci_snapshot_reserved__" / "root-manifest.json"
    ).read_bytes() == b'{"name":"repo-manifest"}'


def test_snapshot_archive_store_rejects_duplicate_archive_blob_paths(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    store = SnapshotArchiveStore(settings=settings)

    with pytest.raises(ValueError, match="아카이브 저장 경로"):
        store.store(
            snapshot_id=uuid.uuid4(),
            entries=(
                SnapshotArchiveEntryDraft(
                    path="manifest.json",
                    content=b'{"name":"repo-manifest"}',
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    archive_blob_path="__tci_snapshot_reserved__/root-manifest.json",
                ),
                SnapshotArchiveEntryDraft(
                    path="__tci_snapshot_reserved__/root-manifest.json",
                    content=b"collision",
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                ),
            ),
        )


def test_snapshot_archive_store_rejects_duplicate_normalized_paths(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    store = SnapshotArchiveStore(settings=settings)

    with pytest.raises(ValueError, match="중복"):
        store.store(
            snapshot_id=uuid.uuid4(),
            entries=(
                SnapshotArchiveEntryDraft(
                    path="src/app.py",
                    content=b"print('one')\n",
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=".py",
                    language_hint="python",
                ),
                SnapshotArchiveEntryDraft(
                    path="src/app.py",
                    content=b"print('two')\n",
                    included_by=SnapshotInclusionReason.USER_INCLUDE,
                    extension=".py",
                    language_hint="python",
                ),
            ),
        )


def test_snapshot_archive_store_rejects_casefold_path_collisions(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    store = SnapshotArchiveStore(settings=settings)

    with pytest.raises(ValueError, match="중복"):
        store.store(
            snapshot_id=uuid.uuid4(),
            entries=(
                SnapshotArchiveEntryDraft(
                    path="src/App.py",
                    content=b"print('one')\n",
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=".py",
                    language_hint="python",
                ),
                SnapshotArchiveEntryDraft(
                    path="src/app.py",
                    content=b"print('two')\n",
                    included_by=SnapshotInclusionReason.USER_INCLUDE,
                    extension=".py",
                    language_hint="python",
                ),
            ),
        )


def test_snapshot_archive_store_cleans_up_archive_when_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots import snapshot_archive_store
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )

    settings = _build_test_settings(tmp_path)
    snapshot_id = uuid.uuid4()
    archive_path = settings.code_snapshot_root / str(snapshot_id)
    original_write_bytes = Path.write_bytes

    def flaky_write_bytes(self: Path, data: bytes) -> int:
        if self.name == "broken.py":
            raise OSError("disk full")
        return original_write_bytes(self, data)

    monkeypatch.setattr(snapshot_archive_store.Path, "write_bytes", flaky_write_bytes)
    store = SnapshotArchiveStore(settings=settings)

    with pytest.raises(OSError, match="disk full"):
        store.store(
            snapshot_id=snapshot_id,
            entries=(
                SnapshotArchiveEntryDraft(
                    path="src/ok.py",
                    content=b"print('ok')\n",
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=".py",
                    language_hint="python",
                ),
                SnapshotArchiveEntryDraft(
                    path="src/broken.py",
                    content=b"print('broken')\n",
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=".py",
                    language_hint="python",
                ),
            ),
        )

    assert not archive_path.exists()


def test_snapshot_manifest_writer_persists_traceability_and_file_metadata(
    tmp_path: Path,
) -> None:
    from tci.domain.services.build_traceability_reference import (
        build_snapshot_traceability_reference,
    )
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )
    from tci.infrastructure.snapshots.snapshot_manifest_writer import (
        SnapshotManifestWriter,
    )

    settings = _build_test_settings(tmp_path)
    planning_input_reference_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    scope_rule_version_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    store = SnapshotArchiveStore(settings=settings)
    archive = store.store(
        snapshot_id=snapshot_id,
        entries=(
            SnapshotArchiveEntryDraft(
                path="src/main.py",
                content=b"print('hello')\n",
                included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                extension=".py",
                language_hint="python",
            ),
        ),
    )
    traceability = build_snapshot_traceability_reference(
        planning_input_reference_id=planning_input_reference_id,
        connection_id=connection_id,
        scope_rule_version_id=scope_rule_version_id,
        sync_run_id=sync_run_id,
        snapshot_id=snapshot_id,
    )
    writer = SnapshotManifestWriter()

    manifest_path = writer.write(archive=archive, traceability=traceability)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["snapshotId"] == str(snapshot_id)
    assert manifest["archivePath"] == f".runtime/code-snapshots/{snapshot_id}"
    assert manifest["traceability"] == {
        "planningInputReferenceId": str(planning_input_reference_id),
        "connectionId": str(connection_id),
        "scopeRuleVersionId": str(scope_rule_version_id),
        "syncRunId": str(sync_run_id),
        "snapshotId": str(snapshot_id),
    }
    assert manifest["files"] == [
        {
            "path": "src/main.py",
            "extension": ".py",
            "languageHint": "python",
            "sizeBytes": len(b"print('hello')\n"),
            "contentSha256": hashlib.sha256(b"print('hello')\n").hexdigest(),
            "archiveBlobPath": "src/main.py",
            "includedBy": "default_policy",
        }
    ]


def test_snapshot_manifest_writer_rejects_snapshot_id_mismatch(tmp_path: Path) -> None:
    from tci.domain.services.build_traceability_reference import (
        build_snapshot_traceability_reference,
    )
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )
    from tci.infrastructure.snapshots.snapshot_manifest_writer import (
        SnapshotManifestWriter,
    )

    settings = _build_test_settings(tmp_path)
    archive_snapshot_id = uuid.uuid4()
    traceability_snapshot_id = uuid.uuid4()
    store = SnapshotArchiveStore(settings=settings)
    archive = store.store(
        snapshot_id=archive_snapshot_id,
        entries=(
            SnapshotArchiveEntryDraft(
                path="src/main.py",
                content=b"print('hello')\n",
                included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                extension=".py",
                language_hint="python",
            ),
        ),
    )
    traceability = build_snapshot_traceability_reference(
        planning_input_reference_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        scope_rule_version_id=uuid.uuid4(),
        sync_run_id=uuid.uuid4(),
        snapshot_id=traceability_snapshot_id,
    )
    writer = SnapshotManifestWriter()

    with pytest.raises(ValueError, match="snapshot_id"):
        writer.write(archive=archive, traceability=traceability)


def test_snapshot_manifest_writer_rejects_manifest_overwrite(tmp_path: Path) -> None:
    from tci.domain.services.build_traceability_reference import (
        build_snapshot_traceability_reference,
    )
    from tci.infrastructure.persistence.models import SnapshotInclusionReason
    from tci.infrastructure.snapshots.snapshot_archive_store import (
        SnapshotArchiveEntryDraft,
        SnapshotArchiveStore,
    )
    from tci.infrastructure.snapshots.snapshot_manifest_writer import (
        SnapshotManifestWriter,
    )

    settings = _build_test_settings(tmp_path)
    snapshot_id = uuid.uuid4()
    store = SnapshotArchiveStore(settings=settings)
    archive = store.store(
        snapshot_id=snapshot_id,
        entries=(
            SnapshotArchiveEntryDraft(
                path="src/main.py",
                content=b"print('hello')\n",
                included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                extension=".py",
                language_hint="python",
            ),
        ),
    )
    traceability = build_snapshot_traceability_reference(
        planning_input_reference_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        scope_rule_version_id=uuid.uuid4(),
        sync_run_id=uuid.uuid4(),
        snapshot_id=snapshot_id,
    )
    writer = SnapshotManifestWriter()
    writer.write(archive=archive, traceability=traceability)

    with pytest.raises(FileExistsError, match="manifest.json"):
        writer.write(archive=archive, traceability=traceability)
