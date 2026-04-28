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
class ParsedProviderEvent:
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
    is_code_moving: bool = True
    source_project_path: str | None = None
    commit_shas: tuple[str, ...] = ()


def utc_now() -> datetime:
    return datetime.now(tz=UTC)
