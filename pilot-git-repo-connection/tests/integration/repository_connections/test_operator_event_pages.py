from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

from tests.support.repository_connection_testkit import (
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
    seed_rotated_webhook_secret_with_grace,
    serialize_github_webhook_payload,
)


def test_connection_detail_page_renders_webhook_health_and_event_timeline_link(
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
        delivery_id="delivery-web-001",
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

    response = client.get(f"/connections/{connection_id}?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "Webhook 상태" in response.text
    assert "healthy" in response.text
    assert "grace_active" in response.text
    assert "grace 중 이전 secret delivery" in response.text
    assert "1" in response.text
    assert "이벤트 타임라인 보기" in response.text
    assert (
        f"/connections/{connection_id}/events?workspaceId={workspace_id}"
        in response.text
    )


def test_repository_events_page_renders_event_timeline_items(
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
    grace_until = datetime.now(tz=UTC) + timedelta(hours=24)
    seed_rotated_webhook_secret_with_grace(
        store,
        connection_id=uuid.UUID(connection_id),
        active_secret="current-secret",
        previous_secret="previous-secret",
        grace_until=grace_until,
    )
    store.resolved_ref_commits["main"] = "b" * 40
    payload = build_github_push_payload(after_sha="b" * 40)
    headers = build_github_webhook_headers(
        secret="previous-secret",
        payload=payload,
        delivery_id="delivery-web-002",
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

    response = client.get(
        f"/connections/{connection_id}/events?workspaceId={workspace_id}"
    )

    assert response.status_code == 200
    assert "이벤트 타임라인" in response.text
    assert "delivery-web-002" in response.text
    assert "push" in response.text
    assert "default_ref" in response.text
    assert "queued" in response.text
    assert "previous_grace" in response.text


def test_repository_events_page_shows_no_secret_configured_without_webhook_health(
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

    response = client.get(
        f"/connections/{connection_id}/events?workspaceId={workspace_id}"
    )

    assert response.status_code == 200
    assert "Webhook 상태: 미설정" in response.text
