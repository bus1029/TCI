from __future__ import annotations

from tci.domain.services.default_scope_policy import V1_MAX_FILE_SIZE_BYTES
from tci.domain.services.scope_filter_engine import (
    ScopeFilterRuleSet,
    filter_snapshot_entries,
)
from tci.infrastructure.persistence.models import SnapshotInclusionReason
from tci.infrastructure.snapshots.snapshot_archive_store import (
    SnapshotArchiveEntryDraft,
)


def test_gitlab_scope_rules_keep_user_precedence_provider_neutral() -> None:
    entries = (
        SnapshotArchiveEntryDraft(
            path="src/app.py",
            content=b"print('app')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
        ),
        SnapshotArchiveEntryDraft(
            path="src/generated.py",
            content=b"print('generated')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
        ),
        SnapshotArchiveEntryDraft(
            path="docs/guide.md",
            content=b"# Guide\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".md",
        ),
    )

    filtered = filter_snapshot_entries(
        entries=entries,
        rule_set=ScopeFilterRuleSet(
            include_paths=("src/**", "docs/**"),
            exclude_paths=("src/generated.py",),
            allowed_file_types=(".py",),
            blocked_file_types=(),
            max_file_size_bytes=V1_MAX_FILE_SIZE_BYTES,
            exclude_binary=True,
        ),
    )

    assert [entry.path for entry in filtered] == ["src/app.py"]
    assert filtered[0].included_by is SnapshotInclusionReason.USER_INCLUDE


def test_gitlab_scope_rules_hard_excludes_override_explicit_includes() -> None:
    entries = (
        SnapshotArchiveEntryDraft(
            path="node_modules/pkg/index.js",
            content=b"console.log('pkg')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".js",
        ),
        SnapshotArchiveEntryDraft(
            path="src/large.py",
            content=b"a" * (V1_MAX_FILE_SIZE_BYTES + 1),
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
        ),
        SnapshotArchiveEntryDraft(
            path="assets/logo.bin",
            content=b"\x00binary",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".bin",
        ),
    )

    filtered = filter_snapshot_entries(
        entries=entries,
        rule_set=ScopeFilterRuleSet(
            include_paths=("node_modules/**", "src/**", "assets/**"),
            exclude_paths=(),
            allowed_file_types=(".js", ".py", ".bin"),
            blocked_file_types=(),
            max_file_size_bytes=V1_MAX_FILE_SIZE_BYTES,
            exclude_binary=True,
        ),
    )

    assert filtered == ()


def test_gitlab_scope_rules_can_keep_binary_when_policy_allows_it() -> None:
    entries = (
        SnapshotArchiveEntryDraft(
            path="assets/logo.bin",
            content=b"\x00binary",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".bin",
        ),
    )

    filtered = filter_snapshot_entries(
        entries=entries,
        rule_set=ScopeFilterRuleSet(
            include_paths=("assets/**",),
            exclude_paths=(),
            allowed_file_types=(".bin",),
            blocked_file_types=(),
            max_file_size_bytes=V1_MAX_FILE_SIZE_BYTES,
            exclude_binary=False,
        ),
    )

    assert [entry.path for entry in filtered] == ["assets/logo.bin"]
    assert filtered[0].included_by is SnapshotInclusionReason.USER_INCLUDE
