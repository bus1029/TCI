from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import RepositoryEventCursor


@dataclass(frozen=True, slots=True)
class RepositoryEventCursorDraft:
    id: uuid.UUID
    connection_id: uuid.UUID
    target_key: str
    latest_head_sha: str
    latest_event_id: uuid.UUID
    updated_at: datetime


class RepositoryEventCursorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self, *, connection_id: uuid.UUID, target_key: str
    ) -> RepositoryEventCursor | None:
        statement = select(RepositoryEventCursor).where(
            RepositoryEventCursor.connection_id == connection_id,
            RepositoryEventCursor.target_key == target_key,
        )
        return self._session.scalar(statement)

    def upsert(self, draft: RepositoryEventCursorDraft) -> RepositoryEventCursor:
        cursor = self.get(connection_id=draft.connection_id, target_key=draft.target_key)
        if cursor is None:
            cursor = RepositoryEventCursor(
                id=draft.id,
                connection_id=draft.connection_id,
                target_key=draft.target_key,
                latest_head_sha=draft.latest_head_sha,
                latest_event_id=draft.latest_event_id,
                updated_at=draft.updated_at,
            )
            self._session.add(cursor)
        else:
            cursor.latest_head_sha = draft.latest_head_sha
            cursor.latest_event_id = draft.latest_event_id
            cursor.updated_at = draft.updated_at
        self._session.flush()
        self._session.refresh(cursor)
        return cursor
