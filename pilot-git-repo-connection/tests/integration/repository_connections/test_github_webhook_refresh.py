from __future__ import annotations

from types import SimpleNamespace
import uuid

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
