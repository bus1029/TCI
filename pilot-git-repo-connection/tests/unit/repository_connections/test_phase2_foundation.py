from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, cast

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
    alembic_stub.op = object()
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
    revision_path = Path(__file__).resolve().parents[3] / "alembic" / "versions" / filename
    spec = spec_from_file_location(module_name, revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{filename} Alembic revision 모듈을 불러올 수 없습니다.")

    module = module_from_spec(spec)
    alembic_stub = ModuleType("alembic")
    alembic_stub.op = object()
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


def _contains_constraint_name(names: set[str | None], target: str) -> bool:
    return any(name is not None and name.endswith(target) for name in names)


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
    assert [member.value for member in RepositoryProvider] == ["github_cloud"]
    assert [member.value for member in RepositoryTransport] == ["ssh", "https"]
    assert [member.value for member in RefType] == ["branch", "tag", "pull_request_branch"]
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
    ]


def test_core_revision_enums_match_orm_metadata() -> None:
    revision_module = _load_core_revision_module()
    connection_table = Base.metadata.tables["repository_connections"]
    sync_run_table = Base.metadata.tables["repository_sync_runs"]
    snapshot_table = Base.metadata.tables["code_snapshots"]
    scope_rule_table = Base.metadata.tables["collection_scope_rule_versions"]

    assert revision_module.DEFAULT_REF_TYPE.enums == _enum_values(
        connection_table.c["default_ref_type"]
    )
    assert revision_module.SYNC_TRIGGER_TYPE.enums == _enum_values(
        sync_run_table.c["trigger_type"]
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


def test_verified_secret_revision_followup_migration_keeps_002_stable() -> None:
    versions_dir = Path(__file__).resolve().parents[3] / "alembic" / "versions"
    revision_002_path = versions_dir / "002_repository_ingestion_webhooks.py"
    revision_003_path = versions_dir / "003_repository_event_verified_secret_revision.py"

    assert revision_003_path.exists()
    assert "verified_secret_revision_id" not in revision_002_path.read_text(encoding="utf-8")
    assert "verified_secret_revision_id" in revision_003_path.read_text(encoding="utf-8")

    revision_003 = _load_revision_module(
        "003_repository_event_verified_secret_revision.py",
        "repository_event_verified_secret_revision",
    )
    assert revision_003.down_revision == "002_repository_ingestion_webhooks"


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
    assert len("fk_code_snapshot_sync_owner") <= 63
    assert len("fk_code_snapshot_scope_owner") <= 63

    assert revision_module.revision == "001_repository_ingestion_core"


def test_phase2_all_foreign_key_names_fit_postgresql_limit() -> None:
    for table in Base.metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            assert constraint.name is not None
            assert len(constraint.name) <= 63


def test_phase2_metadata_includes_connection_ownership_guards() -> None:
    connection_table = Base.metadata.tables["repository_connections"]
    scope_rule_table = Base.metadata.tables["collection_scope_rule_versions"]
    snapshot_table = Base.metadata.tables["code_snapshots"]

    connection_fk_names = {constraint.name for constraint in connection_table.foreign_key_constraints}
    scope_rule_fk_names = {constraint.name for constraint in scope_rule_table.foreign_key_constraints}
    snapshot_fk_names = {constraint.name for constraint in snapshot_table.foreign_key_constraints}

    assert "fk_repo_conn_active_scope_owner" in connection_fk_names
    assert "fk_repo_conn_active_cred_owner" in connection_fk_names
    assert "fk_repo_conn_plan_input_owner" in connection_fk_names
    assert "fk_scope_rule_plan_input_owner" in scope_rule_fk_names
    assert "fk_code_snapshot_sync_owner" in snapshot_fk_names
    assert "fk_code_snapshot_scope_owner" in snapshot_fk_names


def test_phase2_metadata_includes_storage_and_remote_url_guards() -> None:
    connection_table = Base.metadata.tables["repository_connections"]
    credential_table = Base.metadata.tables["repository_credential_revisions"]
    snapshot_table = Base.metadata.tables["code_snapshots"]
    snapshot_file_table = Base.metadata.tables["code_snapshot_files"]

    connection_check_names = {constraint.name for constraint in connection_table.constraints}
    credential_check_names = {constraint.name for constraint in credential_table.constraints}
    snapshot_check_names = {constraint.name for constraint in snapshot_table.constraints}
    snapshot_file_check_names = {
        constraint.name for constraint in snapshot_file_table.constraints
    }

    assert _contains_constraint_name(connection_check_names, "ck_repo_conn_remote_url_host")
    assert _contains_constraint_name(
        connection_check_names, "ck_repo_conn_remote_url_no_userinfo"
    )
    assert _contains_constraint_name(connection_check_names, "ck_repo_conn_mirror_path_safe")
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
