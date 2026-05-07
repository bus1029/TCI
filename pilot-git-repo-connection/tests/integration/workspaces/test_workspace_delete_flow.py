from __future__ import annotations

import uuid
from typing import Any, cast

from tci.api.operator_auth import create_operator_session_cookie
from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus
from tests.support.local_upload_testkit import build_project_zip
from tests.support.repository_connection_testkit import (
    create_test_client,
    now_utc,
)


def test_workspace_owner_delete_removes_archives_and_preserves_audit(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    upload_response = client.post(
        "/api/local-uploads",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
    )
    snapshot_id = uuid.UUID(cast(str, upload_response.json()["latestSnapshotId"]))
    archive_root = cast(Any, client.app).state.settings.code_snapshot_root / str(
        snapshot_id
    )
    assert archive_root.exists()

    impact_response = client.get(
        f"/api/workspaces/{workspace_id}/deletion-impact",
        headers={
            "X-TCI-Operator-Id": "owner-a",
            "X-TCI-Operator-Role": "owner",
        },
    )
    delete_response = client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        headers={
            "X-TCI-Operator-Id": "owner-a",
            "X-TCI-Operator-Role": "owner",
        },
        json={"confirmation": f"DELETE {workspace_id}"},
    )

    assert impact_response.status_code == 200
    assert impact_response.json()["localUploadCount"] == 1
    assert impact_response.json()["snapshotCount"] == 1
    assert delete_response.status_code == 202
    assert delete_response.json()["status"] == "deleted"
    assert archive_root.exists() is False
    assert store.workspaces[workspace_id].status is WorkspaceStatus.DELETED
    assert store.workspaces[workspace_id].deleted_by == "operator"
    assert store.snapshots == {}
    assert store.local_uploads == {}
    record = next(iter(store.workspace_deletion_records.values()))
    assert record.workspace_id == workspace_id
    assert record.local_upload_count == 1
    assert record.snapshot_count == 1
    assert record.purged_archive_count == 1
    assert record.failure_message is None


def test_cookie_cross_origin_delete_attempt_leaves_workspace_active(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    client.cookies.set(
        "tci_operator_token",
        create_operator_session_cookie(
            expected_token=cast(Any, client.app).state.settings.operator_api_token
        ),
    )

    response = client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        headers={"Origin": "https://evil.example"},
        json={"confirmation": f"DELETE {workspace_id}"},
    )

    assert response.status_code == 403
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE
    assert store.workspace_deletion_records == {}


def test_cookie_delete_without_origin_leaves_workspace_active(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    client.cookies.set(
        "tci_operator_token",
        create_operator_session_cookie(
            expected_token=cast(Any, client.app).state.settings.operator_api_token
        ),
    )

    response = client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        json={"confirmation": f"DELETE {workspace_id}"},
    )

    assert response.status_code == 403
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE
    assert store.workspace_deletion_records == {}


def test_deleted_workspace_direct_web_access_shows_next_actions(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        headers={
            "X-TCI-Operator-Id": "admin-a",
            "X-TCI-Operator-Role": "admin",
        },
        json={"confirmation": f"DELETE {workspace_id}"},
    )

    response = client.get(f"/workspaces/{workspace_id}/deleted")

    assert response.status_code == 200
    assert "삭제된 워크스페이스" in response.text
    assert "새 워크스페이스" in response.text
    assert "Local Upload" not in response.text


def test_active_workspace_deleted_page_returns_conflict(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.get(f"/workspaces/{workspace_id}/deleted")

    assert response.status_code == 409
    assert "삭제된 워크스페이스가 아닙니다." in response.text


def _seed_active_workspace(store, *, workspace_id: uuid.UUID) -> None:
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
