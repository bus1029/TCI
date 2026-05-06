from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tci.domain.services.evaluate_scope_rule_warning import (
    EvaluateScopeRuleWarningCommand,
    evaluate_scope_rule_warning,
)
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.update_default_ref import (
    UpdateDefaultRefCommand,
    update_default_ref,
)
from tci.domain.services.verify_repository_connection import (
    VerifyRepositoryConnectionCommand,
    verify_repository_connection,
)
from tci.infrastructure.persistence.models import (
    CredentialRevisionStatus,
    RepositoryConnectionStatus,
    ScopeRuleWarningState,
)
from tests.support.repository_connection_testkit import (
    build_github_pull_request_payload,
    build_github_push_payload,
    build_github_webhook_headers,
    build_gitlab_merge_request_payload,
    build_gitlab_push_payload,
    build_gitlab_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    serialize_github_webhook_payload,
    serialize_gitlab_webhook_payload,
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def _create_connection(client) -> uuid.UUID:
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


def _revoke_active_credential(store, connection_id: uuid.UUID) -> None:
    active_revision_id = store.connections[connection_id].active_credential_revision_id
    assert active_revision_id is not None
    store.credentials[active_revision_id].status = CredentialRevisionStatus.REVOKED


def _corrupt_active_credential_secret(store, connection_id: uuid.UUID) -> None:
    active_revision_id = store.connections[connection_id].active_credential_revision_id
    assert active_revision_id is not None
    store.credentials[active_revision_id].encrypted_secret = "not-a-fernet-token"


class RollbackOnExceptionSessionFactory:
    def __init__(self, *, store) -> None:
        self._store = store
        self._snapshots: list[dict[uuid.UUID, RepositoryConnectionStatus]] = []

    def __call__(self):
        return self

    def __enter__(self):
        self._snapshots.append(
            {
                connection_id: connection.status
                for connection_id, connection in self._store.connections.items()
            }
        )
        return object()

    def __exit__(self, exc_type, exc, traceback) -> None:
        snapshot = self._snapshots.pop()
        if exc_type is not None:
            for connection_id, status in snapshot.items():
                self._store.connections[connection_id].status = status
            return
        for parent_snapshot in self._snapshots:
            for connection_id, connection in self._store.connections.items():
                if connection_id in parent_snapshot:
                    parent_snapshot[connection_id] = connection.status


def _install_rollbacking_session_factory(client, store) -> None:
    object.__setattr__(
        cast(Any, client.app).state.dependencies,
        "session_factory",
        RollbackOnExceptionSessionFactory(store=store),
    )


def test_verify_uses_only_active_workspace_readonly_credential(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    _revoke_active_credential(store, connection_id)
    store.last_resolved_remote_url = None

    result = verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )

    assert result.status is RepositoryConnectionStatus.REAUTH_REQUIRED
    assert store.last_resolved_remote_url is None


def test_snapshot_collect_uses_only_active_workspace_readonly_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )
    _revoke_active_credential(store, connection_id)
    store.last_resolved_remote_url = None

    with pytest.raises(RepositoryConnectionProblem) as error_info:
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=_dependencies(client),
        )

    assert error_info.value.problem_code.value == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs[sync_run.id].status.value == "failed"
    assert store.last_resolved_remote_url is None


def test_reverify_ref_update_uses_only_active_workspace_readonly_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    _revoke_active_credential(store, connection_id)
    store.last_resolved_remote_url = None

    with pytest.raises(RepositoryConnectionProblem) as error_info:
        update_default_ref(
            UpdateDefaultRefCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                default_ref_type="branch",
                default_ref_name="release/2026.04",
            ),
            dependencies=_dependencies(client),
        )

    assert error_info.value.problem_code.value == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.last_resolved_remote_url is None


def test_scope_preview_uses_only_active_workspace_readonly_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    _revoke_active_credential(store, connection_id)
    store.last_resolved_remote_url = None

    warning_state = evaluate_scope_rule_warning(
        EvaluateScopeRuleWarningCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            include_paths=("src",),
            exclude_paths=(),
            allowed_file_types=(".py",),
            blocked_file_types=(),
            max_file_size_bytes=1024 * 1024,
            exclude_binary=True,
        ),
        dependencies=_dependencies(client),
    )

    assert warning_state is ScopeRuleWarningState.PREVIEW_FAILED
    assert store.last_resolved_remote_url is None


def test_github_event_processing_uses_only_active_workspace_readonly_credential(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="webhook-secret",
    )
    _revoke_active_credential(store, connection_id)
    _install_rollbacking_session_factory(client, store)
    store.last_resolved_remote_url = None
    store.resolved_ref_commits["main"] = "c" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_github_push_payload(after_sha="c" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="credential-boundary-github-event",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs == {}
    assert store.last_resolved_remote_url is None


def test_github_record_only_pull_request_action_skips_operation_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="webhook-secret",
    )
    _revoke_active_credential(store, connection_id)
    _install_rollbacking_session_factory(client, store)
    store.last_resolved_remote_url = None
    payload = build_github_pull_request_payload(
        action="closed",
        head_ref="feature/us3",
        head_sha="c" * 40,
    )
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-record-only-pr-action",
        event_name="pull_request",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "github-record-only-pr-action"
    )
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None
    assert store.connections[connection_id].status is RepositoryConnectionStatus.ACTIVE
    assert store.last_resolved_remote_url is None


def test_gitlab_event_processing_uses_only_active_workspace_readonly_credential(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert response.status_code == 201
    connection_id = uuid.UUID(response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    _revoke_active_credential(store, connection_id)
    _install_rollbacking_session_factory(client, store)
    store.last_resolved_remote_url = None
    store.resolved_ref_commits["main"] = "d" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_gitlab_push_payload(after_sha="d" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="credential-boundary-gitlab-event",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs == {}
    assert store.last_resolved_remote_url is None


def test_gitlab_record_only_merge_request_update_skips_operation_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert response.status_code == 201
    connection_id = uuid.UUID(response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    _revoke_active_credential(store, connection_id)
    _install_rollbacking_session_factory(client, store)
    store.last_resolved_remote_url = None
    payload = build_gitlab_merge_request_payload(
        action="update",
        source_branch="feature/us3",
        last_commit_sha="d" * 40,
    )
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-record-only-mr-update",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-record-only-mr-update"
    )
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None
    assert store.connections[connection_id].status is RepositoryConnectionStatus.ACTIVE
    assert store.last_resolved_remote_url is None


def test_event_status_lookup_returns_remediation_for_invalid_operation_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    _revoke_active_credential(store, connection_id)
    _install_rollbacking_session_factory(client, store)
    store.last_resolved_remote_url = None

    response = client.get(f"/api/repository-connections/{connection_id}/events")

    assert response.status_code == 400
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.last_resolved_remote_url is None


def test_github_event_provider_auth_failure_marks_connection_reauth_required(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="webhook-secret",
    )
    store.auth_failure_ref_names.add("main")
    store.resolved_ref_commits["main"] = "e" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_github_push_payload(after_sha="e" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="credential-boundary-github-provider-auth",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs == {}


def test_github_event_corrupted_operation_credential_fails_closed(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="webhook-secret",
    )
    _corrupt_active_credential_secret(store, connection_id)
    store.resolved_ref_commits["main"] = "5" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_github_push_payload(after_sha="5" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="credential-boundary-github-corrupted-credential",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs == {}


def test_github_duplicate_delivery_does_not_require_operation_credential(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="webhook-secret",
    )
    store.resolved_ref_commits["main"] = "f" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_github_push_payload(after_sha="f" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="credential-boundary-github-duplicate",
        event_name="push",
    )
    headers["content-type"] = "application/json"
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    assert first_response.status_code == 202
    _revoke_active_credential(store, connection_id)
    store.connections[connection_id].status = RepositoryConnectionStatus.REF_MISSING
    store.last_resolved_remote_url = None

    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert second_response.status_code == 202
    event = next(iter(store.repository_events.values()))
    assert event.processing_decision == "duplicate_delivery"
    assert store.last_resolved_remote_url is None


def test_gitlab_event_provider_auth_failure_marks_connection_reauth_required(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert response.status_code == 201
    connection_id = uuid.UUID(response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    store.auth_failure_ref_names.add("main")
    store.resolved_ref_commits["main"] = "1" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_gitlab_push_payload(after_sha="1" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="credential-boundary-gitlab-provider-auth",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs == {}


def test_gitlab_event_corrupted_operation_credential_fails_closed(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert response.status_code == 201
    connection_id = uuid.UUID(response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    _corrupt_active_credential_secret(store, connection_id)
    store.resolved_ref_commits["main"] = "6" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_gitlab_push_payload(after_sha="6" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="credential-boundary-gitlab-corrupted-credential",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs == {}


def test_gitlab_duplicate_delivery_does_not_require_operation_credential(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert response.status_code == 201
    connection_id = uuid.UUID(response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    store.resolved_ref_commits["main"] = "2" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_gitlab_push_payload(after_sha="2" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="credential-boundary-gitlab-duplicate",
    )
    headers["content-type"] = "application/json"
    first_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    assert first_response.status_code == 202
    _revoke_active_credential(store, connection_id)
    store.connections[connection_id].status = RepositoryConnectionStatus.REF_MISSING
    store.last_resolved_remote_url = None

    second_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert second_response.status_code == 202
    event = next(iter(store.repository_events.values()))
    assert event.processing_decision == "duplicate_delivery"
    assert store.last_resolved_remote_url is None


def test_github_non_active_connection_records_event_without_operation_credential(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="webhook-secret",
    )
    store.connections[connection_id].status = RepositoryConnectionStatus.REF_MISSING
    store.resolved_ref_commits["main"] = "3" * 40
    store.last_resolved_remote_url = None
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_github_push_payload(after_sha="3" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="credential-boundary-github-non-active",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = next(iter(store.repository_events.values()))
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None
    assert store.sync_runs == {}
    assert store.last_resolved_remote_url is None


def test_gitlab_non_active_connection_records_event_without_operation_credential(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert response.status_code == 201
    connection_id = uuid.UUID(response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    store.connections[connection_id].status = RepositoryConnectionStatus.REF_MISSING
    store.resolved_ref_commits["main"] = "4" * 40
    store.last_resolved_remote_url = None
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_gitlab_push_payload(after_sha="4" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="credential-boundary-gitlab-non-active",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = next(iter(store.repository_events.values()))
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None
    assert store.sync_runs == {}
    assert store.last_resolved_remote_url is None
