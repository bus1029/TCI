from __future__ import annotations

from tci.domain.services.scope_filter_engine import (
    ScopeFilterRuleSet,
    filter_snapshot_entries,
)
from tci.infrastructure.persistence.models import SnapshotInclusionReason
from tci.infrastructure.snapshots.snapshot_archive_store import (
    SnapshotArchiveEntryDraft,
)


def test_scope_filter_engine_applies_include_exclude_and_file_type_in_defined_order() -> (
    None
):
    entries = (
        SnapshotArchiveEntryDraft(
            path="src/app.py",
            content=b"print('app')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
        ),
        SnapshotArchiveEntryDraft(
            path="src/ignored.py",
            content=b"print('ignored')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
        ),
        SnapshotArchiveEntryDraft(
            path="docs/guide.md",
            content=b"# Guide\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".md",
        ),
        SnapshotArchiveEntryDraft(
            path="dist/bundle.js",
            content=b"console.log('bundle')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".js",
        ),
    )

    filtered_entries = filter_snapshot_entries(
        entries=entries,
        rule_set=ScopeFilterRuleSet(
            include_paths=("src/**", "docs/**"),
            exclude_paths=("src/ignored.py",),
            allowed_file_types=(".py",),
            blocked_file_types=(),
            max_file_size_bytes=5 * 1024 * 1024,
            exclude_binary=True,
        ),
    )

    assert tuple(entry.path for entry in filtered_entries) == ("src/app.py",)
    assert filtered_entries[0].included_by is SnapshotInclusionReason.USER_INCLUDE


def test_scope_filter_engine_keeps_v1_hard_excluded_files_out_even_when_included() -> (
    None
):
    entries = (
        SnapshotArchiveEntryDraft(
            path="assets/logo.png",
            content=b"\x89PNG\x00binary",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".png",
        ),
        SnapshotArchiveEntryDraft(
            path="src/large.py",
            content=b"a" * (5 * 1024 * 1024 + 1),
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".py",
        ),
        SnapshotArchiveEntryDraft(
            path="node_modules/pkg/index.js",
            content=b"console.log('pkg')\n",
            included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            extension=".js",
        ),
    )

    filtered_entries = filter_snapshot_entries(
        entries=entries,
        rule_set=ScopeFilterRuleSet(
            include_paths=("assets/**", "src/**", "node_modules/**"),
            exclude_paths=(),
            allowed_file_types=(".png", ".py", ".js"),
            blocked_file_types=(),
            max_file_size_bytes=5 * 1024 * 1024,
            exclude_binary=True,
        ),
    )

    assert filtered_entries == ()
