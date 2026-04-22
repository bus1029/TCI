from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import uuid

import pytest

from tci.infrastructure.queue.repository_ingestion_tasks import _run_webhook_sync_task
from tests.support.repository_connection_testkit import (
    build_github_pull_request_payload,
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
    serialize_github_webhook_payload,
)


def test_push_webhook_records_commits_but_queues_single_default_ref_sync(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "b" * 40
    payload = build_github_push_payload(
        after_sha="b" * 40,
        commits=[
            {"id": "1" * 40, "message": "first commit"},
            {"id": "2" * 40, "message": "second commit"},
        ],
    )
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"
    captured: list[dict[str, str]] = []

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: captured.append(
                {"name": name, **kwargs}
            )
        ),
    )

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert len(store.sync_runs) == 1
    sync_run = next(iter(store.sync_runs.values()))
    assert sync_run.trigger_type.value == "webhook_push"
    assert sync_run.requested_ref_type.value == "branch"
    assert sync_run.requested_ref_name == "main"
    assert len(captured) == 1
    assert captured[0]["name"] == "tci.repository_ingestion.run_webhook_sync"


def test_webhook_refresh_dedupes_redelivery_without_creating_extra_sync(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "c" * 40
    payload = build_github_push_payload(after_sha="c" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-002",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    events_response = client.get(f"/api/repository-connections/{connection_id}/events")

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 1
    assert events_response.json()["items"][0]["processingDecision"] == "duplicate_delivery"
    assert events_response.json()["items"][0]["syncRunId"] is not None


def test_webhook_refresh_skips_stale_head_sha_without_creating_snapshot(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    store.resolved_ref_commits["main"] = "d" * 40
    first_payload = build_github_push_payload(after_sha="d" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-push-003",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )

    stale_payload = build_github_push_payload(after_sha="a" * 40)
    stale_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=stale_payload,
        delivery_id="delivery-push-004",
        event_name="push",
    )
    stale_headers["content-type"] = "application/json"
    stale_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(stale_payload),
        headers=stale_headers,
    )
    events_response = client.get(f"/api/repository-connections/{connection_id}/events")

    assert stale_response.status_code == 202
    assert len(store.sync_runs) == 1
    assert events_response.json()["items"][0]["processingDecision"] == "stale_head"
    assert store.snapshots == {}


def test_pull_request_webhook_uses_source_branch_for_allowed_actions_only(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["feature/us3"] = "e" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    opened_payload = build_github_pull_request_payload(
        action="opened",
        head_ref="feature/us3",
        head_sha="e" * 40,
    )
    opened_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=opened_payload,
        delivery_id="delivery-pr-001",
        event_name="pull_request",
    )
    opened_headers["content-type"] = "application/json"
    opened_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(opened_payload),
        headers=opened_headers,
    )

    closed_payload = build_github_pull_request_payload(
        action="closed",
        head_ref="feature/us3",
        head_sha="e" * 40,
    )
    closed_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=closed_payload,
        delivery_id="delivery-pr-002",
        event_name="pull_request",
    )
    closed_headers["content-type"] = "application/json"
    closed_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(closed_payload),
        headers=closed_headers,
    )
    events_response = client.get(f"/api/repository-connections/{connection_id}/events")

    assert opened_response.status_code == 202
    assert closed_response.status_code == 202
    assert len(store.sync_runs) == 1
    sync_run = next(iter(store.sync_runs.values()))
    assert sync_run.trigger_type.value == "webhook_pull_request"
    assert sync_run.requested_ref_type.value == "pull_request_branch"
    assert sync_run.requested_ref_name == "feature/us3"
    assert events_response.json()["items"][0]["processingDecision"] == "record_only"


def test_push_webhook_for_non_default_branch_is_record_only(tmp_path, monkeypatch) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_github_push_payload(
        ref_name="feature/us3",
        after_sha="f" * 40,
    )
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-005",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    events_response = client.get(f"/api/repository-connections/{connection_id}/events")

    assert response.status_code == 202
    assert store.sync_runs == {}
    assert events_response.json()["items"][0]["processingDecision"] == "record_only"
    assert events_response.json()["items"][0]["targetHeadSha"] == "f" * 40


def test_webhook_refresh_enqueues_sync_only_after_session_commit(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "1" * 40

    committed = {"done": False}
    original_session_factory = client.app.state.dependencies.session_factory

    @contextmanager
    def commit_tracking_session_factory():
        with original_session_factory() as session:
            yield session
        committed["done"] = True

    object.__setattr__(
        client.app.state.dependencies,
        "session_factory",
        commit_tracking_session_factory,
    )
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        assert committed["done"] is True
        assert name == "tci.repository_ingestion.run_webhook_sync"
        event_id = uuid.UUID(kwargs["event_id"])
        sync_run_id = uuid.UUID(kwargs["sync_run_id"])
        assert store.repository_events[event_id].sync_run_id == sync_run_id
        assert store.sync_runs[sync_run_id].requested_ref_name == "main"

    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    payload = build_github_push_payload(after_sha="1" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-006",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert committed["done"] is True


def test_issued_webhook_secret_is_accepted_for_subsequent_github_delivery(
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
    connection_id = uuid.UUID(create_response.json()["id"])
    monkeypatch.setattr(
        repository_connections_routes,
        "generate_webhook_secret",
        lambda: "issued-secret-for-webhook",
    )
    issue_response = client.post(f"/api/repository-connections/{connection_id}/webhook-secret")
    store.resolved_ref_commits["main"] = "2" * 40

    headers = build_github_webhook_headers(
        secret=issue_response.json()["webhookSecret"],
        payload=build_github_push_payload(after_sha="2" * 40),
        delivery_id="delivery-issued-secret-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(
            build_github_push_payload(after_sha="2" * 40)
        ),
        headers=headers,
    )

    assert issue_response.status_code == 201
    assert response.status_code == 202


def test_reissued_webhook_secret_rotates_active_secret_and_preserves_previous_grace(
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
    connection_id = uuid.UUID(create_response.json()["id"])
    issued = iter(["first-issued-secret", "second-issued-secret"])
    monkeypatch.setattr(
        repository_connections_routes,
        "generate_webhook_secret",
        lambda: next(issued),
    )

    first_issue_response = client.post(
        f"/api/repository-connections/{connection_id}/webhook-secret"
    )
    second_issue_response = client.post(
        f"/api/repository-connections/{connection_id}/webhook-secret"
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    first_revision_id = uuid.UUID(first_issue_response.json()["webhookSecretRevisionId"])
    second_revision_id = uuid.UUID(second_issue_response.json()["webhookSecretRevisionId"])
    first_revision = store.webhook_secret_revisions[first_revision_id]
    second_revision = store.webhook_secret_revisions[second_revision_id]

    assert first_issue_response.status_code == 201
    assert second_issue_response.status_code == 201
    assert first_issue_response.json()["webhookSecret"] == "first-issued-secret"
    assert second_issue_response.json()["webhookSecret"] == "second-issued-secret"
    assert second_issue_response.json()["graceUntil"] is not None
    assert getattr(first_revision.status, "value", first_revision.status) == "previous_grace"
    assert getattr(second_revision.status, "value", second_revision.status) == "active"
    assert detail_response.json()["webhookHealth"]["rotationState"] == "grace_active"


def test_webhook_refresh_marks_event_and_sync_run_failed_when_enqueue_fails_after_commit(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "2" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: (_ for _ in ()).throw(
                RuntimeError("queue unavailable")
            )
        ),
    )

    payload = build_github_push_payload(after_sha="2" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-007",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "웹훅 동기화 작업 큐에 연결할 수 없습니다."}
    event = next(iter(store.repository_events.values()))
    sync_run = next(iter(store.sync_runs.values()))
    assert event.processing_status == "failed"
    assert event.processing_decision == "queued"
    assert event.sync_run_id == sync_run.id
    assert sync_run.status.value == "failed"
    assert sync_run.failure_code.value == "QUEUE_DISPATCH_FAILED"
    assert sync_run.failure_message == "웹훅 동기화 작업 큐에 연결할 수 없습니다."


def test_webhook_refresh_marks_event_failed_when_queue_is_not_configured(
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
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "2" * 40

    payload = build_github_push_payload(after_sha="2" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-007-no-redis",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "웹훅 동기화 작업 큐가 설정되지 않았습니다."}
    event = next(iter(store.repository_events.values()))
    sync_run = next(iter(store.sync_runs.values()))
    assert event.processing_status == "failed"
    assert sync_run.status.value == "failed"
    assert sync_run.failure_code.value == "QUEUE_DISPATCH_FAILED"
    assert sync_run.failure_message == "웹훅 동기화 작업 큐가 설정되지 않았습니다."


def test_webhook_refresh_retries_failed_delivery_when_same_delivery_is_redelivered(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "3" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")

    first_attempt = {"count": 0}

    def flaky_send_task(name: str, kwargs: dict[str, str]) -> None:
        first_attempt["count"] += 1
        if first_attempt["count"] == 1:
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=flaky_send_task),
    )

    payload = build_github_push_payload(after_sha="3" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-008",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert first_response.status_code == 503
    assert second_response.status_code == 202
    assert len(store.repository_events) == 1
    assert len(store.sync_runs) == 2
    event = next(iter(store.repository_events.values()))
    assert event.processing_status == "queued"
    assert event.processing_decision == "queued"
    assert store.sync_runs[event.sync_run_id].status.value == "pending"


def test_webhook_refresh_replays_failed_delivery_with_current_stale_head_decision(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "6" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")

    send_attempts = {"count": 0}

    def flaky_send_task(name: str, kwargs: dict[str, str]) -> None:
        send_attempts["count"] += 1
        if send_attempts["count"] == 1:
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=flaky_send_task),
    )

    payload = build_github_push_payload(after_sha="6" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-008-stale",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    store.resolved_ref_commits["main"] = "7" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert first_response.status_code == 503
    assert second_response.status_code == 202
    assert len(store.repository_events) == 1
    assert len(store.sync_runs) == 1
    event = next(iter(store.repository_events.values()))
    assert event.processing_decision == "stale_head"
    assert event.processing_status == "completed"
    assert event.sync_run_id is None


def test_webhook_refresh_retries_same_head_after_failed_enqueue_with_new_delivery(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "4" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")

    captured: list[dict[str, str]] = []

    def flaky_then_ok_send_task(name: str, kwargs: dict[str, str]) -> None:
        if not captured:
            captured.append({"failed_delivery": kwargs["event_id"]})
            raise RuntimeError("queue unavailable")
        captured.append({"retried_delivery": kwargs["event_id"]})

    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=flaky_then_ok_send_task),
    )

    first_payload = build_github_push_payload(after_sha="4" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-push-009a",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-push-009b",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 503
    assert second_response.status_code == 202
    assert len(store.repository_events) == 2
    assert len(store.sync_runs) == 2
    latest_event = store.repository_events[uuid.UUID(second_response.json()["eventId"])]
    assert latest_event.processing_decision == "queued"
    assert latest_event.processing_status == "queued"


def test_webhook_refresh_marks_new_delivery_stale_after_failed_enqueue_when_head_advanced(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "4" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")

    captured: list[dict[str, str]] = []

    def flaky_then_ok_send_task(name: str, kwargs: dict[str, str]) -> None:
        if not captured:
            captured.append({"failed_delivery": kwargs["event_id"]})
            raise RuntimeError("queue unavailable")
        captured.append({"retried_delivery": kwargs["event_id"]})

    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=flaky_then_ok_send_task),
    )

    first_payload = build_github_push_payload(after_sha="4" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-push-009c",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-push-009d",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    store.resolved_ref_commits["main"] = "5" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 503
    assert second_response.status_code == 202
    assert len(store.repository_events) == 2
    assert len(store.sync_runs) == 1
    latest_event = store.repository_events[uuid.UUID(second_response.json()["eventId"])]
    assert latest_event.processing_decision == "stale_head"
    assert latest_event.processing_status == "completed"
    assert latest_event.sync_run_id is None


def test_webhook_refresh_retries_same_head_after_worker_failure(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    store.resolved_ref_commits["main"] = "5" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    payload = build_github_push_payload(after_sha="5" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-010a",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    event_id = uuid.UUID(first_response.json()["eventId"])
    sync_run_id = next(iter(store.sync_runs.keys()))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: client.app.state.dependencies,
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            lambda command, dependencies: (_ for _ in ()).throw(
                RuntimeError("snapshot failed")
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="snapshot failed"):
        _run_webhook_sync_task(
            connection_id=str(connection_id),
            event_id=str(event_id),
            sync_run_id=str(sync_run_id),
        )

    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-push-010b",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 2
    latest_event = store.repository_events[uuid.UUID(second_response.json()["eventId"])]
    assert latest_event.processing_decision == "queued"
    assert latest_event.processing_status == "queued"


def test_webhook_refresh_restores_previous_cursor_after_worker_failure(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=connection_id, secret="webhook-secret")
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    first_payload = build_github_push_payload(after_sha="8" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-push-011a",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "8" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )

    second_payload = build_github_push_payload(after_sha="9" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-push-011b",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "9" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    failed_event_id = uuid.UUID(second_response.json()["eventId"])
    failed_sync_run_id = store.repository_events[failed_event_id].sync_run_id
    assert failed_sync_run_id is not None

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: client.app.state.dependencies,
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            lambda command, dependencies: (_ for _ in ()).throw(
                RuntimeError("snapshot failed")
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="snapshot failed"):
        _run_webhook_sync_task(
            connection_id=str(connection_id),
            event_id=str(failed_event_id),
            sync_run_id=str(failed_sync_run_id),
        )

    store.resolved_ref_commits["main"] = "9" * 40
    replay_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-push-011c",
        event_name="push",
    )
    replay_headers["content-type"] = "application/json"
    replay_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=replay_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert replay_response.status_code == 202
    assert len(store.sync_runs) == 2
    replay_event = store.repository_events[uuid.UUID(replay_response.json()["eventId"])]
    assert replay_event.processing_decision == "duplicate_head"
    assert replay_event.processing_status == "completed"
