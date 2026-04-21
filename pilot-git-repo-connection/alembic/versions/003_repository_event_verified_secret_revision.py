"""repository event verified secret revision

Revision ID: 003_event_secret_revision
Revises: 002_ingestion_webhooks
Create Date: 2026-04-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "003_event_secret_revision"
down_revision = "002_ingestion_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repository_events",
        sa.Column("verified_secret_revision_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_repository_event_verified_webhook_secret_revision_owner",
        "repository_events",
        "webhook_secret_revisions",
        ["connection_id", "verified_secret_revision_id"],
        ["connection_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_repository_event_verified_webhook_secret_revision_owner",
        "repository_events",
        type_="foreignkey",
    )
    op.drop_column("repository_events", "verified_secret_revision_id")
