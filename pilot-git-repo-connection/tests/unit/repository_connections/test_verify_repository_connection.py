from __future__ import annotations

import uuid

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    create_test_ssh_private_key,
    seed_planning_input_reference,
)
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.workspace_lifecycle import WorkspaceLifecycleProblem
from tci.domain.services.verify_repository_connection import (
    VerifyRepositoryConnectionCommand,
    verify_repository_connection,
)
from tci.infrastructure.persistence.models import WorkspaceStatus


def test_verify_repository_connection_keeps_active_status_when_stored_credential_is_valid(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    dependencies = client.app.state.dependencies

    verified = verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )

    assert verified.status.value == "active"
    assert verified.last_verified_at is not None


def test_verify_repository_connection_marks_reauth_required_on_auth_failure(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    dependencies = client.app.state.dependencies
    store.auth_failure_ref_names.add("main")

    verified = verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )

    assert verified.status.value == "reauth_required"


def test_verify_repository_connection_rejects_deleting_workspace_before_git_probe(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    previous_last_verified_at = store.connections[connection_id].last_verified_at
    store.workspaces[workspace_id].status = WorkspaceStatus.DELETING
    store.last_resolved_remote_url = None

    try:
        verify_repository_connection(
            VerifyRepositoryConnectionCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=client.app.state.dependencies,
        )
    except WorkspaceLifecycleProblem as error:
        assert error.code == "workspace_deleting"
    else:
        raise AssertionError("deleting workspace should reject verification")

    assert store.last_resolved_remote_url is None
    assert (
        store.connections[connection_id].last_verified_at == previous_last_verified_at
    )


def test_verify_repository_connection_rejects_unallowlisted_gitlab_before_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.last_resolved_remote_url = None
    object.__setattr__(
        client.app.state.settings,
        "gitlab_self_managed_allowed_hosts",
        (),
    )

    try:
        verify_repository_connection(
            VerifyRepositoryConnectionCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=client.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        assert (
            error.detail == "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다."
        )
    else:
        raise AssertionError("GitLab verify should reject unallowlisted hosts")

    assert store.last_resolved_remote_url is None


def test_verify_repository_connection_rejects_stored_http_when_opt_in_disabled(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TCI_ALLOW_INSECURE_GITLAB_HTTP", "true")
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="http://192.168.10.20/group/sample-repo.git",
            transport="http",
            credential_type="https_pat",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.last_resolved_remote_url = None
    object.__setattr__(
        client.app.state.settings,
        "allow_insecure_gitlab_http",
        False,
    )

    def fail_if_decrypted(*args, **kwargs):
        raise AssertionError("credential decrypt should happen after HTTP opt-in check")

    monkeypatch.setattr(
        "tci.domain.services.verify_repository_connection.decrypt_secret_from_storage",
        fail_if_decrypted,
    )

    try:
        verify_repository_connection(
            VerifyRepositoryConnectionCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=client.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        assert (
            error.detail
            == "GitLab Self-Managed HTTP 연결은 TCI_ALLOW_INSECURE_GITLAB_HTTP=true일 때만 허용됩니다."
        )
    else:
        raise AssertionError("GitLab HTTP verify should reject disabled opt-in")

    assert store.last_resolved_remote_url is None


def test_verify_repository_connection_rejects_ssh_port_not_in_allowlist_before_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="ssh://git@192.168.10.20:2222/group/sample-repo.git",
            transport="ssh",
            credential_type="ssh_private_key",
            credential_secret=create_test_ssh_private_key(tmp_path),
            credential_fingerprint="ssh-key-private-ip",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.last_resolved_remote_url = None
    object.__setattr__(
        client.app.state.settings,
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20",),
    )

    try:
        verify_repository_connection(
            VerifyRepositoryConnectionCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
            ),
            dependencies=client.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        assert (
            error.detail == "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다."
        )
    else:
        raise AssertionError("GitLab verify should reject unallowlisted SSH ports")

    assert store.last_resolved_remote_url is None


def test_verify_repository_connection_marks_ref_missing_when_default_ref_disappears(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    dependencies = client.app.state.dependencies
    store.missing_ref_names.add("main")

    verified = verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )

    assert verified.status.value == "ref_missing"
    assert verified.default_ref_name == "main"


def test_verify_repository_connection_marks_reauth_required_when_secret_cannot_be_decrypted(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    dependencies = client.app.state.dependencies
    active_revision_id = store.connections[connection_id].active_credential_revision_id
    assert active_revision_id is not None
    store.credentials[active_revision_id].encrypted_secret = "legacy-hash-value"

    verified = verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=dependencies,
    )

    assert verified.status.value == "reauth_required"
