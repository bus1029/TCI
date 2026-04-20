from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import (
    WebhookSecretRevision,
    WebhookSecretRevisionStatus,
)


@dataclass(frozen=True, slots=True)
class WebhookSecretCandidate:
    revision_id: uuid.UUID
    encrypted_secret: str
    status: WebhookSecretRevisionStatus
    grace_until: datetime | None


class WebhookSecretRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> WebhookSecretRevision | None:
        statement = select(WebhookSecretRevision).where(
            WebhookSecretRevision.connection_id == connection_id,
            WebhookSecretRevision.status == WebhookSecretRevisionStatus.ACTIVE,
        )
        return self._session.scalar(statement)

    def list_verification_candidates(
        self, *, connection_id: uuid.UUID, as_of: datetime
    ) -> list[WebhookSecretCandidate]:
        statement = (
            select(WebhookSecretRevision)
            .where(
                WebhookSecretRevision.connection_id == connection_id,
                or_(
                    WebhookSecretRevision.status == WebhookSecretRevisionStatus.ACTIVE,
                    (
                        WebhookSecretRevision.status
                        == WebhookSecretRevisionStatus.PREVIOUS_GRACE
                    )
                    & (WebhookSecretRevision.grace_until >= as_of),
                ),
            )
            .order_by(WebhookSecretRevision.created_at.desc(), WebhookSecretRevision.id.desc())
        )
        return [
            WebhookSecretCandidate(
                revision_id=revision.id,
                encrypted_secret=revision.encrypted_secret,
                status=revision.status,
                grace_until=revision.grace_until,
            )
            for revision in self._session.scalars(statement)
        ]
