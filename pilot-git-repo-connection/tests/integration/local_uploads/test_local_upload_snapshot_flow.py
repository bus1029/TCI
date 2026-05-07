from __future__ import annotations

import json
import uuid
from typing import Any, cast

from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus
from tests.support.local_upload_testkit import (
    ZipFixtureEntry,
    build_project_zip,
    build_zip_bytes,
)
from tests.support.repository_connection_testkit import create_test_client, now_utc


def test_valid_root_folder_zip_creates_snapshot_detail_tree(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    upload = _post_zip(client, filename="project.zip", zip_bytes=build_project_zip())
    snapshot = store.snapshots[uuid.UUID(cast(str, upload["latestSnapshotId"]))]
    detail = client.get(
        f"/api/local-uploads/{upload['id']}/snapshots/{snapshot.id}"
    ).json()

    assert upload["status"] == "succeeded"
    assert upload["fileCount"] == 3
    assert detail["source"]["kind"] == "local_upload"
    assert [item["path"] for item in detail["files"]] == [
        "project/.env.example",
        "project/README.md",
        "project/src/main.py",
    ]


def test_nested_zip_hidden_files_and_empty_directories_are_preserved(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    zip_bytes = build_zip_bytes(
        (
            ZipFixtureEntry("project/docs/empty/", is_directory=True),
            ZipFixtureEntry("project/src/nested/main.py", b"print('hello')\n"),
            ZipFixtureEntry("project/.hidden", b"hidden\n"),
        )
    )

    upload = _post_zip(client, filename="nested.zip", zip_bytes=zip_bytes)
    snapshot = store.snapshots[uuid.UUID(cast(str, upload["latestSnapshotId"]))]
    detail = client.get(
        f"/api/local-uploads/{upload['id']}/snapshots/{snapshot.id}"
    ).json()
    manifest = json.loads(
        (
            cast(Any, client.app).state.settings.project_root
            / snapshot.archive_path
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert [item["path"] for item in detail["files"]] == [
        "project/.hidden",
        "project/src/nested/main.py",
    ]
    assert manifest["source"]["directories"] == [
        "project",
        "project/docs",
        "project/docs/empty",
        "project/src",
        "project/src/nested",
    ]
    assert upload["directoryCount"] == 5


def test_three_repeated_uploads_create_independent_snapshots_and_latest_default(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    uploads = [
        _post_zip(
            client,
            filename=f"project-{index}.zip",
            zip_bytes=build_zip_bytes(
                (ZipFixtureEntry(f"project/file-{index}.txt", str(index).encode()),)
            ),
        )
        for index in range(3)
    ]

    snapshot_ids = [upload["latestSnapshotId"] for upload in uploads]
    latest_response = client.get(f"/api/local-uploads/{uploads[-1]['id']}")

    assert len(set(snapshot_ids)) == 3
    assert len(store.snapshots) == 3
    assert latest_response.json()["latestSnapshotId"] == snapshot_ids[-1]


def test_operator_local_upload_page_shows_form_status_and_latest_snapshot(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)
    upload = _post_zip(client, filename="project.zip", zip_bytes=build_project_zip())

    response = client.get(f"/local-uploads?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "Local Upload" in response.text
    assert "project.zip" in response.text
    assert str(upload["latestSnapshotId"]) in response.text
    assert "succeeded" in response.text


def test_operator_local_upload_form_uploads_zip_and_redirects_to_status(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    _seed_active_workspace(store, workspace_id=workspace_id)

    response = client.post(
        f"/local-uploads?workspaceId={workspace_id}",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    upload = next(iter(store.local_uploads.values()))
    assert response.headers["location"] == (
        f"/local-uploads/{upload.id}?workspaceId={workspace_id}"
    )
    status_response = client.get(response.headers["location"])
    assert status_response.status_code == 200
    assert str(upload.latest_snapshot_id) in status_response.text


def test_operator_local_upload_form_queues_when_redis_is_configured(
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

    import tci.web.routes.local_uploads as local_upload_web_routes

    monkeypatch.setattr(
        local_upload_web_routes,
        "create_celery_app",
        lambda settings: FakeCeleryApp(),
    )

    response = client.post(
        f"/local-uploads?workspaceId={workspace_id}",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
        follow_redirects=False,
    )

    upload = next(iter(store.local_uploads.values()))
    assert response.status_code == 303
    assert upload.status.value == "pending"
    assert upload.latest_snapshot_id is None
    assert sent_task == {
        "task_name": "tci.repository_ingestion.run_local_upload_snapshot",
        "kwargs": {
            "workspace_id": str(workspace_id),
            "local_upload_id": str(upload.id),
        },
    }
    assert store.snapshots == {}


def test_operator_local_upload_form_marks_failed_when_queue_staging_fails(
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

    import tci.web.routes.local_uploads as local_upload_web_routes

    monkeypatch.setattr(
        local_upload_web_routes,
        "create_celery_app",
        lambda settings: FakeCeleryApp(),
    )
    monkeypatch.setattr(
        local_upload_web_routes,
        "_write_temp_zip_for_queue",
        lambda **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    response = client.post(
        f"/local-uploads?workspaceId={workspace_id}",
        files={"file": ("project.zip", build_project_zip(), "application/zip")},
        follow_redirects=False,
    )

    upload = next(iter(store.local_uploads.values()))
    assert response.status_code == 503
    assert "Local Upload 처리 파일을 준비하지 못했습니다." in response.text
    assert upload.status.value == "failed"
    assert upload.failure_code == "queue_staging_failed"
    assert upload.latest_snapshot_id is None
    assert sent_task == {}
    assert store.snapshots == {}


def _post_zip(client, *, filename: str, zip_bytes: bytes) -> dict[str, object]:
    response = client.post(
        "/api/local-uploads",
        files={"file": (filename, zip_bytes, "application/zip")},
    )
    assert response.status_code == 201
    return response.json()


def _seed_active_workspace(store, *, workspace_id: uuid.UUID) -> None:
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
