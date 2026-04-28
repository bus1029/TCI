"""sync run active trigger guard

Revision ID: 007_sync_run_active_guard
Revises: 006_scope_rule_auto_default
Create Date: 2026-04-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "007_sync_run_active_guard"
down_revision = "006_scope_rule_auto_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicate_count = op.get_bind().scalar(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT
                    sync_runs.connection_id,
                    sync_runs.requested_ref_type,
                    CASE
                        WHEN events.target_key IS NULL
                          OR events.target_key = ''
                          OR events.target_key = 'default_ref'
                        THEN sync_runs.requested_ref_name
                        ELSE events.target_key
                    END
                        AS requested_ref_key
                FROM repository_sync_runs AS sync_runs
                LEFT JOIN repository_events AS events
                    ON events.id = sync_runs.trigger_event_id
                WHERE sync_runs.status IN ('pending', 'running')
                GROUP BY
                    sync_runs.connection_id,
                    sync_runs.requested_ref_type,
                    CASE
                        WHEN events.target_key IS NULL
                          OR events.target_key = ''
                          OR events.target_key = 'default_ref'
                        THEN sync_runs.requested_ref_name
                        ELSE events.target_key
                    END
                HAVING count(*) > 1
            ) duplicate_active_runs
            """
        )
    )
    if duplicate_count:
        raise RuntimeError(
            "중복 active sync run을 정리한 뒤 migration을 실행해야 합니다."
        )
    duplicate_blocked_count = op.get_bind().scalar(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT
                    sync_runs.connection_id,
                    sync_runs.requested_ref_type,
                    CASE
                        WHEN events.target_key IS NULL
                          OR events.target_key = ''
                          OR events.target_key = 'default_ref'
                        THEN sync_runs.requested_ref_name
                        ELSE events.target_key
                    END
                        AS requested_ref_key
                FROM repository_sync_runs AS sync_runs
                LEFT JOIN repository_events AS events
                    ON events.id = sync_runs.trigger_event_id
                WHERE sync_runs.status = 'blocked'
                GROUP BY
                    sync_runs.connection_id,
                    sync_runs.requested_ref_type,
                    CASE
                        WHEN events.target_key IS NULL
                          OR events.target_key = ''
                          OR events.target_key = 'default_ref'
                        THEN sync_runs.requested_ref_name
                        ELSE events.target_key
                    END
                HAVING count(*) > 1
            ) duplicate_blocked_runs
            """
        )
    )
    if duplicate_blocked_count:
        raise RuntimeError(
            "중복 blocked sync run을 정리한 뒤 migration을 실행해야 합니다."
        )
    op.add_column(
        "repository_sync_runs",
        sa.Column("dispatch_enqueued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repository_sync_runs",
        sa.Column(
            "requested_ref_key",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE repository_sync_runs AS sync_runs
            SET requested_ref_key = CASE
                WHEN events.target_key IS NULL
                  OR events.target_key = ''
                  OR events.target_key = 'default_ref'
                THEN sync_runs.requested_ref_name
                ELSE events.target_key
            END
            FROM repository_events AS events
            WHERE events.id = sync_runs.trigger_event_id
              AND sync_runs.requested_ref_key = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE repository_sync_runs
            SET requested_ref_key = requested_ref_name
            WHERE requested_ref_key = ''
            """
        )
    )
    op.alter_column(
        "repository_sync_runs",
        "requested_ref_key",
        server_default=None,
    )
    op.execute(
        sa.text(
            """
            UPDATE repository_sync_runs
            SET dispatch_enqueued_at = now() - interval '16 minutes'
            WHERE status = 'pending'
              AND dispatch_enqueued_at IS NULL
            """
        )
    )
    op.create_index(
        "ix_sync_run_one_active_per_requested_ref",
        "repository_sync_runs",
        ["connection_id", "requested_ref_type", "requested_ref_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index(
        "ix_sync_run_one_blocked_per_requested_ref",
        "repository_sync_runs",
        ["connection_id", "requested_ref_type", "requested_ref_key"],
        unique=True,
        postgresql_where=sa.text("status = 'blocked'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sync_run_one_blocked_per_requested_ref",
        table_name="repository_sync_runs",
    )
    op.drop_index(
        "ix_sync_run_one_active_per_requested_ref",
        table_name="repository_sync_runs",
    )
    op.drop_column("repository_sync_runs", "requested_ref_key")
    op.drop_column("repository_sync_runs", "dispatch_enqueued_at")
