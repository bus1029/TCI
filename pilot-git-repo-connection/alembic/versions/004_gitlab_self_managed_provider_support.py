"""gitlab self managed provider support

Revision ID: 004_gitlab_provider_support
Revises: 003_event_secret_revision
Create Date: 2026-04-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import conv


revision = "004_gitlab_provider_support"
down_revision = "003_event_secret_revision"
branch_labels = None
depends_on = None


REPOSITORY_PROVIDER = postgresql.ENUM(
    "github_cloud",
    "gitlab_self_managed",
    name="repository_provider",
    create_type=False,
)
PROVIDER_EVENT_TYPE = postgresql.ENUM(
    "push",
    "pull_request",
    "merge_request",
    "ping",
    "unknown",
    name="provider_event_type",
    create_type=False,
)
DOMAIN_EVENT_TYPE = postgresql.ENUM(
    "commit_recorded",
    "push_received",
    "pr_received",
    "mr_received",
    "signature_rejected",
    "secret_missing",
    "secret_mismatch",
    name="domain_event_type",
    create_type=False,
)
EVENT_TARGET_KIND = postgresql.ENUM(
    "default_ref",
    "pull_request_source",
    "merge_request_source",
    "none",
    name="event_target_kind",
    create_type=False,
)
SYNC_TRIGGER_TYPE = postgresql.ENUM(
    "manual_initial",
    "manual_refresh",
    "webhook_push",
    "webhook_pull_request",
    "webhook_merge_request",
    name="sync_trigger_type",
    create_type=False,
)
WEBHOOK_AUTH_MODE = postgresql.ENUM(
    "hmac_sha256",
    "shared_token",
    name="webhook_auth_mode",
    create_type=False,
)
PROVIDER_REACHABILITY_STATUS = postgresql.ENUM(
    "reachable",
    "unreachable_recently",
    "tls_failed_recently",
    "dns_failed_recently",
    name="provider_reachability_status",
    create_type=False,
)
PROVIDER_EVENT_IDEMPOTENCY_SOURCE = postgresql.ENUM(
    "delivery_header",
    "uuid_header",
    "derived_hash",
    name="provider_event_idempotency_source",
    create_type=False,
)
GITLAB_DOWNGRADE_BLOCKED_MESSAGE = (
    "Cannot downgrade 004 while GitLab provider data exists."
)
EVENT_DOWNGRADE_BLOCKED_MESSAGE = (
    "Cannot downgrade 004 while merge-request or derived idempotency data exists."
)
SYNC_RUN_DOWNGRADE_BLOCKED_MESSAGE = (
    "Cannot downgrade 004 while merge-request sync trigger data exists."
)
VERIFIED_SECRET_PAIR_BLOCKED_MESSAGE = (
    "Cannot add ck_repo_event_verified_secret_pair while inconsistent verified "
    "secret audit rows exist."
)
ACTIVE_WEBHOOK_SECRET_FK_BLOCKED_MESSAGE = (
    "Cannot add fk_repo_conn_active_webhook_secret_owner while cross-connection "
    "webhook secret references exist."
)


def _add_enum_value(type_name: str, value: str) -> None:
    op.execute(sa.text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'"))


def _count_rows(query: str) -> int:
    bind = op.get_bind()
    return int(bind.execute(sa.text(query)).scalar_one())


def _check_constraint_name(*, table_name: str, constraint_name: str) -> str:
    metadata_name = conv(f"ck_{table_name}_{constraint_name}")
    return postgresql.dialect().identifier_preparer.truncate_and_render_constraint_name(
        metadata_name
    )


def _add_not_valid_check(
    *, table_name: str, constraint_name: str, condition: str
) -> None:
    effective_constraint_name = _check_constraint_name(
        table_name=table_name, constraint_name=constraint_name
    )
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {table_name}
            ADD CONSTRAINT {effective_constraint_name}
            CHECK {condition} NOT VALID
            """
        )
    )


def _add_not_valid_foreign_key(
    *,
    table_name: str,
    constraint_name: str,
    local_columns: tuple[str, ...],
    referenced_table: str,
    referenced_columns: tuple[str, ...],
) -> None:
    local_column_list = ", ".join(local_columns)
    referenced_column_list = ", ".join(referenced_columns)
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {table_name}
            ADD CONSTRAINT {constraint_name}
            FOREIGN KEY ({local_column_list})
            REFERENCES {referenced_table} ({referenced_column_list}) NOT VALID
            """
        )
    )


def _validate_constraint(*, table_name: str, constraint_name: str) -> None:
    effective_constraint_name = (
        _check_constraint_name(table_name=table_name, constraint_name=constraint_name)
        if constraint_name.startswith("ck_")
        else constraint_name
    )
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {effective_constraint_name}"
        )
    )


def _drop_check_constraint_if_exists(*, table_name: str, constraint_name: str) -> None:
    effective_constraint_name = _check_constraint_name(
        table_name=table_name, constraint_name=constraint_name
    )
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} "
            f"DROP CONSTRAINT IF EXISTS {effective_constraint_name}"
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name}")
    )


def _create_index_concurrently(
    *, index_name: str, table_name: str, columns: tuple[str, ...]
) -> None:
    context = op.get_context()
    column_list = ", ".join(columns)
    with context.autocommit_block():
        op.execute(
            sa.text(
                f"CREATE INDEX CONCURRENTLY {index_name} ON {table_name} ({column_list})"
            )
        )


def _drop_index_concurrently(*, index_name: str) -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(sa.text(f"DROP INDEX CONCURRENTLY {index_name}"))


def _recreate_enum_without_values(
    *,
    type_name: str,
    remaining_values: tuple[str, ...],
    table_name: str,
    column_name: str,
) -> None:
    bind = op.get_bind()
    legacy_type_name = f"{type_name}_old"
    legacy_enum = postgresql.ENUM(*remaining_values, name=legacy_type_name)
    legacy_enum.create(bind, checkfirst=False)
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN {column_name}
            TYPE {legacy_type_name}
            USING {column_name}::text::{legacy_type_name}
            """
        )
    )
    op.execute(sa.text(f"DROP TYPE {type_name}"))
    op.execute(sa.text(f"ALTER TYPE {legacy_type_name} RENAME TO {type_name}"))


def upgrade() -> None:
    bind = op.get_bind()
    context = op.get_context()
    with context.autocommit_block():
        _add_enum_value("repository_provider", "gitlab_self_managed")
        _add_enum_value("provider_event_type", "merge_request")
        _add_enum_value("domain_event_type", "mr_received")
        _add_enum_value("event_target_kind", "merge_request_source")
        _add_enum_value("sync_trigger_type", "webhook_merge_request")

    for enum_type in (
        WEBHOOK_AUTH_MODE,
        PROVIDER_REACHABILITY_STATUS,
        PROVIDER_EVENT_IDEMPOTENCY_SOURCE,
    ):
        enum_type.create(bind, checkfirst=True)

    op.add_column(
        "repository_connections",
        sa.Column("provider_instance_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "repository_connections",
        sa.Column("provider_project_path", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "repository_connections",
        sa.Column(
            "webhook_auth_mode",
            WEBHOOK_AUTH_MODE,
            nullable=False,
            server_default=sa.text("'hmac_sha256'"),
        ),
    )
    op.add_column(
        "repository_connections",
        sa.Column(
            "provider_reachability_status",
            PROVIDER_REACHABILITY_STATUS,
            nullable=False,
            server_default=sa.text("'reachable'"),
        ),
    )
    op.add_column(
        "repository_connections",
        sa.Column(
            "last_reachability_failure_code", sa.String(length=64), nullable=True
        ),
    )
    op.add_column(
        "repository_events",
        sa.Column(
            "provider_event_idempotency_source",
            PROVIDER_EVENT_IDEMPOTENCY_SOURCE,
            nullable=False,
            server_default=sa.text("'delivery_header'"),
        ),
    )
    if _count_rows(
        """
        SELECT count(*)
        FROM repository_connections rc
        LEFT JOIN webhook_secret_revisions wsr
            ON wsr.id = rc.active_webhook_secret_revision_id
           AND wsr.connection_id = rc.id
        WHERE rc.active_webhook_secret_revision_id IS NOT NULL
          AND wsr.id IS NULL
        """
    ):
        raise RuntimeError(ACTIVE_WEBHOOK_SECRET_FK_BLOCKED_MESSAGE)
    _add_not_valid_foreign_key(
        table_name="repository_connections",
        constraint_name="fk_repo_conn_active_webhook_secret_owner",
        local_columns=("id", "active_webhook_secret_revision_id"),
        referenced_table="webhook_secret_revisions",
        referenced_columns=("connection_id", "id"),
    )
    op.drop_constraint(
        "uq_repository_events_connection_delivery",
        "repository_events",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_repository_events_connection_delivery",
        "repository_events",
        [
            "connection_id",
            "provider_delivery_id",
            "provider_event_idempotency_source",
        ],
    )
    if _count_rows(
        """
        SELECT count(*)
        FROM repository_events
        WHERE (verified_secret_revision_id IS NULL)
            <> (verified_secret_revision_status IS NULL)
        """
    ):
        raise RuntimeError(VERIFIED_SECRET_PAIR_BLOCKED_MESSAGE)
    _add_not_valid_check(
        table_name="repository_events",
        constraint_name="ck_repo_event_verified_secret_pair",
        condition=(
            "((verified_secret_revision_id IS NULL) = "
            "(verified_secret_revision_status IS NULL))"
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE repository_connections
            SET provider_project_path = repository_owner || '/' || repository_name
            WHERE provider_project_path IS NULL
            """
        )
    )

    op.drop_constraint(
        "ck_repo_conn_remote_url_host",
        "repository_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_repo_conn_remote_url_no_userinfo",
        "repository_connections",
        type_="check",
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_remote_url_host",
        condition=(
            "((provider = 'github_cloud' AND "
            "(remote_url LIKE 'git@github.com:%' OR remote_url LIKE 'https://github.com/%')) "
            "OR (provider = 'gitlab_self_managed' AND "
            "((remote_url LIKE 'git@%:%' AND remote_url !~* '^git@github\\.com\\.?:' "
            "AND remote_url !~ '^git@[-[:space:][:cntrl:]]' "
            "AND remote_url !~ '^git@[^:]*\\.\\.' "
            "AND remote_url !~ '^git@[^:]*\\.-' "
            "AND remote_url !~ '^git@[^:]*\\.:' "
            "AND remote_url !~ '^git@[^:]*-[.:]' "
            "AND remote_url !~ '^git@[^:]*[[:space:][:cntrl:]][^:]*:') "
            "OR (remote_url LIKE 'https://%/%' "
            "AND remote_url !~* '^https://github\\.com\\.?(?::[0-9]+)?/' "
            "AND remote_url !~ '^https://[-[:space:][:cntrl:]]' "
            "AND remote_url !~ '^https://[^/]*\\.\\.' "
            "AND remote_url !~ '^https://[^/]*\\.-' "
            "AND remote_url !~ '^https://[^/?#]*\\.(?::[0-9]+)?/' "
            "AND remote_url !~ '^https://[^/]*-[.:/]' "
            "AND remote_url !~ '^https://[^/]*[[:space:][:cntrl:]][^/]*/' "
            "AND remote_url !~ '^https://\\[') "
            "OR (remote_url LIKE 'ssh://git@%/%' "
            "AND remote_url !~* '^ssh://(?:[^@/]+@)?github\\.com\\.?(?::[0-9]+)?/' "
            "AND remote_url !~ '^ssh://git@[-[:space:][:cntrl:]]' "
            "AND remote_url !~ '^ssh://git@[^/]*\\.\\.' "
            "AND remote_url !~ '^ssh://git@[^/]*\\.-' "
            "AND remote_url !~ '^ssh://git@[^/?#]*\\.(?::[0-9]+)?/' "
            "AND remote_url !~ '^ssh://git@[^/]*-[.:/]' "
            "AND remote_url !~ '^ssh://git@[^/]*[[:space:][:cntrl:]][^/]*/' "
            "AND remote_url !~ '^ssh://git@\\['))))"
        ),
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_remote_url_no_userinfo",
        condition=(
            "(remote_url NOT LIKE 'https://%@%/%' "
            "AND remote_url NOT LIKE 'ssh://%:%@%/%' "
            "AND remote_url NOT LIKE '%?%' "
            "AND remote_url NOT LIKE '%#%')"
        ),
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_provider_metadata",
        condition=(
            "("
            "(provider = 'github_cloud' AND provider_instance_url IS NULL "
            "AND webhook_auth_mode = 'hmac_sha256') "
            "OR "
            "(provider = 'gitlab_self_managed' AND provider_instance_url IS NOT NULL "
            "AND btrim(provider_instance_url) <> '' "
            "AND webhook_auth_mode = 'shared_token')"
            ")"
        ),
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_instance_url_https",
        condition=(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(provider_instance_url ~ '^https://[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]+)?/?$' "
            "AND provider_instance_url !~ '^https://[^/]*\\.\\.' "
            "AND provider_instance_url !~ '^https://[^/]*\\.-' "
            "AND provider_instance_url !~ '^https://[^/]*\\.(?::[0-9]+)?/?$' "
            "AND provider_instance_url !~ '^https://[^/:/]*-(?::[0-9]+)?/?$' "
            "AND provider_instance_url !~ '^https://[^/]*[[:space:][:cntrl:]][^/]*' "
            "AND provider_instance_url !~ '^https://[^/]*-[.:/]')"
            ")"
        ),
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_instance_host_match",
        condition=(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(lower(regexp_replace(provider_instance_url, '^https://([^/:?#]+)(?::[0-9]+)?(?:/.*)?$', '\\1')) = CASE "
            "WHEN remote_url LIKE 'https://%' "
            "THEN lower(regexp_replace(remote_url, '^https://([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
            "WHEN remote_url LIKE 'git@%:%' "
            "THEN lower(regexp_replace(remote_url, '^git@([^:]+):.*$', '\\1')) "
            "WHEN remote_url LIKE 'ssh://%/%' "
            "THEN lower(regexp_replace(remote_url, '^ssh://(?:[^@/]+@)?([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
            "ELSE '' "
            "END)"
            ")"
        ),
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_https_port_match",
        condition=(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(remote_url NOT LIKE 'https://%/%') "
            "OR "
            "(coalesce(nullif(regexp_replace(provider_instance_url, '^https://[^/:?#]+(?::([0-9]+))?(?:/.*)?$', '\\1'), ''), '443') = "
            "coalesce(nullif(regexp_replace(remote_url, '^https://[^/:?#]+(?::([0-9]+))?/.*$', '\\1'), ''), '443'))"
            ")"
        ),
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_provider_project_path",
        condition=(
            "((provider <> 'gitlab_self_managed') "
            "OR (provider_project_path IS NOT NULL "
            "AND provider_project_path LIKE '%/%' "
            "AND provider_project_path NOT LIKE '/%' "
            "AND provider_project_path NOT LIKE '%/' "
            "AND provider_project_path NOT LIKE '%//%' "
            "AND provider_project_path NOT LIKE '%?%' "
            "AND provider_project_path NOT LIKE '%#%' "
            "AND provider_project_path !~ '[[:space:][:cntrl:]]' "
            "AND provider_project_path !~ '(^|/)\\.\\.?(/|$)'))"
        ),
    )
    _add_not_valid_check(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_project_path_match",
        condition=(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(provider_project_path IS NOT NULL AND provider_project_path = CASE "
            "WHEN remote_url LIKE 'https://%' "
            "THEN regexp_replace(regexp_replace(remote_url, '^https://[^/]+/', ''), '\\.git$', '') "
            "WHEN remote_url LIKE 'git@%:%' "
            "THEN regexp_replace(regexp_replace(remote_url, '^git@[^:]+:', ''), '\\.git$', '') "
            "WHEN remote_url LIKE 'ssh://%/%' "
            "THEN regexp_replace(regexp_replace(remote_url, '^ssh://(?:[^@/]+@)?[^/]+/', ''), '\\.git$', '') "
            "ELSE '' "
            "END)"
            ")"
        ),
    )
    for table_name, constraint_name in (
        ("repository_connections", "fk_repo_conn_active_webhook_secret_owner"),
        ("repository_events", "ck_repo_event_verified_secret_pair"),
        ("repository_connections", "ck_repo_conn_remote_url_host"),
        ("repository_connections", "ck_repo_conn_remote_url_no_userinfo"),
        ("repository_connections", "ck_repo_conn_provider_metadata"),
        ("repository_connections", "ck_repo_conn_gitlab_instance_url_https"),
        ("repository_connections", "ck_repo_conn_gitlab_instance_host_match"),
        ("repository_connections", "ck_repo_conn_gitlab_https_port_match"),
        ("repository_connections", "ck_repo_conn_provider_project_path"),
        ("repository_connections", "ck_repo_conn_gitlab_project_path_match"),
    ):
        _validate_constraint(table_name=table_name, constraint_name=constraint_name)

    for index_name, table_name, columns in (
        (
            "ix_repo_conn_active_webhook_secret_revision_id",
            "repository_connections",
            ("active_webhook_secret_revision_id",),
        ),
        (
            "ix_repo_conn_active_scope_rule_version_id",
            "repository_connections",
            ("active_scope_rule_version_id",),
        ),
        (
            "ix_repo_conn_active_credential_revision_id",
            "repository_connections",
            ("active_credential_revision_id",),
        ),
        (
            "ix_repo_conn_last_processed_event_id",
            "repository_connections",
            ("last_processed_event_id",),
        ),
        (
            "ix_repo_conn_plan_input_ref_id",
            "repository_connections",
            ("planning_input_reference_id",),
        ),
        (
            "ix_cred_rev_connection_id",
            "repository_credential_revisions",
            ("connection_id",),
        ),
        (
            "ix_webhook_secret_rev_connection_id",
            "webhook_secret_revisions",
            ("connection_id",),
        ),
        (
            "ix_scope_rule_plan_input_ref_id",
            "collection_scope_rule_versions",
            ("planning_input_reference_id",),
        ),
        (
            "ix_repository_event_verified_secret_revision_id",
            "repository_events",
            ("verified_secret_revision_id",),
        ),
        ("ix_repository_event_sync_run_id", "repository_events", ("sync_run_id",)),
        ("ix_repository_event_snapshot_id", "repository_events", ("snapshot_id",)),
        (
            "ix_repository_event_cursor_latest_event_id",
            "repository_event_cursors",
            ("latest_event_id",),
        ),
        ("ix_sync_run_trigger_event_id", "repository_sync_runs", ("trigger_event_id",)),
        (
            "ix_code_snapshot_scope_rule_version_id",
            "code_snapshots",
            ("scope_rule_version_id",),
        ),
        (
            "ix_code_snapshot_connection_id",
            "code_snapshots",
            ("connection_id",),
        ),
    ):
        _create_index_concurrently(
            index_name=index_name,
            table_name=table_name,
            columns=columns,
        )


def downgrade() -> None:
    if _count_rows(
        """
        SELECT count(*)
        FROM repository_connections
        WHERE provider = 'gitlab_self_managed'
        """
    ):
        raise RuntimeError(GITLAB_DOWNGRADE_BLOCKED_MESSAGE)
    if _count_rows(
        """
        SELECT count(*)
        FROM repository_events
        WHERE provider_event_idempotency_source <> 'delivery_header'
           OR provider_event_type = 'merge_request'
           OR domain_event_type = 'mr_received'
           OR target_kind = 'merge_request_source'
        """
    ):
        raise RuntimeError(EVENT_DOWNGRADE_BLOCKED_MESSAGE)
    if _count_rows(
        """
        SELECT count(*)
        FROM repository_sync_runs
        WHERE trigger_type = 'webhook_merge_request'
        """
    ):
        raise RuntimeError(SYNC_RUN_DOWNGRADE_BLOCKED_MESSAGE)

    _drop_check_constraint_if_exists(
        table_name="repository_events",
        constraint_name="ck_repo_event_verified_secret_pair",
    )
    op.drop_index("ix_code_snapshot_connection_id", table_name="code_snapshots")
    op.drop_index("ix_code_snapshot_scope_rule_version_id", table_name="code_snapshots")
    op.drop_index("ix_sync_run_trigger_event_id", table_name="repository_sync_runs")
    op.drop_index(
        "ix_repository_event_cursor_latest_event_id",
        table_name="repository_event_cursors",
    )
    op.drop_index("ix_repository_event_snapshot_id", table_name="repository_events")
    op.drop_index("ix_repository_event_sync_run_id", table_name="repository_events")
    op.drop_index(
        "ix_repository_event_verified_secret_revision_id",
        table_name="repository_events",
    )
    op.drop_index(
        "ix_scope_rule_plan_input_ref_id",
        table_name="collection_scope_rule_versions",
    )
    op.drop_index(
        "ix_webhook_secret_rev_connection_id",
        table_name="webhook_secret_revisions",
    )
    op.drop_index(
        "ix_cred_rev_connection_id",
        table_name="repository_credential_revisions",
    )
    op.drop_index(
        "ix_repo_conn_plan_input_ref_id",
        table_name="repository_connections",
    )
    op.drop_index(
        "ix_repo_conn_last_processed_event_id",
        table_name="repository_connections",
    )
    op.drop_index(
        "ix_repo_conn_active_credential_revision_id",
        table_name="repository_connections",
    )
    op.drop_index(
        "ix_repo_conn_active_scope_rule_version_id",
        table_name="repository_connections",
    )
    op.drop_constraint(
        "uq_repository_events_connection_delivery",
        "repository_events",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_repository_events_connection_delivery",
        "repository_events",
        ["connection_id", "provider_delivery_id"],
    )
    op.drop_column("repository_events", "provider_event_idempotency_source")

    op.drop_constraint(
        op.f("fk_repo_conn_active_webhook_secret_owner"),
        "repository_connections",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_repo_conn_active_webhook_secret_revision_id",
        table_name="repository_connections",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_project_path_match",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_provider_project_path",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_https_port_match",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_instance_host_match",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_gitlab_instance_url_https",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_provider_metadata",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_remote_url_host",
    )
    _drop_check_constraint_if_exists(
        table_name="repository_connections",
        constraint_name="ck_repo_conn_remote_url_no_userinfo",
    )
    op.drop_column("repository_connections", "last_reachability_failure_code")
    op.drop_column("repository_connections", "provider_reachability_status")
    op.drop_column("repository_connections", "webhook_auth_mode")
    op.drop_column("repository_connections", "provider_project_path")
    op.drop_column("repository_connections", "provider_instance_url")
    op.create_check_constraint(
        "ck_repo_conn_remote_url_host",
        "repository_connections",
        "(remote_url LIKE 'git@github.com:%' OR remote_url LIKE 'https://github.com/%')",
    )
    op.create_check_constraint(
        "ck_repo_conn_remote_url_no_userinfo",
        "repository_connections",
        "remote_url NOT LIKE 'https://%@%/%'",
    )

    _recreate_enum_without_values(
        type_name="sync_trigger_type",
        remaining_values=(
            "manual_initial",
            "manual_refresh",
            "webhook_push",
            "webhook_pull_request",
        ),
        table_name="repository_sync_runs",
        column_name="trigger_type",
    )
    _recreate_enum_without_values(
        type_name="event_target_kind",
        remaining_values=("default_ref", "pull_request_source", "none"),
        table_name="repository_events",
        column_name="target_kind",
    )
    _recreate_enum_without_values(
        type_name="domain_event_type",
        remaining_values=(
            "commit_recorded",
            "push_received",
            "pr_received",
            "signature_rejected",
            "secret_missing",
            "secret_mismatch",
        ),
        table_name="repository_events",
        column_name="domain_event_type",
    )
    _recreate_enum_without_values(
        type_name="provider_event_type",
        remaining_values=("push", "pull_request", "ping", "unknown"),
        table_name="repository_events",
        column_name="provider_event_type",
    )
    _recreate_enum_without_values(
        type_name="repository_provider",
        remaining_values=("github_cloud",),
        table_name="repository_connections",
        column_name="provider",
    )

    op.execute(sa.text("DROP TYPE provider_event_idempotency_source"))
    op.execute(sa.text("DROP TYPE provider_reachability_status"))
    op.execute(sa.text("DROP TYPE webhook_auth_mode"))
