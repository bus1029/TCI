from __future__ import annotations

import uuid

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def test_scope_rule_routes_require_workspace_header(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(_store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    client.headers.pop("X-TCI-Workspace-Id")

    response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={"includePaths": ["docs/**"]},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
    }


def test_save_scope_rule_returns_warning_and_latest_scope_projection(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["docs/**"],
            "excludePaths": [],
            "allowedFileTypes": [".md"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["includePaths"] == ["docs/**"]
    assert payload["allowedFileTypes"] == [".md"]
    assert payload["warningState"] == "empty_result_risk"

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["traceability"]["activeScopeRuleVersionId"] == payload["id"]
    assert detail["latestScopeRule"] == {
        "id": payload["id"],
        "includePaths": ["docs/**"],
        "excludePaths": [],
        "allowedFileTypes": [".md"],
        "blockedFileTypes": [],
        "maxFileSizeBytes": 5242880,
        "warningState": "empty_result_risk",
    }


def test_save_scope_rule_rejects_non_positive_max_file_size(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["src/**"],
            "excludePaths": [],
            "allowedFileTypes": [".py"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 0,
        },
    )

    assert response.status_code == 422


def test_save_scope_rule_tolerates_preview_failure_and_still_saves_rule(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    def broken_resolve(**kwargs):
        raise RuntimeError("preview failed")

    monkeypatch.setattr(
        client.app.state.dependencies.git_ref_resolver,
        "resolve",
        broken_resolve,
    )

    response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["src/**"],
            "excludePaths": [],
            "allowedFileTypes": [".py"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
        },
    )

    assert response.status_code == 200
    assert response.json()["warningState"] == "ok"
