from __future__ import annotations

import pytest


PHASE_1_SKIP_REASON = "Phase 1 scaffold: implement mixed-provider regression coverage in T015/T026/T035."
pytestmark = pytest.mark.integration
PLANNED_CASES = (
    "test_github_and_gitlab_connections_can_coexist_without_state_collision",
    "test_github_regression_flow_survives_gitlab_provider_addition",
    "test_provider_specific_events_and_snapshots_do_not_cross_contaminate",
)


def test_github_gitlab_compatibility_scaffold_declares_planned_cases() -> None:
    assert "T015/T026/T035" in PHASE_1_SKIP_REASON
    assert tuple(
        name for name in PLANNED_CASES if callable(globals().get(name))
    ) == PLANNED_CASES


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_github_and_gitlab_connections_can_coexist_without_state_collision() -> None:
    """Covers mixed-provider connection summary and detail isolation."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_github_regression_flow_survives_gitlab_provider_addition() -> None:
    """Covers GitHub create, verify, and manual snapshot regression in mixed-provider mode."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_provider_specific_events_and_snapshots_do_not_cross_contaminate() -> None:
    """Covers event, health, and snapshot isolation across providers."""
