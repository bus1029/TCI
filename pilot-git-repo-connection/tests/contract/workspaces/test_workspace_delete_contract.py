from __future__ import annotations

import uuid
from typing import Any, cast

from tci.api.operator_auth import create_operator_session_cookie
from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus
from tests.support.repository_connection_testkit import (
    create_test_client,
    now_utc,
)


def test_workspace_deletion_impact_returns_counts_and_confirmation(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.get(
        f"/api/workspaces/{workspace_id}/deletion-impact",
        headers={
            "X-TCI-Operator-Id": "owner-a",
            "X-TCI-Operator-Role": "owner",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspaceId"] == str(workspace_id)
    assert payload["repositoryConnectionCount"] == 0
    assert payload["localUploadCount"] == 0
    assert payload["snapshotCount"] == 0
    assert payload["projectContentWillBeRemoved"] is True
    assert payload["auditMetadataWillRemain"] is True
    assert payload["confirmation"] == f"DELETE {workspace_id}"


def test_delete_workspace_rejects_non_privileged_server_side_operator(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    object.__setattr__(cast(Any, client.app).state.settings, "operator_role", "viewer")

    response = client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        headers={
            "X-TCI-Operator-Role": "owner",
        },
        json={"confirmation": f"DELETE {workspace_id}"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "workspace_delete_forbidden",
        "message": "워크스페이스 소유자 또는 관리자만 삭제할 수 있습니다.",
        "remediationAction": "request_owner_or_admin",
    }
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE


def test_delete_workspace_requires_confirmation_phrase(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        headers={
            "X-TCI-Operator-Id": "owner-a",
            "X-TCI-Operator-Role": "owner",
        },
        json={"confirmation": "delete"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "workspace_delete_confirmation_required",
        "message": f"삭제하려면 확인 문구 'DELETE {workspace_id}'를 입력해야 합니다.",
        "remediationAction": "confirm_workspace_delete",
    }
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE


def test_delete_workspace_cookie_auth_rejects_cross_origin_post(tmp_path) -> None:
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
    assert response.json() == {
        "code": "invalid_request",
        "message": "허용되지 않은 요청 출처입니다.",
        "remediationAction": "none",
    }
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE


def test_delete_workspace_cookie_auth_rejects_missing_origin_post(tmp_path) -> None:
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
    assert response.json()["code"] == "invalid_request"
    assert store.workspaces[workspace_id].status is WorkspaceStatus.ACTIVE


def test_delete_workspace_soft_deletes_and_returns_audit_response(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        headers={
            "X-TCI-Operator-Id": "admin-a",
            "X-TCI-Operator-Role": "admin",
        },
        json={
            "confirmation": f"DELETE {workspace_id}",
            "reason": "cleanup after upload rehearsal",
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["workspaceId"] == str(workspace_id)
    assert payload["status"] == "deleted"
    assert payload["deletionRecordId"] is not None
    assert payload["auditMetadataRetained"] is True
    assert payload["projectContentRemoved"] is True
    assert payload["message"] == "워크스페이스 삭제가 완료되었습니다."
    assert store.workspaces[workspace_id].status is WorkspaceStatus.DELETED
    assert store.workspaces[workspace_id].deleted_by == "operator"


def test_delete_workspace_reports_existing_deleted_state(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    store.workspaces[workspace_id].status = WorkspaceStatus.DELETED
    store.workspaces[workspace_id].deleted_at = now_utc()
    store.workspaces[workspace_id].deleted_by = "owner-a"

    response = client.request(
        "DELETE",
        f"/api/workspaces/{workspace_id}",
        headers={
            "X-TCI-Operator-Id": "admin-a",
            "X-TCI-Operator-Role": "admin",
        },
        json={"confirmation": f"DELETE {workspace_id}"},
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["workspaceId"] == str(workspace_id)
    assert payload["status"] == "deleted"
    assert payload["auditMetadataRetained"] is True
    assert payload["projectContentRemoved"] is True


def _seed_active_workspace(store, *, workspace_id: uuid.UUID) -> None:
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
