from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
)
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.update_default_ref import (
    UpdateDefaultRefCommand,
    update_default_ref,
)


def _settings(client) -> Any:
    return cast(Any, client.app).state.settings


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def test_update_default_ref_rejects_unallowlisted_gitlab_before_credential_decrypt(
    tmp_path, monkeypatch
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
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        (),
    )

    def fail_if_decrypted(*args, **kwargs):
        raise AssertionError("credential decrypt should happen after allowlist check")

    monkeypatch.setattr(
        "tci.domain.services.update_default_ref.decrypt_secret_from_storage",
        fail_if_decrypted,
    )

    with pytest.raises(RepositoryConnectionProblem) as error_info:
        update_default_ref(
            UpdateDefaultRefCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                default_ref_type="branch",
                default_ref_name="release/2026.04",
            ),
            dependencies=_dependencies(client),
        )

    assert (
        error_info.value.detail
        == "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다."
    )
    assert store.last_resolved_remote_url is None


def test_update_default_ref_rejects_unallowlisted_gitlab_ssh_port_before_decrypt(
    tmp_path, monkeypatch
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
            credential_secret=(
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                "key\n"
                "-----END OPENSSH PRIVATE KEY-----"
            ),
            credential_fingerprint="ssh-custom-port",
        ),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    store.last_resolved_remote_url = None
    object.__setattr__(
        _settings(client),
        "gitlab_self_managed_allowed_hosts",
        ("192.168.10.20",),
    )

    def fail_if_decrypted(*args, **kwargs):
        raise AssertionError("credential decrypt should happen after allowlist check")

    monkeypatch.setattr(
        "tci.domain.services.update_default_ref.decrypt_secret_from_storage",
        fail_if_decrypted,
    )

    with pytest.raises(RepositoryConnectionProblem) as error_info:
        update_default_ref(
            UpdateDefaultRefCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                default_ref_type="branch",
                default_ref_name="release/2026.04",
            ),
            dependencies=_dependencies(client),
        )

    assert (
        error_info.value.detail
        == "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다."
    )
    assert store.last_resolved_remote_url is None
