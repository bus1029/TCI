from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from types import SimpleNamespace
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.domain.services.repository_connection_support import decrypt_secret_from_storage
from tci.infrastructure.git.git_ref_resolver import GitConnectionAuthError, GitRefNotFoundError
from tci.infrastructure.persistence.models import (
    DefaultRefType,
    DomainEventType,
    EventProcessingStatus,
    EventTargetKind,
    ProcessingDecision,
    ProviderEventType,
    SignatureStatus,
    SyncFailureCode,
    SyncTriggerType,
    WebhookHealthState,
    WebhookRejectionReason,
    WebhookSecretRevisionStatus,
)
from tci.infrastructure.persistence.repository_event_cursor_repository import (
    RepositoryEventCursorDraft,
)
from tci.infrastructure.persistence.repository_event_repository import RepositoryEventDraft
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunDraft,
)
from tci.infrastructure.webhooks.github_event_parser import parse_github_event_payload
from tci.infrastructure.webhooks.github_signature import (
    verify_github_webhook_signature,
)


ALLOWED_PULL_REQUEST_ACTIONS = frozenset(
    {"opened", "reopened", "synchronize", "ready_for_review"}
)


@dataclass(frozen=True, slots=True)
class SecretVerificationInput:
    has_any_secret: bool
    signature_header: str | None
    signature_is_valid: bool
    matched_secret_revision_id: uuid.UUID | None = None
    matched_secret_status: str | None = None


@dataclass(frozen=True, slots=True)
class SecretVerificationOutcome:
    signature_status: str
    verified_secret_revision_id: uuid.UUID | None
    verified_secret_revision_status: str | None

    @property
    def rejection_reason(self) -> str | None:
        if self.signature_status == "verified":
            return None
        return self.signature_status

    @property
    def is_verified(self) -> bool:
        return self.signature_status == "verified"


@dataclass(frozen=True, slots=True)
class GitHubDecisionInput:
    provider_event_type: str
    provider_action: str | None
    target_head_sha: str | None
    delivery_already_seen: bool
    latest_cursor_head_sha: str | None
    resolved_current_head_sha: str | None
    retryable_delivery: bool = False


@dataclass(frozen=True, slots=True)
class GitHubDecisionOutcome:
    processing_decision: str
    should_queue_sync: bool


@dataclass(frozen=True, slots=True)
class ProcessGitHubEventCommand:
    connection_id: uuid.UUID
    provider_delivery_id: str
    provider_event_name: str
    signature_header: str | None
    raw_body: bytes
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ProcessGitHubEventResult:
    event_id: uuid.UUID
    provider_delivery_id: str
    sync_run_id: uuid.UUID | None


def evaluate_github_secret_verification(
    verification_input: SecretVerificationInput,
) -> SecretVerificationOutcome:
    if not verification_input.has_any_secret:
        return SecretVerificationOutcome(
            signature_status="secret_missing",
            verified_secret_revision_id=None,
            verified_secret_revision_status=None,
        )
    if (
        verification_input.signature_is_valid
        and verification_input.matched_secret_status is not None
    ):
        return SecretVerificationOutcome(
            signature_status="verified",
            verified_secret_revision_id=verification_input.matched_secret_revision_id,
            verified_secret_revision_status=verification_input.matched_secret_status,
        )
    if not _looks_like_github_signature(verification_input.signature_header):
        return SecretVerificationOutcome(
            signature_status="signature_invalid",
            verified_secret_revision_id=None,
            verified_secret_revision_status=None,
        )
    return SecretVerificationOutcome(
        signature_status="secret_mismatch",
        verified_secret_revision_id=None,
        verified_secret_revision_status=None,
    )


def decide_github_event_processing(
    decision_input: GitHubDecisionInput,
) -> GitHubDecisionOutcome:
    if decision_input.delivery_already_seen and not decision_input.retryable_delivery:
        return GitHubDecisionOutcome(
            processing_decision="duplicate_delivery",
            should_queue_sync=False,
        )
    if (
        decision_input.provider_event_type == "pull_request"
        and decision_input.provider_action not in ALLOWED_PULL_REQUEST_ACTIONS
    ):
        return GitHubDecisionOutcome(
            processing_decision="record_only",
            should_queue_sync=False,
        )
    if decision_input.provider_event_type == "ping":
        return GitHubDecisionOutcome(
            processing_decision="record_only",
            should_queue_sync=False,
        )
    if decision_input.target_head_sha is None:
        return GitHubDecisionOutcome(
            processing_decision="record_only",
            should_queue_sync=False,
        )
    if decision_input.latest_cursor_head_sha == decision_input.target_head_sha:
        return GitHubDecisionOutcome(
            processing_decision="duplicate_head",
            should_queue_sync=False,
        )
    if (
        decision_input.resolved_current_head_sha is not None
        and decision_input.target_head_sha != decision_input.resolved_current_head_sha
    ):
        return GitHubDecisionOutcome(
            processing_decision="stale_head",
            should_queue_sync=False,
        )
    return GitHubDecisionOutcome(processing_decision="queued", should_queue_sync=True)


def _looks_like_github_signature(signature_header: str | None) -> bool:
    if signature_header is None or not signature_header.startswith("sha256="):
        return False
    digest = signature_header.removeprefix("sha256=")
    return bool(digest) and all(character in "0123456789abcdef" for character in digest)


def process_github_event(command: ProcessGitHubEventCommand, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("GitHub 이벤트를 처리하려면 데이터베이스 세션이 필요합니다.")

    now = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(session)
        webhook_secret_repository = dependencies.webhook_secret_repository_factory(session)
        event_repository = dependencies.repository_event_repository_factory(session)
        event_cursor_repository = dependencies.repository_event_cursor_repository_factory(session)
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)

        connection = connection_repository.get_any(connection_id=command.connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")

        secret_candidates = webhook_secret_repository.list_verification_candidates(
            connection_id=command.connection_id,
            as_of=now,
        )
        verification_candidates = [
            _build_verification_candidate(candidate=candidate, dependencies=dependencies)
            for candidate in secret_candidates
        ]
        signature_verification = verify_github_webhook_signature(
            secret_candidates=verification_candidates,
            signature_header=command.signature_header,
            raw_body=command.raw_body,
        )
        verification_outcome = evaluate_github_secret_verification(
            SecretVerificationInput(
                has_any_secret=bool(verification_candidates),
                matched_secret_revision_id=signature_verification.matched_revision_id,
                matched_secret_status=signature_verification.matched_revision_status,
                signature_header=command.signature_header,
                signature_is_valid=signature_verification.signature_is_valid,
            )
        )
        if not verification_outcome.is_verified:
            _record_rejected_event(
                connection_id=command.connection_id,
                command=command,
                verification_outcome=verification_outcome,
                event_repository=event_repository,
                connection_repository=connection_repository,
                processed_at=now,
            )
            raise _problem_for_signature_status(verification_outcome.signature_status)

        parsed_event = parse_github_event_payload(
            event_name=command.provider_event_name,
            payload=command.payload,
            received_at=now,
        )
        _validate_repository_match(connection=connection, parsed_event=parsed_event)
        existing_delivery = event_repository.get_by_delivery_id(
            connection_id=command.connection_id,
            provider_delivery_id=command.provider_delivery_id,
        )
        retryable_delivery = _is_retryable_delivery(existing_delivery)
        latest_cursor = event_cursor_repository.get(
            connection_id=command.connection_id,
            target_key=parsed_event.target_key,
        )
        resolved_current_head_sha = _resolve_current_head_sha(
            connection=connection,
            parsed_event=parsed_event,
            dependencies=dependencies,
        )
        decision = decide_github_event_processing(
            GitHubDecisionInput(
                provider_event_type=_effective_provider_event_type(
                    connection=connection,
                    parsed_event=parsed_event,
                ),
                provider_action=parsed_event.provider_action,
                target_head_sha=parsed_event.target_head_sha,
                delivery_already_seen=existing_delivery is not None,
                latest_cursor_head_sha=(
                    None if latest_cursor is None else latest_cursor.latest_head_sha
                ),
                resolved_current_head_sha=resolved_current_head_sha,
                retryable_delivery=retryable_delivery,
            )
        )
        processing_decision = ProcessingDecision(decision.processing_decision)
        processing_status = (
            EventProcessingStatus.QUEUED
            if decision.should_queue_sync
            else EventProcessingStatus.COMPLETED
        )
        if existing_delivery is None:
            event = event_repository.create(
                RepositoryEventDraft(
                    id=uuid.uuid4(),
                    connection_id=command.connection_id,
                    provider_delivery_id=command.provider_delivery_id,
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
                    verified_secret_revision_id=verification_outcome.verified_secret_revision_id,
                    verified_secret_revision_status=WebhookSecretRevisionStatus(
                        verification_outcome.verified_secret_revision_status
                    ),
                    rejection_reason=None,
                    processing_decision=processing_decision,
                    processing_status=processing_status,
                    payload_hash=hashlib.sha256(command.raw_body).hexdigest(),
                )
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
                        verification_outcome.verified_secret_revision_status
                    )
                )
                existing_delivery.rejection_reason = None
                existing_delivery.payload_hash = hashlib.sha256(command.raw_body).hexdigest()
            event = event_repository.update_processing(
                event_id=existing_delivery.id,
                processing_decision=processing_decision,
                processing_status=processing_status,
                processed_at=now,
                clear_sync_run_id=retryable_delivery and not decision.should_queue_sync,
            )

        sync_run = None
        if decision.should_queue_sync and parsed_event.trigger_type is not None:
            sync_run = sync_run_repository.create_pending(
                RepositorySyncRunDraft(
                    id=uuid.uuid4(),
                    connection_id=command.connection_id,
                    trigger_event_id=event.id,
                    trigger_type=parsed_event.trigger_type,
                    requested_ref_type=parsed_event.requested_ref_type,
                    requested_ref_name=parsed_event.requested_ref_name or "",
                )
            )
            event = event_repository.update_processing(
                event_id=event.id,
                processing_decision=ProcessingDecision.QUEUED,
                processing_status=EventProcessingStatus.QUEUED,
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

        connection_repository.record_processed_event(
            connection_id=command.connection_id,
            event_id=event.id,
            processed_at=now,
            health_state=WebhookHealthState.HEALTHY,
        )
        return ProcessGitHubEventResult(
            event_id=event.id,
            provider_delivery_id=command.provider_delivery_id,
            sync_run_id=None if sync_run is None else sync_run.id,
        )


def record_webhook_enqueue_failure(
    *,
    connection_id: uuid.UUID,
    event_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    dependencies,
    failure_message: str = "웹훅 동기화 작업 큐에 연결할 수 없습니다.",
) -> None:
    if dependencies.session_factory is None:
        raise RuntimeError("웹훅 큐 실패 상태를 기록하려면 데이터베이스 세션이 필요합니다.")

    failed_at = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(session)
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)
        event_repository = dependencies.repository_event_repository_factory(session)
        event_cursor_repository = dependencies.repository_event_cursor_repository_factory(
            session
        )
        connection = connection_repository.get_any(connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        event = event_repository.get(event_id=event_id)
        if event is None:
            raise LookupError("저장소 이벤트를 찾을 수 없습니다.")

        sync_run_repository.mark_failed(
            connection_id=connection_id,
            sync_run_id=sync_run_id,
            failure_code=SyncFailureCode.QUEUE_DISPATCH_FAILED,
            failure_message=failure_message,
            completed_at=failed_at,
        )
        event_repository.update_processing(
            event_id=event_id,
            processing_decision=ProcessingDecision.QUEUED,
            processing_status=EventProcessingStatus.FAILED,
            processed_at=failed_at,
        )
        _restore_event_cursor_after_failure(
            connection_id=connection_id,
            failed_event=event,
            event_repository=event_repository,
            event_cursor_repository=event_cursor_repository,
            restored_at=failed_at,
        )
        connection_repository.record_sync_failure(
            workspace_id=connection.workspace_id,
            connection_id=connection_id,
            failed_at=failed_at,
        )
        connection_repository.record_processed_event(
            connection_id=connection_id,
            event_id=event_id,
            processed_at=failed_at,
            health_state=WebhookHealthState.HEALTHY,
        )


def _is_retryable_delivery(existing_delivery) -> bool:
    if existing_delivery is None:
        return False
    if (
        getattr(existing_delivery.processing_status, "value", existing_delivery.processing_status)
        == EventProcessingStatus.REJECTED.value
    ):
        return True
    return (
        getattr(existing_delivery.processing_decision, "value", existing_delivery.processing_decision)
        == ProcessingDecision.QUEUED.value
        and getattr(existing_delivery.processing_status, "value", existing_delivery.processing_status)
        == EventProcessingStatus.FAILED.value
    )


def _restore_event_cursor_after_failure(
    *,
    connection_id: uuid.UUID,
    failed_event,
    event_repository,
    event_cursor_repository,
    restored_at: datetime,
) -> None:
    fallback_event = next(
        (
            candidate
            for candidate in event_repository.list_for_connection(
                connection_id=connection_id
            )
            if candidate.id != failed_event.id
            and candidate.target_key == failed_event.target_key
            and candidate.target_head_sha is not None
            and getattr(candidate.processing_decision, "value", candidate.processing_decision)
            == ProcessingDecision.QUEUED.value
            and getattr(candidate.processing_status, "value", candidate.processing_status)
            != EventProcessingStatus.FAILED.value
        ),
        None,
    )
    if fallback_event is None:
        event_cursor_repository.delete_if_latest_event(
            connection_id=connection_id,
            target_key=failed_event.target_key,
            latest_event_id=failed_event.id,
        )
        return
    event_cursor_repository.upsert(
        RepositoryEventCursorDraft(
            id=uuid.uuid4(),
            connection_id=connection_id,
            target_key=fallback_event.target_key,
            latest_head_sha=fallback_event.target_head_sha,
            latest_event_id=fallback_event.id,
            updated_at=restored_at,
        )
    )


def _record_rejected_event(
    *,
    connection_id: uuid.UUID,
    command: ProcessGitHubEventCommand,
    verification_outcome: SecretVerificationOutcome,
    event_repository,
    connection_repository,
    processed_at: datetime,
) -> None:
    rejection_reason = WebhookRejectionReason(verification_outcome.signature_status)
    health_state = {
        "secret_missing": WebhookHealthState.MISSING_SECRET,
        "secret_mismatch": WebhookHealthState.SECRET_MISMATCH_DETECTED,
        "signature_invalid": WebhookHealthState.SIGNATURE_INVALID_RECENTLY,
    }[verification_outcome.signature_status]
    existing_event = event_repository.get_by_delivery_id(
        connection_id=connection_id,
        provider_delivery_id=command.provider_delivery_id,
    )
    should_update_connection_health = True
    if existing_event is None:
        event_repository.create(
            RepositoryEventDraft(
                id=uuid.uuid4(),
                connection_id=connection_id,
                provider_delivery_id=command.provider_delivery_id,
                provider_event_type=_provider_event_type_for(command.provider_event_name),
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
            )
        )
    else:
        if (
            getattr(existing_event.signature_status, "value", existing_event.signature_status)
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


def _problem_for_signature_status(signature_status: str) -> RepositoryConnectionProblem:
    if signature_status == "secret_missing":
        return RepositoryConnectionProblem(
            ProblemCode.WEBHOOK_SECRET_MISSING,
            "webhook secret이 아직 등록되지 않았습니다.",
        )
    if signature_status == "secret_mismatch":
        return RepositoryConnectionProblem(
            ProblemCode.WEBHOOK_SECRET_MISMATCH,
            "등록된 webhook secret과 요청 서명이 일치하지 않습니다.",
        )
    return RepositoryConnectionProblem(
        ProblemCode.WEBHOOK_SIGNATURE_INVALID,
        "webhook 서명 검증에 실패했습니다.",
    )


def _provider_event_type_for(event_name: str):
    try:
        return {
            "push": ProviderEventType.PUSH,
            "pull_request": ProviderEventType.PULL_REQUEST,
            "ping": ProviderEventType.PING,
        }[event_name]
    except KeyError:
        return ProviderEventType.UNKNOWN


def _target_kind_for(event_name: str):
    if event_name == "push":
        return EventTargetKind.DEFAULT_REF
    if event_name == "pull_request":
        return EventTargetKind.PULL_REQUEST_SOURCE
    return EventTargetKind.NONE


def _resolve_current_head_sha(*, connection, parsed_event, dependencies) -> str | None:
    if parsed_event.target_head_sha is None or parsed_event.requested_ref_name is None:
        return None
    try:
        resolved_ref = dependencies.git_ref_resolver.resolve(
            remote_url=connection.remote_url,
            ref_type=DefaultRefType.BRANCH,
            ref_name=parsed_event.requested_ref_name,
        )
    except (GitConnectionAuthError, GitRefNotFoundError, RuntimeError):
        return None
    return resolved_ref.commit_sha


def _build_verification_candidate(*, candidate, dependencies):
    if getattr(candidate, "secret", None) is not None:
        return candidate
    encrypted_secret = getattr(candidate, "encrypted_secret", "")
    return SimpleNamespace(
        revision_id=getattr(candidate, "revision_id", None) or getattr(candidate, "id", None),
        status=getattr(candidate, "status", None),
        secret=decrypt_secret_from_storage(
            encrypted_secret,
            settings=dependencies.settings,
        ),
    )


def _validate_repository_match(*, connection, parsed_event) -> None:
    expected_full_name = f"{connection.repository_owner}/{connection.repository_name}"
    if (
        parsed_event.repository_full_name is not None
        and parsed_event.repository_full_name != expected_full_name
    ):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "webhook 저장소 정보가 연결 대상과 일치하지 않습니다.",
        )


def _effective_provider_event_type(*, connection, parsed_event) -> str:
    if parsed_event.provider_event_type is ProviderEventType.PUSH and (
        connection.default_ref_type is not DefaultRefType.BRANCH
        or parsed_event.requested_ref_name != connection.default_ref_name
    ):
        return "ping"
    return parsed_event.provider_event_type.value
