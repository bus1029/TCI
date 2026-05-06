from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

from tci.infrastructure.persistence.models import RepositoryConnectionStatus
from tests.support.repository_connection_testkit import (
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
    seed_rotated_webhook_secret_with_grace,
    serialize_github_webhook_payload,
)


def test_reauth_required_connection_preserves_operator_guidance(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.connections[connection_id].status = RepositoryConnectionStatus.REAUTH_REQUIRED

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )
    detail_response = client.get(
        f"/connections/{connection_id}?workspaceId={workspace_id}"
    )

    assert snapshot_response.status_code == 409
    assert snapshot_response.json() == {
        "code": "CONNECTION_AUTH_FAILED",
        "message": "재인증이 필요한 연결은 새 스냅샷을 시작할 수 없습니다.",
    }
    assert detail_response.status_code == 200
    assert "상태: reauth_required" in detail_response.text
    assert "이 연결은 기본 ref 1개만 지원합니다." in detail_response.text
    assert "새 연결 생성" in detail_response.text
    assert "기본 ref 교체" in detail_response.text


def test_ref_missing_connection_preserves_operator_guidance(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.connections[connection_id].status = RepositoryConnectionStatus.REF_MISSING

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )
    detail_response = client.get(
        f"/connections/{connection_id}?workspaceId={workspace_id}"
    )

    assert snapshot_response.status_code == 409
    assert snapshot_response.json() == {
        "code": "DEFAULT_REF_NOT_FOUND",
        "message": "기본 ref가 유효하지 않아 새 스냅샷을 시작할 수 없습니다.",
    }
    assert detail_response.status_code == 200
    assert "상태: ref_missing" in detail_response.text
    assert "이 연결은 기본 ref 1개만 지원합니다." in detail_response.text
    assert "새 연결 생성" in detail_response.text
    assert "기본 ref 교체" in detail_response.text


def test_previous_secret_delivery_is_rejected_after_grace_expiry(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    grace_until = datetime.now(tz=UTC) - timedelta(minutes=5)
    seed_rotated_webhook_secret_with_grace(
        store,
        connection_id=connection_id,
        active_secret="current-secret",
        previous_secret="previous-secret",
        grace_until=grace_until,
    )
    payload = build_github_push_payload(after_sha="c" * 40)
    headers = build_github_webhook_headers(
        secret="previous-secret",
        payload=payload,
        delivery_id="delivery-expired-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    webhook_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    detail_response = client.get(
        f"/connections/{connection_id}?workspaceId={workspace_id}"
    )
    events_response = client.get(
        f"/connections/{connection_id}/events?workspaceId={workspace_id}"
    )

    assert webhook_response.status_code == 202
    assert webhook_response.json() == {"status": "accepted"}
    assert detail_response.status_code == 200
    assert "상태: secret_mismatch_detected" in detail_response.text
    assert "회전 상태: grace_expired" in detail_response.text
    assert grace_until.isoformat() in detail_response.text
    assert events_response.status_code == 200
    assert "delivery-expired-001" in events_response.text
    assert "rejected" in events_response.text
    assert "없음" in events_response.text


def test_bad_replay_does_not_overwrite_last_processed_event_or_health(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store, connection_id=connection_id, secret="current-secret"
    )
    store.resolved_ref_commits["main"] = "d" * 40
    payload = build_github_push_payload(after_sha="d" * 40)
    good_headers = build_github_webhook_headers(
        secret="current-secret",
        payload=payload,
        delivery_id="delivery-good-001",
        event_name="push",
    )
    good_headers["content-type"] = "application/json"

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    accepted_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=good_headers,
    )
    assert accepted_response.status_code == 202

    bad_headers = dict(good_headers)
    bad_headers["X-Hub-Signature-256"] = "sha256=" + ("0" * 64)

    replay_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=bad_headers,
    )
    detail_response = client.get(
        f"/connections/{connection_id}?workspaceId={workspace_id}"
    )
    events_response = client.get(
        f"/connections/{connection_id}/events?workspaceId={workspace_id}"
    )

    assert replay_response.status_code == 202
    assert detail_response.status_code == 200
    assert "상태: healthy" in detail_response.text
    assert "이벤트 유형: push" in detail_response.text
    assert "처리 결정: queued" in detail_response.text
    assert "회전 상태: not_rotating" in detail_response.text
    assert events_response.status_code == 200
    assert "delivery-good-001" in events_response.text
    assert "queued" in events_response.text
    assert "secret_mismatch" not in events_response.text
