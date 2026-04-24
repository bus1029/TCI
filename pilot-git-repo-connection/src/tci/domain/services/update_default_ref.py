from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    bind_git_credential,
    decrypt_secret_from_storage,
    ensure_gitlab_self_managed_host_allowed,
    parse_default_ref_type,
)
from tci.infrastructure.persistence.models import (
    RepositoryConnectionStatus,
    RepositoryProvider,
)


@dataclass(frozen=True, slots=True)
class UpdateDefaultRefCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    default_ref_type: str
    default_ref_name: str


def update_default_ref(command, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("기본 ref를 수정하려면 데이터베이스 세션이 필요합니다.")

    default_ref_type = parse_default_ref_type(command.default_ref_type)
    (
        provider,
        provider_instance_url,
        remote_url,
        transport,
        credential_type,
        encrypted_secret,
    ) = _load_connection_context(
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
        dependencies=dependencies,
    )

    try:
        ensure_gitlab_self_managed_host_allowed(
            provider=provider,
            provider_instance_url=provider_instance_url,
            settings=dependencies.settings,
            remote_url=remote_url,
        )
        credential_secret = decrypt_secret_from_storage(
            encrypted_secret,
            settings=dependencies.settings,
        )
        with bind_git_credential(
            remote_url=remote_url,
            transport=transport,
            credential_type=credential_type,
            credential_secret=credential_secret,
        ) as credential_bound_remote_url:
            dependencies.git_ref_resolver.resolve(
                remote_url=credential_bound_remote_url,
                ref_type=default_ref_type,
                ref_name=command.default_ref_name,
            )
    except Exception as error:
        status = _map_ref_update_failure_to_status(error)
        if status is not None:
            _update_connection_status(
                workspace_id=command.workspace_id,
                connection_id=command.connection_id,
                status=status,
                dependencies=dependencies,
            )
        if isinstance(error, RepositoryConnectionProblem):
            raise
        problem_code = getattr(error, "problem_code", None)
        raise RepositoryConnectionProblem(
            problem_code or ProblemCode.INVALID_INPUT,
            None if problem_code is not None else "기본 ref 검증에 실패했습니다.",
        ) from error

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        return connection_repository.update_default_ref(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            default_ref_type=default_ref_type,
            default_ref_name=command.default_ref_name,
            status=RepositoryConnectionStatus.ACTIVE,
            last_verified_at=datetime.now(tz=UTC),
        )


def _map_ref_update_failure_to_status(
    error: Exception,
) -> RepositoryConnectionStatus | None:
    if isinstance(error, RepositoryConnectionProblem):
        return None
    problem_code = getattr(error, "problem_code", None)
    if problem_code == ProblemCode.CONNECTION_AUTH_FAILED:
        return RepositoryConnectionStatus.REAUTH_REQUIRED
    if problem_code == ProblemCode.DEFAULT_REF_NOT_FOUND:
        return RepositoryConnectionStatus.REF_MISSING
    return None


def _update_connection_status(
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    status: RepositoryConnectionStatus,
    dependencies,
) -> None:
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        connection_repository.update_verification(
            workspace_id=workspace_id,
            connection_id=connection_id,
            status=status,
            last_verified_at=datetime.now(tz=UTC),
        )


def _load_connection_context(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies
) -> tuple[RepositoryProvider, str | None, object, object, object, str]:
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        credential_repository = dependencies.credential_revision_repository_factory(
            session
        )
        connection = connection_repository.get(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        credential_revision = credential_repository.get_active_for_connection(
            connection_id=connection.id
        )
        if credential_revision is None:
            connection_repository.update_verification(
                workspace_id=workspace_id,
                connection_id=connection_id,
                status=RepositoryConnectionStatus.REAUTH_REQUIRED,
                last_verified_at=datetime.now(tz=UTC),
            )
            raise RepositoryConnectionProblem(
                ProblemCode.CONNECTION_AUTH_FAILED,
                "활성 자격 증명을 찾을 수 없습니다.",
            )
        return (
            connection.provider,
            connection.provider_instance_url,
            connection.remote_url,
            connection.transport,
            credential_revision.credential_type,
            credential_revision.encrypted_secret,
        )
