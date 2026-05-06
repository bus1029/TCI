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

    def create(
        self,
        *,
        connection_id: uuid.UUID,
        encrypted_secret: str,
        status: WebhookSecretRevisionStatus = WebhookSecretRevisionStatus.ACTIVE,
        grace_until: datetime | None = None,
        created_at: datetime | None = None,
    ) -> WebhookSecretRevision:
        revision = WebhookSecretRevision(
            connection_id=connection_id,
            encrypted_secret=encrypted_secret,
            status=status,
            grace_until=grace_until,
        )
        if created_at is not None:
            revision.created_at = created_at
        self._session.add(revision)
        self._session.flush()
        self._session.refresh(revision)
        return revision

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
            .order_by(
                WebhookSecretRevision.created_at.desc(), WebhookSecretRevision.id.desc()
            )
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

    def get_latest_previous_grace_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> WebhookSecretRevision | None:
        statement = (
            select(WebhookSecretRevision)
            .where(
                WebhookSecretRevision.connection_id == connection_id,
                WebhookSecretRevision.status
                == WebhookSecretRevisionStatus.PREVIOUS_GRACE,
            )
            .order_by(
                WebhookSecretRevision.created_at.desc(), WebhookSecretRevision.id.desc()
            )
        )
        return self._session.scalar(statement)

    def mark_previous_grace(
        self, *, revision_id: uuid.UUID, grace_until: datetime
    ) -> WebhookSecretRevision:
        revision = self._require(revision_id=revision_id)
        revision.status = WebhookSecretRevisionStatus.PREVIOUS_GRACE
        revision.grace_until = grace_until
        self._session.flush()
        self._session.refresh(revision)
        return revision

    def revoke_previous_grace_for_connection(
        self, *, connection_id: uuid.UUID
    ) -> list[WebhookSecretRevision]:
        statement = select(WebhookSecretRevision).where(
            WebhookSecretRevision.connection_id == connection_id,
            WebhookSecretRevision.status == WebhookSecretRevisionStatus.PREVIOUS_GRACE,
        )
        revisions = list(self._session.scalars(statement))
        for revision in revisions:
            revision.status = WebhookSecretRevisionStatus.REVOKED
            revision.grace_until = None
        if revisions:
            self._session.flush()
        return revisions

    def _require(self, *, revision_id: uuid.UUID) -> WebhookSecretRevision:
        statement = select(WebhookSecretRevision).where(
            WebhookSecretRevision.id == revision_id
        )
        revision = self._session.scalar(statement)
        if revision is None:
            raise LookupError("webhook secret revision을 찾을 수 없습니다.")
        return revision
