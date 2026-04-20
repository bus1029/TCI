from __future__ import annotations

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
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.infrastructure.persistence.models import SyncFailureCode
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


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
        dependencies=client.app.state.dependencies,
    )

    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=client.app.state.dependencies,
    )
    snapshot_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
    )

    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["scopeRuleVersionId"] == scope_response.json()["id"]
    assert payload["traceability"]["scopeRuleVersionId"] == scope_response.json()["id"]
    assert [file["path"] for file in payload["files"]] == ["src/main.py", "docs/guide.md"]
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
        dependencies=client.app.state.dependencies,
    )

    with pytest.raises(RepositoryConnectionProblem) as captured:
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=client.app.state.dependencies,
        )

    assert captured.value.problem_code is ProblemCode.NO_INCLUDED_FILES
    assert store.sync_runs[sync_run.id].failure_code is SyncFailureCode.NO_INCLUDED_FILES
    assert store.connections[connection_id].last_failed_sync_at is not None
