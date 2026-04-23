from __future__ import annotations

import pytest


PHASE_1_SKIP_REASON = "Phase 1 scaffold: implement GitLab parsing and validation unit coverage in T016/T017/T024."
PLANNED_CASES = (
    "test_gitlab_remote_parser_extracts_instance_namespace_and_project",
    "test_gitlab_remote_parser_rejects_unsupported_or_ambiguous_addresses",
    "test_gitlab_readonly_validator_enforces_read_repository_scope",
)


def test_gitlab_provider_parsing_scaffold_declares_planned_cases() -> None:
    assert "T016/T017/T024" in PHASE_1_SKIP_REASON
    assert tuple(
        name for name in PLANNED_CASES if callable(globals().get(name))
    ) == PLANNED_CASES


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_remote_parser_extracts_instance_namespace_and_project() -> None:
    """Covers SSH/HTTPS parsing for self-managed GitLab remotes."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_remote_parser_rejects_unsupported_or_ambiguous_addresses() -> None:
    """Covers invalid address handling and provider-specific error mapping."""


@pytest.mark.skip(reason=PHASE_1_SKIP_REASON)
def test_gitlab_readonly_validator_enforces_read_repository_scope() -> None:
    """Covers read-only credential policy for GitLab HTTPS and SSH flows."""
