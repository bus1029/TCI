from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
import subprocess
import uuid
from unittest.mock import MagicMock

import pytest

from tci.api.problem_details import ProblemCode
from tci.infrastructure.persistence.models import DefaultRefType, PlanningInputSourceType


def _run_git(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "TCI Test",
        "GIT_AUTHOR_EMAIL": "tci@example.com",
        "GIT_COMMITTER_NAME": "TCI Test",
        "GIT_COMMITTER_EMAIL": "tci@example.com",
    }
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )


def _subprocess_git_runner(command: Sequence[str]):
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
    )
    return GitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def test_build_snapshot_traceability_reference_preserves_phase2_chain() -> None:
    from tci.domain.services.build_traceability_reference import (
        build_snapshot_traceability_reference,
    )

    planning_input_reference_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    scope_rule_version_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()

    reference = build_snapshot_traceability_reference(
        planning_input_reference_id=planning_input_reference_id,
        connection_id=connection_id,
        scope_rule_version_id=scope_rule_version_id,
        sync_run_id=sync_run_id,
        snapshot_id=snapshot_id,
    )

    assert reference.planning_input_reference_id == planning_input_reference_id
    assert reference.connection_id == connection_id
    assert reference.scope_rule_version_id == scope_rule_version_id
    assert reference.sync_run_id == sync_run_id
    assert reference.snapshot_id == snapshot_id


def test_planning_input_reference_repository_rejects_cross_feature_paths() -> None:
    from tci.infrastructure.persistence.planning_input_reference_repository import (
        PlanningInputReferenceDraft,
        PlanningInputReferenceRepository,
    )

    repository = PlanningInputReferenceRepository(session=MagicMock())
    draft = PlanningInputReferenceDraft(
        workspace_id=uuid.uuid4(),
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="코드 저장소 연동",
        source_reference="user-request-001",
        approved_spec_path="specs/001-git-repo-connection/spec.md",
        approved_plan_path="specs/999-other-change/plan.md",
    )

    with pytest.raises(ValueError, match="같은 기능 디렉터리"):
        repository.create(draft)


def test_planning_input_reference_repository_rejects_non_plan_filename() -> None:
    from tci.infrastructure.persistence.planning_input_reference_repository import (
        PlanningInputReferenceDraft,
        PlanningInputReferenceRepository,
    )

    repository = PlanningInputReferenceRepository(session=MagicMock())
    draft = PlanningInputReferenceDraft(
        workspace_id=uuid.uuid4(),
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="코드 저장소 연동",
        source_reference="user-request-001",
        approved_spec_path="specs/001-git-repo-connection/spec.md",
        approved_plan_path="specs/001-git-repo-connection/notes.md",
    )

    with pytest.raises(ValueError, match="plan.md"):
        repository.create(draft)


def test_planning_input_reference_repository_rejects_non_spec_tree_paths() -> None:
    from tci.infrastructure.persistence.planning_input_reference_repository import (
        PlanningInputReferenceDraft,
        PlanningInputReferenceRepository,
    )

    repository = PlanningInputReferenceRepository(session=MagicMock())
    draft = PlanningInputReferenceDraft(
        workspace_id=uuid.uuid4(),
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="코드 저장소 연동",
        source_reference="user-request-001",
        approved_spec_path="/tmp/spec.md",
        approved_plan_path="/tmp/plan.md",
    )

    with pytest.raises(ValueError, match="specs 디렉터리"):
        repository.create(draft)


def test_planning_input_reference_repository_rejects_path_traversal_segments() -> None:
    from tci.infrastructure.persistence.planning_input_reference_repository import (
        PlanningInputReferenceDraft,
        PlanningInputReferenceRepository,
    )

    repository = PlanningInputReferenceRepository(session=MagicMock())
    draft = PlanningInputReferenceDraft(
        workspace_id=uuid.uuid4(),
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="코드 저장소 연동",
        source_reference="user-request-001",
        approved_spec_path="specs/001-git-repo-connection/../001-git-repo-connection/spec.md",
        approved_plan_path="specs/001-git-repo-connection/../001-git-repo-connection/plan.md",
    )

    with pytest.raises(ValueError, match="경로 순회"):
        repository.create(draft)


def test_planning_input_reference_repository_create_persists_reference_and_calls_session_lifecycle() -> None:
    from tci.infrastructure.persistence.planning_input_reference_repository import (
        PlanningInputReferenceDraft,
        PlanningInputReferenceRepository,
    )

    session = MagicMock()

    def refresh_side_effect(reference) -> None:
        reference.id = uuid.uuid4()

    session.refresh.side_effect = refresh_side_effect
    repository = PlanningInputReferenceRepository(session=session)
    draft = PlanningInputReferenceDraft(
        workspace_id=uuid.uuid4(),
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="코드 저장소 연동",
        source_reference="user-request-001",
        approved_spec_path="specs/001-git-repo-connection/spec.md",
        approved_plan_path="specs/001-git-repo-connection/plan.md",
    )

    reference = repository.create(draft)

    session.add.assert_called_once()
    session.flush.assert_called_once()
    session.refresh.assert_called_once_with(reference)
    assert reference.workspace_id == draft.workspace_id
    assert reference.approved_spec_path == draft.approved_spec_path
    assert reference.approved_plan_path == draft.approved_plan_path


def test_planning_input_reference_repository_get_returns_reference_for_same_workspace() -> None:
    from tci.infrastructure.persistence.planning_input_reference_repository import (
        PlanningInputReferenceRepository,
    )
    from tci.infrastructure.persistence.models import PlanningInputReference

    reference_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    session = MagicMock()
    session.get.return_value = PlanningInputReference(
        id=reference_id,
        workspace_id=workspace_id,
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="코드 저장소 연동",
        source_reference="user-request-001",
        approved_spec_path="specs/001-git-repo-connection/spec.md",
        approved_plan_path="specs/001-git-repo-connection/plan.md",
    )

    repository = PlanningInputReferenceRepository(session=session)

    loaded = repository.get(workspace_id=workspace_id, reference_id=reference_id)

    assert loaded is not None
    assert loaded.id == reference_id


def test_planning_input_reference_repository_get_returns_none_for_different_workspace() -> None:
    from tci.infrastructure.persistence.planning_input_reference_repository import (
        PlanningInputReferenceRepository,
    )
    from tci.infrastructure.persistence.models import PlanningInputReference

    reference_id = uuid.uuid4()
    session = MagicMock()
    session.get.return_value = PlanningInputReference(
        id=reference_id,
        workspace_id=uuid.uuid4(),
        source_type=PlanningInputSourceType.USER_REQUEST,
        source_title="코드 저장소 연동",
        source_reference="user-request-001",
        approved_spec_path="specs/001-git-repo-connection/spec.md",
        approved_plan_path="specs/001-git-repo-connection/plan.md",
    )

    repository = PlanningInputReferenceRepository(session=session)

    loaded = repository.get(workspace_id=uuid.uuid4(), reference_id=reference_id)

    assert loaded is None


def test_git_ref_resolver_resolves_branch_head_sha() -> None:
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitRefResolver

    def runner(command: Sequence[str]) -> GitCommandResult:
        assert command[-1] == "refs/heads/main"
        return GitCommandResult(
            returncode=0,
            stdout="0123456789abcdef0123456789abcdef01234567\trefs/heads/main\n",
            stderr="",
        )

    resolver = GitRefResolver(runner=runner)

    resolved = resolver.resolve(
        remote_url="https://github.com/example/repo.git",
        ref_type=DefaultRefType.BRANCH,
        ref_name="main",
    )

    assert resolved.ref_type is DefaultRefType.BRANCH
    assert resolved.ref_name == "main"
    assert resolved.commit_sha == "0123456789abcdef0123456789abcdef01234567"


def test_git_ref_resolver_redacts_https_token_from_runtime_error() -> None:
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitRefResolver

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="fatal: could not access https://x-access-token:secret-token@github.com/acme/repo.git",
        )

    resolver = GitRefResolver(runner=runner)

    with pytest.raises(RuntimeError, match="REDACTED"):
        resolver.resolve(
            remote_url="https://github.com/example/repo.git",
            ref_type=DefaultRefType.BRANCH,
            ref_name="main",
        )


def test_git_readonly_validator_redacts_https_token_from_error_detail() -> None:
    from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="fatal: Authentication failed for https://x-access-token:secret-token@github.com/acme/repo.git",
        )

    validator = GitReadonlyValidator(runner=runner)
    result = validator.probe(remote_url="https://github.com/example/repo.git")

    assert result.problem_code == ProblemCode.CONNECTION_AUTH_FAILED
    assert "REDACTED" in result.detail
    assert "secret-token" not in result.detail


def test_git_ref_resolver_resolves_local_bare_branch_head_sha_with_subprocess_runner(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_ref_resolver import GitRefResolver

    remote_path = tmp_path / "remote.git"
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    _run_git(["git", "init", "--bare", str(remote_path)], cwd=tmp_path)
    _run_git(["git", "init", "-b", "main"], cwd=worktree_path)
    (worktree_path / "README.md").write_text("hello", encoding="utf-8")
    _run_git(["git", "add", "README.md"], cwd=worktree_path)
    _run_git(["git", "commit", "-m", "initial"], cwd=worktree_path)
    _run_git(["git", "remote", "add", "origin", str(remote_path)], cwd=worktree_path)
    _run_git(["git", "push", "origin", "main"], cwd=worktree_path)
    expected_sha = _run_git(["git", "rev-parse", "HEAD"], cwd=worktree_path).stdout.strip()

    resolver = GitRefResolver(runner=_subprocess_git_runner)

    resolved = resolver.resolve(
        remote_url=str(remote_path),
        ref_type=DefaultRefType.BRANCH,
        ref_name="main",
    )

    assert resolved.commit_sha == expected_sha


def test_git_ref_resolver_prefers_peeled_commit_for_annotated_tag() -> None:
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitRefResolver

    def runner(command: Sequence[str]) -> GitCommandResult:
        assert command[-2:] == ("refs/tags/release-2026.04", "refs/tags/release-2026.04^{}")
        return GitCommandResult(
            returncode=0,
            stdout=(
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/tags/release-2026.04\n"
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\trefs/tags/release-2026.04^{}\n"
            ),
            stderr="",
        )

    resolver = GitRefResolver(runner=runner)

    resolved = resolver.resolve(
        remote_url="https://github.com/example/repo.git",
        ref_type=DefaultRefType.TAG,
        ref_name="release-2026.04",
    )

    assert resolved.ref_type is DefaultRefType.TAG
    assert resolved.ref_name == "release-2026.04"
    assert resolved.commit_sha == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_git_ref_resolver_resolves_local_annotated_tag_to_peeled_commit_with_subprocess_runner(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_ref_resolver import GitRefResolver

    remote_path = tmp_path / "remote.git"
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    _run_git(["git", "init", "--bare", str(remote_path)], cwd=tmp_path)
    _run_git(["git", "init", "-b", "main"], cwd=worktree_path)
    (worktree_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    _run_git(["git", "add", "app.py"], cwd=worktree_path)
    _run_git(["git", "commit", "-m", "tag target"], cwd=worktree_path)
    _run_git(["git", "tag", "-a", "v1.0.0", "-m", "release"], cwd=worktree_path)
    _run_git(["git", "remote", "add", "origin", str(remote_path)], cwd=worktree_path)
    _run_git(["git", "push", "origin", "main", "v1.0.0"], cwd=worktree_path)
    expected_sha = _run_git(["git", "rev-parse", "HEAD"], cwd=worktree_path).stdout.strip()

    resolver = GitRefResolver(runner=_subprocess_git_runner)

    resolved = resolver.resolve(
        remote_url=str(remote_path),
        ref_type=DefaultRefType.TAG,
        ref_name="v1.0.0",
    )

    assert resolved.commit_sha == expected_sha


def test_git_ref_resolver_raises_default_ref_not_found() -> None:
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitRefNotFoundError
    from tci.infrastructure.git.git_ref_resolver import GitRefResolver

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(returncode=0, stdout="", stderr="")

    resolver = GitRefResolver(runner=runner)

    with pytest.raises(GitRefNotFoundError) as error_info:
        resolver.resolve(
            remote_url="https://github.com/example/repo.git",
            ref_type=DefaultRefType.BRANCH,
            ref_name="missing-branch",
        )

    assert error_info.value.problem_code is ProblemCode.DEFAULT_REF_NOT_FOUND


def test_git_ref_resolver_maps_permission_denied_to_connection_auth_failed() -> None:
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitConnectionAuthError
    from tci.infrastructure.git.git_ref_resolver import GitRefResolver

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=128,
            stdout="",
            stderr=(
                "ERROR: Permission to example/repo.git denied to octocat.\n"
                "fatal: Could not read from remote repository.\n"
            ),
        )

    resolver = GitRefResolver(runner=runner)

    with pytest.raises(GitConnectionAuthError) as error_info:
        resolver.resolve(
            remote_url="https://github.com/example/repo.git",
            ref_type=DefaultRefType.BRANCH,
            ref_name="main",
        )

    assert error_info.value.problem_code is ProblemCode.CONNECTION_AUTH_FAILED


def test_git_ref_resolver_maps_repository_not_found_to_connection_auth_failed() -> None:
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitConnectionAuthError
    from tci.infrastructure.git.git_ref_resolver import GitRefResolver

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=128,
            stdout="",
            stderr="fatal: repository 'https://github.com/example/private-repo.git/' not found\n",
        )

    resolver = GitRefResolver(runner=runner)

    with pytest.raises(GitConnectionAuthError) as error_info:
        resolver.resolve(
            remote_url="https://github.com/example/private-repo.git",
            ref_type=DefaultRefType.BRANCH,
            ref_name="main",
        )

    assert error_info.value.problem_code is ProblemCode.CONNECTION_AUTH_FAILED


def test_git_readonly_validator_accepts_readonly_probe_result() -> None:
    from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="remote: Write access to repository not granted.\n",
        )

    validator = GitReadonlyValidator(runner=runner)

    result = validator.probe(remote_url="https://github.com/example/repo.git")

    assert result.is_read_only is True
    assert result.problem_code is None


def test_git_readonly_validator_accepts_permission_denied_probe_as_readonly() -> None:
    from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr=(
                "ERROR: Permission to example/repo.git denied to octocat.\n"
                "fatal: Could not read from remote repository.\n"
            ),
        )

    validator = GitReadonlyValidator(runner=runner)

    result = validator.probe(remote_url="https://github.com/example/repo.git")

    assert result.is_read_only is True
    assert result.problem_code is None


def test_git_readonly_validator_reports_auth_failure_for_invalid_credential() -> None:
    from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="fatal: Authentication failed for 'https://github.com/example/repo.git/'\n",
        )

    validator = GitReadonlyValidator(runner=runner)

    result = validator.probe(remote_url="https://github.com/example/repo.git")

    assert result.is_read_only is False
    assert result.problem_code is ProblemCode.CONNECTION_AUTH_FAILED


def test_git_readonly_validator_keeps_unknown_probe_failures_out_of_auth_bucket() -> None:
    from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="fatal: not a git repository (or any of the parent directories): .git\n",
        )

    validator = GitReadonlyValidator(runner=runner)

    result = validator.probe(remote_url="https://github.com/example/repo.git")

    assert result.is_read_only is False
    assert result.problem_code is None


def test_git_readonly_validator_keeps_hook_declined_out_of_readonly_bucket() -> None:
    from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=1,
            stdout="",
            stderr="remote: error: GH013: Repository rule violations found.\nremote: hook declined\n",
        )

    validator = GitReadonlyValidator(runner=runner)

    result = validator.probe(remote_url="https://github.com/example/repo.git")

    assert result.is_read_only is False
    assert result.problem_code is None
