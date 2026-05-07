from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from types import SimpleNamespace
import uuid

from sqlalchemy.exc import IntegrityError

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    bind_git_credential,
    decrypt_secret_from_storage,
    mark_connection_reauth_required,
    require_active_operation_credential_for_connection,
)
from tci.domain.services.repository_event_processing import (
    ProviderEventDecisionInput,
    ProviderEventDecisionOutcome,
    decide_provider_event_processing,
)
from tci.infrastructure.git.git_ref_resolver import (
    GitConnectionAuthError,
    GitRefNotFoundError,
)
from tci.infrastructure.persistence.models import (
    DefaultRefType,
    DomainEventType,
    EventProcessingStatus,
    EventTargetKind,
    ProcessingDecision,
    ProviderEventIdempotencySource,
    ProviderEventType,
    RefType,
    RepositoryConnectionStatus,
    RepositoryProvider,
    SignatureStatus,
    SyncRunStatus,
    WebhookHealthState,
    WebhookRejectionReason,
    WebhookSecretRevisionStatus,
)
from tci.infrastructure.persistence.repository_event_cursor_repository import (
    RepositoryEventCursorDraft,
)
from tci.infrastructure.persistence.repository_event_repository import (
    RepositoryEventDraft,
)
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunDraft,
)
from tci.infrastructure.webhooks.gitlab_event_parser import parse_gitlab_event_payload
from tci.infrastructure.webhooks.gitlab_token_verifier import (
    GitLabTokenCandidate,
    GitLabTokenVerificationInput,
    GitLabTokenVerificationOutcome,
    evaluate_gitlab_token_verification,
)


MAX_PROVIDER_DELIVERY_ID_CHARS = 255
PENDING_SYNC_DISPATCH_RETRY_AFTER = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class ProcessGitLabEventCommand:
    connection_id: uuid.UUID
    provider_delivery_id: str
    provider_event_idempotency_source: str
    provider_event_name: str
    token_header: str | None
    raw_body: bytes
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ProcessGitLabEventResult:
    event_id: uuid.UUID
    provider_delivery_id: str
    sync_run_id: uuid.UUID | None
    should_enqueue_sync: bool = False
    dispatch_event_id: uuid.UUID | None = None


def preflight_gitlab_webhook_token(
    connection_id: uuid.UUID,
    provider_event_name: str,
    token_header: str | None,
    provider_delivery_id: str | None,
    provider_event_idempotency_source: str | None,
    dependencies,
) -> None:
    if dependencies.session_factory is None:
        raise RuntimeError("GitLab 이벤트를 처리하려면 데이터베이스 세션이 필요합니다.")
    if (
        provider_delivery_id is not None
        and len(provider_delivery_id) > MAX_PROVIDER_DELIVERY_ID_CHARS
    ):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "GitLab webhook delivery id가 너무 깁니다.",
        )

    now = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        webhook_secret_repository = dependencies.webhook_secret_repository_factory(
            session
        )
        event_repository = dependencies.repository_event_repository_factory(session)
        connection = connection_repository.get_any(connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        if connection.provider is not RepositoryProvider.GITLAB_SELF_MANAGED:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "GitLab webhook은 GitLab self-managed 연결에서만 처리할 수 있습니다.",
            )

        secret_candidates = webhook_secret_repository.list_verification_candidates(
            connection_id=connection_id,
            as_of=now,
        )
        verification_outcome = evaluate_gitlab_token_verification(
            GitLabTokenVerificationInput(
                token_header=token_header,
                candidates=tuple(
                    _build_verification_candidate(
                        candidate=candidate,
                        dependencies=dependencies,
                    )
                    for candidate in secret_candidates
                ),
            )
        )
        if verification_outcome.is_verified:
            return

        if not _connection_workspace_is_active(
            connection=connection,
            dependencies=dependencies,
            session=session,
        ):
            raise _workspace_not_active_problem()
        if provider_delivery_id is None or provider_event_idempotency_source is None:
            connection_repository.record_webhook_rejection(
                connection_id=connection_id,
                health_state={
                    "secret_missing": WebhookHealthState.MISSING_SECRET,
                    "secret_mismatch": WebhookHealthState.SECRET_MISMATCH_DETECTED,
                }[verification_outcome.signature_status],
                rejection_reason=WebhookRejectionReason(
                    verification_outcome.signature_status
                ),
                rejected_at=now,
            )
            raise _problem_for_signature_status(verification_outcome.signature_status)

        _record_rejected_event(
            connection_id=connection_id,
            command=ProcessGitLabEventCommand(
                connection_id=connection_id,
                provider_delivery_id=provider_delivery_id,
                provider_event_idempotency_source=provider_event_idempotency_source,
                provider_event_name=provider_event_name,
                token_header=token_header,
                raw_body=b"",
                payload={},
            ),
            idempotency_source=ProviderEventIdempotencySource(
                provider_event_idempotency_source
            ),
            verification_outcome=verification_outcome,
            event_repository=event_repository,
            connection_repository=connection_repository,
            processed_at=now,
        )
        raise _problem_for_signature_status(verification_outcome.signature_status)


def record_malformed_gitlab_webhook_attempt(
    *,
    connection_id: uuid.UUID,
    dependencies,
    rejected_at: datetime | None = None,
) -> None:
    if dependencies.session_factory is None:
        return

    rejected_at = rejected_at or datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        connection = connection_repository.get_any(connection_id=connection_id)
        if (
            connection is None
            or connection.provider is not RepositoryProvider.GITLAB_SELF_MANAGED
        ):
            return
        if not _connection_workspace_is_active(
            connection=connection,
            dependencies=dependencies,
            session=session,
        ):
            return
        connection_repository.record_webhook_rejection(
            connection_id=connection_id,
            health_state=WebhookHealthState.SIGNATURE_INVALID_RECENTLY,
            rejection_reason=WebhookRejectionReason.SIGNATURE_INVALID,
            rejected_at=rejected_at,
        )


def process_gitlab_event(command: ProcessGitLabEventCommand, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("GitLab 이벤트를 처리하려면 데이터베이스 세션이 필요합니다.")

    now = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        webhook_secret_repository = dependencies.webhook_secret_repository_factory(
            session
        )
        event_repository = dependencies.repository_event_repository_factory(session)
        event_cursor_repository = (
            dependencies.repository_event_cursor_repository_factory(session)
        )
        sync_run_repository = dependencies.repository_sync_run_repository_factory(
            session
        )
        credential_repository = dependencies.credential_revision_repository_factory(
            session
        )

        connection = connection_repository.get_any(connection_id=command.connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        if connection.provider is not RepositoryProvider.GITLAB_SELF_MANAGED:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "GitLab webhook은 GitLab self-managed 연결에서만 처리할 수 있습니다.",
            )

        secret_candidates = webhook_secret_repository.list_verification_candidates(
            connection_id=command.connection_id,
            as_of=now,
        )
        verification_outcome = evaluate_gitlab_token_verification(
            GitLabTokenVerificationInput(
                token_header=command.token_header,
                candidates=tuple(
                    _build_verification_candidate(
                        candidate=candidate,
                        dependencies=dependencies,
                    )
                    for candidate in secret_candidates
                ),
            )
        )
        idempotency_source = ProviderEventIdempotencySource(
            command.provider_event_idempotency_source
        )
        if not verification_outcome.is_verified:
            if not _connection_workspace_is_active(
                connection=connection,
                dependencies=dependencies,
                session=session,
            ):
                raise _workspace_not_active_problem()
            _record_rejected_event(
                connection_id=command.connection_id,
                command=command,
                idempotency_source=idempotency_source,
                verification_outcome=verification_outcome,
                event_repository=event_repository,
                connection_repository=connection_repository,
                processed_at=now,
            )
            raise _problem_for_signature_status(verification_outcome.signature_status)

        try:
            parsed_event = parse_gitlab_event_payload(
                event_name=command.provider_event_name,
                payload=command.payload,
                received_at=now,
            )
        except ValueError as error:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                str(error),
            ) from error
        try:
            _validate_repository_match(connection=connection, parsed_event=parsed_event)
        except RepositoryConnectionProblem:
            if not _connection_workspace_is_active(
                connection=connection,
                dependencies=dependencies,
                session=session,
            ):
                raise _workspace_not_active_problem()
            _record_payload_rejected_event(
                session=session,
                connection_id=command.connection_id,
                command=command,
                idempotency_source=idempotency_source,
                verification_outcome=verification_outcome,
                parsed_event=parsed_event,
                event_repository=event_repository,
                processed_at=now,
            )
            raise
        latest_cursor = event_cursor_repository.get(
            connection_id=command.connection_id,
            target_key=parsed_event.target_key,
        )
        existing_delivery = event_repository.get_by_delivery_id_for_update(
            connection_id=command.connection_id,
            provider_delivery_id=command.provider_delivery_id,
            provider_event_idempotency_source=idempotency_source,
        )
        retryable_delivery = _is_retryable_delivery(
            existing_delivery,
            sync_run_repository=sync_run_repository,
            connection_id=command.connection_id,
        )
        latest_cursor_head_sha = (
            None if latest_cursor is None else latest_cursor.latest_head_sha
        )
        is_non_retryable_duplicate = (
            existing_delivery is not None and not retryable_delivery
        )
        is_unsupported_fork_merge_request = _is_unsupported_fork_merge_request(
            connection=connection,
            parsed_event=parsed_event,
        )
        workspace_is_active = _connection_workspace_is_active(
            connection=connection,
            dependencies=dependencies,
            session=session,
        )
        if not workspace_is_active:
            raise _workspace_not_active_problem()
        is_code_moving = _is_code_moving(
            parsed_event=parsed_event,
            latest_cursor_head_sha=latest_cursor_head_sha,
        )
        decision = decide_provider_event_processing(
            ProviderEventDecisionInput(
                provider_event_type=_effective_provider_event_type(
                    connection=connection,
                    parsed_event=parsed_event,
                ),
                provider_action=parsed_event.provider_action,
                target_head_sha=parsed_event.target_head_sha,
                delivery_already_seen=existing_delivery is not None,
                latest_cursor_head_sha=latest_cursor_head_sha,
                resolved_current_head_sha=None,
                retryable_delivery=retryable_delivery,
                is_code_moving=is_code_moving,
            )
        )
        if (
            is_non_retryable_duplicate
            or decision.processing_decision in {"record_only", "duplicate_head"}
            or connection.status is not RepositoryConnectionStatus.ACTIVE
            or not workspace_is_active
            or is_unsupported_fork_merge_request
        ):
            resolved_current_head_sha = None
        else:
            operation_credential = _load_operation_credential_for_event(
                connection=connection,
                parsed_event=parsed_event,
                credential_repository=credential_repository,
                dependencies=dependencies,
            )
            resolution_connection = _snapshot_connection_for_git_resolution(connection)
            operation_credential = _snapshot_credential_for_git_resolution(
                operation_credential
            )
            _commit_before_external_git(session)
            resolved_current_head_sha = _resolve_current_head_sha(
                connection=resolution_connection,
                parsed_event=parsed_event,
                operation_credential=operation_credential,
                dependencies=dependencies,
            )
            _expire_after_external_git(session)
            latest_cursor = event_cursor_repository.get(
                connection_id=command.connection_id,
                target_key=parsed_event.target_key,
            )
            existing_delivery = event_repository.get_by_delivery_id_for_update(
                connection_id=command.connection_id,
                provider_delivery_id=command.provider_delivery_id,
                provider_event_idempotency_source=idempotency_source,
            )
            workspace_is_active = _connection_workspace_is_active(
                connection=connection,
                dependencies=dependencies,
                session=session,
            )
            if not workspace_is_active:
                raise _workspace_not_active_problem()
            retryable_delivery = _is_retryable_delivery(
                existing_delivery,
                sync_run_repository=sync_run_repository,
                connection_id=command.connection_id,
            )
            latest_cursor_head_sha = (
                None if latest_cursor is None else latest_cursor.latest_head_sha
            )
            is_non_retryable_duplicate = (
                existing_delivery is not None and not retryable_delivery
            )
            is_code_moving = _is_code_moving(
                parsed_event=parsed_event,
                latest_cursor_head_sha=latest_cursor_head_sha,
            )
            decision = decide_provider_event_processing(
                ProviderEventDecisionInput(
                    provider_event_type=_effective_provider_event_type(
                        connection=connection,
                        parsed_event=parsed_event,
                    ),
                    provider_action=parsed_event.provider_action,
                    target_head_sha=parsed_event.target_head_sha,
                    delivery_already_seen=existing_delivery is not None,
                    latest_cursor_head_sha=latest_cursor_head_sha,
                    resolved_current_head_sha=resolved_current_head_sha,
                    retryable_delivery=retryable_delivery,
                    is_code_moving=is_code_moving,
                )
            )
        if (
            connection.status is not RepositoryConnectionStatus.ACTIVE
            or not workspace_is_active
        ) and not is_non_retryable_duplicate:
            decision = ProviderEventDecisionOutcome(
                processing_decision="record_only",
                should_queue_sync=False,
            )
        if is_unsupported_fork_merge_request and not is_non_retryable_duplicate:
            decision = ProviderEventDecisionOutcome(
                processing_decision="record_only",
                should_queue_sync=False,
            )
        processing_decision = ProcessingDecision(decision.processing_decision)
        processing_status = (
            EventProcessingStatus.QUEUED
            if decision.should_queue_sync
            else EventProcessingStatus.COMPLETED
        )
        if existing_delivery is None:
            event_id = uuid.uuid4()
            event, created_event = _create_event_or_get_concurrent_delivery(
                session=session,
                event_repository=event_repository,
                connection_id=command.connection_id,
                provider_delivery_id=command.provider_delivery_id,
                idempotency_source=idempotency_source,
                draft=RepositoryEventDraft(
                    id=event_id,
                    connection_id=command.connection_id,
                    provider_delivery_id=command.provider_delivery_id,
                    provider_event_idempotency_source=idempotency_source,
                    provider_event_type=parsed_event.provider_event_type,
                    provider_action=parsed_event.provider_action,
                    domain_event_type=parsed_event.domain_event_type,
                    target_kind=parsed_event.target_kind,
                    target_key=parsed_event.target_key,
                    target_ref_name=parsed_event.target_ref_name,
                    target_head_sha=parsed_event.target_head_sha,
                    occurred_at=parsed_event.occurred_at,
                    received_at=now,
                    processed_at=now,
                    signature_status=SignatureStatus.VERIFIED,
                    verified_secret_revision_id=(
                        verification_outcome.verified_secret_revision_id
                    ),
                    verified_secret_revision_status=WebhookSecretRevisionStatus(
                        verification_outcome.verified_secret_revision_status or "active"
                    ),
                    rejection_reason=None,
                    processing_decision=processing_decision,
                    processing_status=processing_status,
                    payload_hash=hashlib.sha256(command.raw_body).hexdigest(),
                ),
            )
            if not created_event:
                return ProcessGitLabEventResult(
                    event_id=event.id,
                    provider_delivery_id=command.provider_delivery_id,
                    sync_run_id=getattr(event, "sync_run_id", None),
                    should_enqueue_sync=False,
                )
        else:
            if retryable_delivery:
                existing_delivery.provider_event_type = parsed_event.provider_event_type
                existing_delivery.provider_action = parsed_event.provider_action
                existing_delivery.domain_event_type = parsed_event.domain_event_type
                existing_delivery.target_kind = parsed_event.target_kind
                existing_delivery.target_key = parsed_event.target_key
                existing_delivery.target_ref_name = parsed_event.target_ref_name
                existing_delivery.target_head_sha = parsed_event.target_head_sha
                existing_delivery.occurred_at = parsed_event.occurred_at
                existing_delivery.received_at = now
                existing_delivery.signature_status = SignatureStatus.VERIFIED
                existing_delivery.verified_secret_revision_id = (
                    verification_outcome.verified_secret_revision_id
                )
                existing_delivery.verified_secret_revision_status = (
                    WebhookSecretRevisionStatus(
                        verification_outcome.verified_secret_revision_status or "active"
                    )
                )
                existing_delivery.rejection_reason = None
                existing_delivery.payload_hash = hashlib.sha256(
                    command.raw_body
                ).hexdigest()
            event = event_repository.update_processing(
                event_id=existing_delivery.id,
                processing_decision=processing_decision,
                processing_status=processing_status,
                processed_at=now,
                clear_sync_run_id=retryable_delivery and not decision.should_queue_sync,
            )

        sync_run = None
        should_enqueue_sync = False
        dispatch_event_id = None
        if parsed_event.trigger_type is not None and (
            decision.should_queue_sync
            or processing_decision is ProcessingDecision.DUPLICATE_HEAD
        ):
            requested_ref_type = parsed_event.requested_ref_type
            if requested_ref_type is None:
                raise RuntimeError(
                    "queue 대상 이벤트에는 requested_ref_type이 필요합니다."
                )
            requested_ref_name = parsed_event.requested_ref_name or ""
            requested_ref_key = _sync_run_ref_key(parsed_event=parsed_event)
            running_sync_run = sync_run_repository.get_running_for_requested_ref(
                connection_id=command.connection_id,
                requested_ref_type=requested_ref_type,
                requested_ref_name=requested_ref_name,
                requested_ref_key=requested_ref_key,
            )
            active_sync_run = sync_run_repository.get_active_for_requested_ref(
                connection_id=command.connection_id,
                trigger_type=parsed_event.trigger_type,
                requested_ref_type=requested_ref_type,
                requested_ref_name=requested_ref_name,
                requested_ref_key=requested_ref_key,
            )
            if active_sync_run is not None:
                sync_run = active_sync_run
                dispatch_event_id = _pending_sync_dispatch_event_id(
                    sync_run=active_sync_run,
                    event_repository=event_repository,
                )
                if dispatch_event_id == event.id:
                    event = event_repository.update_processing(
                        event_id=event.id,
                        processing_decision=ProcessingDecision.QUEUED,
                        processing_status=EventProcessingStatus.QUEUED,
                        processed_at=now,
                        sync_run_id=active_sync_run.id,
                    )
                else:
                    event = event_repository.update_processing(
                        event_id=event.id,
                        processing_decision=ProcessingDecision.DUPLICATE_HEAD,
                        processing_status=EventProcessingStatus.COMPLETED,
                        processed_at=now,
                        sync_run_id=active_sync_run.id,
                    )
                should_enqueue_sync = dispatch_event_id is not None
                if parsed_event.target_key and dispatch_event_id == event.id:
                    event_cursor_repository.upsert(
                        RepositoryEventCursorDraft(
                            id=uuid.uuid4(),
                            connection_id=command.connection_id,
                            target_key=parsed_event.target_key,
                            latest_head_sha=parsed_event.target_head_sha or "",
                            latest_event_id=event.id,
                            updated_at=now,
                        )
                    )
            elif decision.should_queue_sync:
                draft = RepositorySyncRunDraft(
                    id=uuid.uuid4(),
                    connection_id=command.connection_id,
                    trigger_event_id=event.id,
                    trigger_type=parsed_event.trigger_type,
                    requested_ref_type=requested_ref_type,
                    requested_ref_name=requested_ref_name,
                    requested_ref_key=requested_ref_key,
                )
                if running_sync_run is not None:
                    sync_run, created_sync_run = _create_or_replace_blocked_sync_run(
                        session=session,
                        sync_run_repository=sync_run_repository,
                        event_repository=event_repository,
                        connection_id=command.connection_id,
                        draft=draft,
                        processed_at=now,
                    )
                else:
                    sync_run, created_sync_run = _create_sync_run_or_get_active(
                        session=session,
                        sync_run_repository=sync_run_repository,
                        connection_id=command.connection_id,
                        draft=draft,
                    )
                if not created_sync_run:
                    event = event_repository.update_processing(
                        event_id=event.id,
                        processing_decision=ProcessingDecision.DUPLICATE_HEAD,
                        processing_status=EventProcessingStatus.COMPLETED,
                        processed_at=now,
                        sync_run_id=sync_run.id,
                    )
                else:
                    should_enqueue_sync = running_sync_run is None
                    dispatch_event_id = event.id if should_enqueue_sync else None
                    queued_status = (
                        EventProcessingStatus.QUEUED
                        if should_enqueue_sync
                        else EventProcessingStatus.VALIDATED
                    )
                    event = event_repository.update_processing(
                        event_id=event.id,
                        processing_decision=ProcessingDecision.QUEUED,
                        processing_status=queued_status,
                        processed_at=now,
                        sync_run_id=sync_run.id,
                    )
                    event_cursor_repository.upsert(
                        RepositoryEventCursorDraft(
                            id=uuid.uuid4(),
                            connection_id=command.connection_id,
                            target_key=parsed_event.target_key,
                            latest_head_sha=parsed_event.target_head_sha or "",
                            latest_event_id=event.id,
                            updated_at=now,
                        )
                    )

        _record_commit_events(
            session=session,
            command=command,
            parsed_event=parsed_event,
            idempotency_source=idempotency_source,
            verification_outcome=verification_outcome,
            event_repository=event_repository,
            processed_at=now,
        )

        if _should_mark_webhook_healthy(decision=decision):
            connection_repository.record_processed_event(
                connection_id=command.connection_id,
                event_id=event.id,
                processed_at=now,
                health_state=WebhookHealthState.HEALTHY,
            )
        else:
            connection_repository.record_processed_event_preserving_webhook_health(
                connection_id=command.connection_id,
                event_id=event.id,
                processed_at=now,
            )
        return ProcessGitLabEventResult(
            event_id=event.id,
            provider_delivery_id=command.provider_delivery_id,
            sync_run_id=None if sync_run is None else sync_run.id,
            should_enqueue_sync=should_enqueue_sync,
            dispatch_event_id=dispatch_event_id,
        )


def _build_verification_candidate(*, candidate, dependencies) -> GitLabTokenCandidate:
    secret = getattr(candidate, "secret", None)
    if secret is None:
        encrypted_secret = getattr(candidate, "encrypted_secret", None)
        if encrypted_secret:
            secret = decrypt_secret_from_storage(
                encrypted_secret,
                settings=dependencies.settings,
            )
    if secret is None:
        secret = ""
    status = getattr(candidate, "status", "active")
    return GitLabTokenCandidate(
        revision_id=getattr(candidate, "revision_id", None) or getattr(candidate, "id"),
        secret=secret,
        status=str(getattr(status, "value", status)),
    )


def _create_event_or_get_concurrent_delivery(
    *,
    session,
    event_repository,
    connection_id: uuid.UUID,
    provider_delivery_id: str,
    idempotency_source: ProviderEventIdempotencySource,
    draft: RepositoryEventDraft,
):
    try:
        begin_nested = getattr(session, "begin_nested", None)
        if begin_nested is None:
            return event_repository.create(draft), True
        with begin_nested():
            return event_repository.create(draft), True
    except IntegrityError:
        if (
            getattr(session, "begin_nested", None) is None
            and (rollback := getattr(session, "rollback", None)) is not None
        ):
            rollback()
        existing_event = event_repository.get_by_delivery_id(
            connection_id=connection_id,
            provider_delivery_id=provider_delivery_id,
            provider_event_idempotency_source=idempotency_source,
        )
        if existing_event is None:
            raise
        return existing_event, False


def _create_or_replace_blocked_sync_run(
    *,
    session,
    sync_run_repository,
    event_repository,
    connection_id: uuid.UUID,
    draft: RepositorySyncRunDraft,
    processed_at: datetime,
):
    blocked_sync_run = sync_run_repository.get_blocked_for_requested_ref(
        connection_id=connection_id,
        requested_ref_type=draft.requested_ref_type,
        requested_ref_name=draft.requested_ref_name,
        requested_ref_key=draft.requested_ref_key,
    )
    if blocked_sync_run is None:
        try:
            begin_nested = getattr(session, "begin_nested", None)
            if begin_nested is None:
                return sync_run_repository.create_blocked(draft), True
            with begin_nested():
                return sync_run_repository.create_blocked(draft), True
        except IntegrityError:
            if (
                getattr(session, "begin_nested", None) is None
                and (rollback := getattr(session, "rollback", None)) is not None
            ):
                rollback()
            blocked_sync_run = sync_run_repository.get_blocked_for_requested_ref(
                connection_id=connection_id,
                requested_ref_type=draft.requested_ref_type,
                requested_ref_name=draft.requested_ref_name,
                requested_ref_key=draft.requested_ref_key,
            )
            if blocked_sync_run is None:
                raise
        except ValueError as error:
            if (
                getattr(session, "begin_nested", None) is None
                and (rollback := getattr(session, "rollback", None)) is not None
            ):
                rollback()
            raise _workspace_not_active_problem() from error

    previous_event_id = getattr(blocked_sync_run, "trigger_event_id", None)
    if previous_event_id is not None and previous_event_id != draft.trigger_event_id:
        previous_event = event_repository.get(event_id=previous_event_id)
        if previous_event is not None:
            event_repository.update_processing(
                event_id=previous_event_id,
                processing_decision=ProcessingDecision.DUPLICATE_HEAD,
                processing_status=EventProcessingStatus.COMPLETED,
                processed_at=processed_at,
                sync_run_id=blocked_sync_run.id,
            )
    return (
        sync_run_repository.update_blocked_trigger_event(
            connection_id=connection_id,
            sync_run_id=blocked_sync_run.id,
            trigger_event_id=draft.trigger_event_id,
            updated_at=processed_at,
        ),
        True,
    )


def _pending_sync_dispatch_event_id(
    *,
    sync_run,
    event_repository,
) -> uuid.UUID | None:
    if sync_run.trigger_event_id is None:
        return None
    if sync_run.dispatch_enqueued_at is not None and not _pending_dispatch_is_stale(
        sync_run.dispatch_enqueued_at
    ):
        return None
    trigger_event = event_repository.get(event_id=sync_run.trigger_event_id)
    if trigger_event is None or trigger_event.sync_run_id != sync_run.id:
        return None
    if (
        getattr(
            trigger_event.processing_status,
            "value",
            trigger_event.processing_status,
        )
        != EventProcessingStatus.QUEUED.value
    ):
        return None
    return sync_run.trigger_event_id


def _pending_dispatch_is_stale(dispatch_enqueued_at: datetime) -> bool:
    if dispatch_enqueued_at.tzinfo is None:
        dispatch_enqueued_at = dispatch_enqueued_at.replace(tzinfo=UTC)
    return (
        datetime.now(tz=UTC) - dispatch_enqueued_at > PENDING_SYNC_DISPATCH_RETRY_AFTER
    )


def _create_sync_run_or_get_active(
    *,
    session,
    sync_run_repository,
    connection_id: uuid.UUID,
    draft: RepositorySyncRunDraft,
):
    try:
        begin_nested = getattr(session, "begin_nested", None)
        if begin_nested is None:
            return sync_run_repository.create_pending(draft), True
        with begin_nested():
            return sync_run_repository.create_pending(draft), True
    except IntegrityError:
        if (
            getattr(session, "begin_nested", None) is None
            and (rollback := getattr(session, "rollback", None)) is not None
        ):
            rollback()
        active_sync_run = sync_run_repository.get_active_for_requested_ref(
            connection_id=connection_id,
            trigger_type=draft.trigger_type,
            requested_ref_type=draft.requested_ref_type,
            requested_ref_name=draft.requested_ref_name,
            requested_ref_key=draft.requested_ref_key,
        )
        if active_sync_run is None:
            active_sync_run = sync_run_repository.get_running_for_requested_ref(
                connection_id=connection_id,
                requested_ref_type=draft.requested_ref_type,
                requested_ref_name=draft.requested_ref_name,
                requested_ref_key=draft.requested_ref_key,
            )
        if active_sync_run is None:
            raise
        return active_sync_run, False
    except ValueError as error:
        if (
            getattr(session, "begin_nested", None) is None
            and (rollback := getattr(session, "rollback", None)) is not None
        ):
            rollback()
        raise _workspace_not_active_problem() from error


def _workspace_not_active_problem() -> RepositoryConnectionProblem:
    return RepositoryConnectionProblem(
        ProblemCode.WORKSPACE_NOT_ACTIVE,
        "활성 워크스페이스에서만 새 스냅샷 작업을 시작할 수 있습니다.",
    )


def _commit_before_external_git(session) -> None:
    commit = getattr(session, "commit", None)
    if commit is not None:
        commit()


def _expire_after_external_git(session) -> None:
    expire_all = getattr(session, "expire_all", None)
    if expire_all is not None:
        expire_all()


def _snapshot_connection_for_git_resolution(connection):
    return SimpleNamespace(
        id=connection.id,
        workspace_id=connection.workspace_id,
        remote_url=connection.remote_url,
        transport=connection.transport,
    )


def _snapshot_credential_for_git_resolution(operation_credential):
    if operation_credential is None:
        return None
    return SimpleNamespace(
        encrypted_secret=operation_credential.encrypted_secret,
        credential_type=operation_credential.credential_type,
    )


def _connection_workspace_is_active(*, connection, dependencies, session) -> bool:
    workspace_repository_factory = getattr(
        dependencies, "workspace_repository_factory", None
    )
    if workspace_repository_factory is None:
        return True
    workspace_repository = workspace_repository_factory(session)
    get_for_update = getattr(workspace_repository, "get_for_update", None)
    if get_for_update is None:
        workspace = workspace_repository.get(workspace_id=connection.workspace_id)
    else:
        workspace = get_for_update(workspace_id=connection.workspace_id)
    if workspace is None:
        return True
    status = getattr(getattr(workspace, "status", None), "value", workspace.status)
    return status == "active"


def _record_commit_events(
    *,
    session,
    command: ProcessGitLabEventCommand,
    parsed_event,
    idempotency_source: ProviderEventIdempotencySource,
    verification_outcome: GitLabTokenVerificationOutcome,
    event_repository,
    processed_at: datetime,
) -> None:
    payload_hash = hashlib.sha256(command.raw_body).hexdigest()
    for commit_sha in parsed_event.commit_shas:
        commit_delivery_id = _commit_delivery_id(
            provider_delivery_id=command.provider_delivery_id,
            commit_sha=commit_sha,
        )
        existing_commit = event_repository.get_by_delivery_id(
            connection_id=command.connection_id,
            provider_delivery_id=commit_delivery_id,
            provider_event_idempotency_source=idempotency_source,
        )
        if existing_commit is not None:
            continue
        _create_event_or_get_concurrent_delivery(
            session=session,
            event_repository=event_repository,
            connection_id=command.connection_id,
            provider_delivery_id=commit_delivery_id,
            idempotency_source=idempotency_source,
            draft=RepositoryEventDraft(
                id=uuid.uuid4(),
                connection_id=command.connection_id,
                provider_delivery_id=commit_delivery_id,
                provider_event_idempotency_source=idempotency_source,
                provider_event_type=parsed_event.provider_event_type,
                provider_action=parsed_event.provider_action,
                domain_event_type=DomainEventType.COMMIT_RECORDED,
                target_kind=parsed_event.target_kind,
                target_key=f"commit:{commit_sha}",
                target_ref_name=parsed_event.target_ref_name,
                target_head_sha=commit_sha,
                occurred_at=parsed_event.occurred_at,
                received_at=processed_at,
                processed_at=processed_at,
                signature_status=SignatureStatus.VERIFIED,
                verified_secret_revision_id=(
                    verification_outcome.verified_secret_revision_id
                ),
                verified_secret_revision_status=WebhookSecretRevisionStatus(
                    verification_outcome.verified_secret_revision_status or "active"
                ),
                rejection_reason=None,
                processing_decision=ProcessingDecision.RECORD_ONLY,
                processing_status=EventProcessingStatus.COMPLETED,
                payload_hash=payload_hash,
            ),
        )


def _commit_delivery_id(*, provider_delivery_id: str, commit_sha: str) -> str:
    suffix = f":commit:{commit_sha}"
    if len(provider_delivery_id) + len(suffix) <= MAX_PROVIDER_DELIVERY_ID_CHARS:
        return f"{provider_delivery_id}{suffix}"
    digest = hashlib.sha256(provider_delivery_id.encode("utf-8")).hexdigest()[:16]
    prefix_budget = MAX_PROVIDER_DELIVERY_ID_CHARS - len(suffix) - len(digest) - 1
    return f"{provider_delivery_id[:prefix_budget]}:{digest}{suffix}"


def _record_payload_rejected_event(
    *,
    session,
    connection_id: uuid.UUID,
    command: ProcessGitLabEventCommand,
    idempotency_source: ProviderEventIdempotencySource,
    verification_outcome: GitLabTokenVerificationOutcome,
    parsed_event,
    event_repository,
    processed_at: datetime,
) -> None:
    existing_event = event_repository.get_by_delivery_id(
        connection_id=connection_id,
        provider_delivery_id=command.provider_delivery_id,
        provider_event_idempotency_source=idempotency_source,
    )
    if existing_event is not None:
        return
    _create_event_or_get_concurrent_delivery(
        session=session,
        event_repository=event_repository,
        connection_id=connection_id,
        provider_delivery_id=command.provider_delivery_id,
        idempotency_source=idempotency_source,
        draft=RepositoryEventDraft(
            id=uuid.uuid4(),
            connection_id=connection_id,
            provider_delivery_id=command.provider_delivery_id,
            provider_event_idempotency_source=idempotency_source,
            provider_event_type=parsed_event.provider_event_type,
            provider_action=parsed_event.provider_action,
            domain_event_type=DomainEventType.SIGNATURE_REJECTED,
            target_kind=parsed_event.target_kind,
            target_key=parsed_event.target_key,
            target_ref_name=parsed_event.target_ref_name,
            target_head_sha=parsed_event.target_head_sha,
            occurred_at=parsed_event.occurred_at,
            received_at=processed_at,
            processed_at=processed_at,
            signature_status=SignatureStatus.VERIFIED,
            verified_secret_revision_id=(
                verification_outcome.verified_secret_revision_id
            ),
            verified_secret_revision_status=WebhookSecretRevisionStatus(
                verification_outcome.verified_secret_revision_status or "active"
            ),
            rejection_reason=None,
            processing_decision=ProcessingDecision.REJECTED,
            processing_status=EventProcessingStatus.REJECTED,
            payload_hash=hashlib.sha256(command.raw_body).hexdigest(),
        ),
    )


def _should_mark_webhook_healthy(*, decision) -> bool:
    return decision.processing_decision in {
        ProcessingDecision.QUEUED.value,
        ProcessingDecision.RECORD_ONLY.value,
        ProcessingDecision.DUPLICATE_DELIVERY.value,
        ProcessingDecision.DUPLICATE_HEAD.value,
        ProcessingDecision.STALE_HEAD.value,
    }


def _is_retryable_delivery(
    existing_delivery,
    *,
    sync_run_repository,
    connection_id: uuid.UUID,
) -> bool:
    if existing_delivery is None:
        return False
    processing_status = getattr(
        existing_delivery.processing_status,
        "value",
        existing_delivery.processing_status,
    )
    processing_decision = getattr(
        existing_delivery.processing_decision,
        "value",
        existing_delivery.processing_decision,
    )
    if processing_status == EventProcessingStatus.REJECTED.value:
        return True
    if processing_decision != ProcessingDecision.QUEUED.value:
        return False
    if processing_status == EventProcessingStatus.FAILED.value:
        return True
    if processing_status != EventProcessingStatus.QUEUED.value:
        return False
    sync_run_id = getattr(existing_delivery, "sync_run_id", None)
    if sync_run_id is None:
        return False
    sync_run = sync_run_repository.get(
        connection_id=connection_id,
        sync_run_id=sync_run_id,
    )
    if sync_run is None:
        return False
    sync_run_status = getattr(sync_run.status, "value", sync_run.status)
    if sync_run_status != SyncRunStatus.PENDING.value:
        return False
    return sync_run.dispatch_enqueued_at is None or _pending_dispatch_is_stale(
        sync_run.dispatch_enqueued_at
    )


def _record_rejected_event(
    *,
    connection_id: uuid.UUID,
    command: ProcessGitLabEventCommand,
    idempotency_source: ProviderEventIdempotencySource,
    verification_outcome: GitLabTokenVerificationOutcome,
    event_repository,
    connection_repository,
    processed_at: datetime,
) -> None:
    rejection_reason = WebhookRejectionReason(verification_outcome.signature_status)
    health_state = {
        "secret_missing": WebhookHealthState.MISSING_SECRET,
        "secret_mismatch": WebhookHealthState.SECRET_MISMATCH_DETECTED,
    }[verification_outcome.signature_status]
    existing_event = event_repository.get_by_delivery_id(
        connection_id=connection_id,
        provider_delivery_id=command.provider_delivery_id,
        provider_event_idempotency_source=idempotency_source,
    )
    should_update_connection_health = idempotency_source in {
        ProviderEventIdempotencySource.DELIVERY_HEADER,
        ProviderEventIdempotencySource.UUID_HEADER,
    }
    if existing_event is None:
        event, created_event = _create_event_or_get_concurrent_delivery(
            session=getattr(event_repository, "_session", None),
            event_repository=event_repository,
            connection_id=connection_id,
            provider_delivery_id=command.provider_delivery_id,
            idempotency_source=idempotency_source,
            draft=RepositoryEventDraft(
                id=uuid.uuid4(),
                connection_id=connection_id,
                provider_delivery_id=command.provider_delivery_id,
                provider_event_idempotency_source=idempotency_source,
                provider_event_type=_provider_event_type_for(
                    command.provider_event_name
                ),
                provider_action=None,
                domain_event_type=DomainEventType.SIGNATURE_REJECTED,
                target_kind=_target_kind_for(command.provider_event_name),
                target_key="none",
                target_ref_name=None,
                target_head_sha=None,
                occurred_at=processed_at,
                received_at=processed_at,
                processed_at=processed_at,
                signature_status=SignatureStatus(verification_outcome.signature_status),
                verified_secret_revision_id=None,
                verified_secret_revision_status=None,
                rejection_reason=rejection_reason,
                processing_decision=ProcessingDecision.REJECTED,
                processing_status=EventProcessingStatus.REJECTED,
                payload_hash=hashlib.sha256(command.raw_body).hexdigest(),
            ),
        )
        if (
            not created_event
            and _signature_status_value(event) == SignatureStatus.VERIFIED.value
        ):
            should_update_connection_health = False
    else:
        if (
            getattr(
                existing_event.signature_status,
                "value",
                existing_event.signature_status,
            )
            != SignatureStatus.VERIFIED.value
        ):
            existing_event.signature_status = SignatureStatus(
                verification_outcome.signature_status
            )
            existing_event.verified_secret_revision_id = None
            existing_event.verified_secret_revision_status = None
            existing_event.rejection_reason = rejection_reason
            existing_event.processing_decision = ProcessingDecision.REJECTED
            existing_event.processing_status = EventProcessingStatus.REJECTED
            existing_event.processed_at = processed_at
        else:
            should_update_connection_health = False
    if should_update_connection_health:
        connection_repository.record_webhook_rejection(
            connection_id=connection_id,
            health_state=health_state,
            rejection_reason=rejection_reason,
            rejected_at=processed_at,
        )


def _signature_status_value(event) -> str:
    signature_status = getattr(event, "signature_status", None)
    return str(getattr(signature_status, "value", signature_status))


def _problem_for_signature_status(signature_status: str) -> RepositoryConnectionProblem:
    if signature_status == "secret_missing":
        return RepositoryConnectionProblem(
            ProblemCode.WEBHOOK_SECRET_MISSING,
            "webhook secret이 아직 등록되지 않았습니다.",
        )
    return RepositoryConnectionProblem(
        ProblemCode.WEBHOOK_SECRET_MISMATCH,
        "등록된 webhook secret과 요청 서명이 일치하지 않습니다.",
    )


def _provider_event_type_for(event_name: str):
    if event_name in {"Push Hook", "Tag Push Hook"}:
        return ProviderEventType.PUSH
    if event_name == "Merge Request Hook":
        return ProviderEventType.MERGE_REQUEST
    return ProviderEventType.UNKNOWN


def _target_kind_for(event_name: str):
    if event_name in {"Push Hook", "Tag Push Hook"}:
        return EventTargetKind.DEFAULT_REF
    if event_name == "Merge Request Hook":
        return EventTargetKind.MERGE_REQUEST_SOURCE
    return EventTargetKind.NONE


def _load_operation_credential_for_event(
    *,
    connection,
    parsed_event,
    credential_repository,
    dependencies,
):
    if parsed_event.target_head_sha is None or parsed_event.requested_ref_name is None:
        return None
    try:
        return require_active_operation_credential_for_connection(
            credential_repository=credential_repository,
            connection_id=connection.id,
        )
    except RepositoryConnectionProblem:
        mark_connection_reauth_required(
            dependencies=dependencies,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
        )
        raise


def _resolve_current_head_sha(
    *, connection, parsed_event, operation_credential, dependencies
) -> str | None:
    if parsed_event.target_head_sha is None or parsed_event.requested_ref_name is None:
        return None
    if operation_credential is None:
        return None
    try:
        credential_secret = decrypt_secret_from_storage(
            operation_credential.encrypted_secret,
            settings=dependencies.settings,
        )
        with bind_git_credential(
            remote_url=connection.remote_url,
            transport=connection.transport,
            credential_type=operation_credential.credential_type,
            credential_secret=credential_secret,
        ) as credential_bound_remote_url:
            resolved_ref = dependencies.git_ref_resolver.resolve(
                remote_url=credential_bound_remote_url,
                ref_type=_resolver_ref_type(parsed_event=parsed_event),
                ref_name=parsed_event.requested_ref_name,
            )
    except RepositoryConnectionProblem:
        mark_connection_reauth_required(
            dependencies=dependencies,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
        )
        raise
    except GitConnectionAuthError as error:
        mark_connection_reauth_required(
            dependencies=dependencies,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
        )
        raise RepositoryConnectionProblem(
            ProblemCode.CONNECTION_AUTH_FAILED,
            "저장소 자격 증명 검증에 실패했습니다.",
        ) from error
    except (GitRefNotFoundError, RuntimeError):
        return None
    return resolved_ref.commit_sha


def _validate_repository_match(*, connection, parsed_event) -> None:
    expected_full_name = connection.provider_project_path or (
        f"{connection.repository_owner}/{connection.repository_name}"
    )
    if (
        parsed_event.provider_event_type
        in {ProviderEventType.PUSH, ProviderEventType.MERGE_REQUEST}
        and not parsed_event.repository_full_name
    ):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "GitLab webhook 저장소 정보가 누락되었습니다.",
        )
    if (
        parsed_event.repository_full_name is not None
        and parsed_event.repository_full_name != expected_full_name
    ):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "webhook 저장소 정보가 연결 대상과 일치하지 않습니다.",
        )
    if (
        parsed_event.provider_event_type is ProviderEventType.MERGE_REQUEST
        and parsed_event.target_key == "mr:None"
    ):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "GitLab merge request webhook 식별자가 누락되었습니다.",
        )
    if parsed_event.provider_event_type is ProviderEventType.MERGE_REQUEST:
        mr_identifier = parsed_event.target_key.removeprefix("mr:")
        if not mr_identifier.isdecimal() or int(mr_identifier) <= 0:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "GitLab merge request webhook 식별자가 올바르지 않습니다.",
            )


def _effective_provider_event_type(*, connection, parsed_event) -> str:
    if parsed_event.provider_event_type is ProviderEventType.PUSH and (
        connection.default_ref_type.value
        != getattr(
            parsed_event.requested_ref_type, "value", parsed_event.requested_ref_type
        )
        or parsed_event.requested_ref_name != connection.default_ref_name
    ):
        return "ping"
    return parsed_event.provider_event_type.value


def _is_code_moving(*, parsed_event, latest_cursor_head_sha: str | None) -> bool:
    if parsed_event.provider_event_type is not ProviderEventType.MERGE_REQUEST:
        return parsed_event.is_code_moving
    if parsed_event.provider_action in {"open", "opened", "reopen", "reopened"}:
        return True
    if parsed_event.provider_action not in {"update", "updated"}:
        return False
    return parsed_event.is_code_moving or (
        latest_cursor_head_sha is not None
        and parsed_event.target_head_sha != latest_cursor_head_sha
    )


def _resolver_ref_type(*, parsed_event):
    if parsed_event.requested_ref_type is RefType.TAG:
        return DefaultRefType.TAG
    return DefaultRefType.BRANCH


def _sync_run_ref_key(*, parsed_event) -> str:
    if parsed_event.target_key and parsed_event.target_key != "default_ref":
        return parsed_event.target_key
    return parsed_event.requested_ref_name or ""


def _is_unsupported_fork_merge_request(*, connection, parsed_event) -> bool:
    if parsed_event.provider_event_type is not ProviderEventType.MERGE_REQUEST:
        return False
    source_project_path = getattr(parsed_event, "source_project_path", None)
    if source_project_path is None:
        return False
    expected_project_path = connection.provider_project_path or (
        f"{connection.repository_owner}/{connection.repository_name}"
    )
    return source_project_path != expected_project_path
