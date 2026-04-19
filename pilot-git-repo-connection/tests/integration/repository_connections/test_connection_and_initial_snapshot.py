from __future__ import annotations

import uuid

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def test_create_connection_with_readonly_credential_creates_active_connection(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["provider"] == "github_cloud"
    assert payload["transport"] == "https"
    assert payload["defaultRefType"] == "branch"
    assert payload["defaultRefName"] == "main"
    assert payload["status"] == "active"
    assert payload["lastVerifiedAt"] is not None


def test_connection_detail_exposes_traceability_and_placeholder_summaries(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["traceability"]["planningInputReference"]["id"] == str(reference.id)
    assert detail["traceability"]["latestSnapshotId"] is None
    assert detail["lastSuccessfulSnapshotAt"] is None
    assert detail["lastFailedSyncAt"] is None
    assert detail["lastProcessedEvent"] is None
    assert detail["latestSnapshot"] is None


def test_default_ref_change_updates_future_target_without_erasing_existing_state(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={"defaultRefType": "branch", "defaultRefName": "release/hotfix"},
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert patch_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.json()["defaultRefName"] == "release/hotfix"
    assert detail_response.json()["lastSuccessfulSnapshotAt"] is None
    assert detail_response.json()["traceability"]["latestSnapshotId"] is None


def test_verify_endpoint_accepts_known_connection_for_followup_worker_execution(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    verify_response = client.post(f"/api/repository-connections/{connection_id}/verify")

    assert verify_response.status_code == 202
    assert verify_response.json()["status"] == "verification_queued"
    assert verify_response.json()["connectionId"] == connection_id


def test_create_connection_rejects_planning_input_from_other_workspace(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=other_workspace_id)

    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "planningInputReferenceId가 유효하지 않습니다.",
    }
