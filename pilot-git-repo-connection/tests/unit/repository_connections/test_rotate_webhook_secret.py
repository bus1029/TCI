from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

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


def test_rotate_webhook_secret_replaces_active_secret_and_starts_grace_window(tmp_path) -> None:
    from tci.domain.services.rotate_webhook_secret import (
        RotateWebhookSecretCommand,
        rotate_webhook_secret,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    previous_revision = seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="previous-secret",
    )
    rotated_at = datetime.now(tz=UTC)

    rotation_result = rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="current-secret",
            rotated_at=rotated_at,
        ),
        dependencies=client.app.state.dependencies,
    )

    connection = store.connections[connection_id]
    rotated_revision = store.webhook_secret_revisions[rotation_result.webhook_secret_revision_id]
    assert connection.active_webhook_secret_revision_id == rotation_result.webhook_secret_revision_id
    assert getattr(rotated_revision.status, "value", rotated_revision.status) == "active"
    assert previous_revision.status == "previous_grace"
    assert previous_revision.grace_until == rotated_at + timedelta(hours=24)
    assert rotation_result.grace_until == rotated_at + timedelta(hours=24)
    assert store.webhook_rotation_lock_calls == 1


def test_rotate_webhook_secret_returns_null_grace_until_for_first_issue(tmp_path) -> None:
    from tci.domain.services.rotate_webhook_secret import (
        RotateWebhookSecretCommand,
        rotate_webhook_secret,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])

    rotation_result = rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="first-secret",
        ),
        dependencies=client.app.state.dependencies,
    )

    assert rotation_result.grace_until is None
    assert store.webhook_rotation_lock_calls == 1


def test_rotation_projection_counts_only_current_previous_secret_revision(
    tmp_path, monkeypatch
) -> None:
    from tci.domain.services.rotate_webhook_secret import (
        RotateWebhookSecretCommand,
        build_webhook_secret_rotation_projection,
        rotate_webhook_secret,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="initial-secret",
    )
    first_rotated_at = datetime(2026, 4, 21, 9, 0, tzinfo=UTC)
    second_rotated_at = first_rotated_at + timedelta(hours=1)

    rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="current-secret-1",
            rotated_at=first_rotated_at,
        ),
        dependencies=client.app.state.dependencies,
    )
    store.resolved_ref_commits["main"] = "a" * 40
    first_payload = build_github_push_payload(after_sha="a" * 40)
    first_headers = build_github_webhook_headers(
        secret="initial-secret",
        payload=first_payload,
        delivery_id="delivery-old-grace",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    old_grace_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    assert old_grace_response.status_code == 202

    rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="current-secret-2",
            rotated_at=second_rotated_at,
        ),
        dependencies=client.app.state.dependencies,
    )

    with client.app.state.dependencies.session_factory() as session:
        projection = build_webhook_secret_rotation_projection(
            connection_id=connection_id,
            webhook_secret_repository=client.app.state.dependencies.webhook_secret_repository_factory(
                session
            ),
            event_repository=client.app.state.dependencies.repository_event_repository_factory(
                session
            ),
        )

    assert projection.grace_until == second_rotated_at + timedelta(hours=24)
    assert projection.previous_secret_deliveries_during_grace == 0
    assert projection.last_previous_secret_accepted_at is None


def test_rotation_projection_excludes_deliveries_before_revision_entered_grace(
    tmp_path, monkeypatch
) -> None:
    from tci.domain.services.rotate_webhook_secret import (
        RotateWebhookSecretCommand,
        build_webhook_secret_rotation_projection,
        rotate_webhook_secret,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="initial-secret",
    )
    grace_start = datetime(2026, 4, 21, 9, 0, tzinfo=UTC)

    store.resolved_ref_commits["main"] = "c" * 40
    payload = build_github_push_payload(after_sha="c" * 40)
    headers = build_github_webhook_headers(
        secret="initial-secret",
        payload=payload,
        delivery_id="delivery-before-grace",
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
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    assert response.status_code == 202

    accepted_event = next(iter(store.repository_events.values()))
    accepted_event.processed_at = grace_start - timedelta(minutes=1)
    accepted_event.received_at = grace_start - timedelta(minutes=1)

    rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="current-secret",
            rotated_at=grace_start,
        ),
        dependencies=client.app.state.dependencies,
    )

    with client.app.state.dependencies.session_factory() as session:
        projection = build_webhook_secret_rotation_projection(
            connection_id=connection_id,
            webhook_secret_repository=client.app.state.dependencies.webhook_secret_repository_factory(
                session
            ),
            event_repository=client.app.state.dependencies.repository_event_repository_factory(
                session
            ),
        )

    assert projection.grace_until == grace_start + timedelta(hours=24)
    assert projection.previous_secret_deliveries_during_grace == 0
    assert projection.last_previous_secret_accepted_at is None


def test_rotated_active_secret_is_accepted_by_webhook_verification(
    tmp_path, monkeypatch
) -> None:
    from tci.domain.services.rotate_webhook_secret import (
        RotateWebhookSecretCommand,
        rotate_webhook_secret,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="initial-secret",
    )

    rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="rotated-secret",
        ),
        dependencies=client.app.state.dependencies,
    )

    store.resolved_ref_commits["main"] = "b" * 40
    payload = build_github_push_payload(after_sha="b" * 40)
    headers = build_github_webhook_headers(
        secret="rotated-secret",
        payload=payload,
        delivery_id="delivery-rotated-active",
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
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202


def test_rotation_with_reused_secret_prefers_new_active_revision(
    tmp_path, monkeypatch
) -> None:
    from tci.domain.services.rotate_webhook_secret import (
        RotateWebhookSecretCommand,
        rotate_webhook_secret,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="shared-secret",
    )

    rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="shared-secret",
        ),
        dependencies=client.app.state.dependencies,
    )

    store.resolved_ref_commits["main"] = "d" * 40
    payload = build_github_push_payload(after_sha="d" * 40)
    headers = build_github_webhook_headers(
        secret="shared-secret",
        payload=payload,
        delivery_id="delivery-reused-secret",
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
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    assert response.status_code == 202
    accepted_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "delivery-reused-secret"
    )
    assert accepted_event.verified_secret_revision_status == "active"
    assert accepted_event.verified_secret_revision_id == store.connections[
        connection_id
    ].active_webhook_secret_revision_id


def test_rotation_projection_counts_legacy_previous_grace_events_without_revision_id(
    tmp_path, monkeypatch
) -> None:
    from tci.domain.services.rotate_webhook_secret import build_webhook_secret_rotation_projection

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    grace_until = datetime(2026, 4, 22, 9, 0, tzinfo=UTC)
    seed_rotated_webhook_secret_with_grace(
        store,
        connection_id=connection_id,
        active_secret="current-secret",
        previous_secret="previous-secret",
        grace_until=grace_until,
    )

    store.resolved_ref_commits["main"] = "e" * 40
    payload = build_github_push_payload(after_sha="e" * 40)
    headers = build_github_webhook_headers(
        secret="previous-secret",
        payload=payload,
        delivery_id="delivery-legacy-grace",
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
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    assert response.status_code == 202

    accepted_event = next(
        event
        for event in store.repository_events.values()
        if event.provider_delivery_id == "delivery-legacy-grace"
    )
    accepted_event.processed_at = grace_until - timedelta(hours=1)
    accepted_event.received_at = grace_until - timedelta(hours=1)
    accepted_event.verified_secret_revision_id = None

    with client.app.state.dependencies.session_factory() as session:
        projection = build_webhook_secret_rotation_projection(
            connection_id=connection_id,
            webhook_secret_repository=client.app.state.dependencies.webhook_secret_repository_factory(
                session
            ),
            event_repository=client.app.state.dependencies.repository_event_repository_factory(
                session
            ),
        )

    assert projection.previous_secret_deliveries_during_grace == 1
    assert projection.last_previous_secret_accepted_at == accepted_event.processed_at
