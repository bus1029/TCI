"""scope rule preview failed warning state

Revision ID: 005_scope_rule_preview_failed
Revises: 004_gitlab_provider_support
Create Date: 2026-04-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "005_scope_rule_preview_failed"
down_revision = "004_gitlab_provider_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TYPE scope_rule_warning_state ADD VALUE IF NOT EXISTS 'preview_failed'"
        )
    )


def downgrade() -> None:
    pass
