from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from tests.support.repository_connection_testkit import (
    build_gitlab_merge_request_payload,
    build_gitlab_push_payload,
    build_gitlab_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
    serialize_gitlab_webhook_payload,
)
from tci.infrastructure.persistence.models import RepositoryConnectionStatus


pytestmark = pytest.mark.integration


def _create_gitlab_connection(tmp_path, monkeypatch):
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
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    return client, store, connection_id


def test_gitlab_webhook_push_and_merge_request_flows_update_health_and_snapshots(
    tmp_path, monkeypatch
) -> None:
    client, store, connection_id = _create_gitlab_connection(tmp_path, monkeypatch)
    store.resolved_ref_commits["main"] = "b" * 40
    push_payload = build_gitlab_push_payload(after_sha="b" * 40)
    push_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-push-001",
    )
    push_headers["content-type"] = "application/json"

    push_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(push_payload),
        headers=push_headers,
    )
    duplicate_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(push_payload),
        headers=push_headers,
    )

    store.resolved_ref_commits["feature/us3"] = "c" * 40
    mr_payload = build_gitlab_merge_request_payload(
        action="open",
        source_branch="feature/us3",
        last_commit_sha="c" * 40,
    )
    mr_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-mr-001",
    )
    mr_headers["content-type"] = "application/json"
    mr_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(mr_payload),
        headers=mr_headers,
    )

    assert push_response.status_code == 202
    assert duplicate_response.status_code == 202
    assert mr_response.status_code == 202
    events = sorted(
        store.repository_events.values(), key=lambda event: event.received_at
    )
    duplicate_event = next(
        event for event in events if event.provider_delivery_id == "gitlab-push-001"
    )
    mr_event = next(
        event for event in events if event.provider_delivery_id == "gitlab-mr-001"
    )
    assert duplicate_event.processing_status == "completed"
    assert duplicate_event.processing_decision == "duplicate_delivery"
    assert store.connections[connection_id].webhook_health_state.value == "healthy"
    assert mr_event.provider_event_type == "merge_request"
    assert mr_event.target_key == "mr:42"
    assert mr_event.processing_decision == "queued"
    assert store.sync_runs[mr_event.sync_run_id].trigger_type.value == (
        "webhook_merge_request"
    )


def test_gitlab_merge_request_reviewer_only_update_is_record_only(
    tmp_path, monkeypatch
) -> None:
    client, store, connection_id = _create_gitlab_connection(tmp_path, monkeypatch)
    store.resolved_ref_commits["feature/us3"] = "d" * 40
    payload = build_gitlab_merge_request_payload(
        action="update",
        source_branch="feature/us3",
        last_commit_sha="d" * 40,
    )
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-mr-reviewer-only",
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
        if event.provider_delivery_id == "gitlab-mr-reviewer-only"
    )
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None


def test_gitlab_fork_merge_request_is_record_only_until_source_remote_supported(
    tmp_path, monkeypatch
) -> None:
    client, store, connection_id = _create_gitlab_connection(tmp_path, monkeypatch)
    store.resolved_ref_commits["feature/us3"] = "d" * 40
    payload = build_gitlab_merge_request_payload(
        action="open",
        source_branch="feature/us3",
        last_commit_sha="d" * 40,
        source_project_path="user/forked-sample-repo",
    )
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-fork-mr",
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
        if event.provider_delivery_id == "gitlab-fork-mr"
    )
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None


def test_gitlab_webhook_blocks_snapshot_when_connection_requires_action(
    tmp_path, monkeypatch
) -> None:
    client, store, connection_id = _create_gitlab_connection(tmp_path, monkeypatch)
    store.connections[connection_id].status = RepositoryConnectionStatus.REF_MISSING
    payload = build_gitlab_push_payload(after_sha="e" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-blocked-state",
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
        if event.provider_delivery_id == "gitlab-blocked-state"
    )
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None
