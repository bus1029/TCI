from __future__ import annotations

import uuid
from typing import Any, cast

from tests.support.local_upload_testkit import build_project_zip
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)
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


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_github_gitlab_and_local_upload_sources_stay_distinct_in_mixed_workspace(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    github_id = _create_connection(client, provider="github_cloud")
    gitlab_id = _create_connection(
        client,
        provider="gitlab_self_managed",
        remote_url="https://gitlab.example.com/group/sample-repo.git",
    )
    github_snapshot_id = _create_repository_snapshot(client, workspace_id, github_id)
    gitlab_snapshot_id = _create_repository_snapshot(client, workspace_id, gitlab_id)
    local_upload = _post_zip(client, filename="local-project.zip")
    local_snapshot_id = uuid.UUID(cast(str, local_upload["latestSnapshotId"]))

    list_payload = client.get("/api/repository-connections").json()
    github_detail = client.get(f"/api/repository-connections/{github_id}").json()
    gitlab_detail = client.get(f"/api/repository-connections/{gitlab_id}").json()
    local_detail = client.get(
        f"/api/local-uploads/{local_upload['id']}/snapshots/{local_snapshot_id}"
    ).json()

    assert [item["provider"] for item in list_payload["items"]] == [
        "gitlab_self_managed",
        "github_cloud",
    ]
    assert "local_upload" not in {item["provider"] for item in list_payload["items"]}
    assert github_detail["latestSnapshot"]["id"] == str(github_snapshot_id)
    assert github_detail["latestSnapshot"]["requestedRefType"] == "branch"
    assert github_detail["latestSnapshot"]["requestedRefName"] == "main"
    assert github_detail["latestSnapshot"]["resolvedCommitSha"] == "a" * 40
    assert github_detail["latestSnapshot"]["createdAt"] is not None
    assert github_detail["latestSnapshot"]["source"] == {
        "kind": "repository_connection",
        "provider": "github_cloud",
        "connectionId": str(github_id),
    }
    assert gitlab_detail["latestSnapshot"]["source"] == {
        "kind": "repository_connection",
        "provider": "gitlab_self_managed",
        "connectionId": str(gitlab_id),
    }
    assert local_detail["source"]["kind"] == "local_upload"
    assert local_detail["source"]["localUploadId"] == local_upload["id"]
    assert store.snapshots[github_snapshot_id].connection_id == github_id
    assert store.snapshots[gitlab_snapshot_id].connection_id == gitlab_id
    assert store.snapshots[local_snapshot_id].local_upload_id == uuid.UUID(
        cast(str, local_upload["id"])
    )


def _create_connection(
    client,
    *,
    provider: str,
    remote_url: str = "https://github.com/acme/sample-repo.git",
) -> uuid.UUID:
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(provider=provider, remote_url=remote_url),
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


def _create_repository_snapshot(
    client,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> uuid.UUID:
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
    return snapshot.id


def _post_zip(client, *, filename: str) -> dict[str, object]:
    response = client.post(
        "/api/local-uploads",
        files={"file": (filename, build_project_zip(), "application/zip")},
    )
    assert response.status_code == 201
    return response.json()
