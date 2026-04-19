from __future__ import annotations

from functools import lru_cache

from celery import Celery

from tci.infrastructure.queue.repository_ingestion_tasks import (
    REPOSITORY_INGESTION_QUEUE_NAME,
    REPOSITORY_INGESTION_TASK_ROUTES,
    build_repository_ingestion_queues,
    register_repository_ingestion_tasks,
)
from tci.settings import Settings, get_settings


def create_celery_app(settings: Settings) -> Celery:
    if not settings.redis_url:
        raise RuntimeError(
            "Celery 브로커를 초기화하려면 TCI_REDIS_URL이 필요합니다."
        )

    app = Celery("tci", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        task_default_queue=REPOSITORY_INGESTION_QUEUE_NAME,
        task_queues=build_repository_ingestion_queues(),
        task_routes=REPOSITORY_INGESTION_TASK_ROUTES,
    )
    register_repository_ingestion_tasks(app)
    return app


@lru_cache(maxsize=1)
def get_celery_app() -> Celery:
    return create_celery_app(get_settings())
