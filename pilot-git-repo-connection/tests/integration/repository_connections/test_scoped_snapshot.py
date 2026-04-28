from __future__ import annotations

from dataclasses import replace
from typing import Any, cast
import uuid

import pytest

from tci.api.problem_details import ProblemCode
from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.infrastructure.persistence.models import ScopeRuleWarningState, SyncFailureCode
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_active_scope_rule_version,
    seed_planning_input_reference,
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_scoped_snapshot_stores_filtered_files_and_scope_version(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (
        ("src/main.py", b"print('hello')\n"),
        ("src/notes.txt", b"draft\n"),
        ("docs/guide.md", b"# Guide\n"),
        ("dist/bundle.js", b"console.log('bundle')\n"),
    )

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])

    scope_response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["src/**", "docs/**"],
            "excludePaths": ["src/notes.txt"],
            "allowedFileTypes": [".py", ".md"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
        },
    )
    assert scope_response.status_code == 200

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )

    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=_dependencies(client),
    )
    snapshot_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
    )

    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["scopeRuleVersionId"] == scope_response.json()["id"]
    assert payload["traceability"]["scopeRuleVersionId"] == scope_response.json()["id"]
    assert [file["path"] for file in payload["files"]] == [
        "src/main.py",
        "docs/guide.md",
    ]
    assert [file["includedBy"] for file in payload["files"]] == [
        "user_include",
        "user_include",
    ]


def test_scoped_snapshot_fails_when_scope_rule_excludes_everything(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (("src/main.py", b"print('hello')\n"),)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])

    scope_response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["docs/**"],
            "excludePaths": [],
            "allowedFileTypes": [".md"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
        },
    )
    assert scope_response.status_code == 200

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )

    with pytest.raises(RepositoryConnectionProblem) as captured:
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=_dependencies(client),
        )

    assert captured.value.problem_code is ProblemCode.NO_INCLUDED_FILES
    assert captured.value.detail is not None
    assert "범위 규칙" in captured.value.detail
    assert (
        store.sync_runs[sync_run.id].failure_code is SyncFailureCode.NO_INCLUDED_FILES
    )
    assert store.connections[connection_id].last_failed_sync_at is not None


def test_scoped_snapshot_reports_saved_default_equivalent_scope_as_scope_rule(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = ()

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])

    scope_response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": [],
            "excludePaths": [],
            "allowedFileTypes": [],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
            "excludeBinary": True,
        },
    )
    assert scope_response.status_code == 200

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )

    with pytest.raises(RepositoryConnectionProblem) as captured:
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=_dependencies(client),
        )

    assert captured.value.problem_code is ProblemCode.NO_INCLUDED_FILES
    assert captured.value.detail is not None
    assert "범위 규칙" in captured.value.detail


def test_first_snapshot_failure_persists_default_scope_rule_for_traceability(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = ()

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    assert store.connections[connection_id].active_scope_rule_version_id is None

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )

    with pytest.raises(RepositoryConnectionProblem) as captured:
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=_dependencies(client),
        )

    assert captured.value.problem_code is ProblemCode.NO_INCLUDED_FILES
    assert (
        store.sync_runs[sync_run.id].failure_code is SyncFailureCode.NO_INCLUDED_FILES
    )
    active_scope_rule = store.connections[connection_id].active_scope_rule_version
    assert active_scope_rule is not None
    assert active_scope_rule.exclude_binary is True


def test_first_snapshot_refilters_when_scope_rule_is_saved_during_build(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    dependencies = _dependencies(client)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (
        ("src/main.py", b"print('hello')\n"),
        ("docs/guide.md", b"# Guide\n"),
    )

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seeded_scope = None
    original_read_snapshot_entries = (
        dependencies.git_mirror_manager.read_snapshot_entries
    )

    def read_snapshot_entries_with_concurrent_scope_save(**kwargs):
        nonlocal seeded_scope
        if seeded_scope is None:
            seeded_scope = seed_active_scope_rule_version(
                store,
                workspace_id=workspace_id,
                connection_id=connection_id,
                include_paths=["docs/**"],
                allowed_file_types=[".md"],
            )
        return original_read_snapshot_entries(**kwargs)

    monkeypatch.setattr(
        dependencies.git_mirror_manager,
        "read_snapshot_entries",
        read_snapshot_entries_with_concurrent_scope_save,
    )

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )
    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=dependencies,
    )
    snapshot_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
    )

    assert seeded_scope is not None
    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["scopeRuleVersionId"] == str(seeded_scope.id)
    assert [file["path"] for file in payload["files"]] == ["docs/guide.md"]


def test_first_snapshot_rereads_binary_entries_when_scope_saved_during_build(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    dependencies = _dependencies(client)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (("assets/logo.bin", b"\x00binary"),)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seeded_scope = None
    original_read_snapshot_entries = (
        dependencies.git_mirror_manager.read_snapshot_entries
    )

    def read_snapshot_entries_with_concurrent_binary_scope(**kwargs):
        nonlocal seeded_scope
        if seeded_scope is None:
            seeded_scope = seed_active_scope_rule_version(
                store,
                workspace_id=workspace_id,
                connection_id=connection_id,
                exclude_binary=False,
            )
        return original_read_snapshot_entries(**kwargs)

    monkeypatch.setattr(
        dependencies.git_mirror_manager,
        "read_snapshot_entries",
        read_snapshot_entries_with_concurrent_binary_scope,
    )

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )
    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=dependencies,
    )
    snapshot_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
    )

    assert seeded_scope is not None
    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["scopeRuleVersionId"] == str(seeded_scope.id)
    assert [file["path"] for file in payload["files"]] == ["assets/logo.bin"]


def test_first_snapshot_retries_when_scope_changes_before_empty_failure_is_recorded(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    dependencies = _dependencies(client)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (("assets/logo.bin", b"\x00binary"),)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    original_factory = dependencies.repository_connection_repository_factory
    ensure_call_count = 0
    replacement_scope = None

    class ConcurrentScopeChangeRepository:
        def __init__(self, repository):
            self._repository = repository

        def __getattr__(self, name):
            return getattr(self._repository, name)

        def ensure_default_scope_rule_version(self, **kwargs):
            nonlocal ensure_call_count, replacement_scope
            ensure_call_count += 1
            if ensure_call_count == 2:
                replacement_scope = seed_active_scope_rule_version(
                    store,
                    workspace_id=workspace_id,
                    connection_id=connection_id,
                    exclude_binary=False,
                )
            return self._repository.ensure_default_scope_rule_version(**kwargs)

    def repository_factory_with_concurrent_scope_change(session):
        return ConcurrentScopeChangeRepository(original_factory(session))

    dependencies = replace(
        dependencies,
        repository_connection_repository_factory=repository_factory_with_concurrent_scope_change,
    )
    cast(Any, client.app).state.dependencies = dependencies

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )

    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=dependencies,
    )
    snapshot_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
    )

    assert replacement_scope is not None
    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["scopeRuleVersionId"] == str(replacement_scope.id)
    assert [file["path"] for file in payload["files"]] == ["assets/logo.bin"]


def test_snapshot_retries_when_existing_scope_changes_before_metadata_write(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    dependencies = _dependencies(client)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (
        ("src/main.py", b"print('hello')\n"),
        ("docs/guide.md", b"# Guide\n"),
    )

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    original_scope = seed_active_scope_rule_version(
        store,
        workspace_id=workspace_id,
        connection_id=connection_id,
        include_paths=["src/**"],
        allowed_file_types=[".py"],
    )
    replacement_scope = None
    original_store = dependencies.snapshot_archive_store.store

    def store_with_concurrent_scope_save(**kwargs):
        nonlocal replacement_scope
        if replacement_scope is None:
            replacement_scope = seed_active_scope_rule_version(
                store,
                workspace_id=workspace_id,
                connection_id=connection_id,
                include_paths=["docs/**"],
                allowed_file_types=[".md"],
                warning_state=ScopeRuleWarningState.OK,
            )
        return original_store(**kwargs)

    monkeypatch.setattr(
        dependencies.snapshot_archive_store,
        "store",
        store_with_concurrent_scope_save,
    )

    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )

    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=dependencies,
    )
    snapshot_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
    )

    assert replacement_scope is not None
    assert replacement_scope.id != original_scope.id
    assert (
        store.connections[connection_id].active_scope_rule_version_id
        == replacement_scope.id
    )
    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["scopeRuleVersionId"] == str(replacement_scope.id)
    assert [file["path"] for file in payload["files"]] == ["docs/guide.md"]
