from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
import json
import time
from threading import Lock
from typing import Protocol
import uuid

import anyio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tci.api.problem_details import ProblemCode
from tci.domain.services.process_github_event import record_webhook_enqueue_failure
from tci.domain.services.process_gitlab_event import (
    ProcessGitLabEventCommand,
    preflight_gitlab_webhook_token,
    process_gitlab_event,
    record_malformed_gitlab_webhook_attempt,
)
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.infrastructure.queue.repository_ingestion_tasks import (
    RUN_WEBHOOK_SYNC_TASK_NAME,
)
from tci.infrastructure.webhooks.gitlab_delivery_id import extract_gitlab_delivery_id
from tci.workers.celery_app import create_celery_app


router = APIRouter(prefix="/api/webhooks/gitlab", tags=["GitLabWebhooks"])
MAX_GITLAB_WEBHOOK_BODY_BYTES = 1024 * 1024
MAX_GITLAB_DELIVERY_ID_CHARS = 255
GITLAB_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS = 60.0
GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS = 120
GITLAB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS = 600
GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS = 4_096
GITLAB_WEBHOOK_PENDING_DISPATCH_RETRY_AFTER = timedelta(minutes=15)
_gitlab_webhook_source_request_times: OrderedDict[str, deque[float]] = OrderedDict()
_gitlab_webhook_connection_request_times: OrderedDict[
    tuple[str, uuid.UUID], deque[float]
] = OrderedDict()
_gitlab_webhook_rate_limit_lock = Lock()


class _BodyStreamRequest(Protocol):
    def stream(self) -> AsyncIterator[bytes]: ...


@router.post("/{connection_id}")
async def receive_gitlab_webhook_route(connection_id: uuid.UUID, request: Request):
    event_name = request.headers.get("X-Gitlab-Event")
    token_header = request.headers.get("X-Gitlab-Token")
    content_length = request.headers.get("content-length")
    source_key = _source_key(
        request,
        trusted_proxy_hosts=request.app.state.settings.gitlab_webhook_trusted_proxy_hosts,
    )
    try:
        rate_limit_allowed = await anyio.to_thread.run_sync(
            lambda: _allow_gitlab_webhook_request(
                connection_id=connection_id,
                source_key=source_key,
                redis_url=(
                    request.app.state.settings.redis_url
                    if request.app.state.settings.environment != "development"
                    else None
                ),
            )
        )
    except Exception:
        return _webhook_unavailable_response()
    if not rate_limit_allowed:
        return _unauthenticated_webhook_failure_response()
    header_delivery_id, header_idempotency_source = _extract_header_delivery(
        request.headers
    )
    if (
        header_delivery_id is not None
        and len(header_delivery_id) > MAX_GITLAB_DELIVERY_ID_CHARS
    ):
        return _unauthenticated_webhook_failure_response()
    if not event_name or token_header is None:
        return _unauthenticated_webhook_failure_response()
    try:
        await anyio.to_thread.run_sync(
            preflight_gitlab_webhook_token,
            connection_id,
            event_name,
            token_header,
            header_delivery_id,
            header_idempotency_source,
            request.app.state.dependencies,
        )
    except LookupError:
        return _unauthenticated_webhook_failure_response()
    except RepositoryConnectionProblem as error:
        return _webhook_problem_response(error)
    except RuntimeError:
        return _webhook_unavailable_response()
    if _is_oversized_content_length(content_length):
        await _record_malformed_attempt(connection_id, request)
        return _unauthenticated_webhook_failure_response()

    raw_body = await _read_limited_body(request)
    if raw_body is None:
        await _record_malformed_attempt(connection_id, request)
        return _unauthenticated_webhook_failure_response()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        await _record_malformed_attempt(connection_id, request)
        return _unauthenticated_webhook_failure_response()
    if not isinstance(payload, dict):
        await _record_malformed_attempt(connection_id, request)
        return _unauthenticated_webhook_failure_response()

    delivery = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name=event_name,
        headers=dict(request.headers.items()),
        payload=payload,
        raw_body=raw_body,
    )
    if len(delivery.delivery_id) > MAX_GITLAB_DELIVERY_ID_CHARS:
        return _unauthenticated_webhook_failure_response()
    try:
        result = await anyio.to_thread.run_sync(
            _process_gitlab_event_command,
            ProcessGitLabEventCommand(
                connection_id=connection_id,
                provider_delivery_id=delivery.delivery_id,
                provider_event_idempotency_source=delivery.idempotency_source,
                provider_event_name=event_name,
                token_header=token_header,
                raw_body=raw_body,
                payload=payload,
            ),
            request.app.state.dependencies,
        )
        if result.should_enqueue_sync and result.sync_run_id is not None:
            dispatch_event_id = result.dispatch_event_id or result.event_id
            if not request.app.state.settings.redis_url:
                await anyio.to_thread.run_sync(
                    _record_webhook_enqueue_failure,
                    connection_id,
                    dispatch_event_id,
                    result.sync_run_id,
                    request.app.state.dependencies,
                    "웹훅 동기화 작업 큐가 설정되지 않았습니다.",
                )
                return _webhook_unavailable_response()
            try:
                claimed = await anyio.to_thread.run_sync(
                    _claim_webhook_dispatch,
                    connection_id,
                    result.sync_run_id,
                    request.app.state.dependencies,
                )
                if not claimed:
                    return _unauthenticated_webhook_failure_response()
                await anyio.to_thread.run_sync(
                    _send_gitlab_sync_task,
                    request.app.state.settings,
                    connection_id,
                    dispatch_event_id,
                    result.sync_run_id,
                )
            except Exception:
                await anyio.to_thread.run_sync(
                    _record_webhook_enqueue_failure,
                    connection_id,
                    dispatch_event_id,
                    result.sync_run_id,
                    request.app.state.dependencies,
                    None,
                )
                return _webhook_unavailable_response()
    except LookupError:
        return _unauthenticated_webhook_failure_response()
    except RepositoryConnectionProblem as error:
        return _webhook_problem_response(error)
    except RuntimeError:
        return _webhook_unavailable_response()

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "deliveryId": result.provider_delivery_id,
            "eventId": str(result.event_id),
        },
    )


def _process_gitlab_event_command(command: ProcessGitLabEventCommand, dependencies):
    return process_gitlab_event(command, dependencies=dependencies)


def _send_gitlab_sync_task(
    settings,
    connection_id: uuid.UUID,
    event_id: uuid.UUID,
    sync_run_id: uuid.UUID,
) -> None:
    create_celery_app(settings).send_task(
        RUN_WEBHOOK_SYNC_TASK_NAME,
        kwargs={
            "connection_id": str(connection_id),
            "event_id": str(event_id),
            "sync_run_id": str(sync_run_id),
        },
    )


def _record_webhook_enqueue_failure(
    connection_id: uuid.UUID,
    event_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    dependencies,
    failure_message: str | None,
) -> None:
    if failure_message is None:
        record_webhook_enqueue_failure(
            connection_id=connection_id,
            event_id=event_id,
            sync_run_id=sync_run_id,
            dependencies=dependencies,
        )
        return
    record_webhook_enqueue_failure(
        connection_id=connection_id,
        event_id=event_id,
        sync_run_id=sync_run_id,
        dependencies=dependencies,
        failure_message=failure_message,
    )


def _claim_webhook_dispatch(
    connection_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    dependencies,
) -> bool:
    if dependencies.session_factory is None:
        return False
    enqueued_at = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        sync_run_repository = dependencies.repository_sync_run_repository_factory(
            session
        )
        return sync_run_repository.claim_dispatch_enqueued(
            connection_id=connection_id,
            sync_run_id=sync_run_id,
            enqueued_at=enqueued_at,
            stale_before=enqueued_at - GITLAB_WEBHOOK_PENDING_DISPATCH_RETRY_AFTER,
        )


async def _record_malformed_attempt(connection_id: uuid.UUID, request: Request) -> None:
    await anyio.to_thread.run_sync(
        lambda: record_malformed_gitlab_webhook_attempt(
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    )


def _extract_header_delivery(headers) -> tuple[str | None, str | None]:
    idempotency_key = headers.get("Idempotency-Key")
    if idempotency_key:
        return idempotency_key, "delivery_header"
    webhook_uuid = headers.get("X-Gitlab-Webhook-UUID")
    if webhook_uuid:
        return webhook_uuid, "uuid_header"
    return None, None


def _allow_gitlab_webhook_request(
    *,
    connection_id: uuid.UUID,
    source_key: str,
    redis_url: str | None = None,
    now_monotonic: float | None = None,
) -> bool:
    if redis_url:
        return _allow_gitlab_webhook_request_in_redis(
            connection_id=connection_id,
            source_key=source_key,
            redis_url=redis_url,
        )
    now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
    cutoff = now_monotonic - GITLAB_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS
    connection_bucket_key = (source_key, connection_id)
    with _gitlab_webhook_rate_limit_lock:
        source_request_times = _gitlab_webhook_source_request_times.get(source_key)
        if source_request_times is None:
            _prune_source_buckets(cutoff=cutoff)
            source_request_times = deque()
            _gitlab_webhook_source_request_times[source_key] = source_request_times
        _prune_request_times(source_request_times, cutoff=cutoff)
        if len(source_request_times) >= GITLAB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS:
            return False

        request_times = _gitlab_webhook_connection_request_times.get(
            connection_bucket_key
        )
        if request_times is None:
            _prune_connection_buckets(cutoff=cutoff)
            if (
                len(_gitlab_webhook_connection_request_times)
                >= GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS
            ):
                return False
            request_times = deque()
            _gitlab_webhook_connection_request_times[connection_bucket_key] = (
                request_times
            )
        else:
            _gitlab_webhook_connection_request_times.move_to_end(connection_bucket_key)
        _prune_request_times(request_times, cutoff=cutoff)
        if len(request_times) >= GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS:
            return False

        source_request_times.append(now_monotonic)
        request_times.append(now_monotonic)
        return True


def _allow_gitlab_webhook_request_in_redis(
    *, connection_id: uuid.UUID, source_key: str, redis_url: str
) -> bool:
    from redis import Redis

    redis = Redis.from_url(redis_url)
    window = int(GITLAB_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS)
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - (window * 1000)
    request_member = f"{now_ms}:{uuid.uuid4()}"
    source_key_name = f"tci:gitlab-webhook-rate:source:{source_key}"
    source_connections_key_name = (
        f"tci:gitlab-webhook-rate:source-connections:{source_key}"
    )
    connection_key_name = (
        "tci:gitlab-webhook-rate:connection:"
        f"{source_key}:{connection_id}"
    )
    pipe = redis.pipeline()
    pipe.zremrangebyscore(source_key_name, 0, cutoff_ms)
    pipe.zadd(source_key_name, {request_member: now_ms})
    pipe.zcard(source_key_name)
    pipe.expire(source_key_name, window)
    pipe.zremrangebyscore(source_connections_key_name, 0, cutoff_ms)
    pipe.zadd(source_connections_key_name, {str(connection_id): now_ms})
    pipe.zcard(source_connections_key_name)
    pipe.expire(source_connections_key_name, window)
    pipe.zremrangebyscore(connection_key_name, 0, cutoff_ms)
    pipe.zadd(connection_key_name, {request_member: now_ms})
    pipe.zcard(connection_key_name)
    pipe.expire(connection_key_name, window)
    (
        _source_pruned,
        _source_added,
        source_count,
        _source_expire,
        _source_connections_pruned,
        _source_connection_updated,
        source_connection_count,
        _source_connections_expire,
        _connection_pruned,
        _connection_added,
        connection_count,
        _connection_expire,
    ) = pipe.execute()
    return (
        int(source_count) <= GITLAB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS
        and int(source_connection_count)
        <= GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS
        and int(connection_count) <= GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS
    )


def _webhook_problem_response(error: RepositoryConnectionProblem) -> JSONResponse:
    problem_code = error.problem_code
    if (
        getattr(problem_code, "value", problem_code).startswith("WEBHOOK_")
        or problem_code is ProblemCode.INVALID_INPUT
    ):
        return _unauthenticated_webhook_failure_response()
    from tci.api.routes.repository_connections import _problem_response

    return _problem_response(error)


def _unauthenticated_webhook_failure_response() -> JSONResponse:
    return JSONResponse(status_code=202, content={"status": "accepted"})


def _prune_request_times(request_times: deque[float], *, cutoff: float) -> None:
    while request_times and request_times[0] <= cutoff:
        request_times.popleft()


def _source_key(request: Request, *, trusted_proxy_hosts: tuple[str, ...]) -> str:
    direct_host = _direct_host(request)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for and direct_host in trusted_proxy_hosts:
        return _source_from_forwarded_for(
            forwarded_for,
            trusted_proxy_hosts=trusted_proxy_hosts,
        )
    return direct_host


def _direct_host(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


def _source_from_forwarded_for(
    forwarded_for: str, *, trusted_proxy_hosts: tuple[str, ...]
) -> str:
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    if not hops:
        return "unknown"
    trusted_hops = set(trusted_proxy_hosts)
    for hop in reversed(hops):
        if hop not in trusted_hops:
            return hop
    return hops[0]


def _prune_connection_buckets(*, cutoff: float) -> None:
    expired_keys: list[tuple[str, uuid.UUID]] = []
    for key, request_times in _gitlab_webhook_connection_request_times.items():
        _prune_request_times(request_times, cutoff=cutoff)
        if not request_times:
            expired_keys.append(key)
    for key in expired_keys:
        _gitlab_webhook_connection_request_times.pop(key, None)


def _prune_source_buckets(*, cutoff: float) -> None:
    expired_keys: list[str] = []
    for key, request_times in _gitlab_webhook_source_request_times.items():
        _prune_request_times(request_times, cutoff=cutoff)
        if not request_times:
            expired_keys.append(key)
    for key in expired_keys:
        _gitlab_webhook_source_request_times.pop(key, None)


async def _read_limited_body(request: _BodyStreamRequest) -> bytes | None:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_GITLAB_WEBHOOK_BODY_BYTES:
            return None
        body.extend(chunk)
    return bytes(body)


def _is_oversized_content_length(content_length: str | None) -> bool:
    if content_length is None:
        return False
    try:
        return int(content_length) > MAX_GITLAB_WEBHOOK_BODY_BYTES
    except ValueError:
        return False


def _payload_too_large_response() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={
            "code": "PAYLOAD_TOO_LARGE",
            "message": "GitLab webhook 본문이 허용 크기를 초과했습니다.",
        },
    )


def _delivery_id_too_long_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "code": "INVALID_INPUT",
            "message": "GitLab webhook delivery id가 너무 깁니다.",
        },
    )


def _webhook_unavailable_response() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "GitLab webhook을 현재 처리할 수 없습니다."},
    )
