from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
import uuid

import pytest

from tci.infrastructure.queue.repository_ingestion_tasks import _run_webhook_sync_task
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tci.infrastructure.persistence.models import (
    RefType,
    RepositorySyncRun,
    SyncRunStatus,
    SyncTriggerType,
)
from tests.support.repository_connection_testkit import (
    TestRepositoryEvent,
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
    seed_repository_event_cursor,
    serialize_github_webhook_payload,
)


def _settings(client) -> Any:
    return cast(Any, client.app).state.settings


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_build_code_snapshot_rejects_unallowlisted_gitlab_before_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )
    store.last_resolved_remote_url = None
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        (),
    )

    try:
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=_dependencies(client),
        )
    except RepositoryConnectionProblem as error:
        assert (
            error.detail == "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다."
        )
    else:
        raise AssertionError("GitLab snapshot should reject unallowlisted hosts")

    assert store.sync_runs[sync_run.id].status.value == "failed"
    failure_code = store.sync_runs[sync_run.id].failure_code
    assert failure_code is not None
    assert failure_code.value == "MIRROR_SYNC_FAILED"
    assert store.last_resolved_remote_url is None


def test_run_webhook_sync_task_marks_event_failed_when_snapshot_build_fails(
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
    store.resolved_ref_commits["main"] = "b" * 40
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    payload = build_github_push_payload(after_sha="b" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-task-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    event_id = uuid.UUID(response.json()["eventId"])
    sync_run_id = next(iter(store.sync_runs.keys()))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
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

    assert store.repository_events[event_id].processing_status == "failed"
    assert store.sync_runs[sync_run_id].status.value == "failed"
    failure_code = store.sync_runs[sync_run_id].failure_code
    assert failure_code is not None
    assert failure_code.value == "SNAPSHOT_WRITE_FAILED"
    assert store.event_cursors == {}


def test_run_webhook_sync_task_does_not_overwrite_retried_event_state(
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
    store.resolved_ref_commits["main"] = "c" * 40
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    payload = build_github_push_payload(after_sha="c" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-task-002",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    event_id = uuid.UUID(response.json()["eventId"])
    first_sync_run_id = next(iter(store.sync_runs.keys()))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
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
            sync_run_id=str(first_sync_run_id),
        )

    retry_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    second_sync_run_id = store.repository_events[event_id].sync_run_id
    assert second_sync_run_id is not None
    assert second_sync_run_id != first_sync_run_id

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            lambda command, dependencies: SimpleNamespace(
                id=uuid.uuid4(),
                created_at=datetime.now(tz=UTC),
            ),
        ),
    )

    _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert retry_response.status_code == 202
    assert store.repository_events[event_id].sync_run_id == second_sync_run_id
    assert store.repository_events[event_id].processing_status == "queued"
    assert store.repository_events[event_id].snapshot_id is None


def test_run_webhook_sync_task_dispatches_pending_followup_after_active_run_completes(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")

    initial_tasks: list[dict[str, str]] = []
    followup_tasks: list[dict[str, str]] = []
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: initial_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: followup_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="d" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-followup-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "d" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.RUNNING

    second_payload = build_github_push_payload(after_sha="e" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-task-followup-002",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "e" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    second_event_id = uuid.UUID(second_response.json()["eventId"])
    second_sync_run_id = store.repository_events[second_event_id].sync_run_id
    assert second_sync_run_id is not None
    assert second_sync_run_id != first_sync_run_id
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.BLOCKED

    def fake_build_snapshot(command, *, dependencies):
        store.sync_runs[command.sync_run_id].status = SyncRunStatus.SUCCEEDED
        return SimpleNamespace(
            id=uuid.uuid4(),
            created_at=datetime.now(tz=UTC),
        )

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            fake_build_snapshot,
        ),
    )
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.PENDING

    result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )
    replay_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(initial_tasks) == 1
    assert result["status"] == "completed"
    assert replay_result["status"] == "completed"
    assert followup_tasks == [
        {
            "name": "tci.repository_ingestion.run_webhook_sync",
            "connection_id": str(connection_id),
            "event_id": str(second_event_id),
            "sync_run_id": str(second_sync_run_id),
        }
    ]
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.PENDING
    assert store.repository_events[second_event_id].processing_status == "queued"

    store.sync_runs[second_sync_run_id].dispatch_enqueued_at = datetime.now(
        tz=UTC
    ) - timedelta(minutes=16)
    stale_dispatch_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert stale_dispatch_result["status"] == "completed"
    assert followup_tasks[-1] == {
        "name": "tci.repository_ingestion.run_webhook_sync",
        "connection_id": str(connection_id),
        "event_id": str(second_event_id),
        "sync_run_id": str(second_sync_run_id),
    }
    assert len(followup_tasks) == 2


def test_run_webhook_sync_task_dispatches_pending_followup_after_active_run_fails(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    initial_tasks: list[dict[str, str]] = []
    followup_tasks: list[dict[str, str]] = []
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: initial_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: followup_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="f" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-failed-followup-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "f" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.RUNNING
    store.sync_runs[first_sync_run_id].started_at = datetime.now(tz=UTC) - timedelta(
        minutes=20
    )

    second_payload = build_github_push_payload(after_sha="1" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-task-failed-followup-002",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "1" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    second_event_id = uuid.UUID(second_response.json()["eventId"])
    second_sync_run_id = store.repository_events[second_event_id].sync_run_id
    assert second_sync_run_id is not None

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
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
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.PENDING

    with pytest.raises(RuntimeError, match="snapshot failed"):
        _run_webhook_sync_task(
            connection_id=str(connection_id),
            event_id=str(first_event_id),
            sync_run_id=str(first_sync_run_id),
        )
    with pytest.raises(RuntimeError, match="snapshot failed"):
        _run_webhook_sync_task(
            connection_id=str(connection_id),
            event_id=str(first_event_id),
            sync_run_id=str(first_sync_run_id),
        )

    assert second_response.status_code == 202
    assert followup_tasks == [
        {
            "name": "tci.repository_ingestion.run_webhook_sync",
            "connection_id": str(connection_id),
            "event_id": str(second_event_id),
            "sync_run_id": str(second_sync_run_id),
        }
    ]


def test_run_webhook_sync_task_marks_pending_followup_failed_when_dispatch_fails(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: (_ for _ in ()).throw(
                RuntimeError("broker down")
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="2" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-dispatch-fails-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "2" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.RUNNING

    second_payload = build_github_push_payload(after_sha="3" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-task-dispatch-fails-002",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "3" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    second_event_id = uuid.UUID(second_response.json()["eventId"])
    second_sync_run_id = store.repository_events[second_event_id].sync_run_id
    assert second_sync_run_id is not None
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.BLOCKED

    def fake_build_snapshot(command, *, dependencies):
        store.sync_runs[command.sync_run_id].status = SyncRunStatus.SUCCEEDED
        return SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(tz=UTC))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            fake_build_snapshot,
        ),
    )
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.PENDING

    result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert second_response.status_code == 202
    assert result["status"] == "completed"
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.FAILED
    assert store.sync_runs[second_sync_run_id].failure_code.value == (
        "QUEUE_DISPATCH_FAILED"
    )
    assert store.repository_events[second_event_id].processing_status == "failed"


def test_run_webhook_sync_task_marks_stale_pending_followup_failed_when_dispatch_fails(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: (_ for _ in ()).throw(
                RuntimeError("queue unavailable")
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="1" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-stale-pending-fail-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "1" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.SUCCEEDED

    pending_event_id = uuid.uuid4()
    pending_sync_run_id = uuid.uuid4()
    pending_received_at = datetime.now(tz=UTC)
    store.repository_events[pending_event_id] = TestRepositoryEvent(
        id=pending_event_id,
        connection_id=connection_id,
        provider_delivery_id="delivery-task-stale-pending-fail-002",
        provider_event_idempotency_source="delivery_header",
        provider_event_type="push",
        provider_action=None,
        target_key="default_ref",
        target_head_sha="2" * 40,
        signature_status="verified",
        processing_decision="queued",
        processing_status="queued",
        received_at=pending_received_at,
        domain_event_type="push_received",
        target_kind="default_ref",
        target_ref_name="main",
        occurred_at=pending_received_at,
        sync_run_id=pending_sync_run_id,
        processed_at=pending_received_at,
    )
    store.sync_runs[pending_sync_run_id] = RepositorySyncRun(
        id=pending_sync_run_id,
        connection_id=connection_id,
        trigger_event_id=pending_event_id,
        trigger_type=SyncTriggerType.WEBHOOK_PUSH,
        requested_ref_type=RefType.BRANCH,
        requested_ref_name="main",
        requested_ref_key="main",
        status=SyncRunStatus.PENDING,
        started_at=pending_received_at,
        dispatch_enqueued_at=pending_received_at - timedelta(minutes=16),
    )
    seed_repository_event_cursor(
        store,
        connection_id=connection_id,
        target_key="default_ref",
        latest_head_sha="2" * 40,
        latest_event_id=pending_event_id,
    )

    def fake_build_snapshot(command, *, dependencies, _allow_running_retry=False):
        return SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(tz=UTC))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (SimpleNamespace, fake_build_snapshot),
    )

    replay_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert replay_result["status"] == "completed"
    assert store.sync_runs[pending_sync_run_id].status is SyncRunStatus.FAILED
    assert store.sync_runs[pending_sync_run_id].failure_code.value == (
        "QUEUE_DISPATCH_FAILED"
    )
    assert store.repository_events[pending_event_id].processing_status == "failed"
    assert (
        store.event_cursors[(connection_id, "default_ref")].latest_event_id
        != pending_event_id
    )


def test_run_webhook_sync_task_replays_running_sync_after_worker_crash(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")

    initial_tasks: list[dict[str, str]] = []
    followup_tasks: list[dict[str, str]] = []
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: initial_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: followup_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="4" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-running-replay-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "4" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.RUNNING
    store.sync_runs[first_sync_run_id].started_at = datetime.now(tz=UTC) - timedelta(
        minutes=20
    )

    second_payload = build_github_push_payload(after_sha="5" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-task-running-replay-002",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "5" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    second_event_id = uuid.UUID(second_response.json()["eventId"])
    second_sync_run_id = store.repository_events[second_event_id].sync_run_id
    assert second_sync_run_id is not None
    assert second_sync_run_id != first_sync_run_id
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.BLOCKED

    replay_flags: list[bool] = []

    def fake_build_snapshot(command, *, dependencies, _allow_running_retry=False):
        replay_flags.append(_allow_running_retry)
        store.sync_runs[command.sync_run_id].status = SyncRunStatus.SUCCEEDED
        return SimpleNamespace(
            id=uuid.uuid4(),
            created_at=datetime.now(tz=UTC),
        )

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            fake_build_snapshot,
        ),
    )

    replay_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert replay_result["status"] == "completed"
    assert replay_flags == [True]
    assert followup_tasks == [
        {
            "name": "tci.repository_ingestion.run_webhook_sync",
            "connection_id": str(connection_id),
            "event_id": str(second_event_id),
            "sync_run_id": str(second_sync_run_id),
        }
    ]
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.PENDING
    assert store.repository_events[second_event_id].processing_status == "queued"


def test_run_webhook_sync_task_duplicate_replay_does_not_poison_completed_event(
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
    store.resolved_ref_commits["main"] = "6" * 40
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    payload = build_github_push_payload(after_sha="6" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-task-duplicate-replay-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"

    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )

    event_id = uuid.UUID(response.json()["eventId"])
    sync_run_id = store.repository_events[event_id].sync_run_id
    assert sync_run_id is not None

    completed_snapshot_id = uuid.uuid4()

    def fake_build_snapshot(command, *, dependencies):
        store.sync_runs[command.sync_run_id].status = SyncRunStatus.SUCCEEDED
        store.repository_events[event_id].processing_status = "completed"
        store.repository_events[event_id].snapshot_id = completed_snapshot_id
        raise RuntimeError("duplicate replay lost race after success")

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            fake_build_snapshot,
        ),
    )

    with pytest.raises(RuntimeError, match="duplicate replay lost race after success"):
        _run_webhook_sync_task(
            connection_id=str(connection_id),
            event_id=str(event_id),
            sync_run_id=str(sync_run_id),
        )

    assert response.status_code == 202
    assert store.sync_runs[sync_run_id].status is SyncRunStatus.SUCCEEDED
    assert store.repository_events[event_id].processing_status == "completed"
    assert store.repository_events[event_id].snapshot_id == completed_snapshot_id


def test_run_webhook_sync_task_does_not_release_blocked_followup_when_successor_running(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    followup_tasks: list[dict[str, str]] = []
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: followup_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="7" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-successor-running-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "7" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.SUCCEEDED

    second_payload = build_github_push_payload(after_sha="8" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-task-successor-running-002",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "8" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    second_event_id = uuid.UUID(second_response.json()["eventId"])
    second_sync_run_id = store.repository_events[second_event_id].sync_run_id
    assert second_sync_run_id is not None
    store.sync_runs[second_sync_run_id].status = SyncRunStatus.RUNNING

    third_payload = build_github_push_payload(after_sha="9" * 40)
    third_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=third_payload,
        delivery_id="delivery-task-successor-running-003",
        event_name="push",
    )
    third_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "9" * 40
    third_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(third_payload),
        headers=third_headers,
    )
    third_event_id = uuid.UUID(third_response.json()["eventId"])
    third_sync_run_id = store.repository_events[third_event_id].sync_run_id
    assert third_sync_run_id is not None
    assert store.sync_runs[third_sync_run_id].status is SyncRunStatus.BLOCKED

    def fake_build_snapshot(command, *, dependencies):
        return SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(tz=UTC))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (SimpleNamespace, fake_build_snapshot),
    )

    replay_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert third_response.status_code == 202
    assert replay_result["status"] == "completed"
    assert followup_tasks == []
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.RUNNING
    assert store.sync_runs[third_sync_run_id].status is SyncRunStatus.BLOCKED


def test_run_webhook_sync_task_keeps_fresh_running_replay_in_progress(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    payload = build_github_push_payload(after_sha="a" * 40)
    headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=payload,
        delivery_id="delivery-task-fresh-running-replay-001",
        event_name="push",
    )
    headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "a" * 40
    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    event_id = uuid.UUID(response.json()["eventId"])
    sync_run_id = store.repository_events[event_id].sync_run_id
    assert sync_run_id is not None
    store.sync_runs[sync_run_id].status = SyncRunStatus.RUNNING
    store.sync_runs[sync_run_id].started_at = datetime.now(tz=UTC)

    followup_payload = build_github_push_payload(after_sha="b" * 40)
    followup_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=followup_payload,
        delivery_id="delivery-task-fresh-running-replay-002",
        event_name="push",
    )
    followup_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "b" * 40
    followup_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(followup_payload),
        headers=followup_headers,
    )
    followup_event_id = uuid.UUID(followup_response.json()["eventId"])
    followup_sync_run_id = store.repository_events[followup_event_id].sync_run_id
    assert followup_sync_run_id is not None

    def fail_if_snapshot_builds(command, *, dependencies):
        raise AssertionError("fresh running replay should not build a snapshot")

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (SimpleNamespace, fail_if_snapshot_builds),
    )

    replay_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(event_id),
        sync_run_id=str(sync_run_id),
    )

    assert response.status_code == 202
    assert followup_response.status_code == 202
    assert replay_result["status"] == "in_progress"
    assert store.sync_runs[sync_run_id].status is SyncRunStatus.RUNNING
    assert store.sync_runs[followup_sync_run_id].status is SyncRunStatus.BLOCKED


def test_run_webhook_sync_task_does_not_release_blocked_followup_when_release_races(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    followup_tasks: list[dict[str, str]] = []
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: followup_tasks.append(
                {"name": name, **kwargs}
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="1" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-release-race-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "1" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.SUCCEEDED

    second_payload = build_github_push_payload(after_sha="2" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-task-release-race-002",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "2" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    second_event_id = uuid.UUID(second_response.json()["eventId"])
    second_sync_run_id = store.repository_events[second_event_id].sync_run_id
    assert second_sync_run_id is not None
    store.sync_runs[second_sync_run_id].status = SyncRunStatus.RUNNING

    third_payload = build_github_push_payload(after_sha="3" * 40)
    third_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=third_payload,
        delivery_id="delivery-task-release-race-003",
        event_name="push",
    )
    third_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "3" * 40
    third_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(third_payload),
        headers=third_headers,
    )
    third_event_id = uuid.UUID(third_response.json()["eventId"])
    third_sync_run_id = store.repository_events[third_event_id].sync_run_id
    assert third_sync_run_id is not None
    store.sync_runs[second_sync_run_id].status = SyncRunStatus.SUCCEEDED
    store.sync_run_release_conflict_refs.add((connection_id, RefType.BRANCH, "main"))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (
            SimpleNamespace,
            lambda command, *, dependencies: SimpleNamespace(
                id=uuid.uuid4(),
                created_at=datetime.now(tz=UTC),
            ),
        ),
    )

    replay_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert replay_result["status"] == "completed"
    assert followup_tasks == []
    assert store.sync_runs[third_sync_run_id].status is SyncRunStatus.BLOCKED
    assert store.sync_run_release_conflict_refs == set()


def test_run_webhook_sync_task_marks_released_followup_failed_when_dispatch_fails(
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
    object.__setattr__(_settings(client), "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(
        "tci.workers.celery_app.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: (_ for _ in ()).throw(
                RuntimeError("queue unavailable")
            )
        ),
    )

    first_payload = build_github_push_payload(after_sha="1" * 40)
    first_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=first_payload,
        delivery_id="delivery-task-dispatch-fail-001",
        event_name="push",
    )
    first_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "1" * 40
    first_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(first_payload),
        headers=first_headers,
    )
    first_event_id = uuid.UUID(first_response.json()["eventId"])
    first_sync_run_id = store.repository_events[first_event_id].sync_run_id
    assert first_sync_run_id is not None
    store.sync_runs[first_sync_run_id].status = SyncRunStatus.RUNNING
    store.sync_runs[first_sync_run_id].started_at = datetime.now(tz=UTC) - timedelta(
        minutes=16
    )

    second_payload = build_github_push_payload(after_sha="2" * 40)
    second_headers = build_github_webhook_headers(
        secret="webhook-secret",
        payload=second_payload,
        delivery_id="delivery-task-dispatch-fail-002",
        event_name="push",
    )
    second_headers["content-type"] = "application/json"
    store.resolved_ref_commits["main"] = "2" * 40
    second_response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(second_payload),
        headers=second_headers,
    )
    second_event_id = uuid.UUID(second_response.json()["eventId"])
    second_sync_run_id = store.repository_events[second_event_id].sync_run_id
    assert second_sync_run_id is not None
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.BLOCKED

    def fake_build_snapshot(command, *, dependencies, _allow_running_retry=False):
        store.sync_runs[command.sync_run_id].status = SyncRunStatus.SUCCEEDED
        return SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(tz=UTC))

    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: _dependencies(client),
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._load_build_snapshot_service",
        lambda: (SimpleNamespace, fake_build_snapshot),
    )

    replay_result = _run_webhook_sync_task(
        connection_id=str(connection_id),
        event_id=str(first_event_id),
        sync_run_id=str(first_sync_run_id),
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert replay_result["status"] == "completed"
    assert store.sync_runs[second_sync_run_id].status is SyncRunStatus.FAILED
    assert store.sync_runs[second_sync_run_id].failure_code.value == (
        "QUEUE_DISPATCH_FAILED"
    )
    assert store.repository_events[second_event_id].processing_status == "failed"
    assert (
        store.event_cursors[(connection_id, "default_ref")].latest_event_id
        != second_event_id
    )
