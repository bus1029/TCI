from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

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
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.verify_repository_connection import (
    VerifyRepositoryConnectionCommand,
    verify_repository_connection,
)
from tci.infrastructure.persistence.models import RepositoryConnectionStatus


pytestmark = pytest.mark.integration


def _settings(client) -> Any:
    return cast(Any, client.app).state.settings


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_gitlab_ssh_custom_port_scope_preview_and_snapshot_build_share_allowlist(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20:2222",),
    )

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="ssh://git@192.168.10.20:2222/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret=(
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                "key\n"
                "-----END OPENSSH PRIVATE KEY-----"
            ),
            credential_fingerprint="ssh-custom-port",
        ),
    )
    assert create_response.status_code == 201
    connection_id = uuid.UUID(create_response.json()["id"])

    verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )
    scope_response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["src/**"],
            "excludePaths": [],
            "allowedFileTypes": [".py"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5242880,
        },
    )
    assert scope_response.status_code == 200
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

    assert snapshot.file_count == 1
    assert store.last_resolved_remote_url == (
        "ssh://git@192.168.10.20:2222/group/sample-repo.git"
    )


def test_gitlab_ssh_custom_port_requires_port_allowlist_for_each_git_access_path(
    tmp_path, monkeypatch
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20:2222",),
    )
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="ssh://git@192.168.10.20:2222/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret=(
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                "key\n"
                "-----END OPENSSH PRIVATE KEY-----"
            ),
            credential_fingerprint="ssh-custom-port",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20",),
    )

    def fail_if_git_facing_helper_runs(*args, **kwargs):
        raise AssertionError("allowlist rejection should happen before git helpers")

    monkeypatch.setattr(
        _dependencies(client).git_readonly_validator,
        "probe",
        fail_if_git_facing_helper_runs,
    )
    monkeypatch.setattr(
        _dependencies(client).git_mirror_manager,
        "ensure_synced_mirror",
        fail_if_git_facing_helper_runs,
    )

    for path_name, call in (
        (
            "verify",
            lambda: verify_repository_connection(
                VerifyRepositoryConnectionCommand(
                    workspace_id=workspace_id,
                    connection_id=connection_id,
                ),
                dependencies=_dependencies(client),
            ),
        ),
        (
            "scope_preview",
            lambda: client.post(
                f"/api/repository-connections/{connection_id}/scope-rules",
                json={
                    "includePaths": ["src/**"],
                    "excludePaths": [],
                    "allowedFileTypes": [".py"],
                    "blockedFileTypes": [],
                    "maxFileSizeBytes": 5242880,
                },
            ),
        ),
        (
            "snapshot_build",
            lambda: build_code_snapshot(
                BuildCodeSnapshotCommand(
                    workspace_id=workspace_id,
                    connection_id=connection_id,
                    sync_run_id=sync_run.id,
                ),
                dependencies=_dependencies(client),
            ),
        ),
    ):
        store.last_resolved_remote_url = None
        try:
            result = call()
        except RepositoryConnectionProblem as error:
            assert (
                error.detail
                == "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다."
            )
        else:
            assert path_name == "scope_preview"
            assert result.status_code == 400
            assert result.json() == {
                "code": "INVALID_INPUT",
                "message": "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
            }
        assert store.last_resolved_remote_url is None


def test_gitlab_ssh_custom_port_snapshot_failure_records_failed_sync_run(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20:2222",),
    )
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="ssh://git@192.168.10.20:2222/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret=(
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                "key\n"
                "-----END OPENSSH PRIVATE KEY-----"
            ),
            credential_fingerprint="ssh-custom-port",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20",),
    )
    store.last_resolved_remote_url = None

    with pytest.raises(RepositoryConnectionProblem) as error_info:
        build_code_snapshot(
            BuildCodeSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                sync_run_id=sync_run.id,
            ),
            dependencies=_dependencies(client),
        )

    assert (
        error_info.value.detail
        == "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다."
    )
    assert store.last_resolved_remote_url is None
    assert store.sync_runs[sync_run.id].status.value == "failed"


@pytest.mark.parametrize(
    ("status", "expected_message"),
    [
        (
            RepositoryConnectionStatus.REAUTH_REQUIRED,
            "재인증이 필요한 연결은 새 스냅샷을 시작할 수 없습니다.",
        ),
        (
            RepositoryConnectionStatus.REF_MISSING,
            "기본 ref가 유효하지 않아 새 스냅샷을 시작할 수 없습니다.",
        ),
    ],
)
def test_gitlab_action_required_status_blocks_manual_snapshot_collection(
    tmp_path, status, expected_message: str
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.connections[connection_id].status = status

    with pytest.raises(RepositoryConnectionProblem) as error_info:
        create_initial_snapshot(
            CreateInitialSnapshotCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=_dependencies(client),
        )

    assert error_info.value.detail == expected_message
