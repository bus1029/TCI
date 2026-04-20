from __future__ import annotations

from dataclasses import dataclass
import uuid

from tci.domain.services.evaluate_scope_rule_warning import (
    EvaluateScopeRuleWarningCommand,
    evaluate_scope_rule_warning,
)
from tci.infrastructure.persistence.scope_rule_repository import ScopeRuleVersionDraft


@dataclass(frozen=True, slots=True)
class SaveScopeRulesCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    include_paths: tuple[str, ...]
    exclude_paths: tuple[str, ...]
    allowed_file_types: tuple[str, ...]
    blocked_file_types: tuple[str, ...]
    max_file_size_bytes: int
    exclude_binary: bool = True


def save_scope_rules(command: SaveScopeRulesCommand, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("범위 규칙을 저장하려면 데이터베이스 세션이 필요합니다.")

    warning_state = evaluate_scope_rule_warning(
        EvaluateScopeRuleWarningCommand(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            include_paths=command.include_paths,
            exclude_paths=command.exclude_paths,
            allowed_file_types=command.allowed_file_types,
            blocked_file_types=command.blocked_file_types,
            max_file_size_bytes=command.max_file_size_bytes,
            exclude_binary=command.exclude_binary,
        ),
        dependencies=dependencies,
    )

    with dependencies.session_factory() as session:
        scope_rule_repository = dependencies.scope_rule_repository_factory(session)
        return scope_rule_repository.create_active_version(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            draft=ScopeRuleVersionDraft(
                include_paths=list(command.include_paths),
                exclude_paths=list(command.exclude_paths),
                allowed_file_types=list(command.allowed_file_types),
                blocked_file_types=list(command.blocked_file_types),
                max_file_size_bytes=command.max_file_size_bytes,
                exclude_binary=command.exclude_binary,
                warning_state=warning_state,
                created_by=command.workspace_id,
            ),
        )
