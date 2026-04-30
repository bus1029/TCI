from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from tci.domain.services.build_code_snapshot import (
    BuildCodeSnapshotCommand,
    build_code_snapshot,
)
from tci.domain.services.create_initial_snapshot import (
    CreateInitialSnapshotCommand,
    create_initial_snapshot,
)
from tci.domain.services.evaluate_scope_rule_warning import (
    EvaluateScopeRuleWarningCommand,
    evaluate_scope_rule_warning,
)
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.update_default_ref import (
    UpdateDefaultRefCommand,
    update_default_ref,
)
from tci.domain.services.verify_repository_connection import (
    VerifyRepositoryConnectionCommand,
    verify_repository_connection,
)
from tci.infrastructure.persistence.models import (
    CredentialRevisionStatus,
    RepositoryConnectionStatus,
    ScopeRuleWarningState,
)
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
)


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def _create_connection(client) -> uuid.UUID:
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


def _revoke_active_credential(store, connection_id: uuid.UUID) -> None:
    active_revision_id = store.connections[connection_id].active_credential_revision_id
    assert active_revision_id is not None
    store.credentials[active_revision_id].status = CredentialRevisionStatus.REVOKED


def test_verify_uses_only_active_workspace_readonly_credential(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    _revoke_active_credential(store, connection_id)
    store.last_resolved_remote_url = None

    result = verify_repository_connection(
        VerifyRepositoryConnectionCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )

    assert result.status is RepositoryConnectionStatus.REAUTH_REQUIRED
    assert store.last_resolved_remote_url is None


def test_snapshot_collect_uses_only_active_workspace_readonly_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=_dependencies(client),
    )
    _revoke_active_credential(store, connection_id)
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

    assert error_info.value.problem_code.value == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.sync_runs[sync_run.id].status.value == "failed"
    assert store.last_resolved_remote_url is None


def test_reverify_ref_update_uses_only_active_workspace_readonly_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    _revoke_active_credential(store, connection_id)
    store.last_resolved_remote_url = None

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

    assert error_info.value.problem_code.value == "CONNECTION_AUTH_FAILED"
    assert (
        store.connections[connection_id].status
        is RepositoryConnectionStatus.REAUTH_REQUIRED
    )
    assert store.last_resolved_remote_url is None


def test_scope_preview_uses_only_active_workspace_readonly_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    connection_id = _create_connection(client)
    _revoke_active_credential(store, connection_id)
    store.last_resolved_remote_url = None

    warning_state = evaluate_scope_rule_warning(
        EvaluateScopeRuleWarningCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            include_paths=("src",),
            exclude_paths=(),
            allowed_file_types=(".py",),
            blocked_file_types=(),
            max_file_size_bytes=1024 * 1024,
            exclude_binary=True,
        ),
        dependencies=_dependencies(client),
    )

    assert warning_state is ScopeRuleWarningState.PREVIEW_FAILED
    assert store.last_resolved_remote_url is None
