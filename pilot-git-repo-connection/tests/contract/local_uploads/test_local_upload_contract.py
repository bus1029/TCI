from __future__ import annotations

import uuid
from stat import S_IMODE
from typing import Any, cast

from tci.api.operator_auth import create_operator_session_cookie
from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus
from tests.support.local_upload_testkit import (
    ZipFixtureEntry,
    build_corrupt_zip,
    build_project_zip,
    build_zip_bytes,
)
from tests.support.repository_connection_testkit import (
    create_test_client,
    now_utc,
)


def test_create_local_upload_accepts_zip_and_returns_source_metadata(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.post(
        "/api/local-uploads",
        headers={"X-TCI-Operator-Id": "operator-a"},
        files={
            "file": (
                "/private/tmp/team-project.zip?token=secret",
                build_project_zip(),
                "application/zip",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["workspaceId"] == str(workspace_id)
    assert payload["sourceKind"] == "local_upload"
    assert payload["status"] == "succeeded"
    assert payload["originalFilename"] == "team-project.zip"
    assert payload["uploadedBy"] == "operator-a"
    assert payload["uploadedAt"] == payload["createdAt"]
    assert payload["fileCount"] == 3
    assert payload["uncompressedSizeBytes"] > 0
    assert payload["latestSnapshotId"] is not None
    assert payload["failureCode"] is None
    assert payload["failureMessage"] is None
    assert "token=secret" not in response.text


def test_create_local_upload_queues_task_when_redis_is_configured(
    monkeypatch, tmp_path
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    settings = cast(Any, client.app).state.settings
    object.__setattr__(settings, "redis_url", "redis://example")
    sent_task: dict[str, object] = {}

    class FakeCeleryApp:
        def send_task(self, task_name: str, *, kwargs: dict[str, str]) -> None:
            sent_task["task_name"] = task_name
            sent_task["kwargs"] = kwargs

    import tci.api.routes.local_uploads as local_upload_routes

    monkeypatch.setattr(
        local_upload_routes,
        "create_celery_app",
        lambda settings: FakeCeleryApp(),
    )

    zip_bytes = build_project_zip()
    response = client.post(
        "/api/local-uploads",
        files={"file": ("project.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["latestSnapshotId"] is None
    assert sent_task == {
        "task_name": "tci.repository_ingestion.run_local_upload_snapshot",
        "kwargs": {
            "workspace_id": str(workspace_id),
            "local_upload_id": payload["id"],
        },
    }
    temp_path = settings.runtime_root / "local-upload-queue" / f"{payload['id']}.zip"
    assert temp_path.read_bytes() == zip_bytes
    assert S_IMODE(temp_path.stat().st_mode) == 0o600
    assert store.snapshots == {}


def test_create_local_upload_marks_failed_when_queue_staging_fails(
    monkeypatch, tmp_path
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    settings = cast(Any, client.app).state.settings
    object.__setattr__(settings, "redis_url", "redis://example")
    sent_task: dict[str, object] = {}

    class FakeCeleryApp:
        def send_task(self, task_name: str, *, kwargs: dict[str, str]) -> None:
            sent_task["task_name"] = task_name
            sent_task["kwargs"] = kwargs

    import tci.api.routes.local_uploads as local_upload_routes

    monkeypatch.setattr(
        local_upload_routes,
        "create_celery_app",
        lambda settings: FakeCeleryApp(),
    )
    monkeypatch.setattr(
        local_upload_routes,
        "_write_temp_zip_for_queue",
        lambda **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    response = client.post(
        "/api/local-uploads",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
    )

    upload = _only_upload(store)
    assert response.status_code == 503
    assert response.json() == {
        "code": "queue_staging_failed",
        "message": "Local Upload 처리 파일을 준비하지 못했습니다.",
        "remediationAction": "retry_upload",
    }
    assert upload.status.value == "failed"
    assert upload.failure_code == "queue_staging_failed"
    assert upload.latest_snapshot_id is None
    assert sent_task == {}
    assert store.snapshots == {}


def test_get_local_upload_returns_status_and_latest_snapshot(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    upload_id = _create_upload(client, filename="project.zip")

    response = client.get(f"/api/local-uploads/{upload_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == upload_id
    assert payload["workspaceId"] == str(workspace_id)
    assert payload["sourceKind"] == "local_upload"
    assert payload["status"] == "succeeded"
    assert payload["latestSnapshotId"] is not None


def test_get_local_upload_snapshot_returns_tree_and_local_source(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    upload_id = _create_upload(client, filename="project.zip")
    upload = store.local_uploads[uuid.UUID(upload_id)]
    snapshot_id = str(upload.latest_snapshot_id)

    response = client.get(f"/api/local-uploads/{upload_id}/snapshots/{snapshot_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == snapshot_id
    assert payload["workspaceId"] == str(workspace_id)
    assert payload["connectionId"] is None
    assert payload["source"] == {
        "kind": "local_upload",
        "localUploadId": upload_id,
        "originalFilename": "project.zip",
        "uploadedBy": "operator",
        "uploadedAt": upload.created_at.isoformat(),
    }
    assert payload["traceability"] == {
        "sourceKind": "local_upload",
        "localUploadId": upload_id,
        "workspaceId": str(workspace_id),
        "planningInputReference": None,
    }
    assert [item["path"] for item in payload["files"]] == [
        "project/.env.example",
        "project/README.md",
        "project/src/main.py",
    ]


def test_create_local_upload_rejects_corrupt_zip_without_active_snapshot(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.post(
        "/api/local-uploads",
        files={"file": ("broken.zip", build_corrupt_zip(), "application/zip")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "invalid_zip",
        "message": "ZIP 파일을 읽을 수 없습니다.",
        "remediationAction": "upload_valid_zip",
    }
    assert store.snapshots == {}
    assert _only_upload(store).latest_snapshot_id is None
    assert _only_upload(store).status.value == "failed"


def test_create_local_upload_reports_allowed_limits_for_limit_failure(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    settings = cast(Any, client.app).state.settings
    object.__setattr__(settings, "local_upload_max_file_bytes", 5)

    response = client.post(
        "/api/local-uploads",
        files={
            "file": (
                "too-large.zip",
                build_zip_bytes((ZipFixtureEntry("big.txt", b"too large"),)),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "zip_limit_exceeded"
    assert payload["remediationAction"] == "reduce_zip_size"
    assert payload["allowedLimits"]["maxFileBytes"] == 5
    assert payload["allowedLimits"]["maxFileCount"] > 0
    assert "다시 업로드" in payload["message"]
    assert store.snapshots == {}


def test_create_local_upload_rejects_oversized_multipart_body_before_row(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    settings = cast(Any, client.app).state.settings
    object.__setattr__(settings, "local_upload_max_compressed_bytes", 1)

    response = client.post(
        "/api/local-uploads",
        files={"file": ("too-large.zip", b"x" * 70_000, "application/zip")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "zip_limit_exceeded"
    assert response.json()["allowedLimits"]["maxCompressedBytes"] == 1
    assert store.local_uploads == {}
    assert store.snapshots == {}


def test_create_local_upload_cookie_auth_rejects_cross_origin_post(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    settings = cast(Any, client.app).state.settings
    client.cookies.set(
        "tci_operator_token",
        create_operator_session_cookie(expected_token=settings.operator_api_token),
    )

    response = client.post(
        "/api/local-uploads",
        headers={"Origin": "https://evil.example"},
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "invalid_request",
        "message": "허용되지 않은 요청 출처입니다.",
        "remediationAction": "none",
    }
    assert store.local_uploads == {}
    assert store.snapshots == {}


def test_create_local_upload_cookie_auth_rejects_missing_origin_post(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Operator-Token")
    settings = cast(Any, client.app).state.settings
    client.cookies.set(
        "tci_operator_token",
        create_operator_session_cookie(expected_token=settings.operator_api_token),
    )

    response = client.post(
        "/api/local-uploads",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "invalid_request"
    assert store.local_uploads == {}
    assert store.snapshots == {}


def test_local_upload_routes_require_workspace_header(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Workspace-Id")

    response = client.post(
        "/api/local-uploads",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
    }


def _create_upload(client, *, filename: str) -> str:
    response = client.post(
        "/api/local-uploads",
        files={"file": (filename, build_project_zip(), "application/zip")},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _seed_active_workspace(store, *, workspace_id: uuid.UUID) -> None:
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE,
        created_at=now_utc(),
        updated_at=now_utc(),
    )


def _only_upload(store):
    assert len(store.local_uploads) == 1
    return next(iter(store.local_uploads.values()))
