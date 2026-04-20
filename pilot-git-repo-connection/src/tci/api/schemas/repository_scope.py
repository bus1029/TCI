from __future__ import annotations

from pydantic import Field, field_validator

from tci.api.schemas._base import CamelModel


class SaveScopeRulesRequest(CamelModel):
    include_paths: list[str] = Field(default_factory=list, alias="includePaths")
    exclude_paths: list[str] = Field(default_factory=list, alias="excludePaths")
    allowed_file_types: list[str] = Field(
        default_factory=list,
        alias="allowedFileTypes",
    )
    blocked_file_types: list[str] = Field(
        default_factory=list,
        alias="blockedFileTypes",
    )
    max_file_size_bytes: int = Field(
        default=5 * 1024 * 1024,
        alias="maxFileSizeBytes",
        ge=1,
    )

    @field_validator(
        "include_paths",
        "exclude_paths",
        "allowed_file_types",
        "blocked_file_types",
    )
    @classmethod
    def validate_scope_values(cls, values: list[str]) -> list[str]:
        if len(values) > 64:
            raise ValueError("범위 규칙 항목은 최대 64개까지 허용됩니다.")
        for value in values:
            if len(value) > 256:
                raise ValueError("각 범위 규칙 값은 최대 256자까지 허용됩니다.")
        return values


def serialize_scope_rule(scope_rule) -> dict[str, object]:
    return {
        "id": str(scope_rule.id),
        "includePaths": list(scope_rule.include_paths),
        "excludePaths": list(scope_rule.exclude_paths),
        "allowedFileTypes": list(scope_rule.allowed_file_types),
        "blockedFileTypes": list(scope_rule.blocked_file_types),
        "maxFileSizeBytes": scope_rule.max_file_size_bytes,
        "warningState": scope_rule.warning_state.value,
    }
