from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase

from tci.domain.services.default_scope_policy import (
    V1_MAX_FILE_SIZE_BYTES,
    exceeds_v1_size_limit,
    is_binary_content,
    is_hard_excluded_path,
)
from tci.infrastructure.persistence.models import SnapshotInclusionReason
from tci.infrastructure.snapshots.snapshot_archive_store import (
    SnapshotArchiveEntryDraft,
)


@dataclass(frozen=True, slots=True)
class ScopeFilterRuleSet:
    include_paths: tuple[str, ...]
    exclude_paths: tuple[str, ...]
    allowed_file_types: tuple[str, ...]
    blocked_file_types: tuple[str, ...]
    max_file_size_bytes: int = V1_MAX_FILE_SIZE_BYTES
    exclude_binary: bool = True


def filter_snapshot_entries(
    *,
    entries: tuple[SnapshotArchiveEntryDraft, ...],
    rule_set: ScopeFilterRuleSet,
) -> tuple[SnapshotArchiveEntryDraft, ...]:
    filtered_entries: list[SnapshotArchiveEntryDraft] = []

    for entry in entries:
        if is_hard_excluded_path(entry.path):
            continue

        included_by_user_rule = _matches_any_path(entry.path, rule_set.include_paths)
        if rule_set.include_paths and not included_by_user_rule:
            continue
        if _matches_any_path(entry.path, rule_set.exclude_paths):
            continue
        if rule_set.blocked_file_types and _matches_file_type(
            entry.path,
            rule_set.blocked_file_types,
        ):
            continue
        if rule_set.allowed_file_types and not _matches_file_type(
            entry.path,
            rule_set.allowed_file_types,
        ):
            continue
        if rule_set.exclude_binary and is_binary_content(entry.content):
            continue
        if exceeds_v1_size_limit(
            size_bytes=len(entry.content),
            max_file_size_bytes=rule_set.max_file_size_bytes,
        ):
            continue

        filtered_entries.append(
            SnapshotArchiveEntryDraft(
                path=entry.path,
                content=entry.content,
                extension=entry.extension,
                language_hint=entry.language_hint,
                archive_blob_path=entry.archive_blob_path,
                # include 경로가 명시된 경우에만 사용자 규칙으로 포함된 이유를 남긴다.
                included_by=(
                    SnapshotInclusionReason.USER_INCLUDE
                    if included_by_user_rule
                    and entry.included_by is SnapshotInclusionReason.DEFAULT_POLICY
                    else entry.included_by
                ),
            )
        )

    return tuple(filtered_entries)


def rule_set_from_scope_rule(scope_rule) -> ScopeFilterRuleSet:
    return ScopeFilterRuleSet(
        include_paths=tuple(scope_rule.include_paths),
        exclude_paths=tuple(scope_rule.exclude_paths),
        allowed_file_types=tuple(scope_rule.allowed_file_types),
        blocked_file_types=tuple(scope_rule.blocked_file_types),
        max_file_size_bytes=scope_rule.max_file_size_bytes,
        exclude_binary=scope_rule.exclude_binary,
    )


def _matches_any_path(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _matches_file_type(path: str, file_types: tuple[str, ...]) -> bool:
    lowered_path = path.lower()
    for file_type in file_types:
        normalized = file_type.lower()
        if normalized.startswith(".") and lowered_path.endswith(normalized):
            return True
        if not normalized.startswith(".") and lowered_path.endswith(f".{normalized}"):
            return True
    return False
