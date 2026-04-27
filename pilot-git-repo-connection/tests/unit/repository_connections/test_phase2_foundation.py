from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
from collections.abc import Iterable
from typing import Any, cast

import pytest

# mypy: disable-error-code=import-untyped
from sqlalchemy.orm import configure_mappers

from tci.api.problem_details import ProblemCode, problem_details_for
from tci.infrastructure.persistence.models import (
    Base,
    CredentialRevisionStatus,
    CredentialType,
    PlanningInputSourceType,
    RefType,
    RepositoryConnectionStatus,
    RepositoryProvider,
    RepositoryTransport,
    ScopeRuleWarningState,
    SyncFailureCode,
    SyncRunStatus,
)


def _load_core_revision_module():
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "001_repository_ingestion_core.py"
    )
    spec = spec_from_file_location("repository_ingestion_core_revision", revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("코어 Alembic revision 모듈을 불러올 수 없습니다.")

    module = module_from_spec(spec)
    alembic_stub = ModuleType("alembic")
    setattr(alembic_stub, "op", object())
    previous_alembic = sys.modules.get("alembic")
    sys.modules["alembic"] = alembic_stub

    try:
        spec.loader.exec_module(module)
    finally:
        if previous_alembic is None:
            sys.modules.pop("alembic", None)
        else:
            sys.modules["alembic"] = previous_alembic

    return module


def _load_revision_module(filename: str, module_name: str):
    revision_path = (
        Path(__file__).resolve().parents[3] / "alembic" / "versions" / filename
    )
    spec = spec_from_file_location(module_name, revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{filename} Alembic revision 모듈을 불러올 수 없습니다.")

    module = module_from_spec(spec)
    alembic_stub = ModuleType("alembic")
    setattr(alembic_stub, "op", object())
    previous_alembic = sys.modules.get("alembic")
    sys.modules["alembic"] = alembic_stub

    try:
        spec.loader.exec_module(module)
    finally:
        if previous_alembic is None:
            sys.modules.pop("alembic", None)
        else:
            sys.modules["alembic"] = previous_alembic

    return module


def _enum_values(column: Any) -> list[str]:
    return list(cast(Any, column.type).enums)


def _contains_constraint_name(names: Iterable[object | None], target: str) -> bool:
    return any(isinstance(name, str) and name.endswith(target) for name in names)


def test_phase2_models_configure_sqlalchemy_mappers() -> None:
    configure_mappers()


def test_core_repository_ingestion_tables_are_registered() -> None:
    assert {
        "planning_input_references",
        "repository_connections",
        "repository_credential_revisions",
        "collection_scope_rule_versions",
        "repository_sync_runs",
        "code_snapshots",
        "code_snapshot_files",
    } <= set(Base.metadata.tables)


def test_repository_connection_table_includes_phase2_core_columns() -> None:
    table = Base.metadata.tables["repository_connections"]
    column_names = set(table.c.keys())

    assert {
        "id",
        "workspace_id",
        "planning_input_reference_id",
        "provider",
        "remote_url",
        "transport",
        "repository_owner",
        "repository_name",
        "default_ref_type",
        "default_ref_name",
        "status",
        "mirror_path",
        "active_scope_rule_version_id",
        "active_credential_revision_id",
        "last_verified_at",
        "last_successful_snapshot_at",
        "last_failed_sync_at",
        "created_at",
        "updated_at",
    } <= column_names


def test_phase2_enums_match_spec_language() -> None:
    assert [member.value for member in PlanningInputSourceType] == [
        "user_request",
        "planning_brief",
        "imported_note",
    ]
    assert [member.value for member in RepositoryProvider] == [
        "github_cloud",
        "gitlab_self_managed",
    ]
    assert [member.value for member in RepositoryTransport] == ["ssh", "https"]
    assert [member.value for member in RefType] == [
        "branch",
        "tag",
        "pull_request_branch",
    ]
    assert [member.value for member in RepositoryConnectionStatus] == [
        "active",
        "reauth_required",
        "ref_missing",
    ]
    assert [member.value for member in CredentialType] == [
        "ssh_private_key",
        "https_pat",
    ]
    assert [member.value for member in CredentialRevisionStatus] == [
        "active",
        "previous_grace",
        "revoked",
    ]
    assert [member.value for member in ScopeRuleWarningState] == [
        "ok",
        "empty_result_risk",
        "preview_failed",
        "over_broad_include",
    ]
    assert [member.value for member in SyncRunStatus] == [
        "pending",
        "running",
        "succeeded",
        "failed",
        "blocked",
    ]
    assert [member.value for member in SyncFailureCode] == [
        "AUTH_FAILED",
        "REF_NOT_FOUND",
        "NO_INCLUDED_FILES",
        "MIRROR_SYNC_FAILED",
        "SNAPSHOT_WRITE_FAILED",
        "QUEUE_DISPATCH_FAILED",
    ]


def test_phase2_column_types_preserve_domain_constraints() -> None:
    connection_table = Base.metadata.tables["repository_connections"]
    sync_run_table = Base.metadata.tables["repository_sync_runs"]

    assert _enum_values(connection_table.c["default_ref_type"]) == ["branch", "tag"]
    assert _enum_values(sync_run_table.c["trigger_type"]) == [
        "manual_initial",
        "manual_refresh",
        "webhook_push",
        "webhook_pull_request",
        "webhook_merge_request",
    ]


def test_core_revision_enums_match_orm_metadata() -> None:
    revision_module = _load_core_revision_module()
    revision_004 = _load_revision_module(
        "004_gitlab_self_managed_provider_support.py",
        "gitlab_self_managed_provider_support_enums",
    )
    connection_table = Base.metadata.tables["repository_connections"]
    sync_run_table = Base.metadata.tables["repository_sync_runs"]
    snapshot_table = Base.metadata.tables["code_snapshots"]
    scope_rule_table = Base.metadata.tables["collection_scope_rule_versions"]

    assert revision_module.DEFAULT_REF_TYPE.enums == _enum_values(
        connection_table.c["default_ref_type"]
    )
    assert revision_module.REQUESTED_REF_TYPE.enums == _enum_values(
        sync_run_table.c["requested_ref_type"]
    )
    assert revision_module.REQUESTED_REF_TYPE.enums == _enum_values(
        snapshot_table.c["requested_ref_type"]
    )
    assert revision_module.SCOPE_RULE_WARNING_STATE.enums == _enum_values(
        scope_rule_table.c["warning_state"]
    )
    assert revision_004.REPOSITORY_PROVIDER.enums == _enum_values(
        connection_table.c["provider"]
    )
    assert revision_004.SYNC_TRIGGER_TYPE.enums == _enum_values(
        sync_run_table.c["trigger_type"]
    )


def test_verified_secret_revision_followup_migration_keeps_002_stable() -> None:
    versions_dir = Path(__file__).resolve().parents[3] / "alembic" / "versions"
    revision_002_path = versions_dir / "002_repository_ingestion_webhooks.py"
    revision_003_path = (
        versions_dir / "003_repository_event_verified_secret_revision.py"
    )

    assert revision_003_path.exists()
    assert "verified_secret_revision_id" not in revision_002_path.read_text(
        encoding="utf-8"
    )
    assert "verified_secret_revision_id" in revision_003_path.read_text(
        encoding="utf-8"
    )

    revision_003 = _load_revision_module(
        "003_repository_event_verified_secret_revision.py",
        "repository_event_verified_secret_revision",
    )
    assert revision_003.down_revision == "002_ingestion_webhooks"


def test_webhook_revision_enums_do_not_recreate_types_during_table_creation() -> None:
    revision_002 = _load_revision_module(
        "002_repository_ingestion_webhooks.py",
        "repository_ingestion_webhooks",
    )

    for enum_type in (
        revision_002.WEBHOOK_SECRET_REVISION_STATUS,
        revision_002.WEBHOOK_HEALTH_STATE,
        revision_002.WEBHOOK_REJECTION_REASON,
        revision_002.PROVIDER_EVENT_TYPE,
        revision_002.DOMAIN_EVENT_TYPE,
        revision_002.EVENT_TARGET_KIND,
        revision_002.SIGNATURE_STATUS,
        revision_002.PROCESSING_DECISION,
        revision_002.EVENT_PROCESSING_STATUS,
        revision_002.VERIFIED_WEBHOOK_SECRET_REVISION_STATUS,
        revision_002.REPOSITORY_EVENT_REJECTION_REASON,
    ):
        assert getattr(enum_type, "create_type", None) is False


def test_phase2_revision_ids_fit_alembic_version_column_limit() -> None:
    revision_001 = _load_core_revision_module()
    revision_002 = _load_revision_module(
        "002_repository_ingestion_webhooks.py",
        "repository_ingestion_webhooks_revision_ids",
    )
    revision_003 = _load_revision_module(
        "003_repository_event_verified_secret_revision.py",
        "repository_event_verified_secret_revision_ids",
    )
    revision_004 = _load_revision_module(
        "004_gitlab_self_managed_provider_support.py",
        "gitlab_self_managed_provider_support_revision_ids",
    )
    revision_007 = _load_revision_module(
        "007_sync_run_active_trigger_guard.py",
        "sync_run_active_trigger_guard_revision_ids",
    )

    assert len(revision_001.revision) <= 32
    assert len(revision_002.revision) <= 32
    assert len(revision_003.revision) <= 32
    assert len(revision_004.revision) <= 32
    assert len(revision_007.revision) <= 32


def test_sync_run_active_guard_revision_rejects_duplicate_pending_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision_007 = _load_revision_module(
        "007_sync_run_active_trigger_guard.py",
        "sync_run_active_trigger_guard_duplicate_precheck",
    )

    class FakeBind:
        def scalar(self, statement) -> int:
            return 1

    class FakeOp:
        def get_bind(self) -> FakeBind:
            return FakeBind()

        def get_context(self):  # pragma: no cover - should not be reached
            raise AssertionError("duplicate precheck should abort before DDL")

    monkeypatch.setattr(revision_007, "op", FakeOp())

    with pytest.raises(
        RuntimeError,
        match="중복 active sync run을 정리한 뒤 migration을 실행해야 합니다.",
    ):
        revision_007.upgrade()


def test_sync_run_active_guard_revision_rejects_duplicate_blocked_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision_007 = _load_revision_module(
        "007_sync_run_active_trigger_guard.py",
        "sync_run_active_guard_duplicate_blocked_precheck",
    )

    class FakeBind:
        def __init__(self) -> None:
            self.calls = 0

        def scalar(self, statement) -> int:
            self.calls += 1
            return 1 if self.calls == 2 else 0

    class FakeOp:
        def __init__(self) -> None:
            self.bind = FakeBind()

        def get_bind(self) -> FakeBind:
            return self.bind

        def get_context(self):  # pragma: no cover - should not be reached
            raise AssertionError("duplicate precheck should abort before DDL")

    monkeypatch.setattr(revision_007, "op", FakeOp())

    with pytest.raises(
        RuntimeError,
        match="중복 blocked sync run을 정리한 뒤 migration을 실행해야 합니다.",
    ):
        revision_007.upgrade()


def test_sync_run_active_guard_revision_adds_dispatch_column_and_blocked_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision_007 = _load_revision_module(
        "007_sync_run_active_trigger_guard.py",
        "sync_run_active_guard_blocked_index_contract",
    )
    added_columns: list[str] = []
    created_indexes: list[tuple[str, object]] = []
    executed_sql: list[str] = []
    altered_columns: list[tuple[str, str, object]] = []

    class FakeBind:
        def scalar(self, statement) -> int:
            return 0

    class FakeOp:
        def get_bind(self) -> FakeBind:
            return FakeBind()

        def execute(self, statement) -> None:
            executed_sql.append(str(statement))

        def add_column(self, table_name: str, column) -> None:
            added_columns.append(column.name)

        def alter_column(self, table_name: str, column_name: str, **kwargs) -> None:
            altered_columns.append(
                (table_name, column_name, kwargs.get("server_default"))
            )

        def create_index(self, name: str, table_name: str, columns, **kwargs) -> None:
            created_indexes.append(
                (
                    name,
                    tuple(columns),
                    kwargs.get("postgresql_where"),
                    kwargs.get("postgresql_concurrently"),
                )
            )

    monkeypatch.setattr(revision_007, "op", FakeOp())

    revision_007.upgrade()

    assert "dispatch_enqueued_at" in added_columns
    assert "requested_ref_key" in added_columns
    assert ("repository_sync_runs", "requested_ref_key", None) in altered_columns
    assert any("UPDATE repository_sync_runs" in sql for sql in executed_sql)
    assert any("dispatch_enqueued_at" in sql for sql in executed_sql)
    assert any("requested_ref_key = requested_ref_name" in sql for sql in executed_sql)
    assert any("events.target_key" in sql for sql in executed_sql)
    assert any("events.target_key = 'default_ref'" in sql for sql in executed_sql)
    assert any("status = 'pending'" in sql for sql in executed_sql)
    assert any(
        "SET dispatch_enqueued_at = now() - interval '16 minutes'" in sql
        for sql in executed_sql
    )
    assert all("COALESCE(started_at, now())" not in sql for sql in executed_sql)
    assert any(
        name == "ix_sync_run_one_blocked_per_requested_ref"
        and "requested_ref_key" in columns
        and "blocked" in str(where)
        and concurrently is None
        for name, columns, where, concurrently in created_indexes
    )


def test_scope_rule_auto_default_column_is_owned_by_followup_revision() -> None:
    versions_dir = Path(__file__).resolve().parents[3] / "alembic" / "versions"
    revision_001_path = versions_dir / "001_repository_ingestion_core.py"
    revision_006_path = versions_dir / "006_scope_rule_auto_default_flag.py"

    assert "is_auto_default" not in revision_001_path.read_text(encoding="utf-8")
    assert "is_auto_default" in revision_006_path.read_text(encoding="utf-8")
    assert "SET is_auto_default = true" in revision_006_path.read_text(encoding="utf-8")

    revision_006 = _load_revision_module(
        "006_scope_rule_auto_default_flag.py",
        "scope_rule_auto_default_flag_revision_ids",
    )
    assert revision_006.down_revision == "005_scope_rule_preview_failed"

    revision_007 = _load_revision_module(
        "007_sync_run_active_trigger_guard.py",
        "sync_run_active_trigger_guard_revision_ids",
    )
    assert revision_007.down_revision == "006_scope_rule_auto_default"


def test_repository_event_metadata_enforces_secret_revision_same_connection() -> None:
    event_table = Base.metadata.tables["repository_events"]
    fk_names = {constraint.name for constraint in event_table.foreign_key_constraints}

    assert "fk_repository_event_verified_webhook_secret_revision_owner" in fk_names


def test_phase2_explicit_constraint_names_fit_postgresql_limit() -> None:
    revision_module = _load_core_revision_module()

    assert len("fk_repo_conn_active_scope_id") <= 63
    assert len("fk_repo_conn_active_cred_id") <= 63
    assert len("fk_repo_conn_active_scope_owner") <= 63
    assert len("fk_repo_conn_active_cred_owner") <= 63
    assert len("fk_repo_conn_active_webhook_secret_owner") <= 63
    assert len("fk_code_snapshot_sync_owner") <= 63
    assert len("fk_code_snapshot_scope_owner") <= 63

    assert revision_module.revision == "001_repository_ingestion_core"


def test_phase2_all_foreign_key_names_fit_postgresql_limit() -> None:
    for table in Base.metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            assert constraint.name is not None
            assert len(cast(str, constraint.name)) <= 63


def test_phase2_metadata_includes_connection_ownership_guards() -> None:
    connection_table = Base.metadata.tables["repository_connections"]
    scope_rule_table = Base.metadata.tables["collection_scope_rule_versions"]
    snapshot_table = Base.metadata.tables["code_snapshots"]

    connection_fk_names = {
        constraint.name for constraint in connection_table.foreign_key_constraints
    }
    scope_rule_fk_names = {
        constraint.name for constraint in scope_rule_table.foreign_key_constraints
    }
    snapshot_fk_names = {
        constraint.name for constraint in snapshot_table.foreign_key_constraints
    }

    assert "fk_repo_conn_active_scope_owner" in connection_fk_names
    assert "fk_repo_conn_active_cred_owner" in connection_fk_names
    assert "fk_repo_conn_active_webhook_secret_owner" in connection_fk_names
    assert "fk_repo_conn_plan_input_owner" in connection_fk_names
    assert "fk_scope_rule_plan_input_owner" in scope_rule_fk_names
    assert "fk_code_snapshot_sync_owner" in snapshot_fk_names
    assert "fk_code_snapshot_scope_owner" in snapshot_fk_names


def test_phase2_metadata_includes_storage_and_remote_url_guards() -> None:
    connection_table = Base.metadata.tables["repository_connections"]
    credential_table = Base.metadata.tables["repository_credential_revisions"]
    snapshot_table = Base.metadata.tables["code_snapshots"]
    snapshot_file_table = Base.metadata.tables["code_snapshot_files"]

    connection_check_names = {
        constraint.name for constraint in connection_table.constraints
    }
    credential_check_names = {
        constraint.name for constraint in credential_table.constraints
    }
    snapshot_check_names = {
        constraint.name for constraint in snapshot_table.constraints
    }
    snapshot_file_check_names = {
        constraint.name for constraint in snapshot_file_table.constraints
    }

    assert _contains_constraint_name(
        connection_check_names, "ck_repo_conn_remote_url_host"
    )
    assert _contains_constraint_name(
        connection_check_names, "ck_repo_conn_remote_url_no_userinfo"
    )
    assert _contains_constraint_name(
        connection_check_names, "ck_repo_conn_mirror_path_safe"
    )
    assert _contains_constraint_name(
        credential_check_names, "ck_cred_rev_active_requires_ro"
    )
    assert _contains_constraint_name(
        credential_check_names, "ck_cred_rev_grace_until_required"
    )
    assert _contains_constraint_name(
        snapshot_check_names, "ck_code_snapshot_archive_path_safe"
    )
    assert _contains_constraint_name(
        snapshot_file_check_names, "ck_snapshot_file_blob_path_safe"
    )


def test_phase2_metadata_limits_active_credential_revisions_per_connection() -> None:
    credential_table = Base.metadata.tables["repository_credential_revisions"]

    index_names = {index.name for index in credential_table.indexes}

    assert "ix_cred_rev_one_active" in index_names


def test_phase2_metadata_includes_supporting_foreign_key_indexes() -> None:
    expected_indexes = {
        "repository_connections": {
            "ix_repo_conn_active_webhook_secret_revision_id",
            "ix_repo_conn_active_scope_rule_version_id",
            "ix_repo_conn_active_credential_revision_id",
            "ix_repo_conn_last_processed_event_id",
            "ix_repo_conn_plan_input_ref_id",
        },
        "repository_credential_revisions": {"ix_cred_rev_connection_id"},
        "webhook_secret_revisions": {"ix_webhook_secret_rev_connection_id"},
        "collection_scope_rule_versions": {"ix_scope_rule_plan_input_ref_id"},
        "repository_events": {
            "ix_repository_event_verified_secret_revision_id",
            "ix_repository_event_sync_run_id",
            "ix_repository_event_snapshot_id",
        },
        "repository_event_cursors": {"ix_repository_event_cursor_latest_event_id"},
        "repository_sync_runs": {
            "ix_sync_run_trigger_event_id",
            "ix_sync_run_one_active_per_requested_ref",
        },
        "code_snapshots": {
            "ix_code_snapshot_scope_rule_version_id",
            "ix_code_snapshot_connection_id",
        },
    }
    revision_text = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "004_gitlab_self_managed_provider_support.py"
    ).read_text(encoding="utf-8")
    revision_007_text = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "007_sync_run_active_trigger_guard.py"
    ).read_text(encoding="utf-8")

    for table_name, index_names in expected_indexes.items():
        table_index_names = {
            index.name for index in Base.metadata.tables[table_name].indexes
        }
        assert index_names <= table_index_names
        for index_name in index_names:
            assert index_name in revision_text or index_name in revision_007_text


def test_phase2_migration_keeps_provider_project_path_rollout_safe() -> None:
    revision_text = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "004_gitlab_self_managed_provider_support.py"
    ).read_text(encoding="utf-8")

    assert (
        'sa.Column("provider_project_path", sa.String(length=512), nullable=True)'
        in (revision_text)
    )
    assert (
        'op.alter_column("repository_connections", "provider_project_path", nullable=False)'
        not in revision_text
    )


def test_problem_details_registry_covers_phase2_foundation_failures() -> None:
    auth_failed = problem_details_for(ProblemCode.CONNECTION_AUTH_FAILED)
    default_ref_not_found = problem_details_for(ProblemCode.DEFAULT_REF_NOT_FOUND)
    read_write_not_allowed = problem_details_for(
        ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED
    )

    assert auth_failed.status_code == 400
    assert auth_failed.code is ProblemCode.CONNECTION_AUTH_FAILED

    assert default_ref_not_found.status_code == 400
    assert default_ref_not_found.code is ProblemCode.DEFAULT_REF_NOT_FOUND

    assert read_write_not_allowed.status_code == 400
    assert read_write_not_allowed.code is ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED


def test_problem_details_registry_preserves_webhook_rejection_vocabulary() -> None:
    secret_missing = problem_details_for(ProblemCode.WEBHOOK_SECRET_MISSING)
    secret_mismatch = problem_details_for(ProblemCode.WEBHOOK_SECRET_MISMATCH)
    signature_invalid = problem_details_for(ProblemCode.WEBHOOK_SIGNATURE_INVALID)

    assert secret_missing.status_code == 404
    assert secret_missing.code is ProblemCode.WEBHOOK_SECRET_MISSING

    assert secret_mismatch.status_code == 401
    assert secret_mismatch.code is ProblemCode.WEBHOOK_SECRET_MISMATCH

    assert signature_invalid.status_code == 401
    assert signature_invalid.code is ProblemCode.WEBHOOK_SIGNATURE_INVALID
