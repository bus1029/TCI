from __future__ import annotations

from dataclasses import dataclass


ALLOWED_PULL_REQUEST_ACTIONS = frozenset(
    {"opened", "reopened", "synchronize", "ready_for_review"}
)
ALLOWED_MERGE_REQUEST_ACTIONS = frozenset(
    {"open", "opened", "reopen", "reopened", "update", "updated"}
)


@dataclass(frozen=True, slots=True)
class ProviderEventDecisionInput:
    provider_event_type: str
    provider_action: str | None
    target_head_sha: str | None
    delivery_already_seen: bool
    latest_cursor_head_sha: str | None
    resolved_current_head_sha: str | None
    retryable_delivery: bool = False
    is_code_moving: bool = True


@dataclass(frozen=True, slots=True)
class ProviderEventDecisionOutcome:
    processing_decision: str
    should_queue_sync: bool


def decide_provider_event_processing(
    decision_input: ProviderEventDecisionInput,
) -> ProviderEventDecisionOutcome:
    if decision_input.delivery_already_seen and not decision_input.retryable_delivery:
        return ProviderEventDecisionOutcome(
            processing_decision="duplicate_delivery",
            should_queue_sync=False,
        )
    if decision_input.provider_event_type == "pull_request" and (
        decision_input.provider_action not in ALLOWED_PULL_REQUEST_ACTIONS
    ):
        return ProviderEventDecisionOutcome(
            processing_decision="record_only",
            should_queue_sync=False,
        )
    if decision_input.provider_event_type == "merge_request" and (
        decision_input.provider_action not in ALLOWED_MERGE_REQUEST_ACTIONS
        or not decision_input.is_code_moving
    ):
        return ProviderEventDecisionOutcome(
            processing_decision="record_only",
            should_queue_sync=False,
        )
    if decision_input.provider_event_type == "ping":
        return ProviderEventDecisionOutcome(
            processing_decision="record_only",
            should_queue_sync=False,
        )
    if decision_input.target_head_sha is None:
        return ProviderEventDecisionOutcome(
            processing_decision="record_only",
            should_queue_sync=False,
        )
    if (
        not decision_input.retryable_delivery
        and decision_input.latest_cursor_head_sha == decision_input.target_head_sha
    ):
        return ProviderEventDecisionOutcome(
            processing_decision="duplicate_head",
            should_queue_sync=False,
        )
    if (
        decision_input.resolved_current_head_sha is not None
        and decision_input.target_head_sha != decision_input.resolved_current_head_sha
    ):
        return ProviderEventDecisionOutcome(
            processing_decision="stale_head",
            should_queue_sync=False,
        )
    return ProviderEventDecisionOutcome(
        processing_decision="queued",
        should_queue_sync=True,
    )
