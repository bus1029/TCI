from __future__ import annotations

from logging.config import fileConfig
import os
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_database_url_from_env_file(env_path: Path) -> None:
    if "TCI_DATABASE_URL" in os.environ or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()

        key, separator, value = line.partition("=")
        if separator and key.strip() == "TCI_DATABASE_URL":
            os.environ["TCI_DATABASE_URL"] = _parse_env_file_value(value.strip())
            return


def _parse_env_file_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


_load_database_url_from_env_file(PROJECT_ROOT / ".env")

from tci.infrastructure.persistence.models import Base  # noqa: E402
from tci.settings import get_settings  # noqa: E402


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
database_url = settings.database_url or config.get_main_option("sqlalchemy.url")

if not database_url:
    raise RuntimeError(
        "Alembic을 실행하려면 TCI_DATABASE_URL 또는 alembic.ini의 sqlalchemy.url이 필요합니다."
    )

config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
