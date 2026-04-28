from __future__ import annotations

import pytest


PHASE_1_SKIP_REASON = "Phase 1 scaffold: implement GitLab connection contract coverage in T013."
PLANNED_CASES = (
    "test_gitlab_connection_create_and_detail_contract",
    "test_gitlab_connection_verify_and_status_transition_contract",
    "test_gitlab_connection_patch_and_scope_contract_regression",
)


def test_gitlab_connection_contract_scaffold_declares_planned_cases() -> None:
    assert "T013" in PHASE_1_SKIP_REASON
    assert tuple(
        name for name in PLANNED_CASES if callable(globals().get(name))
    ) == PLANNED_CASES


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_connection_create_and_detail_contract() -> None:
    """Covers provider enum, detail shape, and traceability projection for US1."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_connection_verify_and_status_transition_contract() -> None:
    """Covers verify route responses and canonical status transitions for US1."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_connection_patch_and_scope_contract_regression() -> None:
    """Covers mixed-provider contract stability for ref and scope oriented flows."""
