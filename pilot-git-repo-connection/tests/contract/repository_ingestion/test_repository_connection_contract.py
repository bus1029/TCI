from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import uuid
from types import SimpleNamespace

from sqlalchemy.exc import OperationalError

from tci.infrastructure.persistence.models import RepositoryConnectionStatus
from tests.support.repository_connection_testkit import (
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_planning_input_reference_payload,
    create_test_client,
    seed_rotated_webhook_secret_with_grace,
    seed_planning_input_reference,
    serialize_github_webhook_payload,
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
        "message": "지원하지 않는 저장소 provider입니다.",
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


def test_create_planning_input_reference_route_requires_workspace_header(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Workspace-Id")

    response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(workspace_id=workspace_id),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
    }


def test_create_planning_input_reference_rejects_workspace_header_body_mismatch(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    header_workspace_id = uuid.uuid4()
    client, _store = create_test_client(
        tmp_path=tmp_path, workspace_id=header_workspace_id
    )

    response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(workspace_id=workspace_id),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "workspaceId 본문 값과 X-TCI-Workspace-Id 헤더가 일치해야 합니다.",
    }


def test_create_planning_input_reference_returns_503_without_database_session(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    object.__setattr__(client.app.state.dependencies, "session_factory", None)

    response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(workspace_id=workspace_id),
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "planning input reference를 생성하려면 데이터베이스를 사용할 수 있어야 합니다."
    }


def test_create_planning_input_reference_returns_503_when_database_is_unreachable(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    @contextmanager
    def unavailable_session_factory():
        raise OperationalError("SELECT 1", {}, RuntimeError("database down"))
        yield object()

    object.__setattr__(
        client.app.state.dependencies,
        "session_factory",
        unavailable_session_factory,
    )

    response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(workspace_id=workspace_id),
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "planning input reference를 생성하려면 데이터베이스를 사용할 수 있어야 합니다."
    }


def test_openapi_documents_workspace_header_for_repository_connection_routes(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    openapi_response = client.get("/openapi.json")

    assert openapi_response.status_code == 200
    create_parameters = openapi_response.json()["paths"]["/api/repository-connections"][
        "post"
    ]["parameters"]
    assert create_parameters == [
        {
            "name": "X-TCI-Workspace-Id",
            "in": "header",
            "required": False,
            "schema": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "워크스페이스 UUID",
                "title": "X-Tci-Workspace-Id",
            },
            "description": "워크스페이스 UUID",
        }
    ]
    webhook_secret_parameters = openapi_response.json()["paths"][
        "/api/repository-connections/{connection_id}/webhook-secret"
    ]["post"]["parameters"]
    assert webhook_secret_parameters == [
        {
            "name": "connection_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string", "format": "uuid", "title": "Connection Id"},
        },
        {
            "name": "X-TCI-Workspace-Id",
            "in": "header",
            "required": False,
            "schema": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "워크스페이스 UUID",
                "title": "X-Tci-Workspace-Id",
            },
            "description": "워크스페이스 UUID",
        },
    ]
    planning_input_post = openapi_response.json()["paths"][
        "/api/planning-input-references"
    ]["post"]
    assert planning_input_post["parameters"] == [
        {
            "name": "X-TCI-Workspace-Id",
            "in": "header",
            "required": True,
            "schema": {
                "type": "string",
                "title": "X-Tci-Workspace-Id",
                "description": "워크스페이스 UUID",
            },
            "description": "워크스페이스 UUID",
        }
    ]
    assert (
        planning_input_post["responses"]["201"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        == "#/components/schemas/PlanningInputReferenceResponse"
    )


def test_webhook_secret_route_requires_workspace_header(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    client.headers.pop("X-TCI-Workspace-Id")

    response = client.post(
        f"/api/repository-connections/{connection_id}/webhook-secret"
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
    }


def test_create_planning_input_reference_returns_traceable_reference_payload(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(
            workspace_id=workspace_id,
            source_title="GitHub 저장소 연결 테스트",
            source_reference="manual://integration-docs",
        ),
    )

    assert response.status_code == 201
    payload = response.json()
    assert uuid.UUID(payload["id"])
    assert payload["workspaceId"] == str(workspace_id)
    assert payload["sourceType"] == "user_request"
    assert payload["sourceTitle"] == "GitHub 저장소 연결 테스트"
    assert payload["sourceReference"] == "manual://integration-docs"
    assert payload["approvedSpecPath"] == "specs/001-git-repo-connection/spec.md"
    assert payload["approvedPlanPath"] == "specs/001-git-repo-connection/plan.md"
    assert payload["createdAt"] is not None
    assert uuid.UUID(payload["id"]) in store.planning_input_references


def test_create_planning_input_reference_rejects_invalid_feature_paths(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(
            workspace_id=workspace_id,
            approved_spec_path="specs/001-git-repo-connection/spec.md",
            approved_plan_path="specs/002-other-feature/plan.md",
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "승인된 spec/plan 경로는 같은 기능 디렉터리를 가리켜야 합니다.",
    }


def test_create_planning_input_reference_rejects_unknown_source_type(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(
            workspace_id=workspace_id,
            source_type="unknown_source",
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "sourceType은 user_request, planning_brief, imported_note 중 하나여야 합니다.",
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
        "latestScopeRule": None,
        "lastSuccessfulSnapshotAt": None,
        "lastFailedSyncAt": None,
        "lastProcessedEventAt": None,
        "lastProcessedEvent": None,
        "latestSnapshot": None,
        "latestSyncRun": None,
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


def test_create_connection_accepts_gitlab_provider_and_derives_provider_metadata(
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
            remote_url="https://gitlab.example.com/group/subgroup/sample-repo.git",
        ),
    )

    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["provider"] == "gitlab_self_managed"
    assert (
        payload["remoteUrl"]
        == "https://gitlab.example.com/group/subgroup/sample-repo.git"
    )
    assert payload["transport"] == "https"
    assert payload["providerInstanceUrl"] == "https://gitlab.example.com"
    assert payload["providerProjectPath"] == "group/subgroup/sample-repo"
    assert "webhookAuthMode" not in payload
    connection = store.connections[uuid.UUID(payload["id"])]
    assert connection.provider_instance_url == "https://gitlab.example.com"
    assert connection.provider_project_path == "group/subgroup/sample-repo"
    assert connection.repository_owner == "group/subgroup"
    assert connection.repository_name == "sample-repo"


def test_create_connection_rejects_unallowlisted_gitlab_host_before_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    object.__setattr__(
        client.app.state.settings,
        "gitlab_self_managed_allowed_hosts",
        (),
    )
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/subgroup/sample-repo.git",
        ),
    )

    assert create_response.status_code == 400
    assert create_response.json() == {
        "code": "INVALID_INPUT",
        "message": "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
    }
    assert store.last_resolved_remote_url is None


def test_create_connection_rejects_unallowlisted_gitlab_https_port_before_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    object.__setattr__(
        client.app.state.settings,
        "gitlab_self_managed_allowed_hosts",
        ("gitlab.example.com",),
    )
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com:8443/group/sample-repo.git",
        ),
    )

    assert create_response.status_code == 400
    assert create_response.json() == {
        "code": "INVALID_INPUT",
        "message": "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
    }
    assert store.last_resolved_remote_url is None


def test_create_connection_rejects_unallowlisted_gitlab_ssh_port_before_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    object.__setattr__(
        client.app.state.settings,
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20",),
    )
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="ssh://git@192.168.10.20:2222/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret="-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n-----END OPENSSH PRIVATE KEY-----",
            credential_fingerprint="ssh-key-private-ip",
        ),
    )

    assert create_response.status_code == 400
    assert create_response.json() == {
        "code": "INVALID_INPUT",
        "message": "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
    }
    assert store.last_resolved_remote_url is None


def test_create_connection_treats_gitlab_path_prefix_as_project_namespace(
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
            remote_url="https://gitlab.example.com/gitlab/group/subgroup/sample-repo.git",
        ),
    )

    assert create_response.status_code == 201
    connection = store.connections[uuid.UUID(create_response.json()["id"])]
    assert connection.provider_instance_url == "https://gitlab.example.com"
    assert connection.provider_project_path == "gitlab/group/subgroup/sample-repo"
    assert connection.repository_owner == "gitlab/group/subgroup"
    assert connection.repository_name == "sample-repo"


def test_create_connection_treats_gitlab_path_prefix_as_project_namespace_for_ssh_remote(
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
            remote_url="git@gitlab.example.com:gitlab/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret="-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n-----END OPENSSH PRIVATE KEY-----",
            credential_fingerprint="ssh-key-01",
        ),
    )

    assert create_response.status_code == 201
    connection = store.connections[uuid.UUID(create_response.json()["id"])]
    assert connection.provider_instance_url == "https://gitlab.example.com"
    assert connection.provider_project_path == "gitlab/group/sample-repo"
    assert connection.repository_owner == "gitlab/group"
    assert connection.repository_name == "sample-repo"


def test_create_connection_treats_gitlab_path_prefix_as_project_namespace_for_ssh_url_remote(
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
            remote_url="ssh://git@gitlab.example.com/gitlab/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret="-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n-----END OPENSSH PRIVATE KEY-----",
            credential_fingerprint="ssh-key-02",
        ),
    )

    assert create_response.status_code == 201
    connection = store.connections[uuid.UUID(create_response.json()["id"])]
    assert connection.provider_instance_url == "https://gitlab.example.com"
    assert connection.provider_project_path == "gitlab/group/sample-repo"
    assert connection.repository_owner == "gitlab/group"
    assert connection.repository_name == "sample-repo"


def test_create_connection_accepts_private_ip_gitlab_ssh_remote_with_custom_port(
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
            remote_url="ssh://git@192.168.10.20:2222/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret="-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n-----END OPENSSH PRIVATE KEY-----",
            credential_fingerprint="ssh-key-private-ip",
        ),
    )

    assert create_response.status_code == 201
    connection = store.connections[uuid.UUID(create_response.json()["id"])]
    assert connection.provider_instance_url == "https://192.168.10.20"
    assert connection.provider_project_path == "group/sample-repo"
    assert connection.repository_owner == "group"
    assert connection.repository_name == "sample-repo"


def test_create_connection_accepts_gitlab_https_remote_with_custom_port(
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
            remote_url="https://gitlab.example.com:8443/group/sample-repo.git",
        ),
    )

    assert create_response.status_code == 201
    connection = store.connections[uuid.UUID(create_response.json()["id"])]
    assert connection.provider_instance_url == "https://gitlab.example.com:8443"
    assert connection.provider_project_path == "group/sample-repo"
    assert connection.repository_owner == "group"
    assert connection.repository_name == "sample-repo"


def test_get_connection_detail_preserves_shared_shape_for_gitlab_connection(
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
            remote_url="https://gitlab.example.com/group/subgroup/sample-repo.git",
        ),
    )
    connection_id = create_response.json()["id"]

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["provider"] == "gitlab_self_managed"
    assert payload["status"] == "active"
    assert payload["providerInstanceUrl"] == "https://gitlab.example.com"
    assert payload["providerProjectPath"] == "group/subgroup/sample-repo"
    assert "webhookAuthMode" not in payload
    assert payload["traceability"]["planningInputReference"]["id"] == str(reference.id)


def test_get_connection_detail_exposes_webhook_rotation_projection(
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
    grace_until = datetime.now(tz=UTC) + timedelta(hours=24)
    seed_rotated_webhook_secret_with_grace(
        store,
        connection_id=uuid.UUID(connection_id),
        active_secret="current-secret",
        previous_secret="previous-secret",
        grace_until=grace_until,
    )
    store.resolved_ref_commits["main"] = "a" * 40
    payload = build_github_push_payload(after_sha="a" * 40)
    headers = build_github_webhook_headers(
        secret="previous-secret",
        payload=payload,
        delivery_id="delivery-rotation-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    webhook_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    assert webhook_response.status_code == 202

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["webhookHealth"] == {
        "status": "healthy",
        "lastRejectedReason": None,
        "lastRejectedAt": None,
        "rotationState": "grace_active",
        "graceUntil": grace_until.isoformat(),
        "previousSecretDeliveriesDuringGrace": 1,
        "lastPreviousSecretAcceptedAt": detail_response.json()["lastProcessedEventAt"],
    }


def test_issue_webhook_secret_returns_one_time_plaintext_without_leaking_it_in_detail(
    tmp_path, monkeypatch
) -> None:
    import tci.api.routes.repository_connections as repository_connections_routes

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    monkeypatch.setattr(
        repository_connections_routes,
        "generate_webhook_secret",
        lambda: "issued-secret-once",
    )

    issue_response = client.post(
        f"/api/repository-connections/{connection_id}/webhook-secret"
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert issue_response.status_code == 201
    assert issue_response.json() == {
        "status": "secret_issued",
        "connectionId": connection_id,
        "webhookSecret": "issued-secret-once",
        "webhookSecretRevisionId": issue_response.json()["webhookSecretRevisionId"],
        "graceUntil": None,
    }
    assert uuid.UUID(issue_response.json()["webhookSecretRevisionId"])
    detail_payload = detail_response.json()
    assert "issued-secret-once" not in str(detail_payload)
    assert detail_payload["webhookHealth"]["rotationState"] == "not_rotating"


def test_issue_webhook_secret_returns_structured_error_when_encryption_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    import tci.api.routes.repository_connections as repository_connections_routes

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    monkeypatch.setattr(
        repository_connections_routes,
        "generate_webhook_secret",
        lambda: "secret-that-cannot-be-encrypted",
    )
    object.__setattr__(client.app.state.settings, "credential_encryption_key", None)

    response = client.post(
        f"/api/repository-connections/{connection_id}/webhook-secret"
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "CONNECTION_AUTH_FAILED",
        "message": "저장소 자격 증명을 사용할 수 없습니다.",
    }


def test_issue_webhook_secret_returns_not_found_before_encryption_failure_for_missing_connection(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    object.__setattr__(client.app.state.settings, "credential_encryption_key", None)

    response = client.post(f"/api/repository-connections/{uuid.uuid4()}/webhook-secret")

    assert response.status_code == 404
    assert response.json() == {"detail": "저장소 연결을 찾을 수 없습니다."}


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


def test_patch_connection_rejects_unallowlisted_gitlab_before_git_access(
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
        client.app.state.settings,
        "gitlab_self_managed_allowed_hosts",
        (),
    )

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={
            "defaultRefType": "branch",
            "defaultRefName": "release/2026.04",
        },
    )

    assert patch_response.status_code == 400
    assert patch_response.json() == {
        "code": "INVALID_INPUT",
        "message": "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
    }
    assert store.last_resolved_remote_url is None


def test_patch_gitlab_connection_response_includes_provider_metadata_without_webhook_auth_mode(
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

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={
            "defaultRefType": "branch",
            "defaultRefName": "release/2026.04",
        },
    )

    assert patch_response.status_code == 200
    payload = patch_response.json()
    assert payload["defaultRefName"] == "release/2026.04"
    assert payload["providerInstanceUrl"] == "https://gitlab.example.com"
    assert payload["providerProjectPath"] == "group/sample-repo"
    assert "webhookAuthMode" not in payload


def test_patch_missing_gitlab_ref_persists_ref_missing_and_blocks_later_snapshot(
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
    store.missing_ref_names.add("release/2026.04")

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={
            "defaultRefType": "branch",
            "defaultRefName": "release/2026.04",
        },
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert patch_response.status_code == 400
    assert patch_response.json()["code"] == "DEFAULT_REF_NOT_FOUND"
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "ref_missing"
    assert detail_response.json()["defaultRefName"] == "main"
    assert snapshot_response.status_code == 409
    assert snapshot_response.json() == {
        "code": "DEFAULT_REF_NOT_FOUND",
        "message": "기본 ref가 유효하지 않아 새 스냅샷을 시작할 수 없습니다.",
    }


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

    assert verify_response.status_code == 503
    assert verify_response.json() == {
        "detail": "검증 작업 큐가 설정되지 않았습니다.",
    }


def test_verify_connection_enqueues_workspace_scoped_task_when_redis_is_enabled(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    captured: dict[str, object] = {}

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_connections.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    verify_response = client.post(f"/api/repository-connections/{connection_id}/verify")

    assert verify_response.status_code == 202
    assert captured == {
        "name": "tci.repository_ingestion.verify_repository_connection",
        "kwargs": {
            "workspace_id": str(workspace_id),
            "connection_id": connection_id,
        },
    }


def test_create_snapshot_requires_queue_configuration(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 503
    assert snapshot_response.json() == {
        "detail": "스냅샷 작업 큐가 설정되지 않았습니다.",
    }


def test_create_snapshot_returns_not_found_before_queue_check(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    snapshot_response = client.post(
        f"/api/repository-connections/{uuid.uuid4()}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 404
    assert snapshot_response.json() == {"detail": "저장소 연결을 찾을 수 없습니다."}


def test_create_snapshot_enqueues_workspace_scoped_task_when_redis_is_enabled(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    captured: dict[str, object] = {}

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 202
    assert snapshot_response.json()["status"] == "sync_queued"
    assert uuid.UUID(snapshot_response.json()["syncRunId"])
    assert captured["name"] == "tci.repository_ingestion.run_manual_snapshot_sync"
    assert captured["kwargs"]["workspace_id"] == str(workspace_id)
    assert captured["kwargs"]["connection_id"] == connection_id
    assert uuid.UUID(captured["kwargs"]["sync_run_id"])


def test_create_snapshot_defaults_to_manual_initial_when_body_is_missing(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    captured: dict[str, object] = {}

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
    )

    assert snapshot_response.status_code == 202
    assert snapshot_response.json()["status"] == "sync_queued"
    assert captured["name"] == "tci.repository_ingestion.run_manual_snapshot_sync"


def test_create_snapshot_cleans_up_pending_run_when_enqueue_fails(
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

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: (_ for _ in ()).throw(
                RuntimeError("broker down")
            )
        ),
    )

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 503
    assert snapshot_response.json() == {
        "detail": "스냅샷 작업 큐에 연결할 수 없습니다."
    }
    assert store.sync_runs == {}


def test_create_snapshot_rejects_invalid_reason_with_problem_response(
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

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "bad_reason"},
    )

    assert snapshot_response.status_code == 400
    assert snapshot_response.json() == {
        "code": "INVALID_INPUT",
        "message": "reason은 manual_initial 또는 manual_refresh여야 합니다.",
    }


def test_create_snapshot_rejects_empty_reason_with_validation_error(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": ""},
    )

    assert snapshot_response.status_code == 422


def test_create_snapshot_returns_conflict_for_reauth_required_connection(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.connections[connection_id].status = RepositoryConnectionStatus.REAUTH_REQUIRED

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 409
    assert snapshot_response.json() == {
        "code": "CONNECTION_AUTH_FAILED",
        "message": "재인증이 필요한 연결은 새 스냅샷을 시작할 수 없습니다.",
    }


def test_create_snapshot_returns_conflict_for_ref_missing_connection(
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
    connection_id = uuid.UUID(create_response.json()["id"])
    store.connections[connection_id].status = RepositoryConnectionStatus.REF_MISSING

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 409
    assert snapshot_response.json() == {
        "code": "DEFAULT_REF_NOT_FOUND",
        "message": "기본 ref가 유효하지 않아 새 스냅샷을 시작할 수 없습니다.",
    }
