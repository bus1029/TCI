from __future__ import annotations

import hashlib
from collections.abc import Sequence
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy.engine import make_url

from tci.infrastructure.persistence.credential_revision_repository import (
    CredentialRevisionRepository,
)
from tci.infrastructure.persistence.planning_input_reference_repository import (
    PlanningInputReferenceRepository,
)
from tci.infrastructure.persistence.repository_connection_repository import (
    RepositoryConnectionRepository,
)
from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitRefResolver
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_obsolete_planning_connection_payload,
    create_planning_input_reference_payload,
    create_test_client,
    seed_planning_input_reference,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _upgrade_test_database_to_head(database_url: str) -> None:
    if os.getenv("TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS") != "1":
        pytest.skip("명시적 승인 없이 실DB 마이그레이션 테스트를 실행하지 않습니다.")
    if os.getenv("TCI_MIGRATION_TEST_DATABASE_URL_ACK") != database_url:
        pytest.skip("실DB 마이그레이션 테스트는 전체 DSN 확인값이 필요합니다.")
    expected_database_name = os.getenv("TCI_MIGRATION_TEST_DATABASE_NAME")
    if not expected_database_name:
        pytest.skip(
            "실DB 마이그레이션 테스트는 전용 데이터베이스 이름 확인값이 필요합니다."
        )
    database_name = make_url(database_url).database or ""
    if database_name != expected_database_name:
        pytest.skip(
            "TCI_MIGRATION_TEST_DATABASE_URL이 승인된 전용 데이터베이스가 아닙니다."
        )

    env = os.environ.copy()
    env["TCI_DATABASE_URL"] = database_url
    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "downgrade", "base"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert downgrade.returncode == 0, downgrade.stderr
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgrade.returncode == 0, upgrade.stderr


def test_create_connection_with_readonly_credential_creates_active_connection(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["provider"] == "github_cloud"
    assert payload["transport"] == "https"
    assert payload["defaultRefType"] == "branch"
    assert payload["defaultRefName"] == "main"
    assert payload["status"] == "active"
    assert payload["lastVerifiedAt"] is not None


def test_planning_input_reference_create_bootstraps_connection_creation_from_api(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    reference_response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(
            workspace_id=workspace_id,
            source_reference="chat://test",
        ),
    )
    reference_id = uuid.UUID(reference_response.json()["id"])
    connection_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )

    assert reference_response.status_code == 201
    assert reference_id in store.planning_input_references
    assert connection_response.status_code == 201
    assert connection_response.json()["status"] == "active"


@pytest.mark.integration
def test_planning_input_reference_create_bootstraps_connection_creation_with_real_db(
    tmp_path,
) -> None:
    database_url = os.getenv("TCI_MIGRATION_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TCI_MIGRATION_TEST_DATABASE_URL이 없어 실DB bootstrap 테스트를 건너뜁니다."
        )
    _upgrade_test_database_to_head(database_url)

    workspace_id = uuid.uuid4()
    client, _store = create_test_client(
        tmp_path=tmp_path,
        workspace_id=workspace_id,
        use_real_repositories=True,
        database_url=database_url,
    )

    reference_response = client.post(
        "/api/planning-input-references",
        json=create_planning_input_reference_payload(
            workspace_id=workspace_id,
            source_reference="chat://test",
        ),
    )
    assert reference_response.status_code == 201
    reference_payload = reference_response.json()
    reference_id = uuid.UUID(reference_payload["id"])
    connection_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )

    assert reference_payload == {
        "id": str(reference_id),
        "workspaceId": str(workspace_id),
        "sourceType": "user_request",
        "sourceTitle": "저장소 연결 준비",
        "sourceReference": "chat://test",
        "approvedSpecPath": "specs/001-git-repo-connection/spec.md",
        "approvedPlanPath": "specs/001-git-repo-connection/plan.md",
        "createdAt": reference_payload["createdAt"],
    }
    assert reference_payload["createdAt"] is not None
    assert connection_response.status_code == 201
    connection_payload = connection_response.json()
    connection_id = uuid.UUID(connection_payload["id"])
    assert connection_payload["status"] == "active"

    with client.app.state.dependencies.session_factory() as session:
        planning_reference = PlanningInputReferenceRepository(session).get(
            workspace_id=workspace_id,
            reference_id=reference_id,
        )
        connection = RepositoryConnectionRepository(session).get(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        credential = CredentialRevisionRepository(session).get_active_for_connection(
            connection_id=connection_id
        )

    assert planning_reference is not None
    assert connection is not None
    assert credential is not None


def test_connection_detail_exposes_traceability_and_placeholder_summaries(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]

    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["traceability"]["planningInputReference"] is None
    assert detail["origin"]["kind"] == "workspace_repository"
    assert detail["traceability"]["latestSnapshotId"] is None
    assert detail["lastSuccessfulSnapshotAt"] is None
    assert detail["lastFailedSyncAt"] is None
    assert detail["lastProcessedEvent"] is None
    assert detail["latestSnapshot"] is None


def test_default_ref_change_updates_future_target_without_erasing_existing_state(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={"defaultRefType": "branch", "defaultRefName": "release/hotfix"},
    )
    detail_response = client.get(f"/api/repository-connections/{connection_id}")

    assert patch_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.json()["defaultRefName"] == "release/hotfix"
    assert detail_response.json()["lastSuccessfulSnapshotAt"] is None
    assert detail_response.json()["traceability"]["latestSnapshotId"] is None


def test_default_ref_change_reuses_stored_credential_for_ref_validation(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]
    store.resolver_requires_bound_credential = True
    store.last_resolved_remote_url = None

    patch_response = client.patch(
        f"/api/repository-connections/{connection_id}",
        json={"defaultRefType": "branch", "defaultRefName": "release/secured"},
    )

    assert patch_response.status_code == 200
    assert store.last_resolved_remote_url == "https://github.com/acme/sample-repo.git"


def test_candidate_selected_connection_reuses_manual_duplicate_precheck(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    manual_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    assert manual_response.status_code == 201
    store.last_resolved_remote_url = None

    candidate_payload = create_connection_payload()
    candidate_payload["candidateId"] = "github:acme/sample-repo"
    duplicate_response = client.post(
        "/api/repository-connections",
        json=candidate_payload,
    )

    assert duplicate_response.status_code == 400
    assert duplicate_response.json() == {
        "code": "INVALID_INPUT",
        "message": "Repository connection already exists for this workspace.",
    }
    assert store.last_resolved_remote_url is None


def test_github_duplicate_precheck_normalizes_repository_path_case(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    mixed_case_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            remote_url="https://github.com/Acme/Sample-Repo.git",
        ),
    )
    assert mixed_case_response.status_code == 201
    store.last_resolved_remote_url = None

    duplicate_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            remote_url="https://github.com/acme/sample-repo.git",
        ),
    )

    assert duplicate_response.status_code == 400
    assert duplicate_response.json() == {
        "code": "INVALID_INPUT",
        "message": "Repository connection already exists for this workspace.",
    }
    assert store.last_resolved_remote_url is None


def test_gitlab_duplicate_precheck_normalizes_default_https_port(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    default_port_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com:443/group/sample-repo.git",
        ),
    )
    assert default_port_response.status_code == 201
    store.last_resolved_remote_url = None

    duplicate_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )

    assert duplicate_response.status_code == 400
    assert duplicate_response.json() == {
        "code": "INVALID_INPUT",
        "message": "Repository connection already exists for this workspace.",
    }
    assert store.last_resolved_remote_url is None


def test_verify_endpoint_accepts_known_connection_for_followup_worker_execution(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = create_response.json()["id"]

    verify_response = client.post(f"/api/repository-connections/{connection_id}/verify")

    assert verify_response.status_code == 503
    assert verify_response.json() == {
        "detail": "검증 작업 큐가 설정되지 않았습니다.",
    }


def test_create_connection_rejects_planning_input_from_other_workspace(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=other_workspace_id)

    response = client.post(
        "/api/repository-connections",
        json=create_obsolete_planning_connection_payload(
            planning_input_reference_id=reference.id,
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "새 저장소 연결 생성 요청은 planning/spec/plan 참조 필드를 받을 수 없습니다.",
    }


def test_create_connection_validation_error_does_not_echo_secret(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)

    response = client.post(
        "/api/repository-connections",
        json={
            "provider": "github_cloud",
            "remoteUrl": "https://github.com/acme/sample-repo.git",
            "transport": "https",
            "defaultRefType": "branch",
            "defaultRefName": "main",
            "credential": {
                "type": "https_pat",
                "secret": "",
                "fingerprint": "top-secret-fingerprint",
            },
        },
    )

    assert response.status_code == 422
    assert "top-secret-fingerprint" not in response.text


def test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot(
    tmp_path,
) -> None:
    from tci.domain.services.build_code_snapshot import (
        BuildCodeSnapshotCommand,
        build_code_snapshot,
    )
    from tci.domain.services.create_initial_snapshot import (
        CreateInitialSnapshotCommand,
        create_initial_snapshot,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=client.app.state.dependencies,
    )
    pending_detail_response = client.get(f"/api/repository-connections/{connection_id}")
    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=client.app.state.dependencies,
    )

    assert pending_detail_response.status_code == 200
    pending_detail = pending_detail_response.json()
    assert pending_detail["latestSyncRun"]["id"] == str(sync_run.id)
    assert pending_detail["latestSyncRun"]["status"] == "pending"
    assert pending_detail["latestSyncRun"]["requestedRefType"] == "branch"
    assert pending_detail["latestSyncRun"]["requestedRefName"] == "main"
    assert pending_detail["latestSyncRun"]["resolvedCommitSha"] is None
    assert pending_detail["latestSyncRun"]["failureCode"] is None
    assert pending_detail["latestSyncRun"]["failureMessage"] is None
    assert pending_detail["latestSyncRun"]["startedAt"] is not None
    assert pending_detail["latestSyncRun"]["completedAt"] is None

    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    snapshot_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{snapshot.id}"
    )

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["lastSuccessfulSnapshotAt"] is not None
    assert detail["lastFailedSyncAt"] is None
    assert detail["lastProcessedEvent"] is None
    assert detail["latestSnapshot"] == {
        "id": str(snapshot.id),
        "requestedRefType": "branch",
        "requestedRefName": "main",
        "resolvedCommitSha": "a" * 40,
        "createdAt": snapshot.created_at.isoformat(),
    }
    assert detail["latestSyncRun"]["id"] == str(sync_run.id)
    assert detail["latestSyncRun"]["status"] == "succeeded"
    assert detail["latestSyncRun"]["requestedRefType"] == "branch"
    assert detail["latestSyncRun"]["requestedRefName"] == "main"
    assert detail["latestSyncRun"]["resolvedCommitSha"] == "a" * 40
    assert detail["latestSyncRun"]["failureCode"] is None
    assert detail["latestSyncRun"]["failureMessage"] is None
    assert detail["latestSyncRun"]["startedAt"] is not None
    assert detail["latestSyncRun"]["completedAt"] is not None
    assert detail["traceability"]["latestSnapshotId"] == str(snapshot.id)

    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()
    assert snapshot_payload["connectionId"] == str(connection_id)
    assert snapshot_payload["syncRunId"] == str(sync_run.id)
    assert snapshot_payload["files"] == [
        {
            "path": "src/main.py",
            "extension": ".py",
            "languageHint": None,
            "sizeBytes": len(b"print('hello')\n"),
            "contentSha256": hashlib.sha256(b"print('hello')\n").hexdigest(),
            "archiveBlobPath": "src/main.py",
            "includedBy": "default_policy",
        }
    ]
    assert snapshot_payload["traceability"]["planningInputReference"] is None
    assert (
        snapshot_payload["scopeRuleVersionId"]
        == detail["traceability"]["activeScopeRuleVersionId"]
    )


def test_snapshot_build_uses_requested_ref_captured_when_sync_run_was_created(
    tmp_path,
) -> None:
    from tci.domain.services.build_code_snapshot import (
        BuildCodeSnapshotCommand,
        build_code_snapshot,
    )
    from tci.domain.services.create_initial_snapshot import (
        CreateInitialSnapshotCommand,
        create_initial_snapshot,
    )
    from tci.domain.services.update_default_ref import (
        UpdateDefaultRefCommand,
        update_default_ref,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=client.app.state.dependencies,
    )

    update_default_ref(
        UpdateDefaultRefCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            default_ref_type="branch",
            default_ref_name="release/next",
        ),
        dependencies=client.app.state.dependencies,
    )
    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=client.app.state.dependencies,
    )

    assert snapshot.requested_ref_name == "main"


def test_snapshot_build_with_real_git_ref_resolver_treats_sync_run_branch_as_branch(
    tmp_path,
) -> None:
    from tci.domain.services.build_code_snapshot import (
        BuildCodeSnapshotCommand,
        build_code_snapshot,
    )
    from tci.domain.services.create_initial_snapshot import (
        CreateInitialSnapshotCommand,
        create_initial_snapshot,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    captured_commands: list[Sequence[str]] = []

    def runner(command: Sequence[str]) -> GitCommandResult:
        captured_commands.append(command)
        assert command[-1] == "refs/heads/main"
        return GitCommandResult(
            returncode=0,
            stdout="c" * 40 + "\trefs/heads/main\n",
            stderr="",
        )

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=client.app.state.dependencies,
    )

    object.__setattr__(
        client.app.state.dependencies,
        "git_ref_resolver",
        GitRefResolver(runner=runner),
    )
    store.mirror_snapshot_entries = (("src/main.py", b"print('branch')\n"),)
    snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=client.app.state.dependencies,
    )

    assert snapshot.requested_ref_name == "main"
    assert snapshot.resolved_commit_sha == "c" * 40
    assert captured_commands
    assert all("refs/tags/main" not in command for command in captured_commands)


def test_snapshot_build_cleans_up_archive_when_manifest_write_fails(tmp_path) -> None:
    from tci.domain.services.build_code_snapshot import (
        BuildCodeSnapshotCommand,
        build_code_snapshot,
    )
    from tci.domain.services.create_initial_snapshot import (
        CreateInitialSnapshotCommand,
        create_initial_snapshot,
    )
    from tci.domain.services.repository_connection_support import (
        RepositoryConnectionProblem,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=client.app.state.dependencies,
    )

    class FailingManifestWriter:
        def write(self, *, archive, traceability):
            raise OSError("manifest write failed")

    object.__setattr__(
        client.app.state.dependencies,
        "snapshot_manifest_writer",
        FailingManifestWriter(),
    )

    with pytest.raises(RepositoryConnectionProblem, match="manifest write failed"):
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=client.app.state.dependencies,
        )

    snapshot_directories = [
        path
        for path in client.app.state.settings.code_snapshot_root.iterdir()
        if path.is_dir()
    ]
    assert snapshot_directories == []
    assert store.sync_runs[sync_run.id].status.value == "failed"
    assert store.connections[connection_id].last_failed_sync_at is not None


def test_snapshot_build_reuses_existing_result_for_succeeded_sync_run(tmp_path) -> None:
    from tci.domain.services.build_code_snapshot import (
        BuildCodeSnapshotCommand,
        build_code_snapshot,
    )
    from tci.domain.services.create_initial_snapshot import (
        CreateInitialSnapshotCommand,
        create_initial_snapshot,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=client.app.state.dependencies,
    )

    first_snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=client.app.state.dependencies,
    )
    second_snapshot = build_code_snapshot(
        BuildCodeSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            sync_run_id=sync_run.id,
        ),
        dependencies=client.app.state.dependencies,
    )

    assert first_snapshot.id == second_snapshot.id
