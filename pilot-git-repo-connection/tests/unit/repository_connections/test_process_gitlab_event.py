from __future__ import annotations

import pytest


PHASE_1_SKIP_REASON = "Phase 1 scaffold: implement GitLab event processing unit coverage in T033/T036/T037/T038."
PLANNED_CASES = (
    "test_gitlab_delivery_id_extraction_prefers_idempotency_key_then_webhook_uuid",
    "test_gitlab_merge_request_update_gates_record_only_vs_queued",
    "test_process_gitlab_event_marks_duplicate_and_stale_deliveries_without_snapshot",
)


def test_process_gitlab_event_scaffold_declares_planned_cases() -> None:
    assert "T033/T036/T037/T038" in PHASE_1_SKIP_REASON
    assert tuple(
        name for name in PLANNED_CASES if callable(globals().get(name))
    ) == PLANNED_CASES


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_delivery_id_extraction_prefers_idempotency_key_then_webhook_uuid() -> None:
    """Covers provider-specific dedupe key extraction rules."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_merge_request_update_gates_record_only_vs_queued() -> None:
    """Covers MR action and code-moving update gating behavior."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_process_gitlab_event_marks_duplicate_and_stale_deliveries_without_snapshot() -> None:
    """Covers dedupe and stale-head protections for queued GitLab events."""
