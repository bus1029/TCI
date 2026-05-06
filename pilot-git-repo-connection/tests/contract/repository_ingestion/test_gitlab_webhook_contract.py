from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
import uuid

from tci.api.routes import gitlab_webhooks
from tci.infrastructure.persistence.models import RefType, SyncRunStatus
from tests.support.repository_connection_testkit import (
    build_gitlab_push_payload,
    build_gitlab_tag_payload,
    build_gitlab_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
    seed_rotated_webhook_secret_with_grace,
    serialize_gitlab_webhook_payload,
)


def test_gitlab_webhook_accepts_verified_push_and_returns_accepted_payload(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="gitlab-webhook-token",
    )
    store.resolved_ref_commits["main"] = "b" * 40
    payload = build_gitlab_push_payload(after_sha="b" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-delivery-001",
    )
    headers["content-type"] = "application/json"
    captured: dict[str, object] = {}

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["deliveryId"] == "gitlab-delivery-001"
    assert uuid.UUID(response.json()["eventId"])
    assert captured["name"] == "tci.repository_ingestion.run_webhook_sync"
    commit_event = next(
        event
        for event in store.repository_events.values()
        if event.domain_event_type == "commit_recorded"
    )
    assert commit_event.provider_delivery_id == f"gitlab-delivery-001:commit:{'b' * 40}"
    assert commit_event.target_key == f"commit:{'b' * 40}"
    assert commit_event.processing_decision == "record_only"


def test_gitlab_webhook_coalesces_distinct_delivery_when_ref_sync_active(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="gitlab-webhook-token",
    )
    captured: list[dict[str, str]] = []

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured.append(kwargs)

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    first_payload = build_gitlab_push_payload(after_sha="1" * 40)
    first_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-active-coalesce-1",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "1" * 40
    first_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(first_payload),
        headers=first_headers,
    )

    second_payload = build_gitlab_push_payload(after_sha="2" * 40)
    second_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-active-coalesce-2",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "2" * 40
    second_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(second_payload),
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
    assert (
        store.event_cursors[(uuid.UUID(connection_id), "default_ref")].latest_event_id
        == first_event.id
    )


def test_gitlab_webhook_recovers_unmarked_active_dispatch(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="gitlab-webhook-token",
    )
    captured: list[dict[str, str]] = []

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured.append(kwargs)

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    first_payload = build_gitlab_push_payload(after_sha="3" * 40)
    first_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-active-recover-1",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "3" * 40
    first_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].dispatch_enqueued_at = None

    second_payload = build_gitlab_push_payload(after_sha="4" * 40)
    second_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-active-recover-2",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "4" * 40
    second_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(second_payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(store.sync_runs) == 1
    assert len(captured) == 2
    assert captured[1]["event_id"] == str(first_event_id)
    assert captured[1]["sync_run_id"] == str(first_sync_run_id)


def test_gitlab_webhook_queues_followup_when_ref_sync_already_running(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="gitlab-webhook-token",
    )
    captured: list[dict[str, str]] = []

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured.append(kwargs)

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    first_payload = build_gitlab_push_payload(after_sha="5" * 40)
    first_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-running-followup-1",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "5" * 40
    first_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event = store.repository_events[uuid.UUID(first_response.json()["eventId"])]
    first_sync_run_id = first_event.sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.RUNNING

    second_payload = build_gitlab_push_payload(after_sha="6" * 40)
    second_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-running-followup-2",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "6" * 40
    second_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(second_payload),
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

    third_payload = build_gitlab_push_payload(after_sha="7" * 40)
    third_headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-running-followup-3",
    )
    third_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "7" * 40
    third_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(third_payload),
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


def test_gitlab_webhook_recovers_when_pending_insert_races_to_running(
    tmp_path, monkeypatch
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
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    store.resolved_ref_commits["main"] = "6" * 40
    store.sync_run_create_conflict_refs.add((connection_id, RefType.BRANCH, "main"))
    store.sync_run_create_conflict_status = SyncRunStatus.RUNNING
    payload = build_gitlab_push_payload(after_sha="6" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
        idempotency_key="gitlab-running-race",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = store.repository_events[uuid.UUID(response.json()["eventId"])]
    assert event.processing_decision == "duplicate_head"
    assert event.processing_status == "completed"
    assert event.sync_run_id is not None
    assert store.sync_runs[event.sync_run_id].status is SyncRunStatus.RUNNING


def test_gitlab_webhook_accepts_tag_hook_for_tag_default_connection(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
            default_ref_name="v1.0.0",
        )
        | {"defaultRefType": "tag"},
    )
    connection_id = create_response.json()["id"]
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="gitlab-webhook-token",
    )
    store.resolved_ref_commits["v1.0.0"] = "a" * 40
    payload = build_gitlab_tag_payload(tag_name="v1.0.0", after_sha="a" * 40)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Tag Push Hook",
        idempotency_key="gitlab-tag-001",
    )
    headers["content-type"] = "application/json"

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-tag-001"
    )
    assert event.processing_decision == "queued"
    assert event.sync_run_id is not None
    assert store.sync_runs[event.sync_run_id].requested_ref_type.value == "tag"
    assert store.sync_runs[event.sync_run_id].requested_ref_name == "v1.0.0"


def test_gitlab_webhook_treats_concurrent_duplicate_insert_as_idempotent(
    tmp_path,
    monkeypatch,
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "e" * 40
    store.event_create_conflict_delivery_ids.add("gitlab-concurrent-duplicate")
    captured: list[dict[str, str]] = []
    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: captured.append(kwargs)
        ),
    )
    payload = build_gitlab_push_payload(after_sha="e" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-concurrent-duplicate",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json()["deliveryId"] == "gitlab-concurrent-duplicate"
    assert captured == []


def test_gitlab_tag_hook_rejection_records_header_rejection_before_payload_audit(
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
            default_ref_name="v1.0.0",
        )
        | {"defaultRefType": "tag"},
    )
    connection_id = create_response.json()["id"]
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_tag_payload(tag_name="v1.0.0", after_sha="b" * 40)
    headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Tag Push Hook",
        idempotency_key="gitlab-tag-rejected",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    rejected_event = next(iter(store.repository_events.values()))
    assert rejected_event.provider_delivery_id == "gitlab-tag-rejected"
    assert rejected_event.provider_event_idempotency_source == "delivery_header"
    assert rejected_event.signature_status == "secret_mismatch"
    assert rejected_event.processing_decision == "rejected"
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "secret_mismatch_detected"
    )
    assert detail_response.json()["webhookHealth"]["lastRejectionReason"] == (
        "secret_mismatch"
    )


def test_gitlab_webhook_rejects_missing_or_invalid_token(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key="gitlab-delivery-002",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202


def test_gitlab_webhook_uuid_header_secret_mismatch_updates_health(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key=None,
        webhook_uuid="gitlab-uuid-mismatch",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert response.status_code == 202
    rejected_event = next(iter(store.repository_events.values()))
    assert rejected_event.provider_delivery_id == "gitlab-uuid-mismatch"
    assert rejected_event.provider_event_idempotency_source == "uuid_header"
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "secret_mismatch_detected"
    )
    assert detail_response.json()["webhookHealth"]["lastRejectionReason"] == (
        "secret_mismatch"
    )


def test_gitlab_webhook_rejects_when_secret_is_missing(tmp_path) -> None:
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
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="provided-token",
        event_name="Push Hook",
        idempotency_key="gitlab-missing-secret",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert response.status_code == 202
    rejected_event = next(iter(store.repository_events.values()))
    assert rejected_event.provider_delivery_id == "gitlab-missing-secret"
    assert rejected_event.provider_event_idempotency_source == "delivery_header"
    assert rejected_event.signature_status == "secret_missing"
    assert rejected_event.processing_decision == "rejected"
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == "missing_secret"
    assert detail_response.json()["webhookHealth"]["lastRejectionReason"] == (
        "secret_missing"
    )


def test_gitlab_webhook_headerless_invalid_token_rejects_before_payload_audit(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key=None,
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert response.status_code == 202
    assert store.repository_events == {}
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "secret_mismatch_detected"
    )


def test_gitlab_webhook_headerless_missing_secret_records_derived_rejection(
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
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="provided-token",
        event_name="Push Hook",
        idempotency_key=None,
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert response.status_code == 202
    assert store.repository_events == {}
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == "missing_secret"


def test_gitlab_webhook_rejects_overlong_header_delivery_id(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="d" * 256,
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert not store.repository_events


def test_gitlab_webhook_rejects_overlong_header_delivery_id_before_bad_token_preflight(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key="d" * 256,
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert store.repository_events == {}


def test_gitlab_webhook_rejects_overlong_ref_name(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(ref_name="r" * 256, after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-overlong-ref",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert not store.repository_events


def test_gitlab_webhook_accepts_long_parent_delivery_without_commit_id_overflow(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "c" * 40
    payload = build_gitlab_push_payload(after_sha="c" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="d" * 255,
    )
    headers["content-type"] = "application/json"
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    commit_event = next(
        event
        for event in store.repository_events.values()
        if event.domain_event_type == "commit_recorded"
    )
    assert len(commit_event.provider_delivery_id) <= 255
    assert commit_event.provider_delivery_id.endswith(f":commit:{'c' * 40}")


def test_gitlab_webhook_records_queue_failure_when_enqueue_raises(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "e" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: (_ for _ in ()).throw(
                RuntimeError("queue unavailable")
            )
        ),
    )
    payload = build_gitlab_push_payload(after_sha="e" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-queue-fail",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 503
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-queue-fail"
    )
    assert event.sync_run_id is not None
    sync_run = store.sync_runs[event.sync_run_id]
    assert event.processing_decision == "queued"
    assert event.processing_status == "queued"
    assert sync_run.status.value == "pending"
    assert sync_run.dispatch_enqueued_at is None
    assert sync_run.failure_code is None


def test_gitlab_webhook_records_queue_failure_when_queue_is_not_configured(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "e" * 40
    payload = build_gitlab_push_payload(after_sha="e" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-queue-unconfigured",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 503
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-queue-unconfigured"
    )
    assert event.sync_run_id is not None
    sync_run = store.sync_runs[event.sync_run_id]
    assert event.processing_status == "queued"
    assert sync_run.status.value == "pending"
    assert sync_run.dispatch_enqueued_at is None
    assert sync_run.failure_code is None


def test_gitlab_webhook_retries_same_delivery_after_enqueue_503(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "e" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    sent_tasks: list[dict[str, str]] = []

    def flaky_send_task(name: str, kwargs: dict[str, str]) -> None:
        sent_tasks.append({"name": name, **kwargs})
        if len(sent_tasks) == 1:
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=flaky_send_task),
    )
    payload = build_gitlab_push_payload(after_sha="e" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-queue-retry",
    )
    headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    second_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert first_response.status_code == 503
    assert second_response.status_code == 202
    assert len(sent_tasks) == 2
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-queue-retry"
    )
    commit_events = [
        event
        for event in store.repository_events.values()
        if event.domain_event_type == "commit_recorded"
    ]
    assert [task["event_id"] for task in sent_tasks] == [str(event.id), str(event.id)]
    assert len(commit_events) == 1
    assert event.processing_decision == "queued"
    assert event.processing_status == "queued"
    assert event.sync_run_id is not None
    assert len(store.sync_runs) == 1
    assert store.sync_runs[event.sync_run_id].status.value == "pending"


def test_gitlab_webhook_endpoint_rate_limit_short_circuits_before_processing(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "f" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(gitlab_webhooks, "GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 1)
    gitlab_webhooks._gitlab_webhook_connection_request_times.clear()
    payload = build_gitlab_push_payload(after_sha="f" * 40)
    first_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-rate-first",
    )
    first_headers["content-type"] = "application/json"
    second_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-rate-second",
    )
    second_headers["content-type"] = "application/json"

    first_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=first_headers,
    )
    second_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=second_headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json() == {"status": "accepted"}
    assert all(
        event.provider_delivery_id != "gitlab-rate-second"
        for event in store.repository_events.values()
    )


def test_gitlab_webhook_rate_limit_short_circuits_before_token_preflight(
    tmp_path, monkeypatch
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
    monkeypatch.setattr(gitlab_webhooks, "GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 0)
    gitlab_webhooks._gitlab_webhook_connection_request_times.clear()
    monkeypatch.setattr(
        gitlab_webhooks,
        "preflight_gitlab_webhook_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("preflight must not run after rate limit")
        ),
    )
    payload = build_gitlab_push_payload(after_sha="f" * 40)
    headers = build_gitlab_webhook_headers(
        token="invalid-token",
        event_name="Push Hook",
        idempotency_key="gitlab-rate-before-preflight",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.repository_events == {}


def test_gitlab_webhook_authenticated_malformed_without_delivery_updates_health(
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
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="actual-token",
    )

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=b"{",
        headers={
            "X-Gitlab-Event": "Push Hook",
            "X-Gitlab-Token": "actual-token",
            "content-type": "application/json",
        },
    )

    connection = store.connections[connection_id]
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.repository_events == {}
    assert connection.webhook_health_state.value == "signature_invalid_recently"
    assert connection.last_webhook_rejection_reason.value == "signature_invalid"


def test_gitlab_webhook_rejects_project_path_mismatch_without_sync(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(
        after_sha="f" * 40,
        project_path="other-group/other-repo",
    )
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-project-mismatch",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = next(iter(store.repository_events.values()))
    assert event.provider_delivery_id == "gitlab-project-mismatch"
    assert event.signature_status == "verified"
    assert event.processing_decision == "rejected"
    assert event.processing_status == "rejected"
    assert event.sync_run_id is None
    assert store.sync_runs == {}
    assert store.event_cursors == {}


def test_gitlab_merge_requests_with_same_source_branch_use_distinct_sync_keys(
    tmp_path, monkeypatch
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    captured: list[dict[str, str]] = []
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: captured.append(kwargs)
        ),
    )

    def merge_request_payload(iid: int, sha: str) -> dict[str, object]:
        return {
            "object_kind": "merge_request",
            "project": {"path_with_namespace": "group/sample-repo"},
            "object_attributes": {
                "iid": iid,
                "action": "open",
                "source_branch": "feature/shared",
                "last_commit": {"id": sha},
            },
        }

    first_payload = merge_request_payload(41, "1" * 40)
    first_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-mr-shared-branch-41",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["feature/shared"] = "1" * 40
    first_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(first_payload),
        headers=first_headers,
    )
    second_payload = merge_request_payload(42, "2" * 40)
    second_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-mr-shared-branch-42",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["feature/shared"] = "2" * 40
    second_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(second_payload),
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
    } == {"mr:41", "mr:42"}


def test_gitlab_webhook_rate_limit_does_not_evict_active_limited_bucket(
    monkeypatch,
) -> None:
    source_key = "203.0.113.40"
    active_connection_id = uuid.uuid4()
    other_connection_id = uuid.uuid4()
    overflow_connection_id = uuid.uuid4()
    monkeypatch.setattr(gitlab_webhooks, "GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(
        gitlab_webhooks,
        "GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS",
        2,
    )
    gitlab_webhooks._gitlab_webhook_source_request_times.clear()
    gitlab_webhooks._gitlab_webhook_connection_request_times.clear()

    assert gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=active_connection_id,
        source_key=source_key,
        now_monotonic=1.0,
    )
    assert not gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=active_connection_id,
        source_key=source_key,
        now_monotonic=2.0,
    )
    assert gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=other_connection_id,
        source_key=source_key,
        now_monotonic=3.0,
    )

    assert not gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=overflow_connection_id,
        source_key=source_key,
        now_monotonic=4.0,
    )
    assert not gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=active_connection_id,
        source_key=source_key,
        now_monotonic=5.0,
    )


def test_gitlab_webhook_rate_limit_allows_distinct_connections_from_same_source() -> (
    None
):
    source_key = "203.0.113.41"
    gitlab_webhooks._gitlab_webhook_source_request_times.clear()
    gitlab_webhooks._gitlab_webhook_connection_request_times.clear()

    assert gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=uuid.uuid4(),
        source_key=source_key,
        now_monotonic=1.0,
    )
    assert gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=uuid.uuid4(),
        source_key=source_key,
        now_monotonic=2.0,
    )
    assert gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=uuid.uuid4(),
        source_key=source_key,
        now_monotonic=3.0,
    )


def test_gitlab_webhook_rate_limit_uses_redis_branch(monkeypatch) -> None:
    connection_id = uuid.uuid4()
    overflow_connection_id = uuid.uuid4()
    calls: list[tuple[str, object]] = []
    result_sets: list[list[object]] = [
        [0, 1, 1, True, 0, 1, 1, True, 0, 1, 1, True],
        [
            0,
            1,
            gitlab_webhooks.GITLAB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS + 1,
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
            gitlab_webhooks.GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS + 1,
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

    assert gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=connection_id,
        source_key="203.0.113.42",
        redis_url="redis://prod",
    )
    assert not gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=connection_id,
        source_key="203.0.113.42",
        redis_url="redis://prod",
    )
    assert not gitlab_webhooks._allow_gitlab_webhook_request(
        connection_id=overflow_connection_id,
        source_key="203.0.113.42",
        redis_url="redis://prod",
    )
    assert ("zcard", "tci:gitlab-webhook-rate:source:203.0.113.42") in calls
    assert (
        "zcard",
        "tci:gitlab-webhook-rate:source-connections:203.0.113.42",
    ) in calls
    assert (
        "zcard",
        f"tci:gitlab-webhook-rate:connection:203.0.113.42:{connection_id}",
    ) in calls
    assert (
        "expire",
        int(gitlab_webhooks.GITLAB_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS),
    ) in calls


def test_receive_gitlab_webhook_production_redis_rate_limit_short_circuits_before_body_read(
    tmp_path, monkeypatch
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
    payload = build_gitlab_push_payload(after_sha="d" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-redis-rate-before-body",
    )
    headers["content-type"] = "application/json"
    object.__setattr__(
        cast(Any, client.app).state.settings, "environment", "production"
    )
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://prod"
    )

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
                gitlab_webhooks.GITLAB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS + 1,
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
        raise AssertionError("rate-limited GitLab webhook read the request body")

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())
    monkeypatch.setattr(gitlab_webhooks, "_read_limited_body", fail_if_body_is_read)

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.repository_events == {}


def test_gitlab_webhook_redis_rate_limit_uses_sliding_window(monkeypatch) -> None:
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
    monkeypatch.setattr(gitlab_webhooks.time, "time", lambda: current_time["value"])
    monkeypatch.setattr(gitlab_webhooks, "GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 60)

    for second in range(120):
        current_time["value"] = float(second)
        assert gitlab_webhooks._allow_gitlab_webhook_request(
            connection_id=connection_id,
            source_key="203.0.113.42",
            redis_url="redis://prod",
        )


def test_gitlab_webhook_accepts_previous_grace_token_during_rotation(
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
    connection_uuid = uuid.UUID(connection_id)
    _active_revision, _previous_revision = seed_rotated_webhook_secret_with_grace(
        store,
        connection_id=connection_uuid,
        active_secret="current-token",
        previous_secret="previous-token",
        grace_until=datetime.now(tz=UTC) + timedelta(minutes=10),
    )
    payload = build_gitlab_push_payload(after_sha="9" * 40)
    headers = build_gitlab_webhook_headers(
        token="previous-token",
        event_name="Push Hook",
        idempotency_key="gitlab-previous-grace",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    event = store.repository_events[uuid.UUID(response.json()["eventId"])]
    assert event.signature_status == "verified"
    assert event.verified_secret_revision_status == "previous_grace"


def test_gitlab_webhook_rejects_non_utf8_body_as_invalid_input(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-non-utf8",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=b"\xff",
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "signature_invalid_recently"
    )


def test_gitlab_webhook_rejects_payload_without_repository_identity(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="f" * 40)
    payload.pop("project")
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-missing-repo",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.sync_runs == {}
    rejected_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-missing-repo"
    )
    assert rejected_event.signature_status == "verified"
    assert rejected_event.processing_status == "rejected"


def test_gitlab_webhook_rejects_json_array_and_records_verified_malformed_health(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-json-array",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=b"[]",
        headers=headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "signature_invalid_recently"
    )
    assert store.repository_events == {}


def test_gitlab_webhook_rejects_merge_request_without_stable_id(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "group/sample-repo"},
        "object_attributes": {
            "action": "open",
            "source_branch": "feature/us3",
            "last_commit": {"id": "a" * 40},
        },
    }
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-mr-missing-id",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.sync_runs == {}


def test_gitlab_webhook_rejects_merge_request_with_non_numeric_id(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "group/sample-repo"},
        "object_attributes": {
            "iid": "abc",
            "action": "open",
            "source_branch": "feature/us3",
            "last_commit": {"id": "a" * 40},
        },
    }
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-mr-nonnumeric-id",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.sync_runs == {}


def test_gitlab_webhook_rejects_merge_request_with_global_id_only(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "group/sample-repo"},
        "object_attributes": {
            "id": 999,
            "action": "open",
            "source_branch": "feature/us3",
            "last_commit": {"id": "a" * 40},
        },
    }
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Merge Request Hook",
        idempotency_key="gitlab-mr-global-id-only",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert store.sync_runs == {}


def test_gitlab_webhook_rejects_oversized_payload_before_json_parse(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-too-large",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=b"{" + (b" " * (1024 * 1024 + 1)),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "signature_invalid_recently"
    )


def test_gitlab_connection_detail_exposes_webhook_health_projection(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="d" * 40)
    headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key="gitlab-delivery-003",
    )
    headers["content-type"] = "application/json"

    client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "active"
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "secret_mismatch_detected"
    )
    assert detail_response.json()["webhookHealth"]["lastRejectionReason"] == (
        "secret_mismatch"
    )


def test_gitlab_record_only_non_default_push_clears_prior_webhook_health(
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    bad_payload = build_gitlab_push_payload(after_sha="7" * 40)
    bad_headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key="gitlab-prior-mismatch",
    )
    bad_headers["content-type"] = "application/json"
    client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(bad_payload),
        headers=bad_headers,
    )
    store.resolved_ref_commits["feature/ignored"] = "8" * 40
    record_only_payload = build_gitlab_push_payload(
        ref_name="feature/ignored",
        after_sha="8" * 40,
    )
    record_only_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-feature-push",
    )
    record_only_headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(record_only_payload),
        headers=record_only_headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert response.status_code == 202
    event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-feature-push"
    )
    assert event.processing_decision == "record_only"
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == "healthy"
    assert detail_response.json()["lastProcessedEvent"]["id"] == str(event.id)


def test_gitlab_deleted_default_ref_hook_is_record_only(tmp_path) -> None:
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    payload = build_gitlab_push_payload(after_sha="0" * 40, checkout_sha="0" * 40)
    headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-delete-default-ref",
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
        if event.provider_delivery_id == "gitlab-delete-default-ref"
    )
    assert event.target_head_sha is None
    assert event.processing_decision == "record_only"
    assert event.sync_run_id is None


def test_gitlab_webhook_bad_replay_preserves_verified_audit_and_health(
    tmp_path, monkeypatch
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
    connection_uuid = uuid.UUID(connection_id)
    seed_active_webhook_secret(
        store,
        connection_id=connection_uuid,
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "1" * 40
    payload = build_gitlab_push_payload(after_sha="1" * 40)
    accepted_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-replayed-invalid",
    )
    accepted_headers["content-type"] = "application/json"

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    accepted_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=accepted_headers,
    )
    assert accepted_response.status_code == 202

    rejected_headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key="gitlab-replayed-invalid",
    )
    rejected_headers["content-type"] = "application/json"
    rejected_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=rejected_headers,
    )

    assert rejected_response.status_code == 202
    recorded_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-replayed-invalid"
    )
    assert recorded_event.signature_status == "verified"
    assert recorded_event.processing_status == "queued"
    assert recorded_event.processing_decision == "queued"
    assert recorded_event.verified_secret_revision_id is not None
    assert recorded_event.verified_secret_revision_status == "active"
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == "healthy"


def test_gitlab_webhook_derived_bad_replay_does_not_poison_health(
    tmp_path,
    monkeypatch,
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
    seed_active_webhook_secret(
        store,
        connection_id=uuid.UUID(connection_id),
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "4" * 40
    payload = build_gitlab_push_payload(after_sha="4" * 40)
    accepted_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key=None,
    )
    accepted_headers["content-type"] = "application/json"

    object.__setattr__(
        cast(Any, client.app).state.settings,
        "redis_url",
        "redis://example",
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    accepted_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=accepted_headers,
    )
    assert accepted_response.status_code == 202

    rejected_headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key=None,
    )
    rejected_headers["content-type"] = "application/json"
    rejected_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=rejected_headers,
    )

    assert rejected_response.status_code == 202
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == (
        "secret_mismatch_detected"
    )


def test_gitlab_webhook_corrected_redelivery_recovers_rejected_delivery(
    tmp_path, monkeypatch
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
    connection_uuid = uuid.UUID(connection_id)
    seed_active_webhook_secret(
        store,
        connection_id=connection_uuid,
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "2" * 40
    payload = build_gitlab_push_payload(after_sha="2" * 40)

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    rejected_headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key="gitlab-corrected-redelivery",
    )
    rejected_headers["content-type"] = "application/json"
    rejected_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=rejected_headers,
    )
    assert rejected_response.status_code == 202

    accepted_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-corrected-redelivery",
    )
    accepted_headers["content-type"] = "application/json"
    accepted_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=accepted_headers,
    )

    assert accepted_response.status_code == 202
    recorded_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-corrected-redelivery"
    )
    assert recorded_event.signature_status == "verified"
    assert recorded_event.processing_status == "queued"
    assert recorded_event.processing_decision == "queued"
    assert recorded_event.verified_secret_revision_id is not None
    assert recorded_event.verified_secret_revision_status == "active"
    assert recorded_event.rejection_reason is None


def test_gitlab_corrected_redelivery_duplicate_head_clears_prior_mismatch_health(
    tmp_path, monkeypatch
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
    connection_uuid = uuid.UUID(connection_id)
    seed_active_webhook_secret(
        store,
        connection_id=connection_uuid,
        secret="actual-token",
    )
    store.resolved_ref_commits["main"] = "3" * 40
    payload = build_gitlab_push_payload(after_sha="3" * 40)

    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    first_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-first-accepted",
    )
    first_headers["content-type"] = "application/json"
    assert (
        client.post(
            f"/api/webhooks/gitlab/{connection_id}",
            content=serialize_gitlab_webhook_payload(payload),
            headers=first_headers,
        ).status_code
        == 202
    )

    rejected_headers = build_gitlab_webhook_headers(
        token="wrong-token",
        event_name="Push Hook",
        idempotency_key="gitlab-corrected-duplicate-head",
    )
    rejected_headers["content-type"] = "application/json"
    assert (
        client.post(
            f"/api/webhooks/gitlab/{connection_id}",
            content=serialize_gitlab_webhook_payload(payload),
            headers=rejected_headers,
        ).status_code
        == 202
    )

    accepted_headers = build_gitlab_webhook_headers(
        token="actual-token",
        event_name="Push Hook",
        idempotency_key="gitlab-corrected-duplicate-head",
    )
    accepted_headers["content-type"] = "application/json"
    accepted_response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=accepted_headers,
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert accepted_response.status_code == 202
    recorded_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "gitlab-corrected-duplicate-head"
    )
    assert recorded_event.signature_status == "verified"
    assert recorded_event.processing_decision == "duplicate_head"
    assert detail_response.json()["webhookHealth"]["webhookStatus"] == "healthy"
