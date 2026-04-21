from __future__ import annotations

from types import SimpleNamespace
import uuid

from tests.support.repository_connection_testkit import (
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

    assert response.status_code == 404
    assert response.json() == {
        "code": "WEBHOOK_SECRET_MISSING",
        "message": "webhook secret이 아직 등록되지 않았습니다.",
    }


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

    assert mismatch_response.status_code == 401
    assert mismatch_response.json() == {
        "code": "WEBHOOK_SECRET_MISMATCH",
        "message": "등록된 webhook secret과 요청 서명이 일치하지 않습니다.",
    }
    assert invalid_response.status_code == 401
    assert invalid_response.json() == {
        "code": "WEBHOOK_SIGNATURE_INVALID",
        "message": "webhook 서명 검증에 실패했습니다.",
    }


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

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "webhook 저장소 정보가 연결 대상과 일치하지 않습니다.",
    }


def test_receive_github_webhook_handles_rejected_redelivery_idempotently(tmp_path) -> None:
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

    assert first_response.status_code == 401
    assert second_response.status_code == 401
    assert second_response.json() == {
        "code": "WEBHOOK_SECRET_MISMATCH",
        "message": "등록된 webhook secret과 요청 서명이 일치하지 않습니다.",
    }


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

    assert rejected_response.status_code == 401
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
    assert detail_response.json()["webhookHealth"]["status"] == "healthy"


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
    assert rejected_response.status_code == 401

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
        "status": "healthy",
        "lastRejectedReason": None,
        "lastRejectedAt": None,
        "rotationState": "not_rotating",
        "graceUntil": None,
        "previousSecretDeliveriesDuringGrace": 0,
        "lastPreviousSecretAcceptedAt": None,
    }
    assert detail_response.json()["lastProcessedEvent"]["id"] == event_id
    assert detail_response.json()["lastProcessedEvent"]["providerEventType"] == "push"
    assert detail_response.json()["lastProcessedEvent"]["processingDecision"] == "queued"
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
