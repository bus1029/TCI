"""repository first nullable planning provenance

Revision ID: 009_repository_first_connections
Revises: 008_gitlab_insecure_http
Create Date: 2026-04-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv


revision = "009_repository_first_connections"
down_revision = "008_gitlab_insecure_http"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _abort_if_duplicate_repository_identities_exist()
    op.alter_column(
        "repository_connections",
        "planning_input_reference_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.alter_column(
        "collection_scope_rule_versions",
        "planning_input_reference_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    _create_unique_index_concurrently(
        "uq_repo_conn_workspace_github_repo",
        "repository_connections",
        ("workspace_id", "provider", "provider_project_path"),
        "provider = 'github_cloud'",
    )
    _create_unique_index_concurrently(
        "uq_repo_conn_workspace_gitlab_repo",
        "repository_connections",
        ("workspace_id", "provider", "provider_instance_url", "provider_project_path"),
        "provider = 'gitlab_self_managed'",
    )
    _add_check_constraint_not_valid(
        "ck_repo_conn_github_project_path_present",
        "repository_connections",
        "provider <> 'github_cloud' "
        "OR (provider_project_path IS NOT NULL "
        "AND provider_project_path = repository_owner || '/' || repository_name)",
    )


def downgrade() -> None:
    _abort_if_workspace_first_rows_exist()
    op.drop_constraint(
        _check_constraint_name(
            table_name="repository_connections",
            constraint_name="ck_repo_conn_github_project_path_present",
        ),
        "repository_connections",
        type_="check",
    )
    _drop_index_concurrently(
        "uq_repo_conn_workspace_gitlab_repo",
    )
    _drop_index_concurrently(
        "uq_repo_conn_workspace_github_repo",
    )
    op.alter_column(
        "collection_scope_rule_versions",
        "planning_input_reference_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "repository_connections",
        "planning_input_reference_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )


def _abort_if_duplicate_repository_identities_exist() -> None:
    bind = op.get_bind()
    duplicate_github = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM repository_connections
            WHERE provider = 'github_cloud'
            GROUP BY workspace_id, provider, provider_project_path
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate_github is not None:
        raise RuntimeError(
            "Duplicate GitHub repository connections must be resolved before migration 009."
        )
    invalid_github_project_path = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM repository_connections
            WHERE provider = 'github_cloud'
            AND (
                provider_project_path IS NULL
                OR provider_project_path <> repository_owner || '/' || repository_name
            )
            LIMIT 1
            """
        )
    ).first()
    if invalid_github_project_path is not None:
        raise RuntimeError(
            "GitHub repository connections must have canonical provider_project_path before migration 009."
        )

    duplicate_gitlab = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM repository_connections
            WHERE provider = 'gitlab_self_managed'
            GROUP BY workspace_id, provider, provider_instance_url, provider_project_path
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate_gitlab is not None:
        raise RuntimeError(
            "Duplicate GitLab repository connections must be resolved before migration 009."
        )


def _abort_if_workspace_first_rows_exist() -> None:
    bind = op.get_bind()
    null_repository_connections = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM repository_connections
            WHERE planning_input_reference_id IS NULL
            LIMIT 1
            """
        )
    ).first()
    if null_repository_connections is not None:
        raise RuntimeError(
            "Cannot downgrade migration 009 while repository-first connections exist."
        )

    null_scope_rules = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM collection_scope_rule_versions
            WHERE planning_input_reference_id IS NULL
            LIMIT 1
            """
        )
    ).first()
    if null_scope_rules is not None:
        raise RuntimeError(
            "Cannot downgrade migration 009 while repository-first scope rules exist."
        )


def _create_unique_index_concurrently(
    index_name: str,
    table_name: str,
    columns: tuple[str, ...],
    where_clause: str,
) -> None:
    column_list = ", ".join(columns)
    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                f"CREATE UNIQUE INDEX CONCURRENTLY {index_name} "
                f"ON {table_name} ({column_list}) WHERE {where_clause}"
            )
        )


def _drop_index_concurrently(index_name: str) -> None:
    with op.get_context().autocommit_block():
        op.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"))


def _add_check_constraint_not_valid(
    constraint_name: str,
    table_name: str,
    condition: str,
) -> None:
    effective_constraint_name = _check_constraint_name(
        table_name=table_name,
        constraint_name=constraint_name,
    )
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} ADD CONSTRAINT {effective_constraint_name} "
            f"CHECK ({condition}) NOT VALID"
        )
    )
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {effective_constraint_name}"
        )
    )


def _check_constraint_name(*, table_name: str, constraint_name: str) -> str:
    metadata_name = conv(f"ck_{table_name}_{constraint_name}")
    return postgresql.dialect().identifier_preparer.truncate_and_render_constraint_name(
        metadata_name
    )
