from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast
from zipfile import ZipFile

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import configure_mappers

from tests.support.local_upload_testkit import build_encrypted_zip_header
from tci.infrastructure.persistence.code_snapshot_repository import (
    CodeSnapshotDraft,
    CodeSnapshotRepository,
)
from tci.infrastructure.persistence.models import (
    Base,
    CodeSnapshotSourceKind,
    LocalUploadStatus,
    RefType,
    WorkspaceDeletionPurgeStatus,
    WorkspaceStatus,
)


def _enum_values(column: Any) -> list[str]:
    return list(cast(Any, column.type).enums)


def _constraint_sql(table_name: str) -> Iterable[str]:
    table = Base.metadata.tables[table_name]
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint):
            yield str(constraint.sqltext)


def test_workspace_lifecycle_models_configure_sqlalchemy_mappers() -> None:
    configure_mappers()


def test_workspace_lifecycle_tables_are_registered() -> None:
    assert {
        "workspaces",
        "local_uploads",
        "workspace_deletion_records",
        "code_snapshots",
    } <= set(Base.metadata.tables)


def test_workspace_lifecycle_enums_match_spec_language() -> None:
    assert [member.value for member in WorkspaceStatus] == [
        "active",
        "deleting",
        "deleted",
    ]
    assert [member.value for member in LocalUploadStatus] == [
        "pending",
        "processing",
        "succeeded",
        "failed",
    ]
    assert [member.value for member in CodeSnapshotSourceKind] == [
        "repository_connection",
        "local_upload",
    ]
    assert [member.value for member in WorkspaceDeletionPurgeStatus] == [
        "pending",
        "succeeded",
        "failed",
    ]


def test_workspace_table_contains_soft_delete_audit_fields() -> None:
    table = Base.metadata.tables["workspaces"]
    assert {
        "id",
        "status",
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
        "delete_reason",
    } <= set(table.c.keys())
    assert _enum_values(table.c["status"]) == ["active", "deleting", "deleted"]


def test_local_upload_table_contains_processing_and_limit_metadata() -> None:
    table = Base.metadata.tables["local_uploads"]
    assert {
        "id",
        "workspace_id",
        "status",
        "original_filename_display",
        "upload_sha256",
        "compressed_size_bytes",
        "uncompressed_size_bytes",
        "file_count",
        "directory_count",
        "latest_snapshot_id",
        "failure_code",
        "failure_message",
        "created_by",
        "created_at",
        "completed_at",
    } <= set(table.c.keys())
    assert cast(Any, table.c["failure_message"].type).length == 512
    assert "ix_local_upload_workspace_created_id" in {
        index.name for index in table.indexes
    }


def test_workspace_deletion_record_uses_minimum_audit_metadata() -> None:
    table = Base.metadata.tables["workspace_deletion_records"]
    assert {
        "id",
        "workspace_id",
        "deleted_by",
        "requested_at",
        "completed_at",
        "purge_status",
        "repository_connection_count",
        "local_upload_count",
        "snapshot_count",
        "purged_archive_count",
        "failure_message",
    } <= set(table.c.keys())
    assert "remote_url" not in table.c
    assert "archive_path" not in table.c
    assert "file_paths" not in table.c
    assert cast(Any, table.c["failure_message"].type).length == 512
    assert "ix_workspace_deletion_record_workspace_requested_id" in {
        index.name for index in table.indexes
    }


def test_code_snapshot_table_is_source_aware_without_fake_repository_connection() -> (
    None
):
    table = Base.metadata.tables["code_snapshots"]
    assert {
        "workspace_id",
        "source_kind",
        "connection_id",
        "local_upload_id",
        "sync_run_id",
        "scope_rule_version_id",
    } <= set(table.c.keys())
    assert _enum_values(table.c["source_kind"]) == [
        "repository_connection",
        "local_upload",
    ]
    assert table.c["connection_id"].nullable is True
    assert table.c["local_upload_id"].nullable is True
    assert table.c["workspace_id"].nullable is False
    assert "uq_code_snapshot_workspace_local_upload_id" in {
        constraint.name for constraint in table.constraints
    }
    assert "ix_code_snapshot_latest_local_upload" in {
        index.name for index in table.indexes
    }
    assert "ix_code_snapshot_connection_created_id" in {
        index.name for index in table.indexes
    }
    assert "ix_code_snapshot_workspace_created_id" in {
        index.name for index in table.indexes
    }


def test_code_snapshot_constraints_enforce_exactly_one_source_owner() -> None:
    constraint_sql = "\n".join(_constraint_sql("code_snapshots"))

    assert "source_kind = 'repository_connection'" in constraint_sql
    assert "connection_id IS NOT NULL" in constraint_sql
    assert "local_upload_id IS NULL" in constraint_sql
    assert "source_kind = 'local_upload'" in constraint_sql
    assert "local_upload_id IS NOT NULL" in constraint_sql
    assert "connection_id IS NULL" in constraint_sql
    assert "tree_sha IS NULL" in constraint_sql


def test_local_upload_success_and_failure_constraints_are_recorded() -> None:
    constraint_sql = "\n".join(_constraint_sql("local_uploads"))

    assert "status != 'succeeded' OR latest_snapshot_id IS NOT NULL" in constraint_sql
    assert "status != 'failed' OR failure_code IS NOT NULL" in constraint_sql
    assert (
        "status NOT IN ('succeeded', 'failed') OR completed_at IS NOT NULL"
        in constraint_sql
    )


def test_local_upload_latest_snapshot_foreign_key_is_deferred_for_workspace_delete() -> (
    None
):
    table = Base.metadata.tables["local_uploads"]
    constraint = next(
        constraint
        for constraint in table.foreign_key_constraints
        if constraint.name == "fk_local_upload_latest_snapshot_owner"
    )

    assert constraint.deferrable is True
    assert constraint.initially == "DEFERRED"


def test_encrypted_zip_fixture_marks_entry_as_encrypted() -> None:
    from io import BytesIO

    with ZipFile(BytesIO(build_encrypted_zip_header())) as archive:
        assert any(info.flag_bits & 0x1 for info in archive.infolist())


def test_repository_snapshot_rejects_mismatched_workspace_id() -> None:
    connection_workspace_id = "00000000-0000-0000-0000-000000000001"
    draft_workspace_id = "00000000-0000-0000-0000-000000000002"

    class FakeSession:
        def scalar(self, statement: object) -> str:
            return connection_workspace_id

    repository = CodeSnapshotRepository(cast(Any, FakeSession()))
    draft = CodeSnapshotDraft(
        id=cast(Any, "00000000-0000-0000-0000-000000000003"),
        connection_id=cast(Any, "00000000-0000-0000-0000-000000000004"),
        sync_run_id=cast(Any, "00000000-0000-0000-0000-000000000005"),
        scope_rule_version_id=cast(Any, "00000000-0000-0000-0000-000000000006"),
        requested_ref_type=RefType.BRANCH,
        requested_ref_name="main",
        resolved_commit_sha="a" * 40,
        tree_sha="b" * 40,
        archive_path=".runtime/code-snapshots/example",
        file_count=1,
        total_bytes=12,
        workspace_id=cast(Any, draft_workspace_id),
    )

    with pytest.raises(ValueError, match="must match"):
        repository.create(draft=draft, files=())
