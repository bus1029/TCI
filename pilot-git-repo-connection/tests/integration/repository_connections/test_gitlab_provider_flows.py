from __future__ import annotations

import pytest


PHASE_1_SKIP_REASON = "Phase 1 scaffold: implement GitLab provider integration coverage in T014/T025/T034."
pytestmark = pytest.mark.integration
PLANNED_CASES = (
    "test_gitlab_connection_lifecycle_blocks_collection_for_action_required_states",
    "test_gitlab_scope_and_snapshot_flow_applies_provider_neutral_rules",
    "test_gitlab_webhook_push_and_merge_request_flows_update_health_and_snapshots",
)


def test_gitlab_provider_flow_scaffold_declares_planned_cases() -> None:
    assert "T014/T025/T034" in PHASE_1_SKIP_REASON
    assert tuple(
        name for name in PLANNED_CASES if callable(globals().get(name))
    ) == PLANNED_CASES


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_connection_lifecycle_blocks_collection_for_action_required_states() -> None:
    """Covers verify, blocked collection, and state transitions for GitLab connections."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_scope_and_snapshot_flow_applies_provider_neutral_rules() -> None:
    """Covers scope rule persistence and filtered snapshot behavior for GitLab."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_webhook_push_and_merge_request_flows_update_health_and_snapshots() -> None:
    """Covers push/MR queueing, dedupe, stale-head handling, and webhook health."""
