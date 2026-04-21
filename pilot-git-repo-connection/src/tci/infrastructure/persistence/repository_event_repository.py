from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import (
    DomainEventType,
    EventProcessingStatus,
    EventTargetKind,
    ProcessingDecision,
    ProviderEventType,
    RepositoryEvent,
    SignatureStatus,
    WebhookRejectionReason,
    WebhookSecretRevisionStatus,
)


@dataclass(frozen=True, slots=True)
class RepositoryEventDraft:
    id: uuid.UUID
    connection_id: uuid.UUID
    provider_delivery_id: str
    provider_event_type: ProviderEventType
    provider_action: str | None
    domain_event_type: DomainEventType
    target_kind: EventTargetKind
    target_key: str
    target_ref_name: str | None
    target_head_sha: str | None
    occurred_at: datetime
    received_at: datetime
    processed_at: datetime | None
    signature_status: SignatureStatus
    verified_secret_revision_status: WebhookSecretRevisionStatus | None
    verified_secret_revision_id: uuid.UUID | None
    rejection_reason: WebhookRejectionReason | None
    processing_decision: ProcessingDecision
    processing_status: EventProcessingStatus
    payload_hash: str
    sync_run_id: uuid.UUID | None = None
    snapshot_id: uuid.UUID | None = None


class RepositoryEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, draft: RepositoryEventDraft) -> RepositoryEvent:
        event = RepositoryEvent(
            id=draft.id,
            connection_id=draft.connection_id,
            provider_delivery_id=draft.provider_delivery_id,
            provider_event_type=draft.provider_event_type,
            provider_action=draft.provider_action,
            domain_event_type=draft.domain_event_type,
            target_kind=draft.target_kind,
            target_key=draft.target_key,
            target_ref_name=draft.target_ref_name,
            target_head_sha=draft.target_head_sha,
            occurred_at=draft.occurred_at,
            received_at=draft.received_at,
            processed_at=draft.processed_at,
            signature_status=draft.signature_status,
            verified_secret_revision_status=draft.verified_secret_revision_status,
            verified_secret_revision_id=draft.verified_secret_revision_id,
            rejection_reason=draft.rejection_reason,
            processing_decision=draft.processing_decision,
            processing_status=draft.processing_status,
            payload_hash=draft.payload_hash,
            sync_run_id=draft.sync_run_id,
            snapshot_id=draft.snapshot_id,
        )
        self._session.add(event)
        self._session.flush()
        self._session.refresh(event)
        return event

    def get_by_delivery_id(
        self, *, connection_id: uuid.UUID, provider_delivery_id: str
    ) -> RepositoryEvent | None:
        statement = select(RepositoryEvent).where(
            RepositoryEvent.connection_id == connection_id,
            RepositoryEvent.provider_delivery_id == provider_delivery_id,
        )
        return self._session.scalar(statement)

    def get(self, *, event_id: uuid.UUID) -> RepositoryEvent | None:
        statement = select(RepositoryEvent).where(RepositoryEvent.id == event_id)
        return self._session.scalar(statement)

    def list_for_connection(self, *, connection_id: uuid.UUID) -> list[RepositoryEvent]:
        statement = (
            select(RepositoryEvent)
            .where(RepositoryEvent.connection_id == connection_id)
            .order_by(RepositoryEvent.received_at.desc(), RepositoryEvent.id.desc())
        )
        return list(self._session.scalars(statement))

    def update_processing(
        self,
        *,
        event_id: uuid.UUID,
        processing_decision: ProcessingDecision,
        processing_status: EventProcessingStatus,
        processed_at: datetime,
        sync_run_id: uuid.UUID | None = None,
        snapshot_id: uuid.UUID | None = None,
        clear_sync_run_id: bool = False,
    ) -> RepositoryEvent:
        event = self._require(event_id=event_id)
        event.processing_decision = processing_decision
        event.processing_status = processing_status
        event.processed_at = processed_at
        if clear_sync_run_id:
            event.sync_run_id = None
        if sync_run_id is not None:
            event.sync_run_id = sync_run_id
        if snapshot_id is not None:
            event.snapshot_id = snapshot_id
        self._session.flush()
        self._session.refresh(event)
        return event

    def _require(self, *, event_id: uuid.UUID) -> RepositoryEvent:
        event = self.get(event_id=event_id)
        if event is None:
            raise LookupError("저장소 이벤트를 찾을 수 없습니다.")
        return event
