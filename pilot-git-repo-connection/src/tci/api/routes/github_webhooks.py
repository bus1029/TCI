from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tci.api.routes.repository_connections import _problem_response
from tci.domain.services.process_github_event import (
    ProcessGitHubEventCommand,
    process_github_event,
)
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.infrastructure.queue.repository_ingestion_tasks import (
    RUN_WEBHOOK_SYNC_TASK_NAME,
)
from tci.workers.celery_app import create_celery_app


router = APIRouter(prefix="/api/webhooks/github", tags=["GitHubWebhooks"])


@router.post("/{connection_id}")
async def receive_github_webhook_route(connection_id: uuid.UUID, request: Request):
    raw_body = await request.body()
    delivery_id = request.headers.get("X-GitHub-Delivery")
    event_name = request.headers.get("X-GitHub-Event")
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not delivery_id or not event_name or not signature_header:
        return JSONResponse(
            status_code=400,
            content={
                "code": "INVALID_INPUT",
                "message": "GitHub webhook 필수 헤더가 누락되었습니다.",
            },
        )
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={
                "code": "INVALID_INPUT",
                "message": "GitHub webhook 본문이 올바른 JSON이 아닙니다.",
            },
        )

    try:
        enqueue_sync = None
        if request.app.state.settings.redis_url:
            celery_app = create_celery_app(request.app.state.settings)

            def enqueue_sync(*, connection_id: uuid.UUID, event_id: uuid.UUID, sync_run_id: uuid.UUID) -> None:
                try:
                    celery_app.send_task(
                        RUN_WEBHOOK_SYNC_TASK_NAME,
                        kwargs={
                            "connection_id": str(connection_id),
                            "event_id": str(event_id),
                            "sync_run_id": str(sync_run_id),
                        },
                    )
                except Exception as error:
                    raise RuntimeError("웹훅 동기화 작업 큐에 연결할 수 없습니다.") from error

        result = process_github_event(
            ProcessGitHubEventCommand(
                connection_id=connection_id,
                provider_delivery_id=delivery_id,
                provider_event_name=event_name,
                signature_header=signature_header,
                raw_body=raw_body,
                payload=payload,
            ),
            dependencies=request.app.state.dependencies,
            enqueue_sync=enqueue_sync,
        )
    except LookupError:
        return JSONResponse(status_code=404, content={"detail": "저장소 연결을 찾을 수 없습니다."})
    except RepositoryConnectionProblem as error:
        return _problem_response(error)
    except RuntimeError as error:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "deliveryId": result.provider_delivery_id,
            "eventId": str(result.event_id),
        },
    )
