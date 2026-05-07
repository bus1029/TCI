from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import encrypt_secret_for_storage
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.domain.services.workspace_lifecycle import (
    WorkspaceLifecycleProblem,
    ensure_active_workspace,
)
from tci.infrastructure.persistence.models import WebhookSecretRevisionStatus


WEBHOOK_SECRET_GRACE_PERIOD = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class RotateWebhookSecretCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    plaintext_secret: str | None = None
    secret_factory: Callable[[], str] | None = None
    rotated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RotateWebhookSecretResult:
    webhook_secret_revision_id: uuid.UUID
    plaintext_secret: str
    grace_until: datetime | None


@dataclass(frozen=True, slots=True)
class WebhookSecretRotationProjection:
    grace_until: datetime | None
    previous_secret_deliveries_during_grace: int
    last_previous_secret_accepted_at: datetime | None


def rotate_webhook_secret(command: RotateWebhookSecretCommand, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError(
            "webhook secret을 회전하려면 데이터베이스 세션이 필요합니다."
        )

    rotated_at = command.rotated_at or datetime.now(tz=UTC)
    grace_until = rotated_at + WEBHOOK_SECRET_GRACE_PERIOD

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        webhook_secret_repository = dependencies.webhook_secret_repository_factory(
            session
        )
        connection = connection_repository.get_for_update(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        workspace_repository_factory = getattr(
            dependencies, "workspace_repository_factory", None
        )
        if workspace_repository_factory is not None:
            try:
                ensure_active_workspace(
                    workspace_id=command.workspace_id,
                    workspace_repository=workspace_repository_factory(session),
                    lock_for_update=True,
                )
            except WorkspaceLifecycleProblem as error:
                raise RepositoryConnectionProblem(
                    ProblemCode.WORKSPACE_NOT_ACTIVE,
                    "활성 워크스페이스에서만 새 스냅샷 작업을 시작할 수 있습니다.",
                ) from error
        plaintext_secret = _plaintext_secret_for_rotation(command)
        encrypted_secret = encrypt_secret_for_storage(
            plaintext_secret,
            settings=dependencies.settings,
        )

        webhook_secret_repository.revoke_previous_grace_for_connection(
            connection_id=command.connection_id
        )
        active_revision = webhook_secret_repository.get_active_for_connection(
            connection_id=command.connection_id
        )
        if active_revision is not None:
            webhook_secret_repository.mark_previous_grace(
                revision_id=active_revision.id,
                grace_until=grace_until,
            )

        rotated_revision = webhook_secret_repository.create(
            connection_id=command.connection_id,
            encrypted_secret=encrypted_secret,
            status=WebhookSecretRevisionStatus.ACTIVE,
            created_at=rotated_at,
        )
        connection_repository.set_active_webhook_secret_revision(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            webhook_secret_revision_id=rotated_revision.id,
        )
        return RotateWebhookSecretResult(
            webhook_secret_revision_id=rotated_revision.id,
            plaintext_secret=plaintext_secret,
            grace_until=(None if active_revision is None else grace_until),
        )


def _plaintext_secret_for_rotation(command: RotateWebhookSecretCommand) -> str:
    if command.plaintext_secret is not None:
        return command.plaintext_secret
    if command.secret_factory is not None:
        return command.secret_factory()
    raise ValueError("webhook secret plaintext or factory is required.")


def build_webhook_secret_rotation_projection(
    *,
    connection_id: uuid.UUID,
    webhook_secret_repository,
    event_repository,
) -> WebhookSecretRotationProjection:
    previous_revision = (
        webhook_secret_repository.get_latest_previous_grace_for_connection(
            connection_id=connection_id
        )
    )
    if previous_revision is None:
        return WebhookSecretRotationProjection(
            grace_until=None,
            previous_secret_deliveries_during_grace=0,
            last_previous_secret_accepted_at=None,
        )

    grace_until = getattr(previous_revision, "grace_until", None)
    grace_started_at = (
        None if grace_until is None else grace_until - WEBHOOK_SECRET_GRACE_PERIOD
    )
    previous_secret_events: list[datetime] = []
    for event in event_repository.list_for_connection(connection_id=connection_id):
        verified_revision_id = getattr(event, "verified_secret_revision_id", None)
        verified_revision_status = getattr(
            event,
            "verified_secret_revision_status",
            None,
        )
        processed_at = getattr(event, "processed_at", None)
        if processed_at is None:
            continue
        matches_previous_revision = verified_revision_id == previous_revision.id
        matches_legacy_previous_grace = (
            verified_revision_id is None
            and getattr(verified_revision_status, "value", verified_revision_status)
            == WebhookSecretRevisionStatus.PREVIOUS_GRACE.value
        )
        if not matches_previous_revision and not matches_legacy_previous_grace:
            continue
        if grace_started_at is not None and processed_at < grace_started_at:
            continue
        if grace_until is not None and processed_at > grace_until:
            continue
        previous_secret_events.append(processed_at)

    return WebhookSecretRotationProjection(
        grace_until=grace_until,
        previous_secret_deliveries_during_grace=len(previous_secret_events),
        last_previous_secret_accepted_at=max(previous_secret_events, default=None),
    )
