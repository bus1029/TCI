"""scope rule auto default flag

Revision ID: 006_scope_rule_auto_default
Revises: 005_scope_rule_preview_failed
Create Date: 2026-04-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "006_scope_rule_auto_default"
down_revision = "005_scope_rule_preview_failed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "collection_scope_rule_versions",
        sa.Column(
            "is_auto_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE collection_scope_rule_versions
            SET is_auto_default = true
            WHERE include_paths = '[]'::jsonb
              AND exclude_paths = '[]'::jsonb
              AND allowed_file_types = '[]'::jsonb
              AND blocked_file_types = '[]'::jsonb
              AND max_file_size_bytes = 5242880
              AND exclude_binary = true
              AND warning_state = 'ok'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("collection_scope_rule_versions", "is_auto_default")
