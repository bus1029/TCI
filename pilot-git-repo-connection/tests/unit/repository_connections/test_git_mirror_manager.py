from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
import subprocess
import uuid

import pytest

from tci.api.problem_details import ProblemCode

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
    if _GIT_TEST_HOME is None or _GIT_TEST_XDG_HOME is None or _GIT_TEST_GLOBAL_CONFIG is None:
        raise RuntimeError("Git test environment must be configured before subprocess calls.")

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


def _build_test_settings(project_root: Path):
    from tci.settings import Settings

    runtime_root = project_root / ".runtime"
    return Settings(
        project_root=project_root,
        environment="test",
        runtime_root=runtime_root,
        git_mirror_root=runtime_root / "git-mirrors",
        code_snapshot_root=runtime_root / "code-snapshots",
        template_root=project_root / "src" / "tci" / "web" / "templates",
        database_url=None,
        redis_url=None,
        credential_encryption_key=None,
    )


def test_git_mirror_manager_creates_canonical_bare_mirror_under_settings_root(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorManager

    remote_path = tmp_path / "remote.git"
    worktree_path = tmp_path / "worktree"
    connection_id = uuid.uuid4()
    worktree_path.mkdir()
    _run_git(["git", "init", "--bare", str(remote_path)], cwd=tmp_path)
    _run_git(["git", "init", "-b", "main"], cwd=worktree_path)
    (worktree_path / "README.md").write_text("hello", encoding="utf-8")
    _run_git(["git", "add", "README.md"], cwd=worktree_path)
    _run_git(["git", "commit", "-m", "initial"], cwd=worktree_path)
    _run_git(["git", "remote", "add", "origin", str(remote_path)], cwd=worktree_path)
    _run_git(["git", "push", "origin", "main"], cwd=worktree_path)
    expected_sha = _run_git(["git", "rev-parse", "HEAD"], cwd=worktree_path).stdout.strip()
    settings = _build_test_settings(tmp_path)
    manager = GitMirrorManager(settings=settings, runner=_subprocess_git_runner)

    mirror = manager.ensure_synced_mirror(
        connection_id=connection_id,
        remote_url=str(remote_path),
    )

    assert mirror.connection_id == connection_id
    assert mirror.mirror_path == f".runtime/git-mirrors/{connection_id}.git"
    assert mirror.absolute_path == settings.git_mirror_root / f"{connection_id}.git"
    assert mirror.absolute_path.is_dir()
    bare = _run_git(
        ["git", f"--git-dir={mirror.absolute_path}", "rev-parse", "--is-bare-repository"],
        cwd=tmp_path,
    ).stdout.strip()
    mirrored_sha = _run_git(
        ["git", f"--git-dir={mirror.absolute_path}", "rev-parse", "refs/heads/main"],
        cwd=tmp_path,
    ).stdout.strip()
    assert bare == "true"
    assert mirrored_sha == expected_sha


def test_git_mirror_manager_reuses_existing_mirror_without_recloning(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorManager

    remote_path = tmp_path / "remote.git"
    worktree_path = tmp_path / "worktree"
    connection_id = uuid.uuid4()
    worktree_path.mkdir()
    _run_git(["git", "init", "--bare", str(remote_path)], cwd=tmp_path)
    _run_git(["git", "init", "-b", "main"], cwd=worktree_path)
    (worktree_path / "README.md").write_text("hello", encoding="utf-8")
    _run_git(["git", "add", "README.md"], cwd=worktree_path)
    _run_git(["git", "commit", "-m", "initial"], cwd=worktree_path)
    _run_git(["git", "remote", "add", "origin", str(remote_path)], cwd=worktree_path)
    _run_git(["git", "push", "origin", "main"], cwd=worktree_path)
    settings = _build_test_settings(tmp_path)
    manager = GitMirrorManager(settings=settings, runner=_subprocess_git_runner)

    first_mirror = manager.ensure_synced_mirror(
        connection_id=connection_id,
        remote_url=str(remote_path),
    )
    sentinel = first_mirror.absolute_path / "mirror-sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    second_mirror = manager.ensure_synced_mirror(
        connection_id=connection_id,
        remote_url=str(remote_path),
    )

    assert second_mirror.absolute_path == first_mirror.absolute_path
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_git_mirror_manager_fetches_latest_remote_head_into_existing_mirror(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorManager

    remote_path = tmp_path / "remote.git"
    worktree_path = tmp_path / "worktree"
    connection_id = uuid.uuid4()
    worktree_path.mkdir()
    _run_git(["git", "init", "--bare", str(remote_path)], cwd=tmp_path)
    _run_git(["git", "init", "-b", "main"], cwd=worktree_path)
    (worktree_path / "README.md").write_text("hello", encoding="utf-8")
    _run_git(["git", "add", "README.md"], cwd=worktree_path)
    _run_git(["git", "commit", "-m", "initial"], cwd=worktree_path)
    _run_git(["git", "remote", "add", "origin", str(remote_path)], cwd=worktree_path)
    _run_git(["git", "push", "origin", "main"], cwd=worktree_path)
    settings = _build_test_settings(tmp_path)
    manager = GitMirrorManager(settings=settings, runner=_subprocess_git_runner)
    mirror = manager.ensure_synced_mirror(
        connection_id=connection_id,
        remote_url=str(remote_path),
    )

    (worktree_path / "README.md").write_text("hello again", encoding="utf-8")
    _run_git(["git", "add", "README.md"], cwd=worktree_path)
    _run_git(["git", "commit", "-m", "update"], cwd=worktree_path)
    _run_git(["git", "push", "origin", "main"], cwd=worktree_path)
    expected_sha = _run_git(["git", "rev-parse", "HEAD"], cwd=worktree_path).stdout.strip()

    manager.ensure_synced_mirror(connection_id=connection_id, remote_url=str(remote_path))

    mirrored_sha = _run_git(
        ["git", f"--git-dir={mirror.absolute_path}", "rev-parse", "refs/heads/main"],
        cwd=tmp_path,
    ).stdout.strip()
    assert mirrored_sha == expected_sha


def test_git_mirror_manager_updates_origin_when_remote_url_changes(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorManager

    remote_one_path = tmp_path / "remote-one.git"
    remote_two_path = tmp_path / "remote-two.git"
    worktree_one_path = tmp_path / "worktree-one"
    worktree_two_path = tmp_path / "worktree-two"
    connection_id = uuid.uuid4()
    worktree_one_path.mkdir()
    worktree_two_path.mkdir()

    _run_git(["git", "init", "--bare", str(remote_one_path)], cwd=tmp_path)
    _run_git(["git", "init", "-b", "main"], cwd=worktree_one_path)
    (worktree_one_path / "README.md").write_text("remote one", encoding="utf-8")
    _run_git(["git", "add", "README.md"], cwd=worktree_one_path)
    _run_git(["git", "commit", "-m", "remote one"], cwd=worktree_one_path)
    _run_git(["git", "remote", "add", "origin", str(remote_one_path)], cwd=worktree_one_path)
    _run_git(["git", "push", "origin", "main"], cwd=worktree_one_path)

    _run_git(["git", "init", "--bare", str(remote_two_path)], cwd=tmp_path)
    _run_git(["git", "init", "-b", "main"], cwd=worktree_two_path)
    (worktree_two_path / "README.md").write_text("remote two", encoding="utf-8")
    _run_git(["git", "add", "README.md"], cwd=worktree_two_path)
    _run_git(["git", "commit", "-m", "remote two"], cwd=worktree_two_path)
    _run_git(["git", "remote", "add", "origin", str(remote_two_path)], cwd=worktree_two_path)
    _run_git(["git", "push", "origin", "main"], cwd=worktree_two_path)
    expected_sha = _run_git(["git", "rev-parse", "HEAD"], cwd=worktree_two_path).stdout.strip()

    settings = _build_test_settings(tmp_path)
    manager = GitMirrorManager(settings=settings, runner=_subprocess_git_runner)
    mirror = manager.ensure_synced_mirror(
        connection_id=connection_id,
        remote_url=str(remote_one_path),
    )

    manager.ensure_synced_mirror(
        connection_id=connection_id,
        remote_url=str(remote_two_path),
    )

    configured_origin = _run_git(
        ["git", f"--git-dir={mirror.absolute_path}", "config", "--get", "remote.origin.url"],
        cwd=tmp_path,
    ).stdout.strip()
    mirrored_sha = _run_git(
        ["git", f"--git-dir={mirror.absolute_path}", "rev-parse", "refs/heads/main"],
        cwd=tmp_path,
    ).stdout.strip()
    assert configured_origin == str(remote_two_path)
    assert mirrored_sha == expected_sha


def test_git_mirror_manager_restores_origin_after_temporary_authenticated_fetch_failure(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorManager, GitMirrorSyncError
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    connection_id = uuid.uuid4()
    settings = _build_test_settings(tmp_path)
    target_path = settings.git_mirror_root / f"{connection_id}.git"
    target_path.mkdir(parents=True)
    commands: list[tuple[str, ...]] = []

    def runner(command: Sequence[str]) -> GitCommandResult:
        commands.append(tuple(command))
        if command[-1] == "--is-bare-repository":
            return GitCommandResult(returncode=0, stdout="true\n", stderr="")
        if command[-3:] == ("config", "--get", "remote.origin.url"):
            return GitCommandResult(
                returncode=0,
                stdout="https://github.com/acme/sample-repo.git\n",
                stderr="",
            )
        if command[-4:-1] == ("remote", "set-url", "origin"):
            return GitCommandResult(returncode=0, stdout="", stderr="")
        if command[-3:] == ("fetch", "--prune", "origin"):
            return GitCommandResult(
                returncode=128,
                stdout="",
                stderr="fatal: Authentication failed for 'https://github.com/acme/sample-repo.git/'\n",
            )
        raise AssertionError(f"unexpected command: {command}")

    manager = GitMirrorManager(settings=settings, runner=runner)

    with pytest.raises(GitMirrorSyncError):
        manager.ensure_synced_mirror(
            connection_id=connection_id,
            remote_url="https://x-access-token:secret@github.com/acme/sample-repo.git",
            restore_remote_url="https://github.com/acme/sample-repo.git",
        )

    assert commands[-1] == (
        "git",
        f"--git-dir={target_path}",
        "remote",
        "set-url",
        "origin",
        "https://github.com/acme/sample-repo.git",
    )


def test_git_mirror_manager_restores_origin_after_new_temporary_authenticated_clone(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorManager
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    connection_id = uuid.uuid4()
    settings = _build_test_settings(tmp_path)
    commands: list[tuple[str, ...]] = []

    def runner(command: Sequence[str]) -> GitCommandResult:
        commands.append(tuple(command))
        if command[:3] == ("git", "clone", "--mirror"):
            Path(command[-1]).mkdir(parents=True)
            return GitCommandResult(returncode=0, stdout="", stderr="")
        if command[-4:-1] == ("remote", "set-url", "origin"):
            return GitCommandResult(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    manager = GitMirrorManager(settings=settings, runner=runner)

    manager.ensure_synced_mirror(
        connection_id=connection_id,
        remote_url="https://x-access-token:secret@github.com/acme/sample-repo.git",
        restore_remote_url="https://github.com/acme/sample-repo.git",
    )

    assert commands[-1][-1] == "https://github.com/acme/sample-repo.git"


def test_git_mirror_manager_rejects_non_bare_existing_target_path(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorManager, GitMirrorSyncError

    connection_id = uuid.uuid4()
    settings = _build_test_settings(tmp_path)
    target_path = settings.git_mirror_root / f"{connection_id}.git"
    target_path.mkdir(parents=True)
    (target_path / "README.md").write_text("not a bare repo", encoding="utf-8")
    manager = GitMirrorManager(settings=settings, runner=_subprocess_git_runner)

    with pytest.raises(GitMirrorSyncError, match="bare mirror"):
        manager.ensure_synced_mirror(
            connection_id=connection_id,
            remote_url="https://github.com/example/repo.git",
        )


def test_git_mirror_manager_maps_auth_like_fetch_failure_to_auth_error(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorAuthError, GitMirrorManager
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    connection_id = uuid.uuid4()
    settings = _build_test_settings(tmp_path)

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=128,
            stdout="",
            stderr="fatal: Authentication failed for 'https://github.com/example/repo.git/'\n",
        )

    manager = GitMirrorManager(settings=settings, runner=runner)

    with pytest.raises(GitMirrorAuthError) as error_info:
        manager.ensure_synced_mirror(
            connection_id=connection_id,
            remote_url="https://github.com/example/repo.git",
        )

    assert error_info.value.problem_code is ProblemCode.CONNECTION_AUTH_FAILED


def test_git_mirror_manager_maps_repository_not_found_to_auth_error(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.git.git_mirror_manager import GitMirrorAuthError, GitMirrorManager
    from tci.infrastructure.git.git_ref_resolver import GitCommandResult

    connection_id = uuid.uuid4()
    settings = _build_test_settings(tmp_path)

    def runner(command: Sequence[str]) -> GitCommandResult:
        return GitCommandResult(
            returncode=128,
            stdout="",
            stderr="fatal: repository 'https://github.com/example/private-repo.git/' not found\n",
        )

    manager = GitMirrorManager(settings=settings, runner=runner)

    with pytest.raises(GitMirrorAuthError) as error_info:
        manager.ensure_synced_mirror(
            connection_id=connection_id,
            remote_url="https://github.com/example/private-repo.git",
        )

    assert error_info.value.problem_code is ProblemCode.CONNECTION_AUTH_FAILED


def test_git_mirror_manager_subprocess_runner_forces_noninteractive_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tci.infrastructure.git import git_mirror_manager

    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
        env: dict[str, str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["check"] = check
        captured["env"] = env
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(git_mirror_manager.subprocess, "run", fake_run)

    result = git_mirror_manager._subprocess_git_runner(("git", "fetch", "--prune"))

    assert result.returncode == 0
    assert captured["command"] == ["git", "fetch", "--prune"]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False
    assert captured["timeout"] == git_mirror_manager.DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS
    assert isinstance(captured["env"], dict)
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert "BatchMode=yes" in captured["env"]["GIT_SSH_COMMAND"]
