from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
import uuid

from tests.support.repository_connection_testkit import (
    build_github_push_payload,
    build_github_webhook_headers,
    build_gitlab_push_payload,
    build_gitlab_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    serialize_github_webhook_payload,
    serialize_gitlab_webhook_payload,
)
from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_mixed_provider_status_events_snapshots_and_history_stay_separated(
    tmp_path,
    monkeypatch,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    github_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            remote_url="https://github.com/acme/sample-repo.git",
        ),
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

    github_sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=github_id,
        ),
        dependencies=_dependencies(client),
    )
    gitlab_sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=gitlab_id,
        ),
        dependencies=_dependencies(client),
    )
    github_snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=github_id,
            sync_run_id=github_sync_run.id,
        ),
        dependencies=_dependencies(client),
    )
    gitlab_snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=gitlab_id,
            sync_run_id=gitlab_sync_run.id,
        ),
        dependencies=_dependencies(client),
    )

    seed_active_webhook_secret(store, connection_id=github_id, secret="github-secret")
    seed_active_webhook_secret(store, connection_id=gitlab_id, secret="gitlab-token")
    store.resolved_ref_commits["main"] = "b" * 40
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
    github_payload = build_github_push_payload(after_sha="b" * 40)
    github_headers = build_github_webhook_headers(
        secret="github-secret",
        payload=github_payload,
        delivery_id="github-mixed-delivery",
        event_name="push",
    )
    github_headers["content-type"] = "application/json"
    gitlab_payload = build_gitlab_push_payload(after_sha="b" * 40)
    gitlab_headers = build_gitlab_webhook_headers(
        token="gitlab-token",
        event_name="Push Hook",
        idempotency_key="gitlab-mixed-delivery",
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

    github_detail = client.get(f"/api/repository-connections/{github_id}").json()
    gitlab_detail = client.get(f"/api/repository-connections/{gitlab_id}").json()
    github_events = client.get(f"/api/repository-connections/{github_id}/events").json()
    gitlab_events = client.get(f"/api/repository-connections/{gitlab_id}/events").json()
    list_page = client.get(f"/connections?workspaceId={workspace_id}")
    github_detail_page = client.get(
        f"/connections/{github_id}?workspaceId={workspace_id}"
    )
    gitlab_detail_page = client.get(
        f"/connections/{gitlab_id}?workspaceId={workspace_id}"
    )
    github_events_page = client.get(
        f"/connections/{github_id}/events?workspaceId={workspace_id}"
    )
    gitlab_events_page = client.get(
        f"/connections/{gitlab_id}/events?workspaceId={workspace_id}"
    )

    assert github_webhook_response.status_code == 202
    assert gitlab_webhook_response.status_code == 202
    assert github_detail["provider"] == "github_cloud"
    assert gitlab_detail["provider"] == "gitlab_self_managed"
    assert github_detail["latestSnapshot"]["id"] == str(github_snapshot.id)
    assert gitlab_detail["latestSnapshot"]["id"] == str(gitlab_snapshot.id)
    assert github_detail["latestSyncRun"]["id"] != gitlab_detail["latestSyncRun"]["id"]
    assert github_sync_run.connection_id == github_id
    assert gitlab_sync_run.connection_id == gitlab_id
    assert sorted(event["providerDeliveryId"] for event in github_events["items"]) == [
        "github-mixed-delivery"
    ]
    assert sorted(event["providerDeliveryId"] for event in gitlab_events["items"]) == [
        "gitlab-mixed-delivery",
        f"gitlab-mixed-delivery:commit:{'b' * 40}",
    ]
    assert list_page.status_code == 200
    assert "github_cloud" in list_page.text
    assert "gitlab_self_managed" in list_page.text
    assert github_detail_page.status_code == 200
    assert str(workspace_id) in github_detail_page.text
    assert "github_cloud" in github_detail_page.text
    assert "워크스페이스에서 직접 생성된 저장소 연결입니다." in (
        github_detail_page.text
    )
    assert gitlab_detail_page.status_code == 200
    assert str(workspace_id) in gitlab_detail_page.text
    assert "gitlab_self_managed" in gitlab_detail_page.text
    assert "group/sample-repo" in gitlab_detail_page.text
    assert github_events_page.status_code == 200
    assert "github_cloud" in github_events_page.text
    assert "github-mixed-delivery" in github_events_page.text
    assert "gitlab_self_managed" not in github_events_page.text
    assert "gitlab-mixed-delivery" not in github_events_page.text
    assert gitlab_events_page.status_code == 200
    assert "gitlab_self_managed" in gitlab_events_page.text
    assert "gitlab-mixed-delivery" in gitlab_events_page.text
    assert "github_cloud" not in gitlab_events_page.text
    assert "github-mixed-delivery" not in gitlab_events_page.text
