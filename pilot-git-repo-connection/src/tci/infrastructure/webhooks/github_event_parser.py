from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from tci.infrastructure.persistence.models import (
    DomainEventType,
    EventTargetKind,
    ProviderEventType,
    RefType,
    SyncTriggerType,
)


@dataclass(frozen=True, slots=True)
class ParsedGitHubEvent:
    provider_event_type: ProviderEventType
    provider_action: str | None
    domain_event_type: DomainEventType
    target_kind: EventTargetKind
    repository_full_name: str | None
    target_key: str
    target_ref_name: str | None
    target_head_sha: str | None
    requested_ref_type: RefType | None
    requested_ref_name: str | None
    trigger_type: SyncTriggerType | None
    occurred_at: datetime


def parse_github_event_payload(
    *, event_name: str, payload: dict[str, object], received_at: datetime
) -> ParsedGitHubEvent:
    repository = payload.get("repository") or {}
    if not isinstance(repository, dict):
        repository = {}
    repository_full_name = _read_nullable_string(repository.get("full_name"))
    if event_name == "push":
        raw_ref = str(payload.get("ref", ""))
        ref_name = raw_ref.removeprefix("refs/heads/") if raw_ref else None
        return ParsedGitHubEvent(
            provider_event_type=ProviderEventType.PUSH,
            provider_action=None,
            domain_event_type=DomainEventType.PUSH_RECEIVED,
            target_kind=EventTargetKind.DEFAULT_REF,
            repository_full_name=repository_full_name,
            target_key="default_ref",
            target_ref_name=ref_name,
            target_head_sha=_read_nullable_string(payload.get("after")),
            requested_ref_type=RefType.BRANCH,
            requested_ref_name=ref_name,
            trigger_type=SyncTriggerType.WEBHOOK_PUSH,
            occurred_at=received_at,
        )
    if event_name == "pull_request":
        action = _read_nullable_string(payload.get("action"))
        number = payload.get("number")
        pull_request = payload.get("pull_request") or {}
        if not isinstance(pull_request, dict):
            pull_request = {}
        head = pull_request.get("head") or {}
        if not isinstance(head, dict):
            head = {}
        head_ref = _read_nullable_string(head.get("ref"))
        head_sha = _read_nullable_string(head.get("sha"))
        return ParsedGitHubEvent(
            provider_event_type=ProviderEventType.PULL_REQUEST,
            provider_action=action,
            domain_event_type=DomainEventType.PR_RECEIVED,
            target_kind=EventTargetKind.PULL_REQUEST_SOURCE,
            repository_full_name=repository_full_name,
            target_key=f"pr:{number}",
            target_ref_name=head_ref,
            target_head_sha=head_sha,
            requested_ref_type=RefType.PULL_REQUEST_BRANCH,
            requested_ref_name=head_ref,
            trigger_type=SyncTriggerType.WEBHOOK_PULL_REQUEST,
            occurred_at=received_at,
        )
    return ParsedGitHubEvent(
        provider_event_type=ProviderEventType.UNKNOWN,
        provider_action=None,
        domain_event_type=DomainEventType.SIGNATURE_REJECTED,
        target_kind=EventTargetKind.NONE,
        repository_full_name=repository_full_name,
        target_key="none",
        target_ref_name=None,
        target_head_sha=None,
        requested_ref_type=None,
        requested_ref_name=None,
        trigger_type=None,
        occurred_at=received_at,
    )


def _read_nullable_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
