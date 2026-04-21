from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.integration
def test_phase2_core_migration_round_trip() -> None:
    pytest.importorskip("alembic")

    database_url = os.getenv("TCI_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TCI_TEST_DATABASE_URL이 없어 Alembic round-trip 테스트를 건너뜁니다.")

    if os.getenv("TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS") != "1":
        pytest.skip("명시적 승인 환경 변수 없이 파괴적 migration round-trip을 실행하지 않습니다.")

    lower_url = database_url.lower()
    if "test" not in lower_url:
        pytest.skip("테스트 전용 데이터베이스 URL이 아니면 마이그레이션 round-trip을 실행하지 않습니다.")

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

    upgrade_002 = run_alembic("upgrade", "002_repository_ingestion_webhooks")
    assert upgrade_002.returncode == 0, upgrade_002.stderr

    upgrade_head = run_alembic("upgrade", "head")
    assert upgrade_head.returncode == 0, upgrade_head.stderr

    downgrade_002 = run_alembic("downgrade", "002_repository_ingestion_webhooks")
    assert downgrade_002.returncode == 0, downgrade_002.stderr

    downgrade_base = run_alembic("downgrade", "base")
    assert downgrade_base.returncode == 0, downgrade_base.stderr
