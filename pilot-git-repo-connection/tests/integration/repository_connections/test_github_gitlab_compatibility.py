from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)
from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tci.domain.services.verify_repository_connection import (
    VerifyRepositoryConnectionCommand,
    verify_repository_connection,
)


PHASE_1_SKIP_REASON = (
    "Phase 1 scaffold: implement mixed-provider regression coverage in T015/T026/T035."
)
pytestmark = pytest.mark.integration
PLANNED_CASES = (
    "test_github_and_gitlab_connections_can_coexist_without_state_collision",
    "test_github_regression_flow_survives_gitlab_provider_addition",
    "test_provider_specific_events_and_snapshots_do_not_cross_contaminate",
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_github_gitlab_compatibility_scaffold_declares_planned_cases() -> None:
    assert "T015/T026/T035" in PHASE_1_SKIP_REASON
    assert (
        tuple(name for name in PLANNED_CASES if callable(globals().get(name)))
        == PLANNED_CASES
    )


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_github_and_gitlab_connections_can_coexist_without_state_collision() -> None:
    """Covers mixed-provider connection summary and detail isolation."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_github_regression_flow_survives_gitlab_provider_addition() -> None:
    """Covers GitHub create, verify, and manual snapshot regression in mixed-provider mode."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_provider_specific_events_and_snapshots_do_not_cross_contaminate() -> None:
    """Covers event, health, and snapshot isolation across providers."""


def test_github_and_gitlab_connection_verify_and_snapshot_flows_coexist(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    github_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    gitlab_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert github_response.status_code == 201
    assert gitlab_response.status_code == 201
    github_id = uuid.UUID(github_response.json()["id"])
    gitlab_id = uuid.UUID(gitlab_response.json()["id"])

    github_sync_run = None
    gitlab_sync_run = None
    for connection_id in (github_id, gitlab_id):
        verify_repository_connection(
            VerifyRepositoryConnectionCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=_dependencies(client),
        )
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
        if connection_id == github_id:
            github_sync_run = sync_run
            github_snapshot = snapshot
            assert "x-access-token:" in (store.last_resolved_remote_url or "")
        else:
            gitlab_sync_run = sync_run
            gitlab_snapshot = snapshot
            assert store.last_resolved_remote_url == (
                "https://x-access-token:readonly-token-value"
                "@gitlab.example.com/group/sample-repo.git"
            )

    github_detail = client.get(f"/api/repository-connections/{github_id}").json()
    gitlab_detail = client.get(f"/api/repository-connections/{gitlab_id}").json()
    github_connection = store.connections[github_id]
    gitlab_connection = store.connections[gitlab_id]

    assert github_detail["provider"] == "github_cloud"
    assert gitlab_detail["provider"] == "gitlab_self_managed"
    assert (
        github_detail["traceability"]["latestSnapshotId"]
        != gitlab_detail["traceability"]["latestSnapshotId"]
    )
    assert github_connection.active_credential_revision_id != (
        gitlab_connection.active_credential_revision_id
    )
    assert github_connection.mirror_path != gitlab_connection.mirror_path
    assert github_sync_run is not None
    assert gitlab_sync_run is not None
    assert github_snapshot.connection_id == github_id
    assert gitlab_snapshot.connection_id == gitlab_id
    assert github_snapshot.sync_run_id == github_sync_run.id
    assert gitlab_snapshot.sync_run_id == gitlab_sync_run.id
    assert len(store.snapshots) == 2
