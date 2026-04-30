from __future__ import annotations

from dataclasses import dataclass

import pytest

from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    require_active_operation_credential,
)
from tci.infrastructure.persistence.models import (
    CredentialRevisionStatus,
    CredentialType,
)


@dataclass(frozen=True, slots=True)
class _CredentialRevisionStub:
    credential_type: CredentialType
    encrypted_secret: str
    read_only_validated: bool
    status: CredentialRevisionStatus


def _credential_revision(
    *,
    status: CredentialRevisionStatus = CredentialRevisionStatus.ACTIVE,
    read_only_validated: bool = True,
):
    return _CredentialRevisionStub(
        credential_type=CredentialType.HTTPS_PAT,
        encrypted_secret="encrypted-workspace-secret",
        read_only_validated=read_only_validated,
        status=status,
    )


def test_operation_credential_accepts_active_readonly_workspace_revision() -> None:
    credential = require_active_operation_credential(_credential_revision())

    assert credential.credential_type is CredentialType.HTTPS_PAT
    assert credential.encrypted_secret == "encrypted-workspace-secret"


@pytest.mark.parametrize(
    "status",
    [
        CredentialRevisionStatus.PREVIOUS_GRACE,
        CredentialRevisionStatus.REVOKED,
    ],
)
def test_operation_credential_rejects_non_active_revisions(
    status: CredentialRevisionStatus,
) -> None:
    with pytest.raises(RepositoryConnectionProblem) as error_info:
        require_active_operation_credential(_credential_revision(status=status))

    assert error_info.value.problem_code.value == "CONNECTION_AUTH_FAILED"
    assert error_info.value.detail == (
        "활성 워크스페이스 읽기 전용 자격 증명을 찾을 수 없습니다."
    )


def test_operation_credential_rejects_unvalidated_readonly_revision() -> None:
    with pytest.raises(RepositoryConnectionProblem) as error_info:
        require_active_operation_credential(
            _credential_revision(read_only_validated=False)
        )

    assert error_info.value.problem_code.value == "CONNECTION_AUTH_FAILED"
    assert error_info.value.detail == (
        "활성 워크스페이스 읽기 전용 자격 증명을 찾을 수 없습니다."
    )


def test_operation_credential_rejects_missing_revision() -> None:
    with pytest.raises(RepositoryConnectionProblem) as error_info:
        require_active_operation_credential(None)

    assert error_info.value.problem_code.value == "CONNECTION_AUTH_FAILED"
