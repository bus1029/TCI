from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tci.infrastructure.webhooks.github_event_parser import parse_github_event_payload


def test_parse_github_push_rejects_invalid_ref_prefix() -> None:
    with pytest.raises(ValueError, match="ref 형식"):
        parse_github_event_payload(
            event_name="push",
            payload={"ref": "refs/notes/main", "repository": {"full_name": "a/b"}},
            received_at=datetime.now(tz=UTC),
        )


def test_parse_github_push_rejects_empty_ref_name() -> None:
    with pytest.raises(ValueError, match="ref 형식"):
        parse_github_event_payload(
            event_name="push",
            payload={"ref": "refs/heads/", "repository": {"full_name": "a/b"}},
            received_at=datetime.now(tz=UTC),
        )


def test_parse_github_pull_request_rejects_overlong_head_ref() -> None:
    with pytest.raises(ValueError, match="ref 이름이 너무 깁니다"):
        parse_github_event_payload(
            event_name="pull_request",
            payload={
                "action": "opened",
                "number": 1,
                "repository": {"full_name": "a/b"},
                "pull_request": {
                    "head": {"ref": "f" * 256, "sha": "a" * 40},
                    "base": {"ref": "main"},
                },
            },
            received_at=datetime.now(tz=UTC),
        )
