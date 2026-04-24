from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import CheckConstraint, create_engine, text
from sqlalchemy.dialects import postgresql

from tci.infrastructure.persistence.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


@pytest.mark.integration
def test_phase2_core_migration_round_trip() -> None:
    pytest.importorskip("alembic")

    database_url = os.getenv("TCI_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TCI_TEST_DATABASE_URL이 없어 Alembic round-trip 테스트를 건너뜁니다."
        )

    if os.getenv("TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS") != "1":
        pytest.skip(
            "명시적 승인 환경 변수 없이 파괴적 migration round-trip을 실행하지 않습니다."
        )

    lower_url = database_url.lower()
    if "test" not in lower_url:
        pytest.skip(
            "테스트 전용 데이터베이스 URL이 아니면 마이그레이션 round-trip을 실행하지 않습니다."
        )

    env = os.environ.copy()
    env["TCI_DATABASE_URL"] = database_url

    def run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    upgrade_002 = run_alembic("upgrade", "002_ingestion_webhooks")
    assert upgrade_002.returncode == 0, upgrade_002.stderr

    upgrade_head = run_alembic("upgrade", "head")
    assert upgrade_head.returncode == 0, upgrade_head.stderr
    _assert_live_check_names_match_metadata(database_url)

    downgrade_002 = run_alembic("downgrade", "002_ingestion_webhooks")
    assert downgrade_002.returncode == 0, downgrade_002.stderr

    downgrade_base = run_alembic("downgrade", "base")
    assert downgrade_base.returncode == 0, downgrade_base.stderr
