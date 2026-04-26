from __future__ import annotations

import uuid
from typing import Any, cast

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def _settings(client) -> Any:
    return cast(Any, client.app).state.settings


def test_gitlab_scope_rule_save_returns_detail_projection_with_binary_policy(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    store.mirror_snapshot_entries = (
        ("src/main.py", b"print('hello')\n"),
        ("assets/logo.bin", b"\x00binary"),
    )

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    connection_id = create_response.json()["id"]

    response = client.post(
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

    assert response.status_code == 200
    payload = response.json()
    assert payload["includePaths"] == ["src/**", "assets/**"]
    assert payload["allowedFileTypes"] == [".py", ".bin"]
    assert payload["excludeBinary"] is False
    assert payload["warningState"] == "ok"

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["provider"] == "gitlab_self_managed"
    assert detail["latestScopeRule"]["id"] == payload["id"]
    assert detail["latestScopeRule"]["excludeBinary"] is False
    assert "webhookAuthMode" not in detail
    assert "shared_token" not in detail_response.text


def test_gitlab_scope_rule_save_rejects_unallowlisted_host_before_preview(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    connection_id = create_response.json()["id"]
    store.last_resolved_remote_url = None
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        (),
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

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
    }
    assert store.last_resolved_remote_url is None
