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

    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgrade.returncode == 0, upgrade.stderr

    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "downgrade", "base"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert downgrade.returncode == 0, downgrade.stderr
