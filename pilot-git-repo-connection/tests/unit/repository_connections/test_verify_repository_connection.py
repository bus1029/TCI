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
from tci.domain.services.verify_repository_connection import (
    VerifyRepositoryConnectionCommand,
    verify_repository_connection,
)


def test_verify_repository_connection_keeps_active_status_when_stored_credential_is_valid(
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
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
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


def test_verify_repository_connection_rejects_unallowlisted_gitlab_before_git_access(
    tmp_path,
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


def test_verify_repository_connection_rejects_ssh_port_not_in_allowlist_before_git_access(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            planning_input_reference_id=reference.id,
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
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
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
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)

    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
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
