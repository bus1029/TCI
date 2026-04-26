from __future__ import annotations

from typing import Any, cast
import uuid

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
    seed_active_webhook_secret,
    seed_planning_input_reference,
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_connections_page_renders_empty_state_and_create_form(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    response = client.get(f"/connections?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "등록된 저장소 연결이 없습니다." in response.text
    assert 'action="/connections' in response.text
    assert 'name="remoteUrl"' in response.text


def test_connections_page_renders_existing_connection_summary(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(_, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    response = client.get(f"/connections?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "acme/sample-repo" in response.text
    assert "기본 ref: branch main" in response.text
    assert f"/connections/{connection_id}?workspaceId={workspace_id}" in response.text


def test_connections_create_route_redirects_to_detail_page(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    response = client.post(
        f"/connections?workspaceId={workspace_id}",
        data={
            "planningInputReferenceId": str(reference.id),
            "provider": "github_cloud",
            "remoteUrl": "https://github.com/acme/sample-repo.git",
            "transport": "https",
            "defaultRefType": "branch",
            "defaultRefName": "main",
            "credentialType": "https_pat",
            "credentialSecret": "readonly-token-value",
            "credentialFingerprint": "pat-01",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/connections/")
    assert f"workspaceId={workspace_id}" in location


def test_connections_page_requires_workspace_id_query_parameter(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    response = client.get("/connections")

    assert response.status_code == 400
    assert "workspaceId 쿼리 파라미터가 필요합니다." in response.text


def test_connection_detail_page_renders_summary_guidance_and_traceability(
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

    response = client.get(f"/connections/{connection_id}?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "최근 스냅샷 상태" in response.text
    assert "최근 처리 이벤트" in response.text
    assert "아직 처리된 이벤트가 없습니다." in response.text
    assert "이 연결은 기본 ref 1개만 지원합니다." in response.text
    assert str(snapshot.id) in response.text
    assert "승인된 스펙" in response.text
    assert "승인된 계획" in response.text


def test_connection_detail_page_renders_gitlab_provider_summary_without_auth_mode(
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
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-secret",
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

    response = client.get(f"/connections/{connection_id}?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "GitLab 인스턴스" in response.text
    assert "https://gitlab.example.com" in response.text
    assert "GitLab 프로젝트 경로" in response.text
    assert "group/subgroup/sample-repo" in response.text
    assert "활성 수집 규칙" in response.text
    assert str(snapshot.scope_rule_version_id) in response.text
    assert "Webhook 상태" in response.text
    assert "healthy" in response.text
    assert "shared_token" not in response.text
    assert "webhookAuthMode" not in response.text


def test_connection_detail_page_returns_404_for_unknown_connection(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    response = client.get(f"/connections/{uuid.uuid4()}?workspaceId={workspace_id}")

    assert response.status_code == 404
    assert "저장소 연결을 찾을 수 없습니다." in response.text


def test_connections_create_route_does_not_echo_secret_after_validation_error(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    response = client.post(
        f"/connections?workspaceId={workspace_id}",
        data={
            "planningInputReferenceId": str(reference.id),
            "provider": "gitlab",
            "remoteUrl": "https://github.com/acme/sample-repo.git",
            "transport": "https",
            "defaultRefType": "branch",
            "defaultRefName": "main",
            "credentialType": "https_pat",
            "credentialSecret": "top-secret-token",
            "credentialFingerprint": "pat-01",
        },
    )

    assert response.status_code == 400
    assert "top-secret-token" not in response.text
    assert 'name="remoteUrl"' in response.text
    assert 'value="https://github.com/acme/sample-repo.git"' in response.text


def test_connections_create_route_rejects_cross_origin_submission(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    response = client.post(
        f"/connections?workspaceId={workspace_id}",
        data={
            "planningInputReferenceId": str(reference.id),
            "provider": "github_cloud",
            "remoteUrl": "https://github.com/acme/sample-repo.git",
            "transport": "https",
            "defaultRefType": "branch",
            "defaultRefName": "main",
            "credentialType": "https_pat",
            "credentialSecret": "readonly-token-value",
            "credentialFingerprint": "pat-01",
        },
        headers={"origin": "https://evil.example"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert "허용되지 않은 요청 출처입니다." in response.text
