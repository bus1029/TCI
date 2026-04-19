from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    bind_git_credential,
    encrypt_secret_for_storage,
    derive_fingerprint,
    parse_credential_type,
    parse_default_ref_type,
    parse_github_remote,
    parse_provider,
    parse_transport,
)
from tci.infrastructure.persistence.credential_revision_repository import (
    CredentialRevisionDraft,
)
from tci.infrastructure.persistence.models import (
    CredentialRevisionStatus,
    RepositoryConnectionStatus,
)
from tci.infrastructure.persistence.repository_connection_repository import (
    RepositoryConnectionDraft,
)


@dataclass(frozen=True, slots=True)
class CreateRepositoryConnectionCommand:
    workspace_id: uuid.UUID
    planning_input_reference_id: uuid.UUID
    provider: str
    remote_url: str
    transport: str
    default_ref_type: str
    default_ref_name: str
    credential_type: str
    credential_secret: str
    credential_fingerprint: str | None


def create_repository_connection(command, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("저장소 연결을 생성하려면 데이터베이스 세션이 필요합니다.")

    with dependencies.session_factory() as session:
        planning_input_repository = dependencies.planning_input_reference_repository_factory(
            session
        )
        planning_input_reference = planning_input_repository.get(
            workspace_id=command.workspace_id,
            reference_id=command.planning_input_reference_id,
        )
        if planning_input_reference is None:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "planningInputReferenceId가 유효하지 않습니다.",
            )

    provider = parse_provider(command.provider)
    transport = parse_transport(command.transport)
    default_ref_type = parse_default_ref_type(command.default_ref_type)
    credential_type = parse_credential_type(command.credential_type)
    parsed_remote = parse_github_remote(
        remote_url=command.remote_url,
        transport=transport,
    )
    encrypted_secret = encrypt_secret_for_storage(
        command.credential_secret,
        settings=dependencies.settings,
    )

    connection_id = uuid.uuid4()
    try:
        with bind_git_credential(
            remote_url=command.remote_url,
            transport=transport,
            credential_type=credential_type,
            credential_secret=command.credential_secret,
        ) as credential_bound_remote_url:
            resolved_ref = dependencies.git_ref_resolver.resolve(
                remote_url=credential_bound_remote_url,
                ref_type=default_ref_type,
                ref_name=command.default_ref_name,
            )
            probe_result = dependencies.git_readonly_validator.probe(
                remote_url=credential_bound_remote_url
            )
            if not probe_result.is_read_only:
                raise RepositoryConnectionProblem(
                    probe_result.problem_code
                    or ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED,
                    probe_result.detail,
                )

            mirror = dependencies.git_mirror_manager.ensure_synced_mirror(
                connection_id=connection_id,
                remote_url=credential_bound_remote_url,
            )
            if credential_bound_remote_url != command.remote_url:
                # 인증용 URL은 동기화 순간에만 사용하고, mirror 설정에는 원래 원격 주소만 남긴다.
                dependencies.git_mirror_manager.reset_origin_url(
                    mirror=mirror,
                    remote_url=command.remote_url,
                )
    except Exception as error:
        if isinstance(error, RepositoryConnectionProblem):
            raise
        raise _translate_git_failure(error) from error

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        credential_repository = dependencies.credential_revision_repository_factory(session)

        connection = connection_repository.create(
            RepositoryConnectionDraft(
                id=connection_id,
                workspace_id=planning_input_reference.workspace_id,
                planning_input_reference_id=planning_input_reference.id,
                provider=provider,
                remote_url=command.remote_url,
                transport=transport,
                repository_owner=parsed_remote.owner,
                repository_name=parsed_remote.name,
                default_ref_type=resolved_ref.ref_type,
                default_ref_name=resolved_ref.ref_name,
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=mirror.mirror_path,
                last_verified_at=datetime.now(tz=UTC),
            )
        )
        credential_revision = credential_repository.create(
            CredentialRevisionDraft(
                connection_id=connection.id,
                credential_type=credential_type,
                encrypted_secret=encrypted_secret,
                display_fingerprint=derive_fingerprint(
                    secret=command.credential_secret,
                    provided_fingerprint=command.credential_fingerprint,
                ),
                read_only_validated=True,
                status=CredentialRevisionStatus.ACTIVE,
            )
        )
        connection = connection_repository.set_active_credential_revision(
            workspace_id=planning_input_reference.workspace_id,
            connection_id=connection.id,
            credential_revision_id=credential_revision.id,
        )
        connection.planning_input_reference = planning_input_reference
        return connection


def _translate_git_failure(error: Exception) -> RepositoryConnectionProblem:
    problem_code = getattr(error, "problem_code", None)
    if problem_code is not None:
        return RepositoryConnectionProblem(problem_code)
    return RepositoryConnectionProblem(
        ProblemCode.INVALID_INPUT,
        "저장소 연결 검증에 실패했습니다.",
    )
