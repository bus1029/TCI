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
    client, _ = create_test_client(
        tmp_path=tmp_path,
        workspace_id=workspace_id,
        base_url="https://testserver",
    )

    response = client.get(f"/connections?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "등록된 저장소 연결이 없습니다." in response.text
    assert 'action="/connections' in response.text
    assert 'name="remoteUrl"' in response.text


def test_operator_session_bootstraps_browser_cookie_for_operator_pages(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(
        tmp_path=tmp_path,
        workspace_id=workspace_id,
        base_url="https://testserver",
    )
    client.headers.pop("X-TCI-Operator-Token")

    unauthenticated = client.get(f"/connections?workspaceId={workspace_id}")
    login_response = client.post(
        "/operator/session",
        data={
            "operatorToken": "test-operator-token",
            "next": f"/connections?workspaceId={workspace_id}",
        },
        follow_redirects=False,
    )
    authenticated = client.get(f"/connections?workspaceId={workspace_id}")

    assert unauthenticated.status_code == 401
    assert login_response.status_code == 303
    assert (
        login_response.headers["location"] == f"/connections?workspaceId={workspace_id}"
    )
    assert client.cookies.get("tci_operator_token") != "test-operator-token"
    assert authenticated.status_code == 200
    assert "httponly" in login_response.headers["set-cookie"].lower()
    assert "samesite=lax" in login_response.headers["set-cookie"].lower()
    assert "secure" in login_response.headers["set-cookie"].lower()


def test_operator_session_bootstraps_cookie_on_local_http_operator_pages(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")

    login_response = client.post(
        "/operator/session",
        data={
            "operatorToken": "test-operator-token",
            "next": f"/connections?workspaceId={workspace_id}",
        },
        follow_redirects=False,
    )
    authenticated = client.get(f"/connections?workspaceId={workspace_id}")

    assert login_response.status_code == 303
    assert client.cookies.get("tci_operator_token") != "test-operator-token"
    assert authenticated.status_code == 200
    assert "httponly" in login_response.headers["set-cookie"].lower()
    assert "samesite=lax" in login_response.headers["set-cookie"].lower()
    assert "secure" not in login_response.headers["set-cookie"].lower()
    client.cookies.clear()
    client.cookies.set("tci_operator_token", "test-operator-token")
    raw_cookie_response = client.get(f"/connections?workspaceId={workspace_id}")
    assert raw_cookie_response.status_code == 401


def test_operator_session_secures_cookie_behind_trusted_https_proxy(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    object.__setattr__(
        client.app.state.settings,
        "gitlab_webhook_trusted_proxy_hosts",
        ("testclient",),
    )

    login_response = client.post(
        "/operator/session",
        data={
            "operatorToken": "test-operator-token",
            "next": f"/connections?workspaceId={workspace_id}",
        },
        headers={"X-Forwarded-Proto": "https"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303
    assert "secure" in login_response.headers["set-cookie"].lower()


def test_operator_session_rejects_query_token_and_sanitizes_external_redirect(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")

    query_response = client.get(
        "/operator/session?operatorToken=test-operator-token",
        follow_redirects=False,
    )
    bad_token_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        follow_redirects=False,
    )
    malformed_response = client.post(
        "/operator/session",
        content=b"\xff",
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    external_next_response = client.post(
        "/operator/session",
        data={
            "operatorToken": "test-operator-token",
            "next": "https://evil.example/connections",
        },
        follow_redirects=False,
    )

    assert query_response.status_code == 405
    assert bad_token_response.status_code == 401
    assert malformed_response.status_code == 400
    assert external_next_response.status_code == 303
    assert external_next_response.headers["location"] == "/connections"


def test_operator_session_rejects_oversized_body(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")

    response = client.post(
        "/operator/session",
        content=b"x" * 9000,
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 413


def test_operator_session_rate_limit_happens_after_small_body_parse(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    from tci.api import operator_auth

    operator_auth._operator_auth_failure_times.clear()
    monkeypatch.setattr(operator_auth, "OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 0)

    response = client.post(
        "/operator/session",
        content=b"\xff",
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 400


def test_operator_session_rate_limits_failed_token_guesses(tmp_path, monkeypatch) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    from tci.api import operator_auth

    operator_auth._operator_auth_failure_times.clear()
    monkeypatch.setattr(operator_auth, "OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 1)
    object.__setattr__(
        client.app.state.settings,
        "gitlab_webhook_trusted_proxy_hosts",
        (),
    )

    first_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        follow_redirects=False,
    )
    second_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        follow_redirects=False,
    )

    assert first_response.status_code == 401
    assert second_response.status_code == 429


def test_operator_session_accepts_valid_token_after_failed_bucket_is_full(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    from tci.api import operator_auth

    operator_auth._operator_auth_failure_times.clear()
    monkeypatch.setattr(operator_auth, "OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 1)

    failed_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        follow_redirects=False,
    )
    valid_response = client.post(
        "/operator/session",
        data={"operatorToken": "test-operator-token", "next": "/connections"},
        follow_redirects=False,
    )

    assert failed_response.status_code == 401
    assert valid_response.status_code == 303


def test_operator_api_accepts_valid_token_after_failed_bucket_is_full(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    from tci.api import operator_auth

    operator_auth._operator_auth_failure_times.clear()
    monkeypatch.setattr(operator_auth, "OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 1)
    client.headers["X-TCI-Operator-Token"] = "wrong-token"
    failed_response = client.post("/api/repository-connections", json={})

    client.headers["X-TCI-Operator-Token"] = "test-operator-token"
    valid_response = client.post("/api/repository-connections", json={})

    assert failed_response.status_code == 401
    assert valid_response.status_code == 422


def test_operator_session_rate_limit_uses_trusted_forwarded_source(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    object.__setattr__(
        client.app.state.settings,
        "gitlab_webhook_trusted_proxy_hosts",
        (),
    )
    from tci.api import operator_auth

    operator_auth._operator_auth_failure_times.clear()
    monkeypatch.setattr(operator_auth, "OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 1)
    object.__setattr__(
        client.app.state.settings,
        "gitlab_webhook_trusted_proxy_hosts",
        ("testclient",),
    )

    first_source_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        headers={"X-Forwarded-For": "198.51.100.10, testclient"},
        follow_redirects=False,
    )
    second_source_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        headers={"X-Forwarded-For": "198.51.100.11, testclient"},
        follow_redirects=False,
    )
    first_source_again_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        headers={"X-Forwarded-For": "198.51.100.10, testclient"},
        follow_redirects=False,
    )

    assert first_source_response.status_code == 401
    assert second_source_response.status_code == 401
    assert first_source_again_response.status_code == 429


def test_operator_session_rate_limit_ignores_untrusted_forwarded_source(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    from tci.api import operator_auth

    operator_auth._operator_auth_failure_times.clear()
    monkeypatch.setattr(operator_auth, "OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 1)
    object.__setattr__(
        client.app.state.settings,
        "gitlab_webhook_trusted_proxy_hosts",
        (),
    )

    first_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        headers={"X-Forwarded-For": "198.51.100.10"},
        follow_redirects=False,
    )
    spoofed_source_response = client.post(
        "/operator/session",
        data={"operatorToken": "wrong-token", "next": "/connections"},
        headers={"X-Forwarded-For": "198.51.100.11"},
        follow_redirects=False,
    )

    assert first_response.status_code == 401
    assert spoofed_source_response.status_code == 429


def test_operator_session_ignores_untrusted_forwarded_proto_for_cookie_security(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    object.__setattr__(
        client.app.state.settings,
        "gitlab_webhook_trusted_proxy_hosts",
        (),
    )

    response = client.post(
        "/operator/session",
        data={
            "operatorToken": "test-operator-token",
            "next": f"/connections?workspaceId={workspace_id}",
        },
        headers={"X-Forwarded-Proto": "https"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "secure" not in response.headers["set-cookie"].lower()


def test_operator_session_without_configured_token_fails_closed(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    object.__setattr__(client.app.state.settings, "operator_api_token", None)

    response = client.post(
        "/operator/session",
        data={"operatorToken": "test-operator-token", "next": "/connections"},
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert "set-cookie" not in response.headers


def test_operator_api_rate_limits_failed_token_guesses(tmp_path, monkeypatch) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    from tci.api import operator_auth

    operator_auth._operator_auth_failure_times.clear()
    monkeypatch.setattr(operator_auth, "OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 1)
    client.headers["X-TCI-Operator-Token"] = "wrong-token"

    first_response = client.post("/api/repository-connections", json={})
    second_response = client.post("/api/repository-connections", json={})

    assert first_response.status_code == 401
    assert second_response.status_code == 429


def test_operator_api_accepts_signed_cookie_and_rejects_tampered_cookie(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    login_response = client.post(
        "/operator/session",
        data={
            "operatorToken": "test-operator-token",
            "next": "/connections",
        },
        follow_redirects=False,
    )
    cookie_response = client.post("/api/repository-connections", json={})
    client.cookies.set("tci_operator_token", "tampered")
    tampered_response = client.post("/api/repository-connections", json={})

    assert login_response.status_code == 303
    assert cookie_response.status_code == 422
    assert tampered_response.status_code == 401


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


def test_operator_form_routes_reject_oversized_bodies(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _ = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    oversized_body = b"x" * (64 * 1024 + 1)

    create_response = client.post(
        f"/connections?workspaceId={workspace_id}",
        content=oversized_body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    scope_response = client.post(
        f"/connections/{uuid.uuid4()}/scope?workspaceId={workspace_id}",
        content=oversized_body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert create_response.status_code == 413
    assert scope_response.status_code == 413
