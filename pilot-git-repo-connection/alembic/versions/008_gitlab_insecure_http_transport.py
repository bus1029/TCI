"""gitlab insecure http transport

Revision ID: 008_gitlab_insecure_http
Revises: 007_sync_run_active_guard
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import conv


revision = "008_gitlab_insecure_http"
down_revision = "007_sync_run_active_guard"
branch_labels = None
depends_on = None


TABLE_NAME = "repository_connections"
CONSTRAINTS = (
    "ck_repo_conn_remote_url_host",
    "ck_repo_conn_remote_url_no_userinfo",
    "ck_repo_conn_transport_remote_url_scheme_match",
    "ck_repo_conn_gitlab_instance_url_https",
    "ck_repo_conn_gitlab_instance_host_match",
    "ck_repo_conn_gitlab_https_port_match",
    "ck_repo_conn_gitlab_http_scheme_match",
    "ck_repo_conn_gitlab_project_path_match",
)

REMOTE_URL_HOST_HTTP = (
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
    "OR (remote_url LIKE 'http://%/%' "
    "AND remote_url !~* '^http://github\\.com\\.?(?::[0-9]+)?/' "
    "AND remote_url !~ '^http://[-[:space:][:cntrl:]]' "
    "AND remote_url !~ '^http://[^/]*\\.\\.' "
    "AND remote_url !~ '^http://[^/]*\\.-' "
    "AND remote_url !~ '^http://[^/?#]*\\.(?::[0-9]+)?/' "
    "AND remote_url !~ '^http://[^/]*-[.:/]' "
    "AND remote_url !~ '^http://[^/]*[[:space:][:cntrl:]][^/]*/' "
    "AND remote_url !~ '^http://\\[') "
    "OR (remote_url LIKE 'ssh://git@%/%' "
    "AND remote_url !~* '^ssh://(?:[^@/]+@)?github\\.com\\.?(?::[0-9]+)?/' "
    "AND remote_url !~ '^ssh://git@[-[:space:][:cntrl:]]' "
    "AND remote_url !~ '^ssh://git@[^/]*\\.\\.' "
    "AND remote_url !~ '^ssh://git@[^/]*\\.-' "
    "AND remote_url !~ '^ssh://git@[^/?#]*\\.(?::[0-9]+)?/' "
    "AND remote_url !~ '^ssh://git@[^/]*-[.:/]' "
    "AND remote_url !~ '^ssh://git@[^/]*[[:space:][:cntrl:]][^/]*/' "
    "AND remote_url !~ '^ssh://git@\\['))))"
)
REMOTE_URL_HOST_HTTPS = REMOTE_URL_HOST_HTTP.replace(
    "OR (remote_url LIKE 'http://%/%' "
    "AND remote_url !~* '^http://github\\.com\\.?(?::[0-9]+)?/' "
    "AND remote_url !~ '^http://[-[:space:][:cntrl:]]' "
    "AND remote_url !~ '^http://[^/]*\\.\\.' "
    "AND remote_url !~ '^http://[^/]*\\.-' "
    "AND remote_url !~ '^http://[^/?#]*\\.(?::[0-9]+)?/' "
    "AND remote_url !~ '^http://[^/]*-[.:/]' "
    "AND remote_url !~ '^http://[^/]*[[:space:][:cntrl:]][^/]*/' "
    "AND remote_url !~ '^http://\\[') ",
    "",
)
NO_USERINFO_HTTP = (
    "remote_url NOT LIKE 'https://%@%/%' "
    "AND remote_url NOT LIKE 'http://%@%/%' "
    "AND remote_url NOT LIKE 'ssh://%:%@%/%' "
    "AND remote_url NOT LIKE '%?%' "
    "AND remote_url NOT LIKE '%#%'"
)
NO_USERINFO_HTTPS = NO_USERINFO_HTTP.replace(
    "AND remote_url NOT LIKE 'http://%@%/%' ", ""
)
TRANSPORT_REMOTE_URL_SCHEME_MATCH = (
    "((transport = 'http' AND remote_url LIKE 'http://%/%') "
    "OR (transport = 'https' AND remote_url LIKE 'https://%/%') "
    "OR (transport = 'ssh' AND (remote_url LIKE 'git@%:%' OR remote_url LIKE 'ssh://%/%')))"
)
INSTANCE_URL_HTTP = (
    "((provider <> 'gitlab_self_managed') OR "
    "(provider_instance_url ~ '^https?://[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]+)?/?$' "
    "AND provider_instance_url !~ '^https?://[^/]*\\.\\.' "
    "AND provider_instance_url !~ '^https?://[^/]*\\.-' "
    "AND provider_instance_url !~ '^https?://[^/]*\\.(?::[0-9]+)?/?$' "
    "AND provider_instance_url !~ '^https?://[^/:/]*-(?::[0-9]+)?/?$' "
    "AND provider_instance_url !~ '^https?://[^/]*[[:space:][:cntrl:]][^/]*' "
    "AND provider_instance_url !~ '^https?://[^/]*-[.:/]'))"
)
INSTANCE_URL_HTTPS = INSTANCE_URL_HTTP.replace("https?://", "https://")
INSTANCE_HOST_HTTP = (
    "((provider <> 'gitlab_self_managed') OR "
    "(lower(regexp_replace(provider_instance_url, '^https?://([^/:?#]+)(?::[0-9]+)?(?:/.*)?$', '\\1')) = CASE "
    "WHEN remote_url LIKE 'https://%' THEN lower(regexp_replace(remote_url, '^https://([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
    "WHEN remote_url LIKE 'http://%' THEN lower(regexp_replace(remote_url, '^http://([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
    "WHEN remote_url LIKE 'git@%:%' THEN lower(regexp_replace(remote_url, '^git@([^:]+):.*$', '\\1')) "
    "WHEN remote_url LIKE 'ssh://%/%' THEN lower(regexp_replace(remote_url, '^ssh://(?:[^@/]+@)?([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
    "ELSE '' END))"
)
INSTANCE_HOST_HTTPS = (
    "((provider <> 'gitlab_self_managed') OR "
    "(lower(regexp_replace(provider_instance_url, '^https://([^/:?#]+)(?::[0-9]+)?(?:/.*)?$', '\\1')) = CASE "
    "WHEN remote_url LIKE 'https://%' THEN lower(regexp_replace(remote_url, '^https://([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
    "WHEN remote_url LIKE 'git@%:%' THEN lower(regexp_replace(remote_url, '^git@([^:]+):.*$', '\\1')) "
    "WHEN remote_url LIKE 'ssh://%/%' THEN lower(regexp_replace(remote_url, '^ssh://(?:[^@/]+@)?([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
    "ELSE '' END))"
)
PORT_MATCH_HTTP = (
    "((provider <> 'gitlab_self_managed') OR "
    "(remote_url NOT LIKE 'https://%/%' AND remote_url NOT LIKE 'http://%/%') OR "
    "(CASE WHEN provider_instance_url LIKE 'http://%' "
    "THEN coalesce(nullif(regexp_replace(provider_instance_url, '^http://[^/:?#]+(?::([0-9]+))?(?:/.*)?$', '\\1'), ''), '80') "
    "ELSE coalesce(nullif(regexp_replace(provider_instance_url, '^https://[^/:?#]+(?::([0-9]+))?(?:/.*)?$', '\\1'), ''), '443') END = "
    "CASE WHEN remote_url LIKE 'http://%' "
    "THEN coalesce(nullif(regexp_replace(remote_url, '^http://[^/:?#]+(?::([0-9]+))?/.*$', '\\1'), ''), '80') "
    "ELSE coalesce(nullif(regexp_replace(remote_url, '^https://[^/:?#]+(?::([0-9]+))?/.*$', '\\1'), ''), '443') END))"
)
PORT_MATCH_HTTPS = (
    "((provider <> 'gitlab_self_managed') OR "
    "(remote_url NOT LIKE 'https://%/%') OR "
    "(coalesce(nullif(regexp_replace(provider_instance_url, '^https://[^/:?#]+(?::([0-9]+))?(?:/.*)?$', '\\1'), ''), '443') = "
    "coalesce(nullif(regexp_replace(remote_url, '^https://[^/:?#]+(?::([0-9]+))?/.*$', '\\1'), ''), '443')))"
)
SCHEME_MATCH_HTTP = (
    "((provider <> 'gitlab_self_managed') OR "
    "(remote_url NOT LIKE 'https://%/%' AND remote_url NOT LIKE 'http://%/%') OR "
    "((provider_instance_url LIKE 'https://%' AND remote_url LIKE 'https://%/%') "
    "OR (provider_instance_url LIKE 'http://%' AND remote_url LIKE 'http://%/%')))"
)
PROJECT_PATH_HTTP = (
    "((provider <> 'gitlab_self_managed') OR "
    "(provider_project_path IS NOT NULL AND provider_project_path = CASE "
    "WHEN remote_url LIKE 'https://%' THEN regexp_replace(regexp_replace(remote_url, '^https://[^/]+/', ''), '\\.git$', '') "
    "WHEN remote_url LIKE 'http://%' THEN regexp_replace(regexp_replace(remote_url, '^http://[^/]+/', ''), '\\.git$', '') "
    "WHEN remote_url LIKE 'git@%:%' THEN regexp_replace(regexp_replace(remote_url, '^git@[^:]+:', ''), '\\.git$', '') "
    "WHEN remote_url LIKE 'ssh://%/%' THEN regexp_replace(regexp_replace(remote_url, '^ssh://(?:[^@/]+@)?[^/]+/', ''), '\\.git$', '') "
    "ELSE '' END))"
)
PROJECT_PATH_HTTPS = PROJECT_PATH_HTTP.replace(
    "WHEN remote_url LIKE 'http://%' THEN regexp_replace(regexp_replace(remote_url, '^http://[^/]+/', ''), '\\.git$', '') ",
    "",
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            sa.text("ALTER TYPE repository_transport ADD VALUE IF NOT EXISTS 'http'")
        )
    _drop_constraints()
    _create_constraints(
        {
            "ck_repo_conn_remote_url_host": REMOTE_URL_HOST_HTTP,
            "ck_repo_conn_remote_url_no_userinfo": NO_USERINFO_HTTP,
            "ck_repo_conn_transport_remote_url_scheme_match": TRANSPORT_REMOTE_URL_SCHEME_MATCH,
            "ck_repo_conn_gitlab_instance_url_https": INSTANCE_URL_HTTP,
            "ck_repo_conn_gitlab_instance_host_match": INSTANCE_HOST_HTTP,
            "ck_repo_conn_gitlab_https_port_match": PORT_MATCH_HTTP,
            "ck_repo_conn_gitlab_http_scheme_match": SCHEME_MATCH_HTTP,
            "ck_repo_conn_gitlab_project_path_match": PROJECT_PATH_HTTP,
        }
    )


def downgrade() -> None:
    http_connection_count = op.get_bind().scalar(
        sa.text(
            """
            SELECT count(*)
            FROM repository_connections
            WHERE transport = 'http'
               OR remote_url LIKE 'http://%'
               OR provider_instance_url LIKE 'http://%'
            """
        )
    )
    if http_connection_count:
        raise RuntimeError(
            "HTTP GitLab connections must be removed before downgrading 008."
        )
    _drop_constraints()
    _remove_http_transport_enum_value()
    _create_constraints(
        {
            "ck_repo_conn_remote_url_host": REMOTE_URL_HOST_HTTPS,
            "ck_repo_conn_remote_url_no_userinfo": NO_USERINFO_HTTPS,
            "ck_repo_conn_gitlab_instance_url_https": INSTANCE_URL_HTTPS,
            "ck_repo_conn_gitlab_instance_host_match": INSTANCE_HOST_HTTPS,
            "ck_repo_conn_gitlab_https_port_match": PORT_MATCH_HTTPS,
            "ck_repo_conn_gitlab_project_path_match": PROJECT_PATH_HTTPS,
        }
    )


def _remove_http_transport_enum_value() -> None:
    op.execute(
        sa.text("CREATE TYPE repository_transport_legacy AS ENUM ('ssh', 'https')")
    )
    op.execute(
        sa.text(
            "ALTER TABLE repository_connections "
            "ALTER COLUMN transport TYPE repository_transport_legacy "
            "USING transport::text::repository_transport_legacy"
        )
    )
    op.execute(sa.text("DROP TYPE repository_transport"))
    op.execute(
        sa.text("ALTER TYPE repository_transport_legacy RENAME TO repository_transport")
    )


def _drop_constraints() -> None:
    for constraint_name in CONSTRAINTS:
        for candidate_name in {
            constraint_name,
            _check_constraint_name(constraint_name=constraint_name),
        }:
            op.execute(
                sa.text(
                    f"ALTER TABLE {TABLE_NAME} DROP CONSTRAINT IF EXISTS {candidate_name}"
                )
            )


def _create_constraints(constraints: dict[str, str]) -> None:
    for constraint_name, condition in constraints.items():
        effective_constraint_name = _check_constraint_name(
            constraint_name=constraint_name
        )
        op.execute(
            sa.text(
                f"ALTER TABLE {TABLE_NAME} "
                f"ADD CONSTRAINT {effective_constraint_name} "
                f"CHECK ({condition}) NOT VALID"
            )
        )
        op.execute(
            sa.text(
                f"ALTER TABLE {TABLE_NAME} "
                f"VALIDATE CONSTRAINT {effective_constraint_name}"
            )
        )


def _check_constraint_name(*, constraint_name: str) -> str:
    metadata_name = conv(f"ck_{TABLE_NAME}_{constraint_name}")
    preparer = postgresql.dialect().identifier_preparer
    return preparer.truncate_and_render_constraint_name(metadata_name)
