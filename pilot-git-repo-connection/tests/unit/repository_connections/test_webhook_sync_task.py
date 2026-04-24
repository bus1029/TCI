from __future__ import annotations

from datetime import UTC, datetime
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
from tests.support.repository_connection_testkit import (
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
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
