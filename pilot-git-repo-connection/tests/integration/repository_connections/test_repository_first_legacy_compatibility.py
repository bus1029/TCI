from __future__ import annotations

import uuid

import pytest

from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


pytestmark = pytest.mark.integration


def test_connection_with_missing_legacy_planning_reference_shows_compatibility_state(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    connection = store.connections[connection_id]
    connection.planning_input_reference_id = uuid.uuid4()
    connection.planning_input_reference = None

    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    page_response = client.get(
        f"/connections/{connection_id}?workspaceId={workspace_id}"
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["origin"] == {
        "kind": "legacy_unassigned",
        "hasLegacyPlanningTrace": False,
        "compatibilityState": "workspace_assignment_unclear",
        "message": "기존 planning trace를 확인할 수 없어 호환성 확인이 필요합니다.",
    }
    assert page_response.status_code == 200
    assert "호환성 확인 필요" in page_response.text


def test_legacy_connection_with_cross_workspace_planning_reference_is_unassigned(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    other_planning_reference = seed_planning_input_reference(
        store,
        workspace_id=other_workspace_id,
    )
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    connection = store.connections[connection_id]
    connection.planning_input_reference_id = other_planning_reference.id
    connection.planning_input_reference = other_planning_reference

    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    list_response = client.get(f"/connections?workspaceId={workspace_id}")
    other_workspace_response = client.get(
        f"/api/repository-connections/{connection_id}",
        headers={"X-TCI-Workspace-Id": str(other_workspace_id)},
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["origin"] == {
        "kind": "legacy_unassigned",
        "hasLegacyPlanningTrace": False,
        "compatibilityState": "workspace_assignment_unclear",
        "message": "기존 planning trace를 확인할 수 없어 호환성 확인이 필요합니다.",
    }
    assert detail_response.json()["traceability"]["planningInputReference"] is None
    assert list_response.status_code == 200
    assert "출처: 호환성 확인 필요" in list_response.text
    assert other_workspace_response.status_code == 404


def test_cross_workspace_planning_reference_is_hidden_from_snapshot_detail(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    other_planning_reference = seed_planning_input_reference(
        store,
        workspace_id=other_workspace_id,
    )
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    connection = store.connections[connection_id]
    connection.planning_input_reference_id = other_planning_reference.id
    connection.planning_input_reference = other_planning_reference
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
    assert snapshot_response.json()["traceability"]["planningInputReference"] is None
