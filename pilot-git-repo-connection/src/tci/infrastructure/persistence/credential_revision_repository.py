from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import (
    CredentialRevisionStatus,
    CredentialType,
    RepositoryCredentialRevision,
)


@dataclass(frozen=True, slots=True)
class CredentialRevisionDraft:
    connection_id: uuid.UUID
    credential_type: CredentialType
    encrypted_secret: str
    display_fingerprint: str
    read_only_validated: bool
    status: CredentialRevisionStatus


class CredentialRevisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, draft: CredentialRevisionDraft) -> RepositoryCredentialRevision:
        revision = RepositoryCredentialRevision(
            connection_id=draft.connection_id,
            credential_type=draft.credential_type,
            encrypted_secret=draft.encrypted_secret,
            display_fingerprint=draft.display_fingerprint,
            read_only_validated=draft.read_only_validated,
            status=draft.status,
        )
        self._session.add(revision)
        self._session.flush()
        self._session.refresh(revision)
        return revision
