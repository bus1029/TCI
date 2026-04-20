from __future__ import annotations

import uuid
from types import SimpleNamespace

from tci.infrastructure.persistence.models import RepositoryConnectionStatus
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)


def test_create_connection_rejects_unsupported_provider(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_cloud",
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "UNSUPPORTED_PROVIDER",
        "message": "v1에서는 GitHub Cloud 저장소만 지원합니다.",
    }


def test_repository_connection_routes_require_workspace_header(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    client.headers.pop("X-TCI-Workspace-Id")

    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
    }


def test_get_connection_detail_returns_null_last_processed_event_and_traceability(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    assert detail_response.json() == {
        "id": connection_id,
        "provider": "github_cloud",
        "remoteUrl": "https://github.com/acme/sample-repo.git",
        "transport": "https",
        "defaultRefType": "branch",
        "defaultRefName": "main",
        "status": "active",
        "lastVerifiedAt": create_response.json()["lastVerifiedAt"],
        "lastSuccessfulSnapshotAt": None,
        "lastFailedSyncAt": None,
        "lastProcessedEventAt": None,
        "lastProcessedEvent": None,
        "latestSnapshot": None,
        "latestSyncRun": None,
        "traceability": {
            "planningInputReference": {
                "id": str(reference.id),
                "sourceType": "user_request",
                "sourceReference": "chat://test",
                "approvedSpecPath": "specs/001-git-repo-connection/spec.md",
                "approvedPlanPath": "specs/001-git-repo-connection/plan.md",
            },
            "activeScopeRuleVersionId": None,
            "latestEventId": None,
            "latestSnapshotId": None,
        },
        "additionalRefGuidance": {
            "message": "이 연결은 기본 ref 1개만 지원합니다.",
            "options": [
                {
                    "action": "create_new_connection",
                    "label": "새 연결 생성",
                },
                {
                    "action": "replace_default_ref",
                    "label": "기본 ref 교체",
                },
            ],
        },
    }


def test_patch_connection_updates_default_ref(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={
            "defaultRefType": "branch",
            "defaultRefName": "release/2026.04",
        },
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["defaultRefName"] == "release/2026.04"
    assert patch_response.json()["status"] == "active"


def test_verify_connection_returns_accepted_response(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    verify_response = client.post(f"/api/repository-connections/{connection_id}/verify")

    assert verify_response.status_code == 503
    assert verify_response.json() == {
        "detail": "검증 작업 큐가 설정되지 않았습니다.",
    }


def test_verify_connection_enqueues_workspace_scoped_task_when_redis_is_enabled(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    captured: dict[str, object] = {}

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_connections.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    verify_response = client.post(f"/api/repository-connections/{connection_id}/verify")

    assert verify_response.status_code == 202
    assert captured == {
        "name": "tci.repository_ingestion.verify_repository_connection",
        "kwargs": {
            "workspace_id": str(workspace_id),
            "connection_id": connection_id,
        },
    }


def test_create_snapshot_requires_queue_configuration(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 503
    assert snapshot_response.json() == {
        "detail": "스냅샷 작업 큐가 설정되지 않았습니다.",
    }


def test_create_snapshot_returns_not_found_before_queue_check(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    snapshot_response = client.post(
        f"/api/repository-connections/{uuid.uuid4()}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 404
    assert snapshot_response.json() == {"detail": "저장소 연결을 찾을 수 없습니다."}


def test_create_snapshot_enqueues_workspace_scoped_task_when_redis_is_enabled(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    captured: dict[str, object] = {}

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 202
    assert snapshot_response.json()["status"] == "sync_queued"
    assert uuid.UUID(snapshot_response.json()["syncRunId"])
    assert captured["name"] == "tci.repository_ingestion.run_manual_snapshot_sync"
    assert captured["kwargs"]["workspace_id"] == str(workspace_id)
    assert captured["kwargs"]["connection_id"] == connection_id
    assert uuid.UUID(captured["kwargs"]["sync_run_id"])


def test_create_snapshot_defaults_to_manual_initial_when_body_is_missing(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    captured: dict[str, object] = {}

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    def fake_send_task(name: str, kwargs: dict[str, str]) -> None:
        captured["name"] = name
        captured["kwargs"] = kwargs

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: SimpleNamespace(send_task=fake_send_task),
    )

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
    )

    assert snapshot_response.status_code == 202
    assert snapshot_response.json()["status"] == "sync_queued"
    assert captured["name"] == "tci.repository_ingestion.run_manual_snapshot_sync"


def test_create_snapshot_cleans_up_pending_run_when_enqueue_fails(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: SimpleNamespace(
            send_task=lambda name, kwargs: (_ for _ in ()).throw(RuntimeError("broker down"))
        ),
    )

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 503
    assert snapshot_response.json() == {
        "detail": "스냅샷 작업 큐에 연결할 수 없습니다."
    }
    assert store.sync_runs == {}


def test_create_snapshot_rejects_invalid_reason_with_problem_response(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "bad_reason"},
    )

    assert snapshot_response.status_code == 400
    assert snapshot_response.json() == {
        "code": "INVALID_INPUT",
        "message": "reason은 manual_initial 또는 manual_refresh여야 합니다.",
    }


def test_create_snapshot_rejects_empty_reason_with_validation_error(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = create_response.json()["id"]

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": ""},
    )

    assert snapshot_response.status_code == 422


def test_create_snapshot_returns_conflict_for_reauth_required_connection(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.connections[connection_id].status = RepositoryConnectionStatus.REAUTH_REQUIRED

    snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )

    assert snapshot_response.status_code == 409
    assert snapshot_response.json() == {
        "code": "CONNECTION_AUTH_FAILED",
        "message": "재인증이 필요한 연결은 새 스냅샷을 시작할 수 없습니다.",
    }
