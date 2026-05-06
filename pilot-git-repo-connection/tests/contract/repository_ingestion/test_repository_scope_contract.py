from __future__ import annotations

from pathlib import Path
from typing import Any, cast
import uuid

import yaml  # type: ignore[import-untyped]

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def _settings(client) -> Any:
    return cast(Any, client.app).state.settings


def test_scope_rule_routes_require_workspace_header(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(_store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
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
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
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
        "excludeBinary": True,
        "warningState": "empty_result_risk",
    }


def test_save_scope_rule_rejects_non_positive_max_file_size(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
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


def test_save_scope_rule_rejects_max_file_size_above_hard_cap(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]

    response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["src/**"],
            "excludePaths": [],
            "allowedFileTypes": [".py"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242881,
        },
    )

    assert response.status_code == 422


def test_save_scope_rule_uses_neutral_warning_on_preview_infrastructure_failure(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]

    def broken_resolve(**kwargs):
        raise RuntimeError("preview failed")

    monkeypatch.setattr(
        _dependencies(client).git_ref_resolver,
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
    assert response.json()["warningState"] == "preview_failed"
    assert (
        store.connections[uuid.UUID(connection_id)].active_scope_rule_version
        is not None
    )


def test_save_scope_rule_preserves_auth_failure_from_preview(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]
    store.auth_failure_ref_names.add("main")

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
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert store.connections[uuid.UUID(connection_id)].active_scope_rule_version is None


def test_save_scope_rule_preserves_missing_ref_from_preview(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]
    store.missing_ref_names.add("main")

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
    assert response.json()["code"] == "DEFAULT_REF_NOT_FOUND"
    assert store.connections[uuid.UUID(connection_id)].active_scope_rule_version is None


def test_save_scope_rule_rejects_unallowlisted_gitlab_before_preview_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
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


def test_runtime_and_feature_contract_document_exclude_binary_scope_field(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    repo_root = Path(__file__).resolve().parents[4]

    runtime_openapi = client.get("/openapi.json").json()
    request_schema = runtime_openapi["components"]["schemas"]["SaveScopeRulesRequest"][
        "properties"
    ]
    runtime_schemas = runtime_openapi["components"]["schemas"]
    scope_response_schema = runtime_openapi["paths"][
        "/api/repository-connections/{connection_id}/scope-rules"
    ]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    detail_response_schema = runtime_openapi["paths"][
        "/api/repository-connections/{connection_id}"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    feature_contract = yaml.safe_load(
        (
            repo_root
            / "specs/002-gitlab-onprem-connection/contracts/repository-ingestion.openapi.yaml"
        ).read_text()
    )
    baseline_contract = yaml.safe_load(
        (
            repo_root
            / "specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml"
        ).read_text()
    )
    feature_schemas = feature_contract["components"]["schemas"]
    baseline_schemas = baseline_contract["components"]["schemas"]

    assert request_schema["excludeBinary"]["type"] == "boolean"
    assert request_schema["excludeBinary"]["default"] is True
    assert request_schema["maxFileSizeBytes"]["maximum"] == 5242880
    assert scope_response_schema["$ref"] == "#/components/schemas/ScopeRuleResponse"
    assert detail_response_schema["$ref"] == (
        "#/components/schemas/RepositoryConnectionDetailResponse"
    )
    assert (
        runtime_schemas["ScopeRuleResponse"]["properties"]["excludeBinary"]["type"]
        == "boolean"
    )
    latest_scope_schema = runtime_schemas["RepositoryConnectionDetailResponse"][
        "properties"
    ]["latestScopeRule"]
    assert latest_scope_schema["anyOf"][0]["$ref"] == (
        "#/components/schemas/ScopeRuleResponse"
    )
    assert latest_scope_schema["anyOf"][1] == {"type": "null"}
    assert (
        baseline_schemas["SaveScopeRulesRequest"]["properties"]["excludeBinary"][
            "default"
        ]
        is True
    )
    assert (
        baseline_schemas["SaveScopeRulesRequest"]["properties"]["maxFileSizeBytes"][
            "maximum"
        ]
        == 5242880
    )
    assert (
        baseline_schemas["ScopeRuleResponse"]["properties"]["excludeBinary"]["type"]
        == "boolean"
    )
    assert (
        feature_schemas["SaveScopeRulesRequest"]["properties"]["excludeBinary"][
            "default"
        ]
        is True
    )
    assert (
        feature_schemas["SaveScopeRulesRequest"]["properties"]["maxFileSizeBytes"][
            "maximum"
        ]
        == 5242880
    )
    assert (
        feature_schemas["ScopeRuleResponse"]["properties"]["excludeBinary"]["type"]
        == "boolean"
    )
    runtime_latest_scope_shape = runtime_schemas["RepositoryConnectionDetailResponse"][
        "properties"
    ]["latestScopeRule"]
    baseline_latest_scope_shape = baseline_schemas[
        "RepositoryConnectionDetailResponse"
    ]["allOf"][1]["properties"]["latestScopeRule"]
    feature_latest_scope_shape = feature_schemas["RepositoryConnectionDetailResponse"][
        "allOf"
    ][1]["properties"]["latestScopeRule"]
    assert baseline_latest_scope_shape == runtime_latest_scope_shape
    assert feature_latest_scope_shape == runtime_latest_scope_shape


def test_runtime_and_feature_contract_document_operator_auth_and_webhook_health(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    repo_root = Path(__file__).resolve().parents[4]

    runtime_openapi = client.get("/openapi.json").json()
    runtime_security = runtime_openapi["security"]
    runtime_security_schemes = runtime_openapi["components"]["securitySchemes"]
    runtime_webhook_health = runtime_openapi["components"]["schemas"]["WebhookHealth"]
    feature_contract = yaml.safe_load(
        (
            repo_root
            / "specs/002-gitlab-onprem-connection/contracts/repository-ingestion.openapi.yaml"
        ).read_text()
    )
    baseline_contract = yaml.safe_load(
        (
            repo_root
            / "specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml"
        ).read_text()
    )

    for contract in (baseline_contract, feature_contract):
        assert contract["security"] == runtime_security
        assert contract["components"]["securitySchemes"] == runtime_security_schemes
        assert (
            contract["components"]["schemas"]["WebhookHealth"] == runtime_webhook_health
        )
        webhook_paths = [
            path for path in contract["paths"] if path.startswith("/api/webhooks/")
        ]
        assert webhook_paths
        for contract_path in webhook_paths:
            runtime_path = contract_path.replace("{connectionId}", "{connection_id}")
            assert contract["paths"][contract_path]["post"]["security"] == []
            assert runtime_openapi["paths"][runtime_path]["post"]["security"] == []
