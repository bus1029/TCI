from __future__ import annotations

import base64
from collections import OrderedDict, deque
import hashlib
import hmac
import secrets
from threading import Lock
import time
import uuid

from fastapi import HTTPException, Request, status


OPERATOR_SESSION_COOKIE_NAME = "tci_operator_token"
OPERATOR_SESSION_COOKIE_MAX_AGE_SECONDS = 8 * 60 * 60
OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS = 60.0
OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES = 20
OPERATOR_AUTH_RATE_LIMIT_MAX_BUCKETS = 4_096
_OPERATOR_SESSION_COOKIE_VERSION = "v1"
_operator_auth_failure_times: OrderedDict[str, deque[float]] = OrderedDict()
_operator_auth_rate_limit_lock = Lock()


def require_operator_auth(request: Request) -> None:
    expected_token = getattr(request.app.state.settings, "operator_api_token", None)
    if expected_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="운영 API 토큰이 설정되지 않았습니다.",
        )

    if _has_valid_operator_auth(request=request, expected_token=expected_token):
        return
    if not consume_operator_auth_failure_budget(request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="운영 API 토큰 시도가 너무 많습니다.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="운영 API 토큰이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_operator_session_cookie(*, expected_token: str, now: float | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    expires_at = issued_at + OPERATOR_SESSION_COOKIE_MAX_AGE_SECONDS
    nonce = uuid.uuid4().hex
    payload = f"{_OPERATOR_SESSION_COOKIE_VERSION}.{expires_at}.{nonce}"
    signature = _operator_session_signature(payload, expected_token=expected_token)
    return f"{payload}.{signature}"


def _has_valid_operator_auth(*, request: Request, expected_token: str) -> bool:
    header_token = request.headers.get("X-TCI-Operator-Token")
    if is_valid_operator_token(
        expected_token=expected_token,
        supplied_token=header_token,
    ):
        return True

    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, separator, token = authorization.partition(" ")
        if separator and scheme.lower() == "bearer" and is_valid_operator_token(
            expected_token=expected_token,
            supplied_token=token.strip(),
        ):
            return True

    cookie_token = request.cookies.get(OPERATOR_SESSION_COOKIE_NAME)
    return is_valid_operator_session_cookie(
        expected_token=expected_token,
        cookie_value=cookie_token,
    )


def is_valid_operator_token(
    *, expected_token: str | None, supplied_token: str | None
) -> bool:
    return (
        expected_token is not None
        and supplied_token is not None
        and secrets.compare_digest(
            supplied_token,
            expected_token,
        )
    )


def is_operator_auth_allowed(request: Request, *, now_monotonic: float | None = None) -> bool:
    redis_url = _operator_auth_redis_url(request)
    if redis_url:
        return _is_operator_auth_allowed_in_redis(
            request=request,
            redis_url=redis_url,
        )
    now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
    cutoff = now_monotonic - OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS
    source_key = _operator_auth_source_key(request)
    with _operator_auth_rate_limit_lock:
        request_times = _operator_auth_failure_times.get(source_key)
        if request_times is None:
            _prune_operator_auth_failure_buckets(cutoff=cutoff)
            if len(_operator_auth_failure_times) >= OPERATOR_AUTH_RATE_LIMIT_MAX_BUCKETS:
                return False
            request_times = deque()
            _operator_auth_failure_times[source_key] = request_times
        else:
            _operator_auth_failure_times.move_to_end(source_key)
        _prune_request_times(request_times, cutoff=cutoff)
        return len(request_times) < OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES


def record_operator_auth_failure(
    request: Request, *, now_monotonic: float | None = None
) -> None:
    redis_url = _operator_auth_redis_url(request)
    if redis_url:
        _record_operator_auth_failure_in_redis(
            request=request,
            redis_url=redis_url,
        )
        return
    now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
    cutoff = now_monotonic - OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS
    source_key = _operator_auth_source_key(request)
    with _operator_auth_rate_limit_lock:
        request_times = _operator_auth_failure_times.get(source_key)
        if request_times is None:
            _prune_operator_auth_failure_buckets(cutoff=cutoff)
            if len(_operator_auth_failure_times) >= OPERATOR_AUTH_RATE_LIMIT_MAX_BUCKETS:
                _operator_auth_failure_times.popitem(last=False)
            request_times = deque()
            _operator_auth_failure_times[source_key] = request_times
        else:
            _operator_auth_failure_times.move_to_end(source_key)
        _prune_request_times(request_times, cutoff=cutoff)
        request_times.append(now_monotonic)


def consume_operator_auth_failure_budget(
    request: Request, *, now_monotonic: float | None = None
) -> bool:
    redis_url = _operator_auth_redis_url(request)
    if redis_url:
        return _consume_operator_auth_failure_budget_in_redis(
            request=request,
            redis_url=redis_url,
        )
    now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
    cutoff = now_monotonic - OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS
    source_key = _operator_auth_source_key(request)
    with _operator_auth_rate_limit_lock:
        request_times = _operator_auth_failure_times.get(source_key)
        if request_times is None:
            _prune_operator_auth_failure_buckets(cutoff=cutoff)
            if len(_operator_auth_failure_times) >= OPERATOR_AUTH_RATE_LIMIT_MAX_BUCKETS:
                return False
            request_times = deque()
            _operator_auth_failure_times[source_key] = request_times
        else:
            _operator_auth_failure_times.move_to_end(source_key)
        _prune_request_times(request_times, cutoff=cutoff)
        if len(request_times) >= OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES:
            return False
        request_times.append(now_monotonic)
        return True


def _operator_auth_redis_url(request: Request) -> str | None:
    settings = request.app.state.settings
    redis_url = getattr(settings, "redis_url", None)
    if getattr(settings, "environment", "development") == "development":
        return None
    return redis_url


def _is_operator_auth_allowed_in_redis(
    *, request: Request, redis_url: str
) -> bool:
    from redis import Redis

    redis = Redis.from_url(redis_url)
    window = int(OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS)
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - (window * 1000)
    key = f"tci:operator-auth-rate:source:{_operator_auth_source_key(request)}"
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, cutoff_ms)
    pipe.zcard(key)
    pipe.expire(key, window)
    _pruned, failure_count, _expire = pipe.execute()
    return int(failure_count) < OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES


def _record_operator_auth_failure_in_redis(
    *, request: Request, redis_url: str
) -> None:
    from redis import Redis

    redis = Redis.from_url(redis_url)
    window = int(OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS)
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - (window * 1000)
    key = f"tci:operator-auth-rate:source:{_operator_auth_source_key(request)}"
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, cutoff_ms)
    pipe.zadd(key, {f"{now_ms}:{uuid.uuid4()}": now_ms})
    pipe.expire(key, window)
    pipe.execute()


def _consume_operator_auth_failure_budget_in_redis(
    *, request: Request, redis_url: str
) -> bool:
    from redis import Redis

    redis = Redis.from_url(redis_url)
    key = f"tci:operator-auth-rate:source:{_operator_auth_source_key(request)}"
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - int(OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS * 1000)
    window = int(OPERATOR_AUTH_RATE_LIMIT_WINDOW_SECONDS)
    member = f"{now_ms}:{uuid.uuid4()}"
    script = """
local key = KEYS[1]
local cutoff = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local member = ARGV[3]
local max_failures = tonumber(ARGV[4])
local window = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local current = redis.call('ZCARD', key)
if current >= max_failures then
  redis.call('EXPIRE', key, window)
  return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window)
return 1
"""
    return bool(
        redis.eval(
            script,
            1,
            key,
            cutoff_ms,
            now_ms,
            member,
            OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES,
            window,
        )
    )


def is_valid_operator_session_cookie(
    *, expected_token: str | None, cookie_value: str | None, now: float | None = None
) -> bool:
    if expected_token is None or cookie_value is None:
        return False
    parts = cookie_value.split(".")
    if len(parts) != 4:
        return False
    version, raw_expires_at, nonce, supplied_signature = parts
    if version != _OPERATOR_SESSION_COOKIE_VERSION or not nonce:
        return False
    try:
        expires_at = int(raw_expires_at)
    except ValueError:
        return False
    now = time.time() if now is None else now
    if expires_at <= int(now):
        return False
    payload = f"{version}.{expires_at}.{nonce}"
    expected_signature = _operator_session_signature(
        payload,
        expected_token=expected_token,
    )
    return secrets.compare_digest(supplied_signature, expected_signature)


def _operator_session_signature(payload: str, *, expected_token: str) -> str:
    digest = hmac.new(
        expected_token.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _operator_auth_source_key(request: Request) -> str:
    direct_host = _direct_host(request)
    forwarded_for = request.headers.get("X-Forwarded-For")
    trusted_proxy_hosts = getattr(
        request.app.state.settings,
        "gitlab_webhook_trusted_proxy_hosts",
        (),
    )
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


def _prune_request_times(request_times: deque[float], *, cutoff: float) -> None:
    while request_times and request_times[0] <= cutoff:
        request_times.popleft()


def _prune_operator_auth_failure_buckets(*, cutoff: float) -> None:
    expired_keys: list[str] = []
    for key, request_times in _operator_auth_failure_times.items():
        _prune_request_times(request_times, cutoff=cutoff)
        if not request_times:
            expired_keys.append(key)
    for key in expired_keys:
        _operator_auth_failure_times.pop(key, None)
