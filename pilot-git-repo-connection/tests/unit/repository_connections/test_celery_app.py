from __future__ import annotations

from pathlib import Path

import pytest

from tci.settings import load_settings


def test_create_celery_app_requires_redis_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("TCI_REDIS_URL", raising=False)

    from tci.workers.celery_app import create_celery_app

    settings = load_settings()

    with pytest.raises(RuntimeError, match="TCI_REDIS_URL"):
        create_celery_app(settings)


def test_create_celery_app_registers_repository_ingestion_queue_and_task_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_REDIS_URL", "redis://localhost:6379/0")

    from tci.infrastructure.queue.repository_ingestion_tasks import (
        REPOSITORY_INGESTION_QUEUE_NAME,
        REPOSITORY_INGESTION_TASK_ROUTES,
        RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME,
        RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
        RUN_WEBHOOK_SYNC_TASK_NAME,
        VERIFY_REPOSITORY_CONNECTION_TASK_NAME,
    )
    from tci.workers.celery_app import create_celery_app

    settings = load_settings()
    app = create_celery_app(settings)

    assert app.conf.broker_url == "redis://localhost:6379/0"
    assert app.conf.task_default_queue == REPOSITORY_INGESTION_QUEUE_NAME
    assert app.conf.task_routes == REPOSITORY_INGESTION_TASK_ROUTES
    assert [queue.name for queue in app.conf.task_queues] == [
        REPOSITORY_INGESTION_QUEUE_NAME
    ]
    assert VERIFY_REPOSITORY_CONNECTION_TASK_NAME in app.tasks
    assert RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME in app.tasks
    assert RUN_WEBHOOK_SYNC_TASK_NAME in app.tasks
    assert RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME in app.tasks


def test_get_celery_app_uses_current_settings_after_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()

    monkeypatch.setenv("TCI_PROJECT_ROOT", str(first_root))
    monkeypatch.setenv("TCI_REDIS_URL", "redis://localhost:6379/0")

    from tci.settings import get_settings
    from tci.workers.celery_app import get_celery_app

    get_settings.cache_clear()
    get_celery_app.cache_clear()
    first_app = get_celery_app()

    monkeypatch.setenv("TCI_PROJECT_ROOT", str(second_root))
    monkeypatch.setenv("TCI_REDIS_URL", "redis://localhost:6379/1")

    get_settings.cache_clear()
    get_celery_app.cache_clear()
    second_app = get_celery_app()

    assert first_app.conf.broker_url == "redis://localhost:6379/0"
    assert second_app.conf.broker_url == "redis://localhost:6379/1"


def test_celery_cli_proxy_resolves_to_cached_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_REDIS_URL", "redis://localhost:6379/0")

    from celery.app.utils import find_app
    from tci.settings import get_settings
    from tci.workers.celery_app import celery_app, get_celery_app

    get_settings.cache_clear()
    get_celery_app.cache_clear()

    assert celery_app.conf.broker_url == "redis://localhost:6379/0"
    assert celery_app.user_options is get_celery_app().user_options
    discovered_app = find_app("tci.workers.celery_app:celery_app")
    assert discovered_app.conf.broker_url == "redis://localhost:6379/0"
