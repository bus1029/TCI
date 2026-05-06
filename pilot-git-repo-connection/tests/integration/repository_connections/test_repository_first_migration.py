from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tci.api.schemas.repository_connection import serialize_repository_connection_detail
from tci.infrastructure.persistence.repository_connection_repository import (
    RepositoryConnectionRepository,
)


MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "009_repository_first_connections.py"
)


def test_repository_first_migration_makes_planning_references_nullable() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "planning_input_reference_id" in migration
    assert "repository_connections" in migration
    assert "collection_scope_rule_versions" in migration
    assert 'down_revision = "008_gitlab_insecure_http"' in migration
    assert "nullable=True" in migration
    assert "uq_repo_conn_workspace_github_repo" in migration
    assert "uq_repo_conn_workspace_gitlab_repo" in migration
    assert "ck_repo_conn_github_project_path_present" in migration
    assert 'conv(f"ck_{table_name}_{constraint_name}")' in migration
    assert "CREATE UNIQUE INDEX CONCURRENTLY" in migration
    assert "NOT VALID" in migration
    assert "VALIDATE CONSTRAINT" in migration
    assert "_abort_if_duplicate_repository_identities_exist()" in migration
    assert "provider_project_path IS NOT NULL" in migration
    assert (
        "provider_project_path = repository_owner || '/' || repository_name"
        in migration
    )
    assert (
        "provider_project_path <> repository_owner || '/' || repository_name"
        in migration
    )
    assert (
        "GitHub repository connections must have canonical provider_project_path before migration 009."
        in migration
    )


def test_repository_first_migration_preserves_legacy_planning_values() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "UPDATE repository_connections" not in migration
    assert "DELETE FROM planning_input_references" not in migration
    assert "DROP TABLE planning_input_references" not in migration


def test_persisted_legacy_planning_row_keeps_workspace_scope_and_trace() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_repository_first_projection_tables(engine)
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    planning_reference_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    with Session(engine) as session:
        _insert_legacy_planning_reference(
            session,
            workspace_id=workspace_id,
            planning_reference_id=planning_reference_id,
            created_at=now,
        )
        _insert_legacy_repository_connection(
            session,
            workspace_id=workspace_id,
            planning_reference_id=planning_reference_id,
            connection_id=connection_id,
            created_at=now,
        )
        session.commit()
        repository = RepositoryConnectionRepository(session)

        visible_connections = repository.list_for_workspace(workspace_id=workspace_id)
        hidden_connections = repository.list_for_workspace(
            workspace_id=other_workspace_id
        )
        detail = repository.get(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        wrong_workspace_detail = repository.get(
            workspace_id=other_workspace_id,
            connection_id=connection_id,
        )

        assert [connection.id for connection in visible_connections] == [connection_id]
        assert hidden_connections == []
        assert detail is not None
        assert wrong_workspace_detail is None
        assert detail.planning_input_reference is not None
        payload = serialize_repository_connection_detail(detail)
        origin = cast(dict[str, object], payload["origin"])
        traceability = cast(dict[str, object], payload["traceability"])
        assert origin["kind"] == "legacy_planning"
        assert traceability["planningInputReference"] == {
            "id": str(planning_reference_id),
            "sourceType": "user_request",
            "sourceReference": "chat://legacy",
            "approvedSpecPath": "specs/001-git-repo-connection/spec.md",
            "approvedPlanPath": "specs/001-git-repo-connection/plan.md",
        }


def test_repository_first_migration_blocks_unsafe_downgrade_after_new_rows() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "_abort_if_workspace_first_rows_exist()" in migration
    assert (
        "Cannot downgrade migration 009 while repository-first connections exist."
        in migration
    )


def _create_repository_first_projection_tables(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE planning_input_references (
                    id CHAR(32) PRIMARY KEY,
                    workspace_id CHAR(32) NOT NULL,
                    source_type VARCHAR(20) NOT NULL,
                    source_title VARCHAR(255) NOT NULL,
                    source_reference VARCHAR(1024) NOT NULL,
                    approved_spec_path VARCHAR(1024) NOT NULL,
                    approved_plan_path VARCHAR(1024) NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE collection_scope_rule_versions (
                    id CHAR(32) PRIMARY KEY,
                    connection_id CHAR(32) NOT NULL,
                    planning_input_reference_id CHAR(32),
                    include_paths JSON NOT NULL,
                    exclude_paths JSON NOT NULL,
                    allowed_file_types JSON NOT NULL,
                    blocked_file_types JSON NOT NULL,
                    max_file_size_bytes INTEGER NOT NULL,
                    exclude_binary BOOLEAN NOT NULL,
                    is_auto_default BOOLEAN NOT NULL,
                    warning_state VARCHAR(20) NOT NULL,
                    created_at DATETIME NOT NULL,
                    created_by CHAR(32) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE repository_connections (
                    id CHAR(32) PRIMARY KEY,
                    workspace_id CHAR(32) NOT NULL,
                    planning_input_reference_id CHAR(32),
                    provider VARCHAR(30) NOT NULL,
                    remote_url VARCHAR(2048) NOT NULL,
                    provider_instance_url VARCHAR(1024),
                    transport VARCHAR(10) NOT NULL,
                    repository_owner VARCHAR(255) NOT NULL,
                    repository_name VARCHAR(255) NOT NULL,
                    provider_project_path VARCHAR(512),
                    default_ref_type VARCHAR(20) NOT NULL,
                    default_ref_name VARCHAR(255) NOT NULL,
                    status VARCHAR(30) NOT NULL,
                    mirror_path VARCHAR(2048) NOT NULL,
                    active_scope_rule_version_id CHAR(32),
                    active_credential_revision_id CHAR(32),
                    active_webhook_secret_revision_id CHAR(32),
                    webhook_auth_mode VARCHAR(30) NOT NULL,
                    webhook_health_state VARCHAR(30) NOT NULL,
                    provider_reachability_status VARCHAR(30) NOT NULL,
                    last_reachability_failure_code VARCHAR(64),
                    last_webhook_rejection_reason VARCHAR(30),
                    last_webhook_rejected_at DATETIME,
                    last_verified_at DATETIME,
                    last_successful_snapshot_at DATETIME,
                    last_failed_sync_at DATETIME,
                    last_processed_event_id CHAR(32),
                    last_processed_event_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )


def _insert_legacy_planning_reference(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    planning_reference_id: uuid.UUID,
    created_at: datetime,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO planning_input_references (
                id,
                workspace_id,
                source_type,
                source_title,
                source_reference,
                approved_spec_path,
                approved_plan_path,
                created_at
            )
            VALUES (
                :id,
                :workspace_id,
                'user_request',
                'Legacy repository planning trace',
                'chat://legacy',
                'specs/001-git-repo-connection/spec.md',
                'specs/001-git-repo-connection/plan.md',
                :created_at
            )
            """
        ),
        {
            "id": planning_reference_id.hex,
            "workspace_id": workspace_id.hex,
            "created_at": created_at,
        },
    )


def _insert_legacy_repository_connection(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    planning_reference_id: uuid.UUID,
    connection_id: uuid.UUID,
    created_at: datetime,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO repository_connections (
                id,
                workspace_id,
                planning_input_reference_id,
                provider,
                remote_url,
                provider_instance_url,
                transport,
                repository_owner,
                repository_name,
                provider_project_path,
                default_ref_type,
                default_ref_name,
                status,
                mirror_path,
                active_scope_rule_version_id,
                active_credential_revision_id,
                active_webhook_secret_revision_id,
                webhook_auth_mode,
                webhook_health_state,
                provider_reachability_status,
                last_reachability_failure_code,
                last_webhook_rejection_reason,
                last_webhook_rejected_at,
                last_verified_at,
                last_successful_snapshot_at,
                last_failed_sync_at,
                last_processed_event_id,
                last_processed_event_at,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :workspace_id,
                :planning_reference_id,
                'github_cloud',
                'https://github.com/acme/sample-repo.git',
                NULL,
                'https',
                'acme',
                'sample-repo',
                'acme/sample-repo',
                'branch',
                'main',
                'active',
                '.runtime/git-mirrors/legacy.git',
                NULL,
                NULL,
                NULL,
                'hmac_sha256',
                'healthy',
                'reachable',
                NULL,
                NULL,
                NULL,
                :created_at,
                NULL,
                NULL,
                NULL,
                NULL,
                :created_at,
                :created_at
            )
            """
        ),
        {
            "id": connection_id.hex,
            "workspace_id": workspace_id.hex,
            "planning_reference_id": planning_reference_id.hex,
            "created_at": created_at,
        },
    )
