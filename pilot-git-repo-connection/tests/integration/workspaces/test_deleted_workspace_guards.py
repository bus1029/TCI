from __future__ import annotations

import uuid

from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus
from tests.support.local_upload_testkit import build_project_zip
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    now_utc,
)


def test_deleted_workspace_rejects_local_upload_and_repository_connection(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id, status=WorkspaceStatus.DELETED)

    upload_response = client.post(
        "/api/local-uploads",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
    )
    connection_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )

    assert upload_response.status_code == 409
    assert upload_response.json()["code"] == "WORKSPACE_NOT_ACTIVE"
    assert connection_response.status_code == 409
    assert connection_response.json()["code"] == "WORKSPACE_NOT_ACTIVE"
    assert store.local_uploads == {}
    assert store.connections == {}


def test_deleting_workspace_rejects_candidate_and_snapshot_mutations(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id, status=WorkspaceStatus.ACTIVE)
    connection_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = connection_response.json()["id"]
    store.workspaces[workspace_id].status = WorkspaceStatus.DELETING

    candidates_response = client.get("/api/repository-candidates")
    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={},
    )

    assert candidates_response.status_code == 409
    assert candidates_response.json()["code"] == "workspace_deleting"
    assert snapshot_response.status_code == 409
    assert snapshot_response.json()["code"] == "WORKSPACE_NOT_ACTIVE"


def test_deleted_workspace_connection_list_is_empty(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_workspace(store, workspace_id=workspace_id, status=WorkspaceStatus.DELETED)

    response = client.get("/api/repository-connections")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def _seed_workspace(store, *, workspace_id: uuid.UUID, status: WorkspaceStatus) -> None:
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=status,
        created_at=now_utc(),
        updated_at=now_utc(),
        deleted_at=now_utc() if status is WorkspaceStatus.DELETED else None,
        deleted_by="owner-a" if status is WorkspaceStatus.DELETED else None,
    )
