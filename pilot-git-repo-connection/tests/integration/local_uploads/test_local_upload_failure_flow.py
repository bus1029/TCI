from __future__ import annotations

import uuid
from typing import Any, cast

from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus
from tests.support.local_upload_testkit import (
    ZipFixtureEntry,
    build_corrupt_zip,
    build_zip_bytes,
    build_zip_with_traversal_path,
)
from tests.support.repository_connection_testkit import create_test_client, now_utc


def test_corrupt_zip_fails_without_active_snapshot_and_retry_guidance(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.post(
        "/api/local-uploads",
        files={"file": ("broken.zip", build_corrupt_zip(), "application/zip")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_zip"
    assert response.json()["remediationAction"] == "upload_valid_zip"
    assert len(store.local_uploads) == 1
    assert next(iter(store.local_uploads.values())).latest_snapshot_id is None
    assert store.snapshots == {}


def test_unsafe_path_zip_fails_without_active_snapshot(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.post(
        "/api/local-uploads",
        files={
            "file": (
                "unsafe.zip",
                build_zip_with_traversal_path(),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "unsafe_zip_path"
    assert response.json()["remediationAction"] == "remove_unsafe_paths"
    assert next(iter(store.local_uploads.values())).latest_snapshot_id is None
    assert store.snapshots == {}


def test_limit_exceeded_zip_returns_allowed_limits_and_retry_guidance(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    settings = cast(Any, client.app).state.settings
    object.__setattr__(settings, "local_upload_max_file_bytes", 3)

    response = client.post(
        "/api/local-uploads",
        files={
            "file": (
                "limit.zip",
                build_zip_bytes((ZipFixtureEntry("src/main.py", b"1234"),)),
                "application/zip",
            )
        },
    )

    payload = response.json()
    assert response.status_code == 400
    assert payload["code"] == "zip_limit_exceeded"
    assert payload["remediationAction"] == "reduce_zip_size"
    assert payload["allowedLimits"]["maxFileBytes"] == 3
    assert "다시 업로드" in payload["message"]
    assert next(iter(store.local_uploads.values())).latest_snapshot_id is None
    assert store.snapshots == {}


def _seed_active_workspace(store, *, workspace_id: uuid.UUID) -> None:
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
