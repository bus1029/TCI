from __future__ import annotations

import uuid

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def test_scope_page_renders_current_warning_state(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["docs/**"],
            "excludePaths": [],
            "allowedFileTypes": [".md"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
        },
    )

    response = client.get(f"/connections/{connection_id}/scope?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "수집 범위 설정" in response.text
    assert "현재 경고 상태: empty_result_risk" in response.text
    assert 'name="includePaths"' in response.text


def test_scope_page_save_redirects_back_to_scope_view(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    response = client.post(
        f"/connections/{connection_id}/scope?workspaceId={workspace_id}",
        data={
            "includePaths": "src/**, docs/**",
            "excludePaths": "docs/private/**",
            "allowedFileTypes": ".py, .md",
            "blockedFileTypes": "",
            "maxFileSizeBytes": "5242880",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/connections/{connection_id}/scope?workspaceId={workspace_id}"
    )
    active_scope_rule = store.connections[uuid.UUID(connection_id)].active_scope_rule_version
    assert active_scope_rule is not None
    assert active_scope_rule.include_paths == ["src/**", "docs/**"]
    assert active_scope_rule.exclude_paths == ["docs/private/**"]
    assert active_scope_rule.allowed_file_types == [".py", ".md"]


def test_scope_page_rejects_non_positive_max_file_size(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    response = client.post(
        f"/connections/{connection_id}/scope?workspaceId={workspace_id}",
        data={
            "includePaths": "src/**",
            "excludePaths": "",
            "allowedFileTypes": ".py",
            "blockedFileTypes": "",
            "maxFileSizeBytes": "0",
        },
    )

    assert response.status_code == 400
    assert "greater than or equal to 1" in response.text
