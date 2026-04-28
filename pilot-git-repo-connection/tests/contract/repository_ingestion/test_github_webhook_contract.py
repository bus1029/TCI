from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

from tci.api.routes import github_webhooks
from tci.infrastructure.persistence.models import RefType, SyncRunStatus, WebhookHealthState
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


def test_receive_github_webhook_accepts_verified_push_and_returns_accepted_payload(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    store.resolved_ref_commits["main"] = "b" * 40
    payload = build_github_push_payload(after_sha="b" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"
    captured: dict[str, object] = {}

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["deliveryId"] == "delivery-001"
    assert uuid.UUID(response.json()["eventId"])
    assert captured["name"] == "tci.repository_ingestion.run_webhook_sync"


def test_github_pull_requests_with_same_source_branch_use_distinct_sync_keys(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    captured: list[dict[str, str]] = []
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: captured.append(kwargs)
        ),
    )

    first_payload = build_github_pull_request_payload(
        number=101,
        head_ref="feature/shared",
        head_sha="1" * 40,
    )
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="github-pr-shared-branch-101",
        event_name="pull_request",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["feature/shared"] = "1" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    second_payload = build_github_pull_request_payload(
        number=102,
        head_ref="feature/shared",
        head_sha="2" * 40,
    )
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="github-pr-shared-branch-102",
        event_name="pull_request",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["feature/shared"] = "2" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 2
    assert len(captured) == 2
    assert {
        store.sync_runs[event.sync_run_id].requested_ref_key
        for event in store.repository_events.values()
        if event.sync_run_id is not None
    } == {"pr:101", "pr:102"}


def test_github_webhook_retries_same_delivery_after_enqueue_503(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    store.resolved_ref_commits["main"] = "e" * 40
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    sent_tasks: list[dict[str, str]] = []

    def flaky_send_task(name: str, kwargs: dict[str, str]) -> None:
        sent_tasks.append({"name": name, **kwargs})
        if len(sent_tasks) == 1:
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=flaky_send_task),
    )
    payload = build_github_push_payload(after_sha="e" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-queue-retry",
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
    assert len(sent_tasks) == 2
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "github-queue-retry"
    )
    assert [task["event_id"] for task in sent_tasks] == [str(event.id), str(event.id)]
    assert event.processing_decision == "queued"
    assert event.processing_status == "queued"
    assert event.sync_run_id is not None
    assert len(store.sync_runs) == 1
    sync_run = store.sync_runs[event.sync_run_id]
    assert sync_run.status.value == "pending"
    assert sync_run.dispatch_enqueued_at is not None


def test_receive_github_webhook_coalesces_distinct_delivery_when_ref_sync_active(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    captured: list[dict[str, str]] = []

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured.append(kwargs)

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    first_payload = build_github_push_payload(after_sha="1" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-active-coalesce-1",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "1" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )

    second_payload = build_github_push_payload(after_sha="2" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-active-coalesce-2",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "2" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 1
    assert len(captured) == 1
    first_event = store.repository_events[uuid.UUID(first_response.json()["eventId"])]
    second_event = store.repository_events[uuid.UUID(second_response.json()["eventId"])]
    assert first_event.sync_run_id is not None
    assert second_event.sync_run_id == first_event.sync_run_id
    assert second_event.processing_decision == "duplicate_head"
    assert second_event.processing_status == "completed"
    assert store.event_cursors[(uuid.UUID(connection_id), "default_ref")].latest_event_id == first_event.id


def test_receive_github_webhook_recovers_unmarked_active_dispatch(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    captured: list[dict[str, str]] = []

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured.append(kwargs)

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    first_payload = build_github_push_payload(after_sha="3" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-active-recover-1",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "3" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].dispatch_enqueued_at = None

    second_payload = build_github_push_payload(after_sha="4" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-active-recover-2",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "4" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 1
    assert len(captured) == 2
    assert captured[1]["event_id"] == str(first_event_id)
    assert captured[1]["sync_run_id"] == str(first_sync_run_id)


def test_receive_github_webhook_redelivers_stale_pending_dispatch_without_clearing_marker(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    captured: list[dict[str, str]] = []

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured.append(kwargs)

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    first_payload = build_github_push_payload(after_sha="3" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-active-stale-dispatch-1",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "3" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    stale_marker = datetime.now(tz=UTC) - timedelta(minutes=16)
    store.sync_runs[first_sync_run_id].dispatch_enqueued_at = stale_marker

    second_payload = build_github_push_payload(after_sha="4" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-active-stale-dispatch-2",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "4" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 1
    assert len(captured) == 2
    assert captured[1]["event_id"] == str(first_event_id)
    assert captured[1]["sync_run_id"] == str(first_sync_run_id)
    assert store.sync_runs[first_sync_run_id].dispatch_enqueued_at != stale_marker


def test_receive_github_webhook_queues_followup_when_ref_sync_already_running(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    captured: list[dict[str, str]] = []

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured.append(kwargs)

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    first_payload = build_github_push_payload(after_sha="5" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-running-followup-1",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "5" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event = store.repository_events[uuid.UUID(first_response.json()["eventId"])]
    first_sync_run_id = first_event.sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.RUNNING

    second_payload = build_github_push_payload(after_sha="6" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-running-followup-2",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "6" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 2
    assert len(captured) == 1
    second_event = store.repository_events[uuid.UUID(second_response.json()["eventId"])]
    second_sync_run_id = second_event.sync_run_id
    assert second_sync_run_id is not None
    assert second_sync_run_id != first_sync_run_id
    assert second_event.processing_decision == "queued"
    assert second_event.processing_status == "validated"
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.BLOCKED

    third_payload = build_github_push_payload(after_sha="7" * 40)
    third_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=third_payload,
        delivery_id="delivery-running-followup-3",
        event_name="push",
    )
    third_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "7" * 40
    third_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(third_payload),
        headers=third_headers,
    )

    third_event = store.repository_events[uuid.UUID(third_response.json()["eventId"])]
    assert third_response.status_code == 202
    assert third_event.sync_run_id == second_sync_run_id
    assert third_event.processing_decision == "queued"
    assert third_event.processing_status == "validated"
    assert second_event.processing_decision == "duplicate_head"
    assert second_event.processing_status == "completed"
    assert store.sync_runs[second_sync_run_id].trigger_event_id == third_event.id


def test_receive_github_webhook_accepts_non_default_tag_push_as_record_only(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    payload = build_github_push_payload(after_sha="3" * 40)
    payload["ref"] = "refs/tags/v1.0.0"
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-tag-record-only",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = store.repository_events[uuid.UUID(response.json()["eventId"])]
    assert event.target_ref_name == "v1.0.0"
    assert event.processing_decision == "record_only"
    assert event.processing_status == "completed"
    assert store.sync_runs == {}


def test_receive_github_webhook_queues_default_tag_push(tmp_path, monkeypatch) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            default_ref_name="v1.0.0",
        )
        | {"defaultRefType": "tag"},
    )
    connection_id = create_response.json()["id"]
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    captured: list[dict[str, str]] = []
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: captured.append(kwargs)),
    )
    payload = build_github_push_payload(ref_name="v1.0.0", after_sha="3" * 40)
    payload["ref"] = "refs/tags/v1.0.0"
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-tag-queued",
        event_name="push",
    )
    headers["content-type"] = "application/json"
    store.resolved_ref_commits["v1.0.0"] = "3" * 40

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    event = store.repository_events[uuid.UUID(response.json()["eventId"])]
    assert response.status_code == 202
    assert event.target_ref_name == "v1.0.0"
    assert event.processing_decision == "queued"
    assert event.processing_status == "queued"
    assert event.sync_run_id is not None
    assert store.sync_runs[event.sync_run_id].requested_ref_type.value == "tag"
    assert captured == [
        {
            "connection_id": connection_id,
            "event_id": str(event.id),
            "sync_run_id": str(event.sync_run_id),
        }
    ]


def test_receive_github_webhook_treats_concurrent_duplicate_insert_as_idempotent(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    store.resolved_ref_commits["main"] = "b" * 40
    store.event_create_conflict_delivery_ids.add("github-concurrent-duplicate")
    captured: list[dict[str, str]] = []
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: captured.append(kwargs)
        ),
    )
    payload = build_github_push_payload(after_sha="b" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-concurrent-duplicate",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json()["deliveryId"] == "github-concurrent-duplicate"
    assert store.sync_runs == {}
    assert captured == []


def test_receive_github_webhook_rejects_oversized_non_object_and_long_delivery(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    payload = build_github_push_payload()
    long_delivery_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="d" * 256,
        event_name="push",
    )
    long_delivery_headers["content-type"] = "application/json"
    non_object_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-non-object",
        event_name="push",
    )
    non_object_headers["content-type"] = "application/json"

    long_delivery_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=long_delivery_headers,
    )
    non_object_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=b"[]",
        headers=non_object_headers,
    )
    oversized_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=b"{" + (b" " * (1024 * 1024 + 1)),
        headers=non_object_headers,
    )

    assert long_delivery_response.status_code == 202
    assert non_object_response.status_code == 202
    assert oversized_response.status_code == 202
    assert store.repository_events == {}


def test_receive_github_webhook_rejects_malformed_json_payloads(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    payload = build_github_push_payload()
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-malformed-json",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    invalid_utf8_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=b"\xff",
        headers=headers,
    )
    malformed_json_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=b"{",
        headers={**headers, "X-GitHub-Delivery": "github-malformed-json-2"},
    )
    oversized_header_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=b"{}",
        headers={
            **headers,
            "X-GitHub-Delivery": "github-malformed-json-3",
            "content-length": str(1024 * 1024 + 1),
        },
    )

    assert invalid_utf8_response.status_code == 202
    assert malformed_json_response.status_code == 202
    assert oversized_header_response.status_code == 202
    assert store.repository_events == {}


def test_receive_github_webhook_rate_limits_per_connection_bucket(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    monkeypatch.setattr(github_webhooks, "GITHUB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 1)
    github_webhooks._github_webhook_connection_request_times.clear()
    payload = build_github_push_payload(after_sha="4" * 40)
    store.resolved_ref_commits["main"] = "4" * 40

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-rate-limited-1",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-rate-limited-2",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=first_headers,
    )
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json() == {"status": "accepted"}
    assert {
        event.provider_delivery_id for event in store.repository_events.values()
    } == {"github-rate-limited-1"}


def test_receive_github_webhook_rate_limit_uses_trusted_forwarded_client(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    monkeypatch.setattr(github_webhooks, "GITHUB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 1)
    github_webhooks._github_webhook_connection_request_times.clear()
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    payload = build_github_push_payload(after_sha="4" * 40)
    store.resolved_ref_commits["main"] = "4" * 40

    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-forwarded-rate-1",
        event_name="push",
    )
    first_headers.update(
        {"content-type": "application/json", "X-Forwarded-For": "203.0.113.10"}
    )
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-forwarded-rate-2",
        event_name="push",
    )
    second_headers.update(
        {"content-type": "application/json", "X-Forwarded-For": "203.0.113.11"}
    )

    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=first_headers,
    )
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202


def test_github_webhook_rate_limit_does_not_evict_active_limited_bucket(
    monkeypatch,
) -> None:
    source_key = "203.0.113.30"
    active_connection_id = uuid.uuid4()
    other_connection_id = uuid.uuid4()
    overflow_connection_id = uuid.uuid4()
    monkeypatch.setattr(github_webhooks, "GITHUB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(
        github_webhooks,
        "GITHUB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS",
        2,
    )
    github_webhooks._github_webhook_source_request_times.clear()
    github_webhooks._github_webhook_connection_request_times.clear()

    assert github_webhooks._allow_github_webhook_request(
        connection_id=active_connection_id,
        source_key=source_key,
        now_monotonic=1.0,
    )
    assert not github_webhooks._allow_github_webhook_request(
        connection_id=active_connection_id,
        source_key=source_key,
        now_monotonic=2.0,
    )
    assert github_webhooks._allow_github_webhook_request(
        connection_id=other_connection_id,
        source_key=source_key,
        now_monotonic=3.0,
    )

    assert not github_webhooks._allow_github_webhook_request(
        connection_id=overflow_connection_id,
        source_key=source_key,
        now_monotonic=4.0,
    )
    assert not github_webhooks._allow_github_webhook_request(
        connection_id=active_connection_id,
        source_key=source_key,
        now_monotonic=5.0,
    )


def test_github_webhook_rate_limit_allows_distinct_connections_from_same_source() -> None:
    source_key = "203.0.113.31"
    github_webhooks._github_webhook_source_request_times.clear()
    github_webhooks._github_webhook_connection_request_times.clear()

    assert github_webhooks._allow_github_webhook_request(
        connection_id=uuid.uuid4(),
        source_key=source_key,
        now_monotonic=1.0,
    )
    assert github_webhooks._allow_github_webhook_request(
        connection_id=uuid.uuid4(),
        source_key=source_key,
        now_monotonic=2.0,
    )
    assert github_webhooks._allow_github_webhook_request(
        connection_id=uuid.uuid4(),
        source_key=source_key,
        now_monotonic=3.0,
    )


def test_github_webhook_rate_limit_uses_redis_branch(monkeypatch) -> None:
    connection_id = uuid.uuid4()
    overflow_connection_id = uuid.uuid4()
    calls: list[tuple[str, object]] = []
    result_sets: list[list[object]] = [
        [0, 1, 1, True, 0, 1, 1, True, 0, 1, 1, True],
        [
            0,
            1,
            github_webhooks.GITHUB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS + 1,
            True,
            0,
            1,
            True,
            1,
            True,
            0,
            1,
            True,
        ],
        [
            0,
            1,
            1,
            True,
            0,
            1,
            github_webhooks.GITHUB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS + 1,
            True,
            0,
            1,
            1,
            True,
        ],
    ]
    results = iter(result_sets)

    class FakePipeline:
        def __init__(self, result: list[object]) -> None:
            self._result = result

        def zremrangebyscore(self, key: str, minimum: int, maximum: int):
            calls.append(("zremrangebyscore", key))
            return self

        def zadd(self, key: str, values: dict[str, int]):
            calls.append(("zadd", key))
            return self

        def zcard(self, key: str):
            calls.append(("zcard", key))
            return self

        def expire(self, key: str, window: int):
            calls.append(("expire", window))
            return self

        def execute(self) -> list[object]:
            return self._result

    class FakeRedis:
        def pipeline(self) -> FakePipeline:
            return FakePipeline(next(results))

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())

    assert github_webhooks._allow_github_webhook_request(
        connection_id=connection_id,
        source_key="203.0.113.32",
        redis_url="redis://prod",
    )
    assert not github_webhooks._allow_github_webhook_request(
        connection_id=connection_id,
        source_key="203.0.113.32",
        redis_url="redis://prod",
    )
    assert not github_webhooks._allow_github_webhook_request(
        connection_id=overflow_connection_id,
        source_key="203.0.113.32",
        redis_url="redis://prod",
    )
    assert ("zcard", "tci:github-webhook-rate:source:203.0.113.32") in calls
    assert (
        "zcard",
        "tci:github-webhook-rate:source-connections:203.0.113.32",
    ) in calls
    assert (
        "zcard",
        f"tci:github-webhook-rate:connection:203.0.113.32:{connection_id}",
    ) in calls
    assert ("expire", int(github_webhooks.GITHUB_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS)) in calls


def test_receive_github_webhook_rate_limit_short_circuits_before_body_read(
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
    payload = build_github_push_payload(after_sha="d" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-rate-before-body",
        event_name="push",
    )
    headers["content-type"] = "application/json"
    github_webhooks._github_webhook_source_request_times.clear()
    github_webhooks._github_webhook_connection_request_times.clear()
    monkeypatch.setattr(github_webhooks, "GITHUB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 0)

    async def fail_if_body_is_read(request):
        raise AssertionError("rate-limited GitHub webhook read the request body")

    monkeypatch.setattr(github_webhooks, "_read_limited_body", fail_if_body_is_read)

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.repository_events == {}


def test_receive_github_webhook_production_redis_rate_limit_short_circuits_before_body_read(
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
    payload = build_github_push_payload(after_sha="d" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-redis-rate-before-body",
        event_name="push",
    )
    headers["content-type"] = "application/json"
    object.__setattr__(client.app.state.settings, "environment", "production")
    object.__setattr__(client.app.state.settings, "redis_url", "redis://prod")

    class FakePipeline:
        def zremrangebyscore(self, key: str, minimum: int, maximum: int):
            return self

        def zadd(self, key: str, values: dict[str, int]):
            return self

        def zcard(self, key: str):
            return self

        def expire(self, key: str, window: int):
            return self

        def execute(self) -> list[object]:
            return [
                0,
                1,
                github_webhooks.GITHUB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS + 1,
                True,
                0,
                1,
                1,
                True,
                0,
                1,
                1,
                True,
            ]

    class FakeRedis:
        def pipeline(self) -> FakePipeline:
            return FakePipeline()

    async def fail_if_body_is_read(request):
        raise AssertionError("rate-limited GitHub webhook read the request body")

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())
    monkeypatch.setattr(github_webhooks, "_read_limited_body", fail_if_body_is_read)

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.repository_events == {}


def test_github_webhook_redis_rate_limit_uses_sliding_window(monkeypatch) -> None:
    connection_id = uuid.uuid4()
    values_by_key: dict[str, dict[str, int]] = {}
    current_time = {"value": 0.0}

    class FakePipeline:
        def __init__(self) -> None:
            self.ops: list[tuple[str, tuple[object, ...]]] = []

        def zremrangebyscore(self, key: str, minimum: int, maximum: int):
            self.ops.append(("zremrangebyscore", (key, minimum, maximum)))
            return self

        def zadd(self, key: str, values: dict[str, int]):
            self.ops.append(("zadd", (key, values)))
            return self

        def zcard(self, key: str):
            self.ops.append(("zcard", (key,)))
            return self

        def expire(self, key: str, window: int):
            self.ops.append(("expire", (key, window)))
            return self

        def execute(self) -> list[object]:
            results: list[object] = []
            for op_name, args in self.ops:
                key = str(args[0])
                bucket = values_by_key.setdefault(key, {})
                if op_name == "zremrangebyscore":
                    maximum = int(args[2])
                    for member, score in list(bucket.items()):
                        if score <= maximum:
                            bucket.pop(member)
                    results.append(0)
                elif op_name == "zadd":
                    bucket.update(args[1])
                    results.append(1)
                elif op_name == "zcard":
                    results.append(len(bucket))
                elif op_name == "expire":
                    results.append(True)
            return results

    class FakeRedis:
        def pipeline(self) -> FakePipeline:
            return FakePipeline()

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())
    monkeypatch.setattr(github_webhooks.time, "time", lambda: current_time["value"])
    monkeypatch.setattr(github_webhooks, "GITHUB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 60)

    for second in range(120):
        current_time["value"] = float(second)
        assert github_webhooks._allow_github_webhook_request(
            connection_id=connection_id,
            source_key="203.0.113.32",
            redis_url="redis://prod",
        )


def test_receive_github_webhook_recovers_when_pending_insert_races_to_running(
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
    seed_active_webhook_secret(
        store, connection_id=connection_id, secret="webhook-secret"
    )
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    store.resolved_ref_commits["main"] = "4" * 40
    store.sync_run_create_conflict_refs.add((connection_id, RefType.BRANCH, "main"))
    store.sync_run_create_conflict_status = SyncRunStatus.RUNNING
    payload = build_github_push_payload(after_sha="4" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="github-running-race",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = store.repository_events[uuid.UUID(response.json()["eventId"])]
    assert event.processing_decision == "duplicate_head"
    assert event.processing_status == "completed"
    assert event.sync_run_id is not None
    assert store.sync_runs[event.sync_run_id].status is SyncRunStatus.RUNNING


def test_receive_github_webhook_rejects_when_secret_is_missing(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    payload = build_github_push_payload()
    headers = build_github_webhook_headers(
        secret="missing-secret",
        payload=payload,
        delivery_id="delivery-002",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    event = next(iter(store.repository_events.values()))
    connection = store.connections[uuid.UUID(connection_id)]
    assert event.provider_delivery_id == "delivery-002"
    assert event.signature_status == "secret_missing"
    assert event.rejection_reason == "secret_missing"
    assert event.processing_decision == "rejected"
    assert event.processing_status == "rejected"
    assert event.sync_run_id is None
    assert connection.webhook_health_state is WebhookHealthState.MISSING_SECRET
    assert connection.last_webhook_rejection_reason == "secret_missing"
    assert store.sync_runs == {}


def test_receive_github_webhook_distinguishes_secret_mismatch_from_signature_invalid(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-secret",
    )
    payload = build_github_push_payload(after_sha="c" * 40)
    mismatch_headers = build_github_webhook_headers(
        secret="wrong-secret",
        payload=payload,
        delivery_id="delivery-003",
        event_name="push",
    )
    mismatch_headers["content-type"] = "application/json"

    mismatch_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=mismatch_headers,
    )

    invalid_headers = dict(mismatch_headers)
    invalid_headers["X-GitHub-Delivery"] = "delivery-004"
    invalid_headers["X-Hub-Signature-256"] = "sha256=not-a-valid-hex"
    invalid_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=invalid_headers,
    )

    assert mismatch_response.status_code == 202
    assert mismatch_response.json() == {"status": "accepted"}
    assert invalid_response.status_code == 202
    assert invalid_response.json() == {"status": "accepted"}
    mismatch_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "delivery-003"
    )
    invalid_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "delivery-004"
    )
    connection = store.connections[uuid.UUID(connection_id)]
    assert mismatch_event.signature_status == "secret_mismatch"
    assert mismatch_event.rejection_reason == "secret_mismatch"
    assert mismatch_event.processing_status == "rejected"
    assert invalid_event.signature_status == "signature_invalid"
    assert invalid_event.rejection_reason == "signature_invalid"
    assert invalid_event.processing_status == "rejected"
    assert mismatch_event.sync_run_id is None
    assert invalid_event.sync_run_id is None
    assert connection.webhook_health_state is WebhookHealthState.SIGNATURE_INVALID_RECENTLY
    assert connection.last_webhook_rejection_reason == "signature_invalid"
    assert store.sync_runs == {}


def test_receive_github_webhook_rejects_repository_mismatch(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-secret",
    )
    payload = build_github_push_payload(
        after_sha="e" * 40,
        repository_full_name="evil-org/other-repo",
    )
    headers = build_github_webhook_headers(
        secret="actual-secret",
        payload=payload,
        delivery_id="delivery-004a",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    connection = store.connections[uuid.UUID(connection_id)]
    assert store.repository_events == {}
    assert store.sync_runs == {}
    assert connection.webhook_health_state is WebhookHealthState.HEALTHY
    assert connection.last_webhook_rejection_reason is None


def test_receive_github_webhook_rejects_invalid_ref_without_audit_event(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-secret",
    )
    payload = build_github_push_payload(after_sha="e" * 40)
    payload["ref"] = "refs/notes/main"
    headers = build_github_webhook_headers(
        secret="actual-secret",
        payload=payload,
        delivery_id="delivery-invalid-ref",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.repository_events == {}


def test_receive_github_webhook_handles_rejected_redelivery_idempotently(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-secret",
    )
    payload = build_github_push_payload(after_sha="f" * 40)
    headers = build_github_webhook_headers(
        secret="wrong-secret",
        payload=payload,
        delivery_id="delivery-004b",
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

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json() == {"status": "accepted"}


def test_receive_github_webhook_bad_replay_preserves_existing_verified_secret_audit_fields(
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
    connection_uuid = uuid.UUID(connection_id)
    seed_active_webhook_secret(
        store,
        connection_id=connection_uuid,
        secret="actual-secret",
    )
    store.resolved_ref_commits["main"] = "1" * 40
    payload = build_github_push_payload(after_sha="1" * 40)
    accepted_headers = build_github_webhook_headers(
        secret="actual-secret",
        payload=payload,
        delivery_id="delivery-replayed-invalid",
        event_name="push",
    )
    accepted_headers["content-type"] = "application/json"

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    accepted_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=accepted_headers,
    )
    assert accepted_response.status_code == 202

    rejected_headers = build_github_webhook_headers(
        secret="wrong-secret",
        payload=payload,
        delivery_id="delivery-replayed-invalid",
        event_name="push",
    )
    rejected_headers["content-type"] = "application/json"

    rejected_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=rejected_headers,
    )

    assert rejected_response.status_code == 202
    recorded_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "delivery-replayed-invalid"
    )
    assert recorded_event.signature_status == "verified"
    assert recorded_event.processing_status == "queued"
    assert recorded_event.processing_decision == "queued"
    assert recorded_event.verified_secret_revision_id is not None
    assert recorded_event.verified_secret_revision_status == "active"
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == "healthy"


def test_receive_github_webhook_corrected_redelivery_recovers_rejected_delivery(
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
    connection_uuid = uuid.UUID(connection_id)
    seed_active_webhook_secret(
        store,
        connection_id=connection_uuid,
        secret="actual-secret",
    )
    store.resolved_ref_commits["main"] = "2" * 40
    payload = build_github_push_payload(after_sha="2" * 40)

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    rejected_headers = build_github_webhook_headers(
        secret="wrong-secret",
        payload=payload,
        delivery_id="delivery-corrected-redelivery",
        event_name="push",
    )
    rejected_headers["content-type"] = "application/json"
    rejected_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=rejected_headers,
    )
    assert rejected_response.status_code == 202

    accepted_headers = build_github_webhook_headers(
        secret="actual-secret",
        payload=payload,
        delivery_id="delivery-corrected-redelivery",
        event_name="push",
    )
    accepted_headers["content-type"] = "application/json"
    accepted_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=accepted_headers,
    )

    assert accepted_response.status_code == 202
    recorded_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "delivery-corrected-redelivery"
    )
    assert recorded_event.signature_status == "verified"
    assert recorded_event.processing_status == "queued"
    assert recorded_event.processing_decision == "queued"
    assert recorded_event.verified_secret_revision_id is not None
    assert recorded_event.verified_secret_revision_status == "active"


def test_connection_detail_and_event_list_expose_webhook_health_and_last_processed_event(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="webhook-secret",
    )
    store.resolved_ref_commits["main"] = "d" * 40
    payload = build_github_push_payload(after_sha="d" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-005",
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
    event_id = webhook_response.json()["eventId"]

    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    events_response = client.get(f"/api/repository-connections/{connection_id}/events")

    assert detail_response.status_code == 200
    assert detail_response.json()["webhookHealth"] == {
        "webhookStatus": "healthy",
        "providerReachabilityStatus": "reachable",
        "lastRejectionReason": None,
        "lastRejectionAt": None,
        "rotationState": "not_rotating",
        "graceUntil": None,
        "previousSecretDeliveriesDuringGrace": 0,
        "lastPreviousSecretAcceptedAt": None,
    }
    assert detail_response.json()["lastProcessedEvent"]["id"] == event_id
    assert detail_response.json()["lastProcessedEvent"]["providerEventType"] == "push"
    assert (
        detail_response.json()["lastProcessedEvent"]["processingDecision"] == "queued"
    )
    assert detail_response.json()["traceability"]["latestEventId"] == event_id

    assert events_response.status_code == 200
    event_item = events_response.json()["items"][0]
    assert event_item["id"] == event_id
    assert event_item["providerDeliveryId"] == "delivery-005"
    assert event_item["providerEventType"] == "push"
    assert event_item["providerAction"] is None
    assert event_item["targetKey"] == "default_ref"
    assert event_item["targetHeadSha"] == "d" * 40
    assert event_item["signatureStatus"] == "verified"
    assert event_item["verifiedSecretRevisionStatus"] == "active"
    assert event_item["rejectionReason"] is None
    assert event_item["processingDecision"] == "queued"
    assert event_item["processingStatus"] == "queued"
    assert event_item["snapshotId"] is None
    assert uuid.UUID(event_item["syncRunId"])
