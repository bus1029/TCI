"""repository ingestion core

Revision ID: 001_repository_ingestion_core
Revises:
Create Date: 2026-04-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "001_repository_ingestion_core"
down_revision = None
branch_labels = None
depends_on = None


PLANNING_INPUT_SOURCE_TYPE = sa.Enum(
    "user_request",
    "planning_brief",
    "imported_note",
    name="planning_input_source_type",
)
REPOSITORY_PROVIDER = sa.Enum("github_cloud", name="repository_provider")
REPOSITORY_TRANSPORT = sa.Enum("ssh", "https", name="repository_transport")
DEFAULT_REF_TYPE = sa.Enum(
    "branch",
    "tag",
    name="default_ref_type",
)
REQUESTED_REF_TYPE = sa.Enum(
    "branch",
    "tag",
    "pull_request_branch",
    name="requested_ref_type",
)
REPOSITORY_CONNECTION_STATUS = sa.Enum(
    "active",
    "reauth_required",
    "ref_missing",
    name="repository_connection_status",
)
CREDENTIAL_TYPE = sa.Enum("ssh_private_key", "https_pat", name="credential_type")
CREDENTIAL_REVISION_STATUS = sa.Enum(
    "active",
    "previous_grace",
    "revoked",
    name="credential_revision_status",
)
SCOPE_RULE_WARNING_STATE = sa.Enum(
    "ok",
    "empty_result_risk",
    "preview_failed",
    "over_broad_include",
    name="scope_rule_warning_state",
)
SYNC_TRIGGER_TYPE = sa.Enum(
    "manual_initial",
    "manual_refresh",
    "webhook_push",
    "webhook_pull_request",
    name="sync_trigger_type",
)
SYNC_RUN_STATUS = sa.Enum(
    "pending",
    "running",
    "succeeded",
    "failed",
    "blocked",
    name="sync_run_status",
)
SYNC_FAILURE_CODE = sa.Enum(
    "AUTH_FAILED",
    "REF_NOT_FOUND",
    "NO_INCLUDED_FILES",
    "MIRROR_SYNC_FAILED",
    "SNAPSHOT_WRITE_FAILED",
    "QUEUE_DISPATCH_FAILED",
    name="sync_failure_code",
)
SNAPSHOT_INCLUSION_REASON = sa.Enum(
    "default_policy",
    "user_include",
    "pr_source_snapshot",
    name="snapshot_inclusion_reason",
)


def upgrade() -> None:
    op.create_table(
        "planning_input_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", PLANNING_INPUT_SOURCE_TYPE, nullable=False),
        sa.Column("source_title", sa.String(length=255), nullable=False),
        sa.Column("source_reference", sa.String(length=1024), nullable=False),
        sa.Column("approved_spec_path", sa.String(length=1024), nullable=False),
        sa.Column("approved_plan_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planning_input_references")),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_plan_input_workspace_id_id",
        ),
    )

    op.create_table(
        "repository_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("planning_input_reference_id", sa.Uuid(), nullable=False),
        sa.Column("provider", REPOSITORY_PROVIDER, nullable=False),
        sa.Column("remote_url", sa.String(length=2048), nullable=False),
        sa.Column("transport", REPOSITORY_TRANSPORT, nullable=False),
        sa.Column("repository_owner", sa.String(length=255), nullable=False),
        sa.Column("repository_name", sa.String(length=255), nullable=False),
        sa.Column("default_ref_type", DEFAULT_REF_TYPE, nullable=False),
        sa.Column("default_ref_name", sa.String(length=255), nullable=False),
        sa.Column("status", REPOSITORY_CONNECTION_STATUS, nullable=False),
        sa.Column("mirror_path", sa.String(length=2048), nullable=False),
        sa.Column("active_scope_rule_version_id", sa.Uuid(), nullable=True),
        sa.Column("active_credential_revision_id", sa.Uuid(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_successful_snapshot_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("last_failed_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["planning_input_reference_id"],
            ["planning_input_references.id"],
            name="fk_repo_conn_plan_input_id",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "planning_input_reference_id"],
            ["planning_input_references.workspace_id", "planning_input_references.id"],
            name="fk_repo_conn_plan_input_owner",
        ),
        sa.CheckConstraint(
            "(remote_url LIKE 'git@github.com:%' OR remote_url LIKE 'https://github.com/%')",
            name="ck_repo_conn_remote_url_host",
        ),
        sa.CheckConstraint(
            "remote_url NOT LIKE 'https://%@github.com/%'",
            name="ck_repo_conn_remote_url_no_userinfo",
        ),
        sa.CheckConstraint(
            "mirror_path NOT LIKE '/%' AND mirror_path NOT LIKE '%..%'",
            name="ck_repo_conn_mirror_path_safe",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_connections")),
        sa.UniqueConstraint(
            "id",
            "planning_input_reference_id",
            name="uq_repo_conn_id_plan_input_id",
        ),
    )

    op.create_table(
        "repository_credential_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("credential_type", CREDENTIAL_TYPE, nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("display_fingerprint", sa.String(length=255), nullable=False),
        sa.Column(
            "read_only_validated",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("status", CREDENTIAL_REVISION_STATUS, nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["repository_connections.id"],
            name="fk_cred_rev_conn_id",
        ),
        sa.CheckConstraint(
            "status != 'active' OR read_only_validated",
            name="ck_cred_rev_active_requires_ro",
        ),
        sa.CheckConstraint(
            "status != 'previous_grace' OR grace_until IS NOT NULL",
            name="ck_cred_rev_grace_until_required",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_credential_revisions")),
        sa.UniqueConstraint(
            "connection_id",
            "id",
            name="uq_cred_rev_conn_id_id",
        ),
    )
    op.create_index(
        "ix_cred_rev_one_active",
        "repository_credential_revisions",
        ["connection_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "collection_scope_rule_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("planning_input_reference_id", sa.Uuid(), nullable=False),
        sa.Column(
            "include_paths",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "exclude_paths",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "allowed_file_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "blocked_file_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "max_file_size_bytes",
            sa.Integer(),
            server_default=sa.text("5242880"),
            nullable=False,
        ),
        sa.Column(
            "exclude_binary",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "warning_state",
            SCOPE_RULE_WARNING_STATE,
            server_default=sa.text("'ok'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["repository_connections.id"],
            name="fk_scope_rule_conn_id",
        ),
        sa.ForeignKeyConstraint(
            ["planning_input_reference_id"],
            ["planning_input_references.id"],
            name="fk_scope_rule_plan_input_id",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "planning_input_reference_id"],
            [
                "repository_connections.id",
                "repository_connections.planning_input_reference_id",
            ],
            name="fk_scope_rule_plan_input_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_scope_rule_versions")),
        sa.UniqueConstraint(
            "connection_id",
            "id",
            name="uq_scope_rule_conn_id_id",
        ),
    )

    op.create_table(
        "repository_sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_type", SYNC_TRIGGER_TYPE, nullable=False),
        sa.Column("requested_ref_type", REQUESTED_REF_TYPE, nullable=False),
        sa.Column("requested_ref_name", sa.String(length=255), nullable=False),
        sa.Column("resolved_commit_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            SYNC_RUN_STATUS,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("failure_code", SYNC_FAILURE_CODE, nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["repository_connections.id"],
            name="fk_sync_run_conn_id",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_sync_runs")),
        sa.UniqueConstraint(
            "connection_id",
            "id",
            name="uq_sync_run_conn_id_id",
        ),
    )

    op.create_table(
        "code_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("scope_rule_version_id", sa.Uuid(), nullable=False),
        sa.Column("requested_ref_type", REQUESTED_REF_TYPE, nullable=False),
        sa.Column("requested_ref_name", sa.String(length=255), nullable=False),
        sa.Column("resolved_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("tree_sha", sa.String(length=64), nullable=False),
        sa.Column("archive_path", sa.String(length=2048), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["repository_connections.id"],
            name="fk_code_snapshot_conn_id",
        ),
        sa.ForeignKeyConstraint(
            ["scope_rule_version_id"],
            ["collection_scope_rule_versions.id"],
            name="fk_code_snapshot_scope_id",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "scope_rule_version_id"],
            [
                "collection_scope_rule_versions.connection_id",
                "collection_scope_rule_versions.id",
            ],
            name="fk_code_snapshot_scope_owner",
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["repository_sync_runs.id"],
            name="fk_code_snapshot_sync_id",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "sync_run_id"],
            ["repository_sync_runs.connection_id", "repository_sync_runs.id"],
            name="fk_code_snapshot_sync_owner",
        ),
        sa.CheckConstraint(
            "archive_path NOT LIKE '/%' AND archive_path NOT LIKE '%..%'",
            name="ck_code_snapshot_archive_path_safe",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_code_snapshots")),
        sa.UniqueConstraint("sync_run_id", name="uq_code_snapshot_sync_run_id"),
    )

    op.create_table(
        "code_snapshot_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("extension", sa.String(length=32), nullable=True),
        sa.Column("language_hint", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("archive_blob_path", sa.String(length=2048), nullable=False),
        sa.Column("included_by", SNAPSHOT_INCLUSION_REASON, nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["code_snapshots.id"],
            name="fk_snapshot_file_snapshot_id",
        ),
        sa.CheckConstraint(
            "archive_blob_path NOT LIKE '/%' AND archive_blob_path NOT LIKE '%..%'",
            name="ck_snapshot_file_blob_path_safe",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_code_snapshot_files")),
        sa.UniqueConstraint(
            "snapshot_id",
            "path",
            name=op.f("uq_code_snapshot_files_snapshot_id"),
        ),
    )

    op.create_foreign_key(
        "fk_repo_conn_active_cred_id",
        "repository_connections",
        "repository_credential_revisions",
        ["active_credential_revision_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_repo_conn_active_cred_owner",
        "repository_connections",
        "repository_credential_revisions",
        ["id", "active_credential_revision_id"],
        ["connection_id", "id"],
    )
    op.create_foreign_key(
        "fk_repo_conn_active_scope_id",
        "repository_connections",
        "collection_scope_rule_versions",
        ["active_scope_rule_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_repo_conn_active_scope_owner",
        "repository_connections",
        "collection_scope_rule_versions",
        ["id", "active_scope_rule_version_id"],
        ["connection_id", "id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint(
        "fk_repo_conn_active_scope_owner",
        "repository_connections",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_repo_conn_active_scope_id",
        "repository_connections",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_repo_conn_active_cred_owner",
        "repository_connections",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_repo_conn_active_cred_id",
        "repository_connections",
        type_="foreignkey",
    )

    op.drop_table("code_snapshot_files")
    op.drop_table("code_snapshots")
    op.drop_table("repository_sync_runs")
    op.drop_table("collection_scope_rule_versions")
    op.drop_index(
        "ix_cred_rev_one_active", table_name="repository_credential_revisions"
    )
    op.drop_table("repository_credential_revisions")
    op.drop_table("repository_connections")
    op.drop_table("planning_input_references")

    for enum_type in (
        SNAPSHOT_INCLUSION_REASON,
        SYNC_FAILURE_CODE,
        SYNC_RUN_STATUS,
        SYNC_TRIGGER_TYPE,
        SCOPE_RULE_WARNING_STATE,
        CREDENTIAL_REVISION_STATUS,
        CREDENTIAL_TYPE,
        REPOSITORY_CONNECTION_STATUS,
        REQUESTED_REF_TYPE,
        DEFAULT_REF_TYPE,
        REPOSITORY_TRANSPORT,
        REPOSITORY_PROVIDER,
        PLANNING_INPUT_SOURCE_TYPE,
    ):
        enum_type.drop(bind, checkfirst=True)
