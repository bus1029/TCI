from __future__ import annotations

import asyncio
import json
from typing import Any, cast
import uuid

from tests.support.repository_connection_testkit import (
    build_gitlab_merge_request_payload,
    build_gitlab_push_payload,
    serialize_gitlab_webhook_payload,
)
from tci.domain.services.repository_event_processing import (
    ProviderEventDecisionInput,
    decide_provider_event_processing,
)
from tci.infrastructure.webhooks.gitlab_delivery_id import extract_gitlab_delivery_id
from tci.infrastructure.webhooks.gitlab_event_parser import parse_gitlab_event_payload
from tci.infrastructure.webhooks.gitlab_token_verifier import (
    GitLabTokenVerificationInput,
    evaluate_gitlab_token_verification,
)
from tci.api.routes import gitlab_webhooks
from tci.api.routes.gitlab_webhooks import _read_limited_body
from tci.api.routes.gitlab_webhooks import (
    GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS,
    GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS,
    _allow_gitlab_webhook_request,
    _source_key,
    _gitlab_webhook_connection_request_times,
    _gitlab_webhook_source_request_times,
)


def test_gitlab_delivery_id_extraction_prefers_idempotency_key_then_webhook_uuid() -> (
    None
):
    connection_id = uuid.uuid4()
    payload = build_gitlab_push_payload()
    raw_body = serialize_gitlab_webhook_payload(payload)

    preferred = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={
            "Idempotency-Key": "idem-001",
            "X-Gitlab-Webhook-UUID": "uuid-001",
        },
        payload=payload,
        raw_body=raw_body,
    )
    fallback_uuid = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={"X-Gitlab-Webhook-UUID": "uuid-001"},
        payload=payload,
        raw_body=raw_body,
    )
    derived = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={},
        payload=payload,
        raw_body=raw_body,
    )

    assert preferred.delivery_id == "idem-001"
    assert preferred.idempotency_source == "delivery_header"
    assert fallback_uuid.delivery_id == "uuid-001"
    assert fallback_uuid.idempotency_source == "uuid_header"
    assert derived.delivery_id.startswith("gitlab:")
    assert derived.idempotency_source == "derived_hash"


def test_gitlab_delivery_id_fallback_uses_semantic_event_identity_only() -> None:
    connection_id = uuid.uuid4()
    payload = build_gitlab_push_payload(after_sha="b" * 40)
    compact_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    pretty_body = json.dumps(payload, indent=2).encode("utf-8")

    compact = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={},
        payload=payload,
        raw_body=compact_body,
    )
    pretty = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={},
        payload=payload,
        raw_body=pretty_body,
    )

    assert compact.delivery_id == pretty.delivery_id
    assert compact.idempotency_source == "derived_hash"


def test_gitlab_delivery_id_fallback_distinguishes_same_sha_different_refs() -> None:
    connection_id = uuid.uuid4()
    main_payload = build_gitlab_push_payload(ref_name="main", after_sha="b" * 40)
    release_payload = build_gitlab_push_payload(
        ref_name="release/1.0",
        after_sha="b" * 40,
    )

    main_delivery = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={},
        payload=main_payload,
        raw_body=serialize_gitlab_webhook_payload(main_payload),
    )
    release_delivery = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={},
        payload=release_payload,
        raw_body=serialize_gitlab_webhook_payload(release_payload),
    )

    assert main_delivery.delivery_id != release_delivery.delivery_id


def test_gitlab_delivery_id_fallback_distinguishes_same_ref_sha_different_before() -> (
    None
):
    connection_id = uuid.uuid4()
    first_payload = build_gitlab_push_payload(ref_name="main", after_sha="b" * 40)
    second_payload = build_gitlab_push_payload(ref_name="main", after_sha="b" * 40)
    first_payload["before"] = "a" * 40
    second_payload["before"] = "c" * 40

    first_delivery = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={},
        payload=first_payload,
        raw_body=serialize_gitlab_webhook_payload(first_payload),
    )
    second_delivery = extract_gitlab_delivery_id(
        connection_id=connection_id,
        event_name="Push Hook",
        headers={},
        payload=second_payload,
        raw_body=serialize_gitlab_webhook_payload(second_payload),
    )

    assert first_delivery.delivery_id != second_delivery.delivery_id


def test_gitlab_webhook_rate_limit_is_scoped_by_connection_without_source_ip() -> None:
    _gitlab_webhook_connection_request_times.clear()
    connection_id = uuid.uuid4()

    for _ in range(GITLAB_WEBHOOK_RATE_LIMIT_MAX_REQUESTS):
        assert _allow_gitlab_webhook_request(
            connection_id=connection_id,
            source_key="proxy",
            now_monotonic=100.0,
        )

    assert not _allow_gitlab_webhook_request(
        connection_id=connection_id,
        source_key="proxy",
        now_monotonic=100.0,
    )
    assert _allow_gitlab_webhook_request(
        connection_id=connection_id,
        source_key="gitlab-source",
        now_monotonic=100.0,
    )
    assert _allow_gitlab_webhook_request(
        connection_id=connection_id,
        source_key="proxy",
        now_monotonic=161.0,
    )


def test_gitlab_webhook_rate_limit_caps_connection_bucket_growth(monkeypatch) -> None:
    _gitlab_webhook_connection_request_times.clear()
    _gitlab_webhook_source_request_times.clear()
    monkeypatch.setattr(
        gitlab_webhooks,
        "GITLAB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS",
        GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS + 1,
    )

    for _ in range(GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS):
        assert _allow_gitlab_webhook_request(
            connection_id=uuid.uuid4(),
            source_key="proxy",
            now_monotonic=200.0,
        )

    new_connection_id = uuid.uuid4()
    assert not _allow_gitlab_webhook_request(
        connection_id=new_connection_id,
        source_key="proxy",
        now_monotonic=200.0,
    )
    assert (
        len(_gitlab_webhook_connection_request_times)
        == GITLAB_WEBHOOK_RATE_LIMIT_MAX_CONNECTION_BUCKETS
    )
    assert ("proxy", new_connection_id) not in _gitlab_webhook_connection_request_times


def test_gitlab_source_key_only_trusts_forwarded_for_from_configured_proxy() -> None:
    class Client:
        host = "proxy.local"

    class Request:
        client = Client()
        headers = {"X-Forwarded-For": "198.51.100.10, proxy.local"}

    request = Request()
    typed_request = cast(Any, request)

    assert (
        _source_key(typed_request, trusted_proxy_hosts=("proxy.local",))
        == "198.51.100.10"
    )
    assert _source_key(typed_request, trusted_proxy_hosts=()) == "proxy.local"


def test_gitlab_source_key_ignores_spoofed_leftmost_forwarded_for() -> None:
    class Client:
        host = "proxy.local"

    class Request:
        client = Client()
        headers = {"X-Forwarded-For": "198.51.100.10, 203.0.113.20, proxy.local"}

    request = cast(Any, Request())

    assert _source_key(request, trusted_proxy_hosts=("proxy.local",)) == "203.0.113.20"


def test_gitlab_token_verification_requires_active_exact_match_only() -> None:
    missing = evaluate_gitlab_token_verification(
        GitLabTokenVerificationInput(
            active_secret=None,
            token_header="webhook-secret",
            active_secret_revision_id=None,
        )
    )
    mismatch = evaluate_gitlab_token_verification(
        GitLabTokenVerificationInput(
            active_secret="webhook-secret",
            token_header="wrong-secret",
            active_secret_revision_id=uuid.uuid4(),
        )
    )
    verified_revision_id = uuid.uuid4()
    verified = evaluate_gitlab_token_verification(
        GitLabTokenVerificationInput(
            active_secret="webhook-secret",
            token_header="webhook-secret",
            active_secret_revision_id=verified_revision_id,
        )
    )

    assert missing.signature_status == "secret_missing"
    assert missing.is_verified is False
    assert mismatch.signature_status == "secret_mismatch"
    assert mismatch.is_verified is False
    assert verified.signature_status == "verified"
    assert verified.verified_secret_revision_id == verified_revision_id
    assert verified.verified_secret_revision_status == "active"


def test_gitlab_merge_request_update_gates_record_only_vs_queued() -> None:
    record_only_event = parse_gitlab_event_payload(
        event_name="Merge Request Hook",
        payload=build_gitlab_merge_request_payload(
            action="update",
            last_commit_sha="b" * 40,
        ),
    )
    code_moving_event = parse_gitlab_event_payload(
        event_name="Merge Request Hook",
        payload=build_gitlab_merge_request_payload(
            action="update",
            oldrev="a" * 40,
            last_commit_sha="b" * 40,
        ),
    )

    record_only_decision = decide_provider_event_processing(
        ProviderEventDecisionInput(
            provider_event_type=record_only_event.provider_event_type.value,
            provider_action=record_only_event.provider_action,
            target_head_sha=record_only_event.target_head_sha,
            delivery_already_seen=False,
            latest_cursor_head_sha="b" * 40,
            resolved_current_head_sha="b" * 40,
            is_code_moving=False,
        )
    )
    queued_decision = decide_provider_event_processing(
        ProviderEventDecisionInput(
            provider_event_type=code_moving_event.provider_event_type.value,
            provider_action=code_moving_event.provider_action,
            target_head_sha=code_moving_event.target_head_sha,
            delivery_already_seen=False,
            latest_cursor_head_sha="a" * 40,
            resolved_current_head_sha="b" * 40,
            is_code_moving=True,
        )
    )

    assert record_only_decision.processing_decision == "record_only"
    assert record_only_decision.should_queue_sync is False
    assert queued_decision.processing_decision == "queued"
    assert queued_decision.should_queue_sync is True


def test_gitlab_push_payload_requires_valid_branch_ref() -> None:
    payload = build_gitlab_push_payload()
    payload["ref"] = None

    try:
        parse_gitlab_event_payload(event_name="Push Hook", payload=payload)
    except ValueError as error:
        assert str(error) == "GitLab webhook ref 형식이 올바르지 않습니다."
    else:
        raise AssertionError("missing GitLab ref should be rejected")


def test_gitlab_event_header_must_match_payload_kind() -> None:
    payload = build_gitlab_push_payload()
    payload["object_kind"] = "tag_push"
    payload["ref"] = "refs/tags/v1.0.0"

    try:
        parse_gitlab_event_payload(event_name="Push Hook", payload=payload)
    except ValueError as error:
        assert (
            str(error) == "GitLab webhook 이벤트 헤더와 본문 유형이 일치하지 않습니다."
        )
    else:
        raise AssertionError("mismatched GitLab event kind should be rejected")


def test_process_gitlab_event_marks_duplicate_and_stale_deliveries_without_snapshot() -> (
    None
):
    duplicate_delivery = decide_provider_event_processing(
        ProviderEventDecisionInput(
            provider_event_type="push",
            provider_action=None,
            target_head_sha="a" * 40,
            delivery_already_seen=True,
            latest_cursor_head_sha=None,
            resolved_current_head_sha="a" * 40,
        )
    )
    stale_head = decide_provider_event_processing(
        ProviderEventDecisionInput(
            provider_event_type="push",
            provider_action=None,
            target_head_sha="c" * 40,
            delivery_already_seen=False,
            latest_cursor_head_sha="b" * 40,
            resolved_current_head_sha="b" * 40,
        )
    )

    assert duplicate_delivery.processing_decision == "duplicate_delivery"
    assert duplicate_delivery.should_queue_sync is False
    assert stale_head.processing_decision == "stale_head"
    assert stale_head.should_queue_sync is False


def test_gitlab_limited_body_reader_rejects_chunk_before_appending() -> None:
    class StreamingRequest:
        def __init__(self, chunk: bytes) -> None:
            self.consumed = 0
            self._chunk = chunk

        async def stream(self):
            self.consumed += 1
            yield self._chunk

    async def run_check() -> None:
        chunk = b"x" * (1024 * 1024 + 1)
        request = StreamingRequest(chunk)

        result = await _read_limited_body(request)

        assert result is None
        assert request.consumed == 1

    asyncio.run(run_check())
