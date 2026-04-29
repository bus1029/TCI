from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)
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
from tci.infrastructure.persistence.models import SyncFailureCode


pytestmark = pytest.mark.integration


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_gitlab_scoped_snapshot_stamps_scope_version_and_preserves_binary_opt_in(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (
        ("src/main.py", b"print('hello')\n"),
        ("assets/logo.bin", b"\x00binary"),
        ("docs/guide.md", b"# Guide\n"),
    )

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    scope_response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["src/**", "assets/**"],
            "excludePaths": [],
            "allowedFileTypes": [".py", ".bin"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
            "excludeBinary": False,
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
    assert payload["requestedRefName"] == "main"
    assert payload["scopeRuleVersionId"] == scope_response.json()["id"]
    assert payload["traceability"]["scopeRuleVersionId"] == scope_response.json()["id"]
    assert [file["path"] for file in payload["files"]] == [
        "src/main.py",
        "assets/logo.bin",
    ]


def test_gitlab_default_ref_change_affects_future_sync_without_mutating_history(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    store.resolved_ref_commits["main"] = "a" * 40
    store.resolved_ref_commits["release/2026.04"] = "c" * 40

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    first_sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )
    first_snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=first_sync_run.id,
        ),
        dependencies=_dependencies(client),
    )

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={
            "defaultRefType": "branch",
            "defaultRefName": "release/2026.04",
        },
    )
    assert patch_response.status_code == 200
    second_sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            reason="manual_refresh",
        ),
        dependencies=_dependencies(client),
    )
    second_snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=second_sync_run.id,
        ),
        dependencies=_dependencies(client),
    )

    first_payload = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{first_snapshot.id}"
    ).json()
    second_payload = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{second_snapshot.id}"
    ).json()
    detail = client.get(f"/api/repository-connections/{connection_id}").json()

    assert first_payload["requestedRefName"] == "main"
    assert first_payload["resolvedCommitSha"] == "a" * 40
    assert second_payload["requestedRefName"] == "release/2026.04"
    assert second_payload["resolvedCommitSha"] == "c" * 40
    assert detail["traceability"]["latestSnapshotId"] == str(second_snapshot.id)
    assert len(store.snapshots) == 2


def test_gitlab_scoped_snapshot_fails_empty_result_without_status_transition(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (("src/main.py", b"print('hello')\n"),)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
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
    assert scope_response.json()["warningState"] == "empty_result_risk"

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
    assert store.connections[connection_id].status.value == "active"
