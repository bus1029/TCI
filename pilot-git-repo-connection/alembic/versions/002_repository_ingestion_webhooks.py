"""repository ingestion webhooks

Revision ID: 002_repository_ingestion_webhooks
Revises: 001_repository_ingestion_core
Create Date: 2026-04-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "002_repository_ingestion_webhooks"
down_revision = "001_repository_ingestion_core"
branch_labels = None
depends_on = None


WEBHOOK_SECRET_REVISION_STATUS = sa.Enum(
    "active",
    "previous_grace",
    "revoked",
    name="webhook_secret_revision_status",
)
WEBHOOK_HEALTH_STATE = sa.Enum(
    "healthy",
    "missing_secret",
    "secret_mismatch_detected",
    "signature_invalid_recently",
    name="webhook_health_state",
)
WEBHOOK_REJECTION_REASON = sa.Enum(
    "secret_missing",
    "secret_mismatch",
    "signature_invalid",
    name="webhook_rejection_reason",
)
PROVIDER_EVENT_TYPE = sa.Enum(
    "push",
    "pull_request",
    "ping",
    "unknown",
    name="provider_event_type",
)
DOMAIN_EVENT_TYPE = sa.Enum(
    "commit_recorded",
    "push_received",
    "pr_received",
    "signature_rejected",
    "secret_missing",
    "secret_mismatch",
    name="domain_event_type",
)
EVENT_TARGET_KIND = sa.Enum(
    "default_ref",
    "pull_request_source",
    "none",
    name="event_target_kind",
)
SIGNATURE_STATUS = sa.Enum(
    "verified",
    "secret_missing",
    "secret_mismatch",
    "signature_invalid",
    name="signature_status",
)
PROCESSING_DECISION = sa.Enum(
    "record_only",
    "queued",
    "duplicate_delivery",
    "duplicate_head",
    "stale_head",
    "rejected",
    name="processing_decision",
)
EVENT_PROCESSING_STATUS = sa.Enum(
    "received",
    "validated",
    "queued",
    "completed",
    "failed",
    "rejected",
    name="event_processing_status",
)
VERIFIED_WEBHOOK_SECRET_REVISION_STATUS = sa.Enum(
    "active",
    "previous_grace",
    "revoked",
    name="verified_webhook_secret_revision_status",
)
REPOSITORY_EVENT_REJECTION_REASON = sa.Enum(
    "secret_missing",
    "secret_mismatch",
    "signature_invalid",
    name="repository_event_rejection_reason",
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        WEBHOOK_SECRET_REVISION_STATUS,
        WEBHOOK_HEALTH_STATE,
        WEBHOOK_REJECTION_REASON,
        PROVIDER_EVENT_TYPE,
        DOMAIN_EVENT_TYPE,
        EVENT_TARGET_KIND,
        SIGNATURE_STATUS,
        PROCESSING_DECISION,
        EVENT_PROCESSING_STATUS,
        VERIFIED_WEBHOOK_SECRET_REVISION_STATUS,
        REPOSITORY_EVENT_REJECTION_REASON,
    ):
        enum_type.create(bind, checkfirst=True)

    op.add_column(
        "repository_connections",
        sa.Column("active_webhook_secret_revision_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "repository_connections",
        sa.Column(
            "webhook_health_state",
            WEBHOOK_HEALTH_STATE,
            nullable=False,
            server_default=sa.text("'healthy'"),
        ),
    )
    op.add_column(
        "repository_connections",
        sa.Column("last_webhook_rejection_reason", WEBHOOK_REJECTION_REASON, nullable=True),
    )
    op.add_column(
        "repository_connections",
        sa.Column("last_webhook_rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repository_connections",
        sa.Column("last_processed_event_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "repository_connections",
        sa.Column("last_processed_event_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "webhook_secret_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("status", WEBHOOK_SECRET_REVISION_STATUS, nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status != 'previous_grace' OR grace_until IS NOT NULL",
            name="ck_webhook_secret_rev_grace_until_required",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["repository_connections.id"],
            name="fk_webhook_secret_rev_conn_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_secret_revisions")),
        sa.UniqueConstraint(
            "connection_id",
            "id",
            name="uq_webhook_secret_rev_conn_id_id",
        ),
    )
    op.create_index(
        "ix_webhook_secret_rev_one_active",
        "webhook_secret_revisions",
        ["connection_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "repository_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_delivery_id", sa.String(length=255), nullable=False),
        sa.Column("provider_event_type", PROVIDER_EVENT_TYPE, nullable=False),
        sa.Column("provider_action", sa.String(length=128), nullable=True),
        sa.Column("domain_event_type", DOMAIN_EVENT_TYPE, nullable=False),
        sa.Column("target_kind", EVENT_TARGET_KIND, nullable=False),
        sa.Column("target_key", sa.String(length=255), nullable=False),
        sa.Column("target_ref_name", sa.String(length=255), nullable=True),
        sa.Column("target_head_sha", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signature_status", SIGNATURE_STATUS, nullable=False),
        sa.Column(
            "verified_secret_revision_status",
            VERIFIED_WEBHOOK_SECRET_REVISION_STATUS,
            nullable=True,
        ),
        sa.Column(
            "rejection_reason",
            REPOSITORY_EVENT_REJECTION_REASON,
            nullable=True,
        ),
        sa.Column("processing_decision", PROCESSING_DECISION, nullable=False),
        sa.Column("processing_status", EVENT_PROCESSING_STATUS, nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["repository_connections.id"],
            name="fk_repository_event_conn_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["repository_sync_runs.id"],
            name="fk_repository_event_sync_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["code_snapshots.id"],
            name="fk_repository_event_snapshot_id",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_events")),
        sa.UniqueConstraint(
            "connection_id",
            "provider_delivery_id",
            name="uq_repository_events_connection_delivery",
        ),
    )

    op.create_table(
        "repository_event_cursors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("target_key", sa.String(length=255), nullable=False),
        sa.Column("latest_head_sha", sa.String(length=64), nullable=False),
        sa.Column("latest_event_id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["repository_connections.id"],
            name="fk_repository_event_cursor_conn_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["latest_event_id"],
            ["repository_events.id"],
            name="fk_repository_event_cursor_latest_event_id",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_event_cursors")),
        sa.UniqueConstraint(
            "connection_id",
            "target_key",
            name="uq_repository_event_cursors_connection_target",
        ),
    )

    op.add_column(
        "repository_sync_runs",
        sa.Column("trigger_event_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sync_run_trigger_event_id",
        "repository_sync_runs",
        "repository_events",
        ["trigger_event_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_repo_conn_active_webhook_secret_id",
        "repository_connections",
        "webhook_secret_revisions",
        ["active_webhook_secret_revision_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_repo_conn_last_processed_event_id",
        "repository_connections",
        "repository_events",
        ["last_processed_event_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_repo_conn_last_processed_event_id",
        "repository_connections",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_repo_conn_active_webhook_secret_id",
        "repository_connections",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_sync_run_trigger_event_id",
        "repository_sync_runs",
        type_="foreignkey",
    )
    op.drop_column("repository_sync_runs", "trigger_event_id")

    op.drop_table("repository_event_cursors")
    op.drop_table("repository_events")
    op.drop_index("ix_webhook_secret_rev_one_active", table_name="webhook_secret_revisions")
    op.drop_table("webhook_secret_revisions")

    op.drop_column("repository_connections", "last_processed_event_at")
    op.drop_column("repository_connections", "last_processed_event_id")
    op.drop_column("repository_connections", "last_webhook_rejected_at")
    op.drop_column("repository_connections", "last_webhook_rejection_reason")
    op.drop_column("repository_connections", "webhook_health_state")
    op.drop_column("repository_connections", "active_webhook_secret_revision_id")

    bind = op.get_bind()
    for enum_type in (
        REPOSITORY_EVENT_REJECTION_REASON,
        VERIFIED_WEBHOOK_SECRET_REVISION_STATUS,
        EVENT_PROCESSING_STATUS,
        PROCESSING_DECISION,
        SIGNATURE_STATUS,
        EVENT_TARGET_KIND,
        DOMAIN_EVENT_TYPE,
        PROVIDER_EVENT_TYPE,
        WEBHOOK_REJECTION_REASON,
        WEBHOOK_HEALTH_STATE,
        WEBHOOK_SECRET_REVISION_STATUS,
    ):
        enum_type.drop(bind, checkfirst=True)
