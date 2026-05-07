from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    bind_git_credential,
    decrypt_secret_from_storage,
    ensure_gitlab_self_managed_host_allowed,
    require_active_operation_credential,
)
from tci.domain.services.workspace_lifecycle import ensure_active_workspace
from tci.domain.services.workspace_lifecycle import WorkspaceLifecycleProblem
from tci.infrastructure.persistence.models import (
    RepositoryConnectionStatus,
    RepositoryProvider,
)


@dataclass(frozen=True, slots=True)
class VerifyRepositoryConnectionCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class VerificationContext:
    provider: RepositoryProvider
    provider_instance_url: str | None
    remote_url: str
    transport: object
    default_ref_type: object
    default_ref_name: str
    credential_type: object | None
    encrypted_secret: str | None


def verify_repository_connection(command, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("저장소 연결을 검증하려면 데이터베이스 세션이 필요합니다.")

    verification_context = _load_verification_context(
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
        dependencies=dependencies,
    )
    if isinstance(verification_context, WorkspaceLifecycleProblem):
        raise verification_context
    if (
        verification_context.credential_type is None
        or verification_context.encrypted_secret is None
    ):
        return _update_verification_status(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            status=RepositoryConnectionStatus.REAUTH_REQUIRED,
            dependencies=dependencies,
        )

    try:
        ensure_gitlab_self_managed_host_allowed(
            provider=verification_context.provider,
            provider_instance_url=verification_context.provider_instance_url,
            settings=dependencies.settings,
            transport=verification_context.transport,
            remote_url=verification_context.remote_url,
        )
        credential_secret = decrypt_secret_from_storage(
            verification_context.encrypted_secret,
            settings=dependencies.settings,
        )
        with bind_git_credential(
            remote_url=verification_context.remote_url,
            transport=verification_context.transport,
            credential_type=verification_context.credential_type,
            credential_secret=credential_secret,
        ) as credential_bound_remote_url:
            probe_result = dependencies.git_readonly_validator.probe(
                remote_url=credential_bound_remote_url
            )
            if not probe_result.is_read_only:
                raise RepositoryConnectionProblem(
                    probe_result.problem_code
                    or ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED,
                    probe_result.detail,
                )
            dependencies.git_ref_resolver.resolve(
                remote_url=credential_bound_remote_url,
                ref_type=verification_context.default_ref_type,
                ref_name=verification_context.default_ref_name,
            )
    except Exception as error:
        status = _map_verification_failure_to_status(error)
        if status is None:
            raise
        return _update_verification_status(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            status=status,
            dependencies=dependencies,
        )

    return _update_verification_status(
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
        status=RepositoryConnectionStatus.ACTIVE,
        dependencies=dependencies,
    )


def _map_verification_failure_to_status(
    error: Exception,
) -> RepositoryConnectionStatus | None:
    problem_code = getattr(error, "problem_code", None)
    if problem_code == ProblemCode.CONNECTION_AUTH_FAILED:
        return RepositoryConnectionStatus.REAUTH_REQUIRED
    if problem_code == ProblemCode.DEFAULT_REF_NOT_FOUND:
        return RepositoryConnectionStatus.REF_MISSING
    return None


def _load_verification_context(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies
):
    lifecycle_problem = None
    with dependencies.session_factory() as session:
        workspace_repository = dependencies.workspace_repository_factory(session)
        try:
            ensure_active_workspace(
                workspace_id=workspace_id,
                workspace_repository=workspace_repository,
                lock_for_update=True,
            )
        except WorkspaceLifecycleProblem as error:
            lifecycle_problem = error
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
        if lifecycle_problem is None and connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        if lifecycle_problem is not None:
            return lifecycle_problem

        credential_revision = credential_repository.get_active_for_connection(
            connection_id=connection.id
        )
        try:
            operation_credential = require_active_operation_credential(
                credential_revision
            )
        except RepositoryConnectionProblem:
            operation_credential = None
        verification_context = VerificationContext(
            provider=connection.provider,
            provider_instance_url=connection.provider_instance_url,
            remote_url=connection.remote_url,
            transport=connection.transport,
            default_ref_type=connection.default_ref_type,
            default_ref_name=connection.default_ref_name,
            credential_type=(
                None
                if operation_credential is None
                else operation_credential.credential_type
            ),
            encrypted_secret=(
                None
                if operation_credential is None
                else operation_credential.encrypted_secret
            ),
        )
    return verification_context


def _update_verification_status(
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    status: RepositoryConnectionStatus,
    dependencies,
):
    lifecycle_problem = None
    with dependencies.session_factory() as session:
        workspace_repository = dependencies.workspace_repository_factory(session)
        try:
            ensure_active_workspace(
                workspace_id=workspace_id,
                workspace_repository=workspace_repository,
                lock_for_update=True,
            )
        except WorkspaceLifecycleProblem as error:
            lifecycle_problem = error
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        if lifecycle_problem is None:
            updated_connection = connection_repository.update_verification(
                workspace_id=workspace_id,
                connection_id=connection_id,
                status=status,
                last_verified_at=datetime.now(tz=UTC),
            )
        else:
            updated_connection = None
    if lifecycle_problem is not None:
        raise lifecycle_problem
    return updated_connection
