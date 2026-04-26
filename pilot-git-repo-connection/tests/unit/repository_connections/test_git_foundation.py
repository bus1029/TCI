from __future__ import annotations

import os
from collections.abc import Sequence
import logging
from pathlib import Path
import subprocess
from threading import Event
import time
import uuid
from unittest.mock import MagicMock

import pytest

from tci.api.problem_details import ProblemCode
from tci.infrastructure.persistence.models import (
    CredentialType,
    DefaultRefType,
    PlanningInputSourceType,
    RefType,
    RepositoryTransport,
)

_GIT_TEST_HOME: Path | None = None
_GIT_TEST_XDG_HOME: Path | None = None
_GIT_TEST_GLOBAL_CONFIG: Path | None = None


@pytest.fixture(scope="module", autouse=True)
def _configure_git_test_home(tmp_path_factory: pytest.TempPathFactory) -> None:
    global _GIT_TEST_HOME, _GIT_TEST_XDG_HOME, _GIT_TEST_GLOBAL_CONFIG

    _GIT_TEST_HOME = tmp_path_factory.mktemp("git-home")
    _GIT_TEST_XDG_HOME = _GIT_TEST_HOME / ".config"
    _GIT_TEST_XDG_HOME.mkdir(parents=True, exist_ok=True)
    _GIT_TEST_GLOBAL_CONFIG = _GIT_TEST_HOME / ".gitconfig"
    _GIT_TEST_GLOBAL_CONFIG.write_text("", encoding="utf-8")


def _git_test_env() -> dict[str, str]:
    if (
        _GIT_TEST_HOME is None
        or _GIT_TEST_XDG_HOME is None
        or _GIT_TEST_GLOBAL_CONFIG is None
    ):
        raise RuntimeError(
            "Git test environment must be configured before subprocess calls."
        )

    base_env = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    return {
        **base_env,
        "GIT_AUTHOR_NAME": "TCI Test",
        "GIT_AUTHOR_EMAIL": "tci@example.com",
        "GIT_COMMITTER_NAME": "TCI Test",
        "GIT_COMMITTER_EMAIL": "tci@example.com",
        # Isolate subprocess git calls from the user's broken/global config.
        "HOME": str(_GIT_TEST_HOME),
        "XDG_CONFIG_HOME": str(_GIT_TEST_XDG_HOME),
        "GIT_CONFIG_GLOBAL": str(_GIT_TEST_GLOBAL_CONFIG),
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def _run_git(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env=_git_test_env(),
    )


def _subprocess_git_runner(command: Sequence[str]):
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
        env=_git_test_env(),
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


def test_planning_input_reference_repository_create_persists_reference_and_calls_session_lifecycle() -> (
    None
):
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


def test_planning_input_reference_repository_get_returns_reference_for_same_workspace() -> (
    None
):
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


def test_planning_input_reference_repository_get_returns_none_for_different_workspace() -> (
    None
):
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
    expected_sha = _run_git(
        ["git", "rev-parse", "HEAD"], cwd=worktree_path
    ).stdout.strip()

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
        assert command[-2:] == (
            "refs/tags/release-2026.04",
            "refs/tags/release-2026.04^{}",
        )
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
    expected_sha = _run_git(
        ["git", "rev-parse", "HEAD"], cwd=worktree_path
    ).stdout.strip()

    resolver = GitRefResolver(runner=_subprocess_git_runner)

    resolved = resolver.resolve(
        remote_url=str(remote_path),
        ref_type=DefaultRefType.TAG,
        ref_name="v1.0.0",
    )

    assert resolved.commit_sha == expected_sha


def test_git_ref_resolver_raises_default_ref_not_found() -> None:
    from tci.infrastructure.git.git_ref_resolver import (
        GitCommandResult,
        GitRefNotFoundError,
    )
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


def test_git_ref_resolver_logs_missing_ref_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tci.infrastructure.git.git_ref_resolver import (
        GitCommandResult,
        GitRefNotFoundError,
        GitRefResolver,
    )

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=0,
            stdout="",
            stderr="",
        )

    resolver = GitRefResolver(runner=runner)

    with caplog.at_level(
        logging.WARNING, logger="tci.infrastructure.git.git_ref_resolver"
    ):
        with pytest.raises(GitRefNotFoundError) as error_info:
            resolver.resolve(
                remote_url="https://github.com/example/repo.git",
                ref_type=DefaultRefType.BRANCH,
                ref_name="main",
            )

    assert error_info.value.problem_code is ProblemCode.DEFAULT_REF_NOT_FOUND
    assert "git ref not found after ls-remote" in caplog.text
    assert "refs/heads/main" in caplog.text
    assert "stdout=''" in caplog.text


def test_git_ref_resolver_normalizes_branch_ref_type_from_sync_run() -> None:
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
        ref_type=RefType.BRANCH,
        ref_name="main",
    )

    assert resolved.ref_type is DefaultRefType.BRANCH
    assert resolved.commit_sha == "0123456789abcdef0123456789abcdef01234567"


def test_git_ref_resolver_maps_permission_denied_to_connection_auth_failed() -> None:
    from tci.infrastructure.git.git_ref_resolver import (
        GitCommandResult,
        GitConnectionAuthError,
    )
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


def test_git_ref_resolver_logs_redacted_git_failure_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitRefResolver

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=128,
            stdout="",
            stderr=(
                "fatal: could not access "
                "https://x-access-token:secret-token@github.com/acme/private-repo.git"
            ),
        )

    resolver = GitRefResolver(runner=runner)

    with caplog.at_level(
        logging.WARNING, logger="tci.infrastructure.git.git_ref_resolver"
    ):
        with pytest.raises(RuntimeError):
            resolver.resolve(
                remote_url="https://x-access-token:secret-token@github.com/acme/private-repo.git",
                ref_type=DefaultRefType.BRANCH,
                ref_name="main",
            )

    assert "git ls-remote failed" in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "secret-token" not in caplog.text


def test_build_git_env_isolates_ambient_git_config_and_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.infrastructure.git.git_command_env import build_git_env

    monkeypatch.setenv("HOME", "/tmp/host-home")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/host-xdg")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/tmp/host-home/.gitconfig")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/tmp/system-gitconfig")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "0")
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -oProxyCommand=evil")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/host-agent.sock")

    git_env = build_git_env()

    assert "HOME" not in git_env
    assert "XDG_CONFIG_HOME" not in git_env
    assert "SSH_AUTH_SOCK" not in git_env
    assert git_env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert git_env["GIT_CONFIG_SYSTEM"] == os.devnull
    assert git_env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert git_env["GIT_SSH_COMMAND"] == "ssh -oBatchMode=yes"


def test_https_credential_binding_uses_git_header_env_not_remote_url() -> None:
    from tci.domain.services.repository_connection_support import bind_git_credential
    from tci.infrastructure.git.git_command_env import current_git_command_environment

    remote_url = "https://github.com/acme/private-repo.git"

    with bind_git_credential(
        remote_url=remote_url,
        transport=RepositoryTransport.HTTPS,
        credential_type=CredentialType.HTTPS_PAT,
        credential_secret="secret-token",
    ) as bound_remote_url:
        git_env = current_git_command_environment()

        assert bound_remote_url == remote_url
        assert "secret-token" not in bound_remote_url
        assert "secret-token" not in str(git_env)
        assert "GIT_ASKPASS" in git_env
        assert "TCI_GIT_ASKPASS_SOCKET" in git_env
        username = subprocess.run(
            (git_env["GIT_ASKPASS"], "Username for https://github.com"),
            capture_output=True,
            check=True,
            env={**os.environ, **git_env},
            text=True,
        )
        password = subprocess.run(
            (git_env["GIT_ASKPASS"], "Password for https://x-access-token@github.com"),
            capture_output=True,
            check=True,
            env={**os.environ, **git_env},
            text=True,
        )

        assert username.stdout == "x-access-token\n"
        assert password.stdout == "secret-token\n"

    assert current_git_command_environment() == {}


def test_https_askpass_environment_waits_for_server_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.domain.services import repository_connection_support as support

    server_ready = Event()

    def fake_serve_https_askpass(**kwargs) -> None:
        time.sleep(0.05)
        kwargs["ready_event"].set()
        server_ready.set()

    monkeypatch.setattr(support, "_serve_https_askpass", fake_serve_https_askpass)

    with support._https_askpass_environment(credential_secret="secret-token"):
        assert server_ready.is_set()


def test_https_askpass_environment_surfaces_server_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.domain.services import repository_connection_support as support
    from tci.domain.services.repository_connection_support import (
        RepositoryConnectionProblem,
    )

    def fake_serve_https_askpass(**kwargs) -> None:
        kwargs["startup_errors"].append(OSError("bind failed"))
        kwargs["ready_event"].set()

    monkeypatch.setattr(support, "_serve_https_askpass", fake_serve_https_askpass)

    with pytest.raises(RepositoryConnectionProblem) as error_info:
        with support._https_askpass_environment(credential_secret="secret-token"):
            pass

    assert error_info.value.problem_code is ProblemCode.CONNECTION_AUTH_FAILED


def test_ssh_credential_binding_uses_agent_without_private_key_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.domain.services.repository_connection_support import bind_git_credential
    from tci.infrastructure.git.git_command_env import current_git_command_environment

    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_run(
        command: tuple[str, ...],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        env: dict[str, str],
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, input))
        if command == ("ssh-agent", "-s"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="SSH_AUTH_SOCK=/tmp/tci-agent.sock; export SSH_AUTH_SOCK;\n"
                "SSH_AGENT_PID=12345; export SSH_AGENT_PID;\n",
                stderr="",
            )
        if command == ("ssh-add", "-"):
            assert input == "PRIVATE KEY\n"
            assert env["SSH_AUTH_SOCK"] == "/tmp/tci-agent.sock"
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ("ssh-agent", "-k"):
            assert env["SSH_AGENT_PID"] == "12345"
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with bind_git_credential(
        remote_url="ssh://git@gitlab.example.com/group/repo.git",
        transport=RepositoryTransport.SSH,
        credential_type=CredentialType.SSH_PRIVATE_KEY,
        credential_secret="PRIVATE KEY",
    ) as bound_remote_url:
        git_env = current_git_command_environment()

        assert bound_remote_url == "ssh://git@gitlab.example.com/group/repo.git"
        assert "SSH_AUTH_SOCK" not in git_env
        assert "SSH_AGENT_PID" not in git_env
        assert "-F /dev/null" in git_env["GIT_SSH_COMMAND"]
        assert "-oIdentitiesOnly=yes" in git_env["GIT_SSH_COMMAND"]
        assert "-oIdentityAgent=/tmp/tci-agent.sock" in git_env["GIT_SSH_COMMAND"]
        assert "-oIdentityFile=none" in git_env["GIT_SSH_COMMAND"]
        assert "PRIVATE KEY" not in str(git_env)

    assert [call[0] for call in calls] == [
        ("ssh-agent", "-s"),
        ("ssh-add", "-"),
        ("ssh-agent", "-k"),
    ]
    assert current_git_command_environment() == {}


def test_ssh_credential_cleanup_failure_does_not_fail_successful_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.domain.services.repository_connection_support import bind_git_credential

    def fake_run(
        command: tuple[str, ...],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        env: dict[str, str],
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if command == ("ssh-agent", "-s"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="SSH_AUTH_SOCK=/tmp/tci-agent.sock; export SSH_AUTH_SOCK;\n"
                "SSH_AGENT_PID=12345; export SSH_AGENT_PID;\n",
                stderr="",
            )
        if command == ("ssh-add", "-"):
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ("ssh-agent", "-k"):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with bind_git_credential(
        remote_url="ssh://git@gitlab.example.com/group/repo.git",
        transport=RepositoryTransport.SSH,
        credential_type=CredentialType.SSH_PRIVATE_KEY,
        credential_secret="PRIVATE KEY",
    ):
        pass


def test_ssh_credential_cleanup_failure_preserves_body_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.domain.services.repository_connection_support import bind_git_credential

    def fake_run(
        command: tuple[str, ...],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        env: dict[str, str],
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if command == ("ssh-agent", "-s"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="SSH_AUTH_SOCK=/tmp/tci-agent.sock; export SSH_AUTH_SOCK;\n"
                "SSH_AGENT_PID=12345; export SSH_AGENT_PID;\n",
                stderr="",
            )
        if command == ("ssh-add", "-"):
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ("ssh-agent", "-k"):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="git operation failed"):
        with bind_git_credential(
            remote_url="ssh://git@gitlab.example.com/group/repo.git",
            transport=RepositoryTransport.SSH,
            credential_type=CredentialType.SSH_PRIVATE_KEY,
            credential_secret="PRIVATE KEY",
        ):
            raise RuntimeError("git operation failed")


def test_git_ref_resolver_maps_repository_not_found_to_connection_auth_failed() -> None:
    from tci.infrastructure.git.git_ref_resolver import (
        GitCommandResult,
        GitConnectionAuthError,
    )
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


def test_git_readonly_validator_keeps_unknown_probe_failures_out_of_auth_bucket() -> (
    None
):
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
