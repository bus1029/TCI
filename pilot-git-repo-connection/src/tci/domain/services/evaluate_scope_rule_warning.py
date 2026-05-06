from __future__ import annotations

from dataclasses import dataclass
import uuid

from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    bind_git_credential,
    decrypt_secret_from_storage,
    ensure_gitlab_self_managed_host_allowed,
    require_active_operation_credential,
)
from tci.domain.services.scope_filter_engine import (
    ScopeFilterRuleSet,
    filter_snapshot_entries,
)
from tci.infrastructure.persistence.models import ScopeRuleWarningState


@dataclass(frozen=True, slots=True)
class EvaluateScopeRuleWarningCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    include_paths: tuple[str, ...]
    exclude_paths: tuple[str, ...]
    allowed_file_types: tuple[str, ...]
    blocked_file_types: tuple[str, ...]
    max_file_size_bytes: int
    exclude_binary: bool


def evaluate_scope_rule_warning(
    command: EvaluateScopeRuleWarningCommand, *, dependencies
):
    if dependencies.session_factory is None:
        raise RuntimeError(
            "범위 규칙 경고를 계산하려면 데이터베이스 세션이 필요합니다."
        )

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        credential_repository = dependencies.credential_revision_repository_factory(
            session
        )
        connection = connection_repository.get(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        credential_revision = credential_repository.get_active_for_connection(
            connection_id=connection.id
        )
        try:
            operation_credential = require_active_operation_credential(
                credential_revision
            )
        except RepositoryConnectionProblem:
            return ScopeRuleWarningState.PREVIEW_FAILED

        try:
            ensure_gitlab_self_managed_host_allowed(
                provider=connection.provider,
                provider_instance_url=connection.provider_instance_url,
                settings=dependencies.settings,
                transport=connection.transport,
                remote_url=connection.remote_url,
            )
            credential_secret = decrypt_secret_from_storage(
                operation_credential.encrypted_secret,
                settings=dependencies.settings,
            )
            with bind_git_credential(
                remote_url=connection.remote_url,
                transport=connection.transport,
                credential_type=operation_credential.credential_type,
                credential_secret=credential_secret,
            ) as credential_bound_remote_url:
                resolved_ref = dependencies.git_ref_resolver.resolve(
                    remote_url=credential_bound_remote_url,
                    ref_type=connection.default_ref_type,
                    ref_name=connection.default_ref_name,
                )
                mirror = dependencies.git_mirror_manager.ensure_synced_mirror(
                    connection_id=connection.id,
                    remote_url=credential_bound_remote_url,
                    restore_remote_url=(
                        None
                        if credential_bound_remote_url == connection.remote_url
                        else connection.remote_url
                    ),
                )
                materialized_snapshot = (
                    dependencies.git_mirror_manager.read_snapshot_entries(
                        mirror=mirror,
                        commit_sha=resolved_ref.commit_sha,
                        include_binary=not command.exclude_binary,
                        include_paths=command.include_paths,
                        exclude_paths=command.exclude_paths,
                        allowed_file_types=command.allowed_file_types,
                        blocked_file_types=command.blocked_file_types,
                        max_file_size_bytes=command.max_file_size_bytes,
                    )
                )
        except RepositoryConnectionProblem:
            raise
        except Exception as error:
            problem_code = getattr(error, "problem_code", None)
            if problem_code is not None:
                raise RepositoryConnectionProblem(problem_code, str(error)) from error
            return ScopeRuleWarningState.PREVIEW_FAILED

    filtered_entries = filter_snapshot_entries(
        entries=materialized_snapshot.entries,
        rule_set=ScopeFilterRuleSet(
            include_paths=command.include_paths,
            exclude_paths=command.exclude_paths,
            allowed_file_types=command.allowed_file_types,
            blocked_file_types=command.blocked_file_types,
            max_file_size_bytes=command.max_file_size_bytes,
            exclude_binary=command.exclude_binary,
        ),
    )
    if not filtered_entries:
        return ScopeRuleWarningState.EMPTY_RESULT_RISK
    return ScopeRuleWarningState.OK
