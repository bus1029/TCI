from __future__ import annotations

import uuid

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def test_create_connection_rejects_unsupported_provider(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_cloud",
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "UNSUPPORTED_PROVIDER",
        "message": "v1에서는 GitHub Cloud 저장소만 지원합니다.",
    }


def test_repository_connection_routes_require_workspace_header(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Workspace-Id")

    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
    }


def test_get_connection_detail_returns_null_last_processed_event_and_traceability(
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

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    assert detail_response.json() == {
        "id": connection_id,
        "provider": "github_cloud",
        "remoteUrl": "https://github.com/acme/sample-repo.git",
        "transport": "https",
        "defaultRefType": "branch",
        "defaultRefName": "main",
        "status": "active",
        "lastVerifiedAt": create_response.json()["lastVerifiedAt"],
        "lastSuccessfulSnapshotAt": None,
        "lastFailedSyncAt": None,
        "lastProcessedEventAt": None,
        "lastProcessedEvent": None,
        "latestSnapshot": None,
        "traceability": {
            "planningInputReference": {
                "id": str(reference.id),
                "sourceType": "user_request",
                "sourceReference": "chat://test",
                "approvedSpecPath": "specs/001-git-repo-connection/spec.md",
                "approvedPlanPath": "specs/001-git-repo-connection/plan.md",
            },
            "activeScopeRuleVersionId": None,
            "latestEventId": None,
            "latestSnapshotId": None,
        },
        "additionalRefGuidance": {
            "message": "이 연결은 기본 ref 1개만 지원합니다.",
            "options": [
                {
                    "action": "create_new_connection",
                    "label": "새 연결 생성",
                },
                {
                    "action": "replace_default_ref",
                    "label": "기본 ref 교체",
                },
            ],
        },
    }


def test_patch_connection_updates_default_ref(tmp_path) -> None:
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
        json={
            "defaultRefType": "branch",
            "defaultRefName": "release/2026.04",
        },
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["defaultRefName"] == "release/2026.04"
    assert patch_response.json()["status"] == "active"


def test_verify_connection_returns_accepted_response(tmp_path) -> None:
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
    assert verify_response.json() == {
        "status": "verification_queued",
        "connectionId": connection_id,
    }
