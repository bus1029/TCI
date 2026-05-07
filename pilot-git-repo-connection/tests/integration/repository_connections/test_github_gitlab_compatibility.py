from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.support.repository_connection_testkit import (
    build_github_push_payload,
    build_github_webhook_headers,
    build_gitlab_push_payload,
    build_gitlab_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_legacy_planning_repository_connection,
    seed_planning_input_reference,
    serialize_github_webhook_payload,
    serialize_gitlab_webhook_payload,
)
from tests.support.local_upload_testkit import build_project_zip
from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tci.domain.services.verify_repository_connection import (
    VerifyRepositoryConnectionCommand,
    verify_repository_connection,
)


PHASE_1_SKIP_REASON = (
    "Phase 1 scaffold: implement mixed-provider regression coverage in T015/T026/T035."
)
pytestmark = pytest.mark.integration
PLANNED_CASES = (
    "test_github_and_gitlab_connections_can_coexist_without_state_collision",
    "test_github_regression_flow_survives_gitlab_provider_addition",
    "test_provider_specific_events_and_snapshots_do_not_cross_contaminate",
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_github_gitlab_compatibility_scaffold_declares_planned_cases() -> None:
    assert "T015/T026/T035" in PHASE_1_SKIP_REASON
    assert (
        tuple(name for name in PLANNED_CASES if callable(globals().get(name)))
        == PLANNED_CASES
    )


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_github_and_gitlab_connections_can_coexist_without_state_collision() -> None:
    """Covers mixed-provider connection summary and detail isolation."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_github_regression_flow_survives_gitlab_provider_addition() -> None:
    """Covers GitHub create, verify, and manual snapshot regression in mixed-provider mode."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_provider_specific_events_and_snapshots_do_not_cross_contaminate() -> None:
    """Covers event, health, and snapshot isolation across providers."""


def test_github_and_gitlab_connection_verify_and_snapshot_flows_coexist(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    github_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    gitlab_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert github_response.status_code == 201
    assert gitlab_response.status_code == 201
    github_id = uuid.UUID(github_response.json()["id"])
    gitlab_id = uuid.UUID(gitlab_response.json()["id"])

    github_sync_run = None
    gitlab_sync_run = None
    for connection_id in (github_id, gitlab_id):
        verify_repository_connection(
            VerifyRepositoryConnectionCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=_dependencies(client),
        )
        sync_run = create_initial_snapshot(
            CreateInitialSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=_dependencies(client),
        )
        snapshot = build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=_dependencies(client),
        )
        if connection_id == github_id:
            github_sync_run = sync_run
            github_snapshot = snapshot
            assert store.last_resolved_remote_url == (
                "https://github.com/acme/sample-repo.git"
            )
        else:
            gitlab_sync_run = sync_run
            gitlab_snapshot = snapshot
            assert store.last_resolved_remote_url == (
                "https://gitlab.example.com/group/sample-repo.git"
            )

    github_detail = client.get(f"/api/repository-connections/{github_id}").json()
    gitlab_detail = client.get(f"/api/repository-connections/{gitlab_id}").json()
    github_connection = store.connections[github_id]
    gitlab_connection = store.connections[gitlab_id]

    assert github_detail["provider"] == "github_cloud"
    assert gitlab_detail["provider"] == "gitlab_self_managed"
    assert (
        github_detail["traceability"]["latestSnapshotId"]
        != gitlab_detail["traceability"]["latestSnapshotId"]
    )
    assert github_connection.active_credential_revision_id != (
        gitlab_connection.active_credential_revision_id
    )
    assert github_connection.mirror_path != gitlab_connection.mirror_path
    assert github_sync_run is not None
    assert gitlab_sync_run is not None
    assert github_snapshot.connection_id == github_id
    assert gitlab_snapshot.connection_id == gitlab_id
    assert github_snapshot.sync_run_id == github_sync_run.id
    assert gitlab_snapshot.sync_run_id == gitlab_sync_run.id
    assert len(store.snapshots) == 2


def test_local_upload_coexists_without_changing_github_gitlab_provider_details(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    github_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    gitlab_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    upload_response = client.post(
        "/api/local-uploads",
        files={"file": ("local-project.zip", build_project_zip(), "application/zip")},
    )

    assert upload_response.status_code == 201
    list_payload = client.get("/api/repository-connections").json()
    github_detail = client.get(
        f"/api/repository-connections/{github_response.json()['id']}"
    ).json()
    gitlab_detail = client.get(
        f"/api/repository-connections/{gitlab_response.json()['id']}"
    ).json()

    assert [item["provider"] for item in list_payload["items"]] == [
        "gitlab_self_managed",
        "github_cloud",
    ]
    assert github_detail["provider"] == "github_cloud"
    assert github_detail["origin"]["kind"] == "workspace_repository"
    assert gitlab_detail["provider"] == "gitlab_self_managed"
    assert gitlab_detail["providerInstanceUrl"] == "https://gitlab.example.com"
    assert gitlab_detail["providerProjectPath"] == "group/sample-repo"
    assert "local_upload" not in {item["provider"] for item in list_payload["items"]}
    assert len(store.local_uploads) == 1
    assert len(store.connections) == 2


def test_github_and_gitlab_webhook_events_do_not_cross_contaminate(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    github_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    gitlab_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    github_id = uuid.UUID(github_response.json()["id"])
    gitlab_id = uuid.UUID(gitlab_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=github_id, secret="github-secret")
    seed_active_webhook_secret(store, connection_id=gitlab_id, secret="gitlab-token")
    store.resolved_ref_commits["main"] = "a" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    github_payload = build_github_push_payload(after_sha="a" * 40)
    github_headers = build_github_webhook_headers(
        secret="github-secret",
        payload=github_payload,
        delivery_id="github-delivery",
        event_name="push",
    )
    github_headers["content-type"] = "application/json"
    gitlab_payload = build_gitlab_push_payload(after_sha="a" * 40)
    gitlab_headers = build_gitlab_webhook_headers(
        token="gitlab-token",
        event_name="Push Hook",
        idempotency_key="gitlab-delivery",
    )
    gitlab_headers["content-type"] = "application/json"

    github_webhook_response = client.post(
        f"/api/webhooks/github/{github_id}",
        content=serialize_github_webhook_payload(github_payload),
        headers=github_headers,
    )
    gitlab_webhook_response = client.post(
        f"/api/webhooks/gitlab/{gitlab_id}",
        content=serialize_gitlab_webhook_payload(gitlab_payload),
        headers=gitlab_headers,
    )

    assert github_webhook_response.status_code == 202
    assert gitlab_webhook_response.status_code == 202
    github_events = [
        event
        for event in store.repository_events.values()
        if event.connection_id == github_id
    ]
    gitlab_events = [
        event
        for event in store.repository_events.values()
        if event.connection_id == gitlab_id
    ]
    assert [event.provider_delivery_id for event in github_events] == [
        "github-delivery"
    ]
    assert [event.provider_delivery_id for event in gitlab_events] == [
        "gitlab-delivery",
        f"gitlab-delivery:commit:{'a' * 40}",
    ]
    assert store.connections[github_id].last_processed_event_id == github_events[0].id
    assert store.connections[gitlab_id].last_processed_event_id == gitlab_events[0].id


def test_webhook_routes_reject_wrong_provider_connection_without_state_mutation(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    github_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    gitlab_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    github_id = uuid.UUID(github_response.json()["id"])
    gitlab_id = uuid.UUID(gitlab_response.json()["id"])
    seed_active_webhook_secret(store, connection_id=github_id, secret="github-secret")
    seed_active_webhook_secret(store, connection_id=gitlab_id, secret="gitlab-token")
    github_payload = build_github_push_payload(after_sha="a" * 40)
    github_headers = build_github_webhook_headers(
        secret="github-secret",
        payload=github_payload,
        delivery_id="github-wrong-provider",
        event_name="push",
    )
    github_headers["content-type"] = "application/json"
    gitlab_payload = build_gitlab_push_payload(after_sha="a" * 40)
    gitlab_headers = build_gitlab_webhook_headers(
        token="gitlab-token",
        event_name="Push Hook",
        idempotency_key="gitlab-wrong-provider",
    )
    gitlab_headers["content-type"] = "application/json"

    github_to_gitlab_response = client.post(
        f"/api/webhooks/github/{gitlab_id}",
        content=serialize_github_webhook_payload(github_payload),
        headers=github_headers,
    )
    gitlab_to_github_response = client.post(
        f"/api/webhooks/gitlab/{github_id}",
        content=serialize_gitlab_webhook_payload(gitlab_payload),
        headers=gitlab_headers,
    )

    assert github_to_gitlab_response.status_code == 202
    assert github_to_gitlab_response.json() == {"status": "accepted"}
    assert gitlab_to_github_response.status_code == 202
    assert gitlab_to_github_response.json() == {"status": "accepted"}
    assert store.repository_events == {}
    assert store.sync_runs == {}


def test_legacy_github_planning_connection_remains_visible_and_operational(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection, planning_reference = seed_legacy_planning_repository_connection(
        client=client,
        store=store,
        workspace_id=workspace_id,
        provider="github_cloud",
        remote_url="https://github.com/acme/legacy-repo.git",
    )

    verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection.id,
        ),
        dependencies=_dependencies(client),
    )
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection.id,
        ),
        dependencies=_dependencies(client),
    )
    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection.id,
            sync_run_id=sync_run.id,
        ),
        dependencies=_dependencies(client),
    )

    list_response = client.get(f"/connections?workspaceId={workspace_id}")
    detail_response = client.get(f"/api/repository-connections/{connection.id}")

    assert list_response.status_code == 200
    assert "legacy-repo" in list_response.text
    assert "출처: 기존 planning trace" in list_response.text
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["provider"] == "github_cloud"
    assert detail_payload["origin"]["kind"] == "legacy_planning"
    assert detail_payload["origin"]["compatibilityState"] == "legacy_trace_preserved"
    assert detail_payload["traceability"]["planningInputReference"]["id"] == str(
        planning_reference.id
    )
    assert snapshot.connection_id == connection.id


def test_legacy_gitlab_planning_connection_remains_visible_and_operational(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection, planning_reference = seed_legacy_planning_repository_connection(
        client=client,
        store=store,
        workspace_id=workspace_id,
        provider="gitlab_self_managed",
        remote_url="https://gitlab.example.com/group/legacy-repo.git",
    )

    verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection.id,
        ),
        dependencies=_dependencies(client),
    )
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection.id,
        ),
        dependencies=_dependencies(client),
    )
    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection.id,
            sync_run_id=sync_run.id,
        ),
        dependencies=_dependencies(client),
    )

    list_response = client.get(f"/connections?workspaceId={workspace_id}")
    detail_response = client.get(f"/api/repository-connections/{connection.id}")

    assert list_response.status_code == 200
    assert "group/legacy-repo" in list_response.text
    assert "출처: 기존 planning trace" in list_response.text
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["provider"] == "gitlab_self_managed"
    assert detail_payload["providerInstanceUrl"] == "https://gitlab.example.com"
    assert detail_payload["providerProjectPath"] == "group/legacy-repo"
    assert detail_payload["origin"]["kind"] == "legacy_planning"
    assert detail_payload["traceability"]["planningInputReference"]["id"] == str(
        planning_reference.id
    )
    assert snapshot.connection_id == connection.id


def test_legacy_github_gitlab_webhooks_preserve_provider_isolation(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    github_connection, _github_reference = seed_legacy_planning_repository_connection(
        client=client,
        store=store,
        workspace_id=workspace_id,
        provider="github_cloud",
        remote_url="https://github.com/acme/sample-repo.git",
    )
    gitlab_connection, _gitlab_reference = seed_legacy_planning_repository_connection(
        client=client,
        store=store,
        workspace_id=workspace_id,
        provider="gitlab_self_managed",
        remote_url="https://gitlab.example.com/group/sample-repo.git",
    )
    seed_active_webhook_secret(
        store, connection_id=github_connection.id, secret="github-secret"
    )
    seed_active_webhook_secret(
        store, connection_id=gitlab_connection.id, secret="gitlab-token"
    )
    store.resolved_ref_commits["main"] = "a" * 40
    object.__setattr__(
        cast(Any, client.app).state.settings, "redis_url", "redis://example"
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: SimpleNamespace(send_task=lambda name, kwargs: None),
    )

    github_payload = build_github_push_payload(after_sha="a" * 40)
    github_headers = build_github_webhook_headers(
        secret="github-secret",
        payload=github_payload,
        delivery_id="legacy-github-delivery",
        event_name="push",
    )
    github_headers["content-type"] = "application/json"
    gitlab_payload = build_gitlab_push_payload(after_sha="a" * 40)
    gitlab_headers = build_gitlab_webhook_headers(
        token="gitlab-token",
        event_name="Push Hook",
        idempotency_key="legacy-gitlab-delivery",
    )
    gitlab_headers["content-type"] = "application/json"

    github_webhook_response = client.post(
        f"/api/webhooks/github/{github_connection.id}",
        content=serialize_github_webhook_payload(github_payload),
        headers=github_headers,
    )
    gitlab_webhook_response = client.post(
        f"/api/webhooks/gitlab/{gitlab_connection.id}",
        content=serialize_gitlab_webhook_payload(gitlab_payload),
        headers=gitlab_headers,
    )

    assert github_webhook_response.status_code == 202
    assert gitlab_webhook_response.status_code == 202
    assert [
        event.provider_delivery_id
        for event in store.repository_events.values()
        if event.connection_id == github_connection.id
    ] == ["legacy-github-delivery"]
    assert [
        event.provider_delivery_id
        for event in store.repository_events.values()
        if event.connection_id == gitlab_connection.id
    ] == [
        "legacy-gitlab-delivery",
        f"legacy-gitlab-delivery:commit:{'a' * 40}",
    ]
