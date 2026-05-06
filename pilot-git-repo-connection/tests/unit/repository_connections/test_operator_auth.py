from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tci.api.operator_auth import (
    consume_operator_auth_failure_budget,
    create_operator_session_cookie,
    is_valid_operator_session_cookie,
)
from tci.web.routes.operator_session import _read_limited_body


def test_operator_session_cookie_rejects_expired_tampered_and_wrong_token() -> None:
    cookie = create_operator_session_cookie(
        expected_token="test-operator-token",
        now=1_000.0,
    )

    assert is_valid_operator_session_cookie(
        expected_token="test-operator-token",
        cookie_value=cookie,
        now=1_001.0,
    )
    assert not is_valid_operator_session_cookie(
        expected_token="test-operator-token",
        cookie_value=cookie,
        now=30_000.0,
    )
    assert not is_valid_operator_session_cookie(
        expected_token="different-operator-token",
        cookie_value=cookie,
        now=1_001.0,
    )

    parts = cookie.split(".")
    wrong_version = ".".join(("v2", *parts[1:]))
    tampered_signature = ".".join((*parts[:3], "bad-signature"))
    assert not is_valid_operator_session_cookie(
        expected_token="test-operator-token",
        cookie_value=wrong_version,
        now=1_001.0,
    )
    assert not is_valid_operator_session_cookie(
        expected_token="test-operator-token",
        cookie_value=tampered_signature,
        now=1_001.0,
    )


def test_operator_session_body_reader_rejects_chunked_body_before_full_buffer() -> None:
    class ChunkedRequest:
        async def stream(self):
            yield b"x" * 4096
            yield b"x" * 4097
            raise AssertionError("reader consumed chunks after size limit")

    try:
        asyncio.run(_read_limited_body(ChunkedRequest()))
    except ValueError:
        return
    raise AssertionError("oversized chunked operator session body was accepted")


def test_operator_auth_rate_limit_uses_redis_outside_development(monkeypatch) -> None:
    values_by_key: dict[str, dict[str, int]] = {}

    class FakeRedis:
        def eval(self, script: str, key_count: int, key: str, *args):
            cutoff = int(args[0])
            now = int(args[1])
            member = str(args[2])
            max_failures = int(args[3])
            bucket = values_by_key.setdefault(key, {})
            for existing_member, score in list(bucket.items()):
                if score <= cutoff:
                    bucket.pop(existing_member)
            if len(bucket) >= max_failures:
                return 0
            bucket[member] = now
            return 1

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    environment="production",
                    redis_url="redis://prod",
                    gitlab_webhook_trusted_proxy_hosts=(),
                )
            )
        ),
        client=SimpleNamespace(host="203.0.113.99"),
        headers={},
    )

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())
    monkeypatch.setattr(
        "tci.api.operator_auth.OPERATOR_AUTH_RATE_LIMIT_MAX_FAILURES", 1
    )

    assert consume_operator_auth_failure_budget(request)
    assert not consume_operator_auth_failure_budget(request)
    assert "tci:operator-auth-rate:source:203.0.113.99" in values_by_key
