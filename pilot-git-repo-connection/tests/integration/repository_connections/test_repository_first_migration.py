from __future__ import annotations

from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "009_repository_first_connections.py"
)


def test_repository_first_migration_makes_planning_references_nullable() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "planning_input_reference_id" in migration
    assert "repository_connections" in migration
    assert "collection_scope_rule_versions" in migration
    assert 'down_revision = "008_gitlab_insecure_http"' in migration
    assert "nullable=True" in migration
    assert "uq_repo_conn_workspace_github_repo" in migration
    assert "uq_repo_conn_workspace_gitlab_repo" in migration
    assert "ck_repo_conn_github_project_path_present" in migration
    assert 'conv(f"ck_{table_name}_{constraint_name}")' in migration
    assert "CREATE UNIQUE INDEX CONCURRENTLY" in migration
    assert "NOT VALID" in migration
    assert "VALIDATE CONSTRAINT" in migration
    assert "_abort_if_duplicate_repository_identities_exist()" in migration
    assert "provider_project_path IS NOT NULL" in migration
    assert (
        "provider_project_path = repository_owner || '/' || repository_name"
        in migration
    )
    assert (
        "provider_project_path <> repository_owner || '/' || repository_name"
        in migration
    )
    assert (
        "GitHub repository connections must have canonical provider_project_path before migration 009."
        in migration
    )


def test_repository_first_migration_preserves_legacy_planning_values() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "UPDATE repository_connections" not in migration
    assert "DELETE FROM planning_input_references" not in migration
    assert "DROP TABLE planning_input_references" not in migration


def test_repository_first_migration_blocks_unsafe_downgrade_after_new_rows() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "_abort_if_workspace_first_rows_exist()" in migration
    assert (
        "Cannot downgrade migration 009 while repository-first connections exist."
        in migration
    )
