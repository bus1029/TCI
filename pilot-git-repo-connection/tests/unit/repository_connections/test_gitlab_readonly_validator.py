from __future__ import annotations

from collections.abc import Sequence

from tci.api.problem_details import ProblemCode
from tci.infrastructure.git.git_ref_resolver import GitCommandResult
from tci.infrastructure.git.gitlab_readonly_validator import GitLabReadonlyValidator


def test_gitlab_readonly_validator_accepts_gitlab_push_denied_message() -> None:
    def runner(command: Sequence[str]) -> GitCommandResult:
        assert command[:3] == ("git", "push", "--dry-run")
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="remote: You are not allowed to push code to this project.",
        )

    result = GitLabReadonlyValidator(runner=runner).probe(
        remote_url="https://x-access-token:secret-token@gitlab.example.com/group/repo.git"
    )

    assert result.is_read_only is True
    assert result.problem_code is None
    assert result.detail == "remote: You are not allowed to push code to this project."


def test_gitlab_readonly_validator_sanitizes_auth_failure_detail() -> None:
    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr=(
                "remote: HTTP Basic: Access denied for "
                "https://x-access-token:secret-token@gitlab.example.com/group/repo.git"
            ),
        )

    result = GitLabReadonlyValidator(runner=runner).probe(
        remote_url="https://x-access-token:secret-token@gitlab.example.com/group/repo.git"
    )

    assert result.is_read_only is False
    assert result.problem_code == ProblemCode.CONNECTION_AUTH_FAILED
    assert "secret-token" not in result.detail


def test_gitlab_readonly_validator_does_not_treat_generic_forbidden_as_auth_failure() -> (
    None
):
    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="remote: 403 forbidden by repository policy",
        )

    result = GitLabReadonlyValidator(runner=runner).probe(
        remote_url="https://gitlab.example.com/group/repo.git"
    )

    assert result.is_read_only is False
    assert result.problem_code is None
