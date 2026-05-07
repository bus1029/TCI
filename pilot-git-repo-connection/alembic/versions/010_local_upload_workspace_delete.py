"""local upload workspace lifecycle foundation

Revision ID: 010_local_upload_workspace_del
Revises: 009_repository_first_connections
Create Date: 2026-05-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "010_local_upload_workspace_del"
down_revision = "009_repository_first_connections"
branch_labels = None
depends_on = None


WORKSPACE_STATUS = sa.Enum("active", "deleting", "deleted", name="workspace_status")
LOCAL_UPLOAD_STATUS = sa.Enum(
    "pending", "processing", "succeeded", "failed", name="local_upload_status"
)
CODE_SNAPSHOT_SOURCE_KIND = sa.Enum(
    "repository_connection", "local_upload", name="code_snapshot_source_kind"
)
WORKSPACE_DELETION_PURGE_STATUS = sa.Enum(
    "pending",
    "succeeded",
    "failed",
    name="workspace_deletion_purge_status",
)


def upgrade() -> None:
    _abort_if_code_snapshots_without_connection_workspace_exist()
    _abort_if_invalid_code_snapshot_file_counts_exist()

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            WORKSPACE_STATUS,
            server_default=sa.text("'active'"),
            nullable=False,
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=255), nullable=True),
        sa.Column("delete_reason", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "status != 'deleted' OR (deleted_at IS NOT NULL AND deleted_by IS NOT NULL)",
            name="ck_workspace_deleted_requires_audit",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
    )
    _backfill_workspaces()
    _create_partial_index_concurrently(
        "ix_workspace_active_created_id",
        "workspaces",
        ("created_at DESC", "id DESC"),
        "status = 'active'",
    )
    _create_index_concurrently(
        "ix_plan_input_workspace_id",
        "planning_input_references",
        ("workspace_id",),
    )
    _create_index_concurrently(
        "ix_repo_conn_workspace_created_id",
        "repository_connections",
        ("workspace_id", "created_at DESC", "id DESC"),
    )
    _create_index_concurrently(
        "ix_sync_run_connection_started_id",
        "repository_sync_runs",
        ("connection_id", "started_at DESC", "id DESC"),
    )
    _create_unique_index_concurrently(
        "uq_repo_conn_workspace_id_id",
        "repository_connections",
        ("workspace_id", "id"),
    )
    _add_foreign_key_not_valid(
        "fk_plan_input_workspace_id",
        "planning_input_references",
        ("workspace_id",),
        "workspaces",
        ("id",),
    )
    _add_foreign_key_not_valid(
        "fk_repo_conn_workspace_id",
        "repository_connections",
        ("workspace_id",),
        "workspaces",
        ("id",),
    )

    op.create_table(
        "local_uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            LOCAL_UPLOAD_STATUS,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("original_filename_display", sa.String(length=255), nullable=False),
        sa.Column("upload_sha256", sa.String(length=64), nullable=False),
        sa.Column("compressed_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "uncompressed_size_bytes",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "file_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "directory_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("latest_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_local_upload_workspace_id"
        ),
        sa.CheckConstraint(
            "compressed_size_bytes >= 0 "
            "AND uncompressed_size_bytes >= 0 "
            "AND file_count >= 0 "
            "AND directory_count >= 0",
            name="ck_local_upload_counts_non_negative",
        ),
        sa.CheckConstraint(
            "status != 'succeeded' OR latest_snapshot_id IS NOT NULL",
            name="ck_local_upload_success_requires_snapshot",
        ),
        sa.CheckConstraint(
            "status != 'failed' OR failure_code IS NOT NULL",
            name="ck_local_upload_failure_requires_code",
        ),
        sa.CheckConstraint(
            "status NOT IN ('succeeded', 'failed') OR completed_at IS NOT NULL",
            name="ck_local_upload_terminal_requires_completed_at",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_local_uploads")),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_local_upload_workspace_id_id",
        ),
    )
    op.create_index("ix_local_upload_workspace_id", "local_uploads", ["workspace_id"])
    op.create_index(
        "ix_local_upload_workspace_created_id",
        "local_uploads",
        ["workspace_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_local_upload_latest_snapshot_id", "local_uploads", ["latest_snapshot_id"]
    )
    op.create_table(
        "workspace_deletion_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("deleted_by", sa.String(length=255), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "purge_status",
            WORKSPACE_DELETION_PURGE_STATUS,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "repository_connection_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "local_upload_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "purged_archive_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("failure_message", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_deletion_workspace_id",
        ),
        sa.CheckConstraint(
            "repository_connection_count >= 0 "
            "AND local_upload_count >= 0 "
            "AND snapshot_count >= 0 "
            "AND purged_archive_count >= 0",
            name="ck_workspace_deletion_counts_non_negative",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_deletion_records")),
    )
    op.create_index(
        "ix_workspace_deletion_record_workspace_id",
        "workspace_deletion_records",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_deletion_record_workspace_requested_id",
        "workspace_deletion_records",
        ["workspace_id", sa.text("requested_at DESC"), sa.text("id DESC")],
    )

    op.add_column("code_snapshots", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    CODE_SNAPSHOT_SOURCE_KIND.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "code_snapshots",
        sa.Column(
            "source_kind",
            CODE_SNAPSHOT_SOURCE_KIND,
            server_default=sa.text("'repository_connection'"),
            nullable=False,
        ),
    )
    op.add_column(
        "code_snapshots", sa.Column("local_upload_id", sa.Uuid(), nullable=True)
    )
    _backfill_code_snapshot_workspaces()
    _add_check_constraint_not_valid(
        "ck_code_snapshot_workspace_id_not_null",
        "code_snapshots",
        "workspace_id IS NOT NULL",
    )
    op.alter_column("code_snapshots", "workspace_id", nullable=False)
    op.drop_constraint(
        "ck_code_snapshot_workspace_id_not_null", "code_snapshots", type_="check"
    )
    op.alter_column(
        "code_snapshots", "connection_id", existing_type=sa.Uuid(), nullable=True
    )
    op.alter_column(
        "code_snapshots", "sync_run_id", existing_type=sa.Uuid(), nullable=True
    )
    op.alter_column(
        "code_snapshots",
        "scope_rule_version_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.alter_column(
        "code_snapshots",
        "requested_ref_type",
        existing_type=sa.Enum(
            "branch",
            "tag",
            "pull_request_branch",
            name="requested_ref_type",
        ),
        nullable=True,
    )
    op.alter_column(
        "code_snapshots",
        "requested_ref_name",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.alter_column(
        "code_snapshots",
        "resolved_commit_sha",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.alter_column(
        "code_snapshots",
        "tree_sha",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    _create_unique_index_concurrently(
        "uq_code_snapshot_workspace_local_upload_id",
        "code_snapshots",
        ("workspace_id", "local_upload_id", "id"),
    )
    _add_foreign_key_not_valid(
        "fk_code_snapshot_workspace_id",
        "code_snapshots",
        ("workspace_id",),
        "workspaces",
        ("id",),
    )
    _add_foreign_key_not_valid(
        "fk_code_snapshot_local_upload_id",
        "code_snapshots",
        ("local_upload_id",),
        "local_uploads",
        ("id",),
    )
    _add_foreign_key_not_valid(
        "fk_code_snapshot_connection_workspace_owner",
        "code_snapshots",
        ("workspace_id", "connection_id"),
        "repository_connections",
        ("workspace_id", "id"),
    )
    _add_foreign_key_not_valid(
        "fk_code_snapshot_local_upload_workspace_owner",
        "code_snapshots",
        ("workspace_id", "local_upload_id"),
        "local_uploads",
        ("workspace_id", "id"),
    )
    op.create_foreign_key(
        "fk_local_upload_latest_snapshot_owner",
        "local_uploads",
        "code_snapshots",
        ["workspace_id", "id", "latest_snapshot_id"],
        ["workspace_id", "local_upload_id", "id"],
        deferrable=True,
        initially="DEFERRED",
    )
    _add_check_constraint_not_valid(
        "ck_code_snapshot_source_owner",
        "code_snapshots",
        "("
        "source_kind = 'repository_connection' "
        "AND workspace_id IS NOT NULL "
        "AND connection_id IS NOT NULL "
        "AND local_upload_id IS NULL "
        "AND sync_run_id IS NOT NULL "
        "AND scope_rule_version_id IS NOT NULL "
        "AND requested_ref_type IS NOT NULL "
        "AND requested_ref_name IS NOT NULL "
        "AND resolved_commit_sha IS NOT NULL "
        "AND tree_sha IS NOT NULL"
        ") OR ("
        "source_kind = 'local_upload' "
        "AND workspace_id IS NOT NULL "
        "AND local_upload_id IS NOT NULL "
        "AND connection_id IS NULL "
        "AND sync_run_id IS NULL "
        "AND scope_rule_version_id IS NULL "
        "AND requested_ref_type IS NULL "
        "AND requested_ref_name IS NULL "
        "AND resolved_commit_sha IS NULL "
        "AND tree_sha IS NULL"
        ")",
    )
    _add_check_constraint_not_valid(
        "ck_code_snapshot_file_count_positive",
        "code_snapshots",
        "file_count > 0",
    )
    _create_index_concurrently(
        "ix_code_snapshot_workspace_id", "code_snapshots", ("workspace_id",)
    )
    _create_index_concurrently(
        "ix_code_snapshot_workspace_created_id",
        "code_snapshots",
        ("workspace_id", "created_at DESC", "id DESC"),
    )
    _create_partial_index_concurrently(
        "ix_code_snapshot_connection_created_id",
        "code_snapshots",
        ("connection_id", "created_at DESC", "id DESC"),
        "source_kind = 'repository_connection'",
    )
    _create_index_concurrently(
        "ix_code_snapshot_local_upload_id", "code_snapshots", ("local_upload_id",)
    )
    _create_partial_index_concurrently(
        "ix_code_snapshot_latest_local_upload",
        "code_snapshots",
        ("workspace_id", "created_at DESC", "id DESC"),
        "source_kind = 'local_upload'",
    )


def downgrade() -> None:
    _abort_if_local_upload_data_exists()
    _drop_index_concurrently("ix_code_snapshot_latest_local_upload")
    _drop_index_concurrently("ix_code_snapshot_local_upload_id")
    _drop_index_concurrently("ix_code_snapshot_connection_created_id")
    _drop_index_concurrently("ix_code_snapshot_workspace_created_id")
    _drop_index_concurrently("ix_code_snapshot_workspace_id")
    op.drop_constraint(
        "ck_code_snapshot_file_count_positive", "code_snapshots", type_="check"
    )
    op.drop_constraint("ck_code_snapshot_source_owner", "code_snapshots", type_="check")
    op.drop_constraint(
        "fk_local_upload_latest_snapshot_owner", "local_uploads", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_code_snapshot_local_upload_id", "code_snapshots", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_code_snapshot_local_upload_workspace_owner",
        "code_snapshots",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_code_snapshot_connection_workspace_owner",
        "code_snapshots",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_code_snapshot_workspace_id", "code_snapshots", type_="foreignkey"
    )
    _drop_index_concurrently("uq_code_snapshot_workspace_local_upload_id")
    op.alter_column(
        "code_snapshots", "tree_sha", existing_type=sa.String(length=64), nullable=False
    )
    op.alter_column(
        "code_snapshots",
        "resolved_commit_sha",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "code_snapshots",
        "requested_ref_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "code_snapshots",
        "requested_ref_type",
        existing_type=sa.Enum(
            "branch",
            "tag",
            "pull_request_branch",
            name="requested_ref_type",
        ),
        nullable=False,
    )
    op.alter_column(
        "code_snapshots",
        "scope_rule_version_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "code_snapshots", "sync_run_id", existing_type=sa.Uuid(), nullable=False
    )
    op.alter_column(
        "code_snapshots", "connection_id", existing_type=sa.Uuid(), nullable=False
    )
    op.drop_column("code_snapshots", "local_upload_id")
    op.drop_column("code_snapshots", "source_kind")
    op.drop_column("code_snapshots", "workspace_id")

    op.drop_index(
        "ix_workspace_deletion_record_workspace_id",
        table_name="workspace_deletion_records",
    )
    op.drop_index(
        "ix_workspace_deletion_record_workspace_requested_id",
        table_name="workspace_deletion_records",
    )
    op.drop_table("workspace_deletion_records")
    op.drop_index("ix_local_upload_latest_snapshot_id", table_name="local_uploads")
    op.drop_index("ix_local_upload_workspace_created_id", table_name="local_uploads")
    op.drop_index("ix_local_upload_workspace_id", table_name="local_uploads")
    op.drop_table("local_uploads")
    op.drop_constraint(
        "fk_repo_conn_workspace_id", "repository_connections", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_plan_input_workspace_id", "planning_input_references", type_="foreignkey"
    )
    _drop_index_concurrently("uq_repo_conn_workspace_id_id")
    _drop_index_concurrently("ix_sync_run_connection_started_id")
    _drop_index_concurrently("ix_repo_conn_workspace_created_id")
    _drop_index_concurrently("ix_plan_input_workspace_id")
    _drop_index_concurrently("ix_workspace_active_created_id")
    op.drop_table("workspaces")

    CODE_SNAPSHOT_SOURCE_KIND.drop(op.get_bind(), checkfirst=True)
    WORKSPACE_DELETION_PURGE_STATUS.drop(op.get_bind(), checkfirst=True)
    LOCAL_UPLOAD_STATUS.drop(op.get_bind(), checkfirst=True)
    WORKSPACE_STATUS.drop(op.get_bind(), checkfirst=True)


def _backfill_workspaces() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO workspaces (id, status, created_at, updated_at)
            SELECT DISTINCT workspace_id, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM (
                SELECT workspace_id FROM planning_input_references
                UNION
                SELECT workspace_id FROM repository_connections
            ) workspace_ids
            """
        )
    )


def _backfill_code_snapshot_workspaces() -> None:
    op.execute(
        sa.text(
            """
            UPDATE code_snapshots
            SET workspace_id = repository_connections.workspace_id
            FROM repository_connections
            WHERE code_snapshots.connection_id = repository_connections.id
            """
        )
    )


def _abort_if_code_snapshots_without_connection_workspace_exist() -> None:
    bind = op.get_bind()
    unowned_snapshot = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM code_snapshots
            LEFT JOIN repository_connections
              ON repository_connections.id = code_snapshots.connection_id
            WHERE repository_connections.workspace_id IS NULL
            LIMIT 1
            """
        )
    ).first()
    if unowned_snapshot is not None:
        raise RuntimeError(
            "Existing code snapshots must belong to a repository connection workspace before migration 010."
        )


def _abort_if_invalid_code_snapshot_file_counts_exist() -> None:
    bind = op.get_bind()
    invalid_snapshot = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM code_snapshots
            WHERE file_count <= 0
            LIMIT 1
            """
        )
    ).first()
    if invalid_snapshot is not None:
        raise RuntimeError(
            "Existing code snapshots with file_count <= 0 must be fixed before migration 010."
        )


def _abort_if_local_upload_data_exists() -> None:
    bind = op.get_bind()
    local_snapshot = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM code_snapshots
            WHERE source_kind = 'local_upload' OR local_upload_id IS NOT NULL
            LIMIT 1
            """
        )
    ).first()
    if local_snapshot is not None:
        raise RuntimeError(
            "Cannot downgrade migration 010 while Local Upload snapshots exist."
        )
    local_upload = bind.execute(sa.text("SELECT 1 FROM local_uploads LIMIT 1")).first()
    if local_upload is not None:
        raise RuntimeError("Cannot downgrade migration 010 while Local Uploads exist.")
    deletion_record = bind.execute(
        sa.text("SELECT 1 FROM workspace_deletion_records LIMIT 1")
    ).first()
    if deletion_record is not None:
        raise RuntimeError(
            "Cannot downgrade migration 010 while workspace deletion audit records exist."
        )
    deleted_workspace = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM workspaces
            WHERE status <> 'active'
               OR deleted_at IS NOT NULL
               OR deleted_by IS NOT NULL
               OR delete_reason IS NOT NULL
            LIMIT 1
            """
        )
    ).first()
    if deleted_workspace is not None:
        raise RuntimeError(
            "Cannot downgrade migration 010 while workspace lifecycle audit data exists."
        )


def _create_index_concurrently(
    index_name: str, table_name: str, columns: tuple[str, ...]
) -> None:
    column_list = ", ".join(columns)
    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                f"{index_name} "
                f"ON {table_name} ({column_list})"
            )
        )


def _create_partial_index_concurrently(
    index_name: str,
    table_name: str,
    columns: tuple[str, ...],
    predicate: str,
) -> None:
    column_list = ", ".join(columns)
    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                f"{index_name} "
                f"ON {table_name} ({column_list}) "
                f"WHERE {predicate}"
            )
        )


def _create_unique_index_concurrently(
    index_name: str, table_name: str, columns: tuple[str, ...]
) -> None:
    column_list = ", ".join(columns)
    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
                f"{index_name} "
                f"ON {table_name} ({column_list})"
            )
        )


def _drop_index_concurrently(index_name: str) -> None:
    with op.get_context().autocommit_block():
        op.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"))


def _add_foreign_key_not_valid(
    constraint_name: str,
    table_name: str,
    columns: tuple[str, ...],
    referred_table_name: str,
    referred_columns: tuple[str, ...],
) -> None:
    column_list = ", ".join(columns)
    referred_column_list = ", ".join(referred_columns)
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} "
            f"FOREIGN KEY ({column_list}) "
            f"REFERENCES {referred_table_name} ({referred_column_list}) NOT VALID"
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {constraint_name}")
    )


def _add_check_constraint_not_valid(
    constraint_name: str,
    table_name: str,
    condition: str,
) -> None:
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} "
            f"CHECK ({condition}) NOT VALID"
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {constraint_name}")
    )
