from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import CheckConstraint, create_engine, text
from sqlalchemy.dialects import postgresql

from tci.infrastructure.persistence.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _destructive_migration_database_url() -> str:
    database_url = os.getenv("TCI_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TCI_TEST_DATABASE_URL이 없어 Alembic round-trip 테스트를 건너뜁니다."
        )
    if os.getenv("TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS") != "1":
        pytest.skip(
            "명시적 승인 환경 변수 없이 파괴적 migration round-trip을 실행하지 않습니다."
        )
    if "test" not in database_url.lower():
        pytest.skip(
            "테스트 전용 데이터베이스 URL이 아니면 마이그레이션 round-trip을 실행하지 않습니다."
        )
    return database_url


def _run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TCI_DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_revision_006_connection(connection, *, connection_id: uuid.UUID) -> None:
    workspace_id = uuid.uuid4()
    planning_input_reference_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO planning_input_references (
                id, workspace_id, source_type, source_title, source_reference,
                approved_spec_path, approved_plan_path
            )
            VALUES (
                :planning_input_reference_id, :workspace_id, 'user_request',
                'seed', 'manual://seed',
                'specs/002-gitlab-onprem-connection/spec.md',
                'specs/002-gitlab-onprem-connection/plan.md'
            )
            """
        ),
        {
            "planning_input_reference_id": planning_input_reference_id,
            "workspace_id": workspace_id,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO repository_connections (
                id, workspace_id, planning_input_reference_id, provider,
                remote_url, transport, repository_owner, repository_name,
                default_ref_type, default_ref_name, status, mirror_path
            )
            VALUES (
                :connection_id, :workspace_id, :planning_input_reference_id,
                'github_cloud', 'https://github.com/acme/sample-repo.git',
                'https', 'acme', 'sample-repo', 'branch', 'main',
                'active', 'mirrors/acme/sample-repo'
            )
            """
        ),
        {
            "connection_id": connection_id,
            "workspace_id": workspace_id,
            "planning_input_reference_id": planning_input_reference_id,
        },
    )


def _seed_revision_006_event_and_sync_run(
    connection,
    *,
    connection_id: uuid.UUID,
    target_key: str,
    requested_ref_name: str,
    status: str,
    event_id: uuid.UUID | None = None,
    sync_run_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    event_id = event_id or uuid.uuid4()
    sync_run_id = sync_run_id or uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO repository_events (
                id, connection_id, provider_delivery_id, provider_event_type,
                domain_event_type, target_kind, target_key, target_ref_name,
                target_head_sha, occurred_at, received_at, signature_status,
                processing_decision, processing_status, payload_hash
            )
            VALUES (
                :event_id, :connection_id, :provider_delivery_id, 'push',
                'push_received', 'default_ref', :target_key, :requested_ref_name,
                :target_head_sha, now(), now(), 'verified',
                'queued', 'queued', :payload_hash
            )
            """
        ),
        {
            "event_id": event_id,
            "connection_id": connection_id,
            "provider_delivery_id": f"seed-{event_id}",
            "target_key": target_key,
            "requested_ref_name": requested_ref_name,
            "target_head_sha": uuid.uuid4().hex + uuid.uuid4().hex[:8],
            "payload_hash": "a" * 64,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO repository_sync_runs (
                id, connection_id, trigger_event_id, trigger_type,
                requested_ref_type, requested_ref_name, status, started_at
            )
            VALUES (
                :sync_run_id, :connection_id, :event_id, 'webhook_push',
                'branch', :requested_ref_name, :status, now()
            )
            """
        ),
        {
            "sync_run_id": sync_run_id,
            "connection_id": connection_id,
            "event_id": event_id,
            "requested_ref_name": requested_ref_name,
            "status": status,
        },
    )
    connection.execute(
        text("UPDATE repository_events SET sync_run_id = :sync_run_id WHERE id = :event_id"),
        {"sync_run_id": sync_run_id, "event_id": event_id},
    )
    return event_id, sync_run_id


def _expected_metadata_check_names(table_names: tuple[str, ...]) -> set[str]:
    names: set[str] = set()
    preparer = postgresql.dialect().identifier_preparer
    for table_name in table_names:
        table = Base.metadata.tables[table_name]
        names.update(
            preparer.format_constraint(constraint)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
    return names


def _assert_live_check_names_match_metadata(database_url: str) -> None:
    table_names = ("repository_connections", "repository_events")
    expected_names = _expected_metadata_check_names(table_names)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE contype = 'c'
                      AND conrelid::regclass::text = ANY(:table_names)
                    """
                ),
                {"table_names": list(table_names)},
            )
            live_names = {str(row.conname) for row in rows}
    finally:
        engine.dispose()

    assert expected_names <= live_names


def _assert_active_sync_run_index_matches_migration(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            index_definition = connection.scalar(
                text(
                    """
                    SELECT indexdef
                    FROM pg_indexes
                    WHERE tablename = 'repository_sync_runs'
                      AND indexname = 'ix_sync_run_one_active_per_requested_ref'
                    """
                )
            )
    finally:
        engine.dispose()

    assert index_definition is not None
    assert "UNIQUE" in index_definition
    assert "connection_id" in index_definition
    assert "trigger_type" not in index_definition
    assert "requested_ref_type" in index_definition
    assert "requested_ref_key" in index_definition
    assert "status" in index_definition
    assert "pending" in index_definition
    assert "running" in index_definition


def _assert_blocked_sync_run_index_and_dispatch_column_match_migration(
    database_url: str,
) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            index_definition = connection.scalar(
                text(
                    """
                    SELECT indexdef
                    FROM pg_indexes
                    WHERE tablename = 'repository_sync_runs'
                      AND indexname = 'ix_sync_run_one_blocked_per_requested_ref'
                    """
                )
            )
            dispatch_column = connection.execute(
                text(
                    """
                    SELECT data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'repository_sync_runs'
                      AND column_name = 'dispatch_enqueued_at'
                    """
                )
            ).one_or_none()
            ref_key_column = connection.execute(
                text(
                    """
                    SELECT data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'repository_sync_runs'
                      AND column_name = 'requested_ref_key'
                    """
                )
            ).one_or_none()
    finally:
        engine.dispose()

    assert index_definition is not None
    assert "UNIQUE" in index_definition
    assert "connection_id" in index_definition
    assert "trigger_type" not in index_definition
    assert "requested_ref_type" in index_definition
    assert "requested_ref_key" in index_definition
    assert "status" in index_definition
    assert "blocked" in index_definition
    assert dispatch_column is not None
    assert dispatch_column.data_type == "timestamp with time zone"
    assert dispatch_column.is_nullable == "YES"
    assert ref_key_column is not None
    assert ref_key_column.data_type == "character varying"
    assert ref_key_column.is_nullable == "NO"
    assert ref_key_column.column_default is None


@pytest.mark.integration
def test_phase2_core_migration_round_trip() -> None:
    pytest.importorskip("alembic")

    database_url = _destructive_migration_database_url()

    upgrade_002 = _run_alembic(database_url, "upgrade", "002_ingestion_webhooks")
    assert upgrade_002.returncode == 0, upgrade_002.stderr

    upgrade_head = _run_alembic(database_url, "upgrade", "head")
    assert upgrade_head.returncode == 0, upgrade_head.stderr
    _assert_live_check_names_match_metadata(database_url)
    _assert_active_sync_run_index_matches_migration(database_url)
    _assert_blocked_sync_run_index_and_dispatch_column_match_migration(database_url)

    downgrade_002 = _run_alembic(database_url, "downgrade", "002_ingestion_webhooks")
    assert downgrade_002.returncode == 0, downgrade_002.stderr

    downgrade_base = _run_alembic(database_url, "downgrade", "base")
    assert downgrade_base.returncode == 0, downgrade_base.stderr


@pytest.mark.integration
def test_sync_run_active_guard_migrates_seeded_revision_006_rows() -> None:
    pytest.importorskip("alembic")
    database_url = _destructive_migration_database_url()

    downgrade_base = _run_alembic(database_url, "downgrade", "base")
    assert downgrade_base.returncode == 0, downgrade_base.stderr
    upgrade_006 = _run_alembic(database_url, "upgrade", "006_scope_rule_auto_default")
    assert upgrade_006.returncode == 0, upgrade_006.stderr

    engine = create_engine(database_url)
    connection_id = uuid.uuid4()
    try:
        with engine.begin() as connection:
            _seed_revision_006_connection(connection, connection_id=connection_id)
            default_event_id, _default_sync_run_id = _seed_revision_006_event_and_sync_run(
                connection,
                connection_id=connection_id,
                target_key="default_ref",
                requested_ref_name="main",
                status="pending",
            )
            pr_event_id, _pr_sync_run_id = _seed_revision_006_event_and_sync_run(
                connection,
                connection_id=connection_id,
                target_key="pr:101",
                requested_ref_name="feature/shared",
                status="blocked",
            )
            fallback_event_id, _fallback_sync_run_id = (
                _seed_revision_006_event_and_sync_run(
                    connection,
                    connection_id=connection_id,
                    target_key="",
                    requested_ref_name="release/1",
                    status="succeeded",
                )
            )

        upgrade_007 = _run_alembic(database_url, "upgrade", "007_sync_run_active_guard")
        assert upgrade_007.returncode == 0, upgrade_007.stderr

        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT trigger_event_id, requested_ref_key, dispatch_enqueued_at
                    FROM repository_sync_runs
                    WHERE connection_id = :connection_id
                    """
                ),
                {"connection_id": connection_id},
            ).all()
            values = {row.trigger_event_id: row for row in rows}
            ref_key_default = connection.scalar(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_name = 'repository_sync_runs'
                      AND column_name = 'requested_ref_key'
                    """
                )
            )
    finally:
        engine.dispose()

    assert values[default_event_id].requested_ref_key == "main"
    assert values[default_event_id].dispatch_enqueued_at is not None
    assert values[pr_event_id].requested_ref_key == "pr:101"
    assert values[pr_event_id].dispatch_enqueued_at is None
    assert values[fallback_event_id].requested_ref_key == "release/1"
    assert ref_key_default is None


@pytest.mark.integration
def test_sync_run_active_guard_rejects_seeded_duplicate_active_rows() -> None:
    pytest.importorskip("alembic")
    database_url = _destructive_migration_database_url()

    downgrade_base = _run_alembic(database_url, "downgrade", "base")
    assert downgrade_base.returncode == 0, downgrade_base.stderr
    upgrade_006 = _run_alembic(database_url, "upgrade", "006_scope_rule_auto_default")
    assert upgrade_006.returncode == 0, upgrade_006.stderr

    engine = create_engine(database_url)
    connection_id = uuid.uuid4()
    try:
        with engine.begin() as connection:
            _seed_revision_006_connection(connection, connection_id=connection_id)
            _seed_revision_006_event_and_sync_run(
                connection,
                connection_id=connection_id,
                target_key="default_ref",
                requested_ref_name="main",
                status="pending",
            )
            _seed_revision_006_event_and_sync_run(
                connection,
                connection_id=connection_id,
                target_key="default_ref",
                requested_ref_name="main",
                status="running",
            )

        upgrade_007 = _run_alembic(database_url, "upgrade", "007_sync_run_active_guard")
    finally:
        engine.dispose()

    assert upgrade_007.returncode != 0
    assert "중복 active sync run" in upgrade_007.stderr
