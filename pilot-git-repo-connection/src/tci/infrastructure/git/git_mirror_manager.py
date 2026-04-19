from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from tci.api.problem_details import ProblemCode
from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitCommandRunner
from tci.settings import Settings


DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS = 600


@dataclass(frozen=True, slots=True)
class ManagedGitMirror:
    connection_id: uuid.UUID
    mirror_path: str
    absolute_path: Path


class GitMirrorSyncError(RuntimeError):
    pass


class GitMirrorAuthError(GitMirrorSyncError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.problem_code = ProblemCode.CONNECTION_AUTH_FAILED


def _subprocess_git_runner(command: Sequence[str]) -> GitCommandResult:
    ssh_command = os.environ.get("GIT_SSH_COMMAND", "ssh")
    if "batchmode=yes" not in ssh_command.lower():
        ssh_command = f"{ssh_command} -oBatchMode=yes"
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": ssh_command,
    }
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        return GitCommandResult(
            returncode=124,
            stdout=_normalize_subprocess_output(error.stdout),
            stderr=_normalize_subprocess_output(error.stderr).strip()
            or "Git 명령 실행 시간이 제한을 초과했습니다.",
        )
    return GitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


class GitMirrorManager:
    def __init__(
        self,
        *,
        settings: Settings,
        runner: GitCommandRunner | None = None,
    ) -> None:
        self._settings = settings
        self._runner = runner or _subprocess_git_runner

    def ensure_synced_mirror(
        self,
        *,
        connection_id: uuid.UUID,
        remote_url: str,
    ) -> ManagedGitMirror:
        absolute_path = self._settings.git_mirror_root / f"{connection_id}.git"
        self._settings.git_mirror_root.mkdir(parents=True, exist_ok=True)

        if absolute_path.exists():
            self._ensure_existing_target_is_bare_mirror(absolute_path)
            self._ensure_origin_url(absolute_path=absolute_path, remote_url=remote_url)
            self._run_git(
                (
                    "git",
                    f"--git-dir={absolute_path}",
                    "fetch",
                    "--prune",
                    "origin",
                )
            )
        else:
            temp_path = absolute_path.with_name(f".{connection_id}.{uuid.uuid4().hex}.tmp")
            try:
                self._run_git(("git", "clone", "--mirror", remote_url, str(temp_path)))
                if absolute_path.exists():
                    shutil.rmtree(temp_path, ignore_errors=True)
                    return self.ensure_synced_mirror(
                        connection_id=connection_id,
                        remote_url=remote_url,
                    )
                temp_path.replace(absolute_path)
            except Exception:
                shutil.rmtree(temp_path, ignore_errors=True)
                raise

        return ManagedGitMirror(
            connection_id=connection_id,
            mirror_path=self._to_project_relative_path(absolute_path),
            absolute_path=absolute_path,
        )

    def reset_origin_url(self, *, mirror: ManagedGitMirror, remote_url: str) -> None:
        self._run_git(
            (
                "git",
                f"--git-dir={mirror.absolute_path}",
                "remote",
                "set-url",
                "origin",
                remote_url,
            )
        )

    def _ensure_existing_target_is_bare_mirror(self, absolute_path: Path) -> None:
        result = self._runner(
            ("git", f"--git-dir={absolute_path}", "rev-parse", "--is-bare-repository")
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise GitMirrorSyncError(
                "기존 미러 경로가 유효한 bare mirror가 아닙니다."
            )

    def _ensure_origin_url(self, *, absolute_path: Path, remote_url: str) -> None:
        result = self._runner(
            ("git", f"--git-dir={absolute_path}", "config", "--get", "remote.origin.url")
        )
        current_origin = result.stdout.strip()
        if result.returncode != 0 or current_origin != remote_url:
            self._run_git(
                (
                    "git",
                    f"--git-dir={absolute_path}",
                    "remote",
                    "set-url",
                    "origin",
                    remote_url,
                )
            )

    def _run_git(self, command: Sequence[str]) -> GitCommandResult:
        result = self._runner(command)
        if result.returncode == 0:
            return result
        if _looks_like_auth_failure(result.stderr):
            raise GitMirrorAuthError(
                result.stderr.strip() or "저장소 자격 증명 검증에 실패했습니다."
            )
        raise GitMirrorSyncError(result.stderr.strip() or "Git mirror 동기화에 실패했습니다.")

    def _to_project_relative_path(self, absolute_path: Path) -> str:
        try:
            return absolute_path.relative_to(self._settings.project_root).as_posix()
        except ValueError as error:
            raise GitMirrorSyncError(
                "미러 경로는 프로젝트 루트 아래에 있어야 합니다."
            ) from error


def _looks_like_auth_failure(stderr: str) -> bool:
    lowered = stderr.lower()
    if "fatal: repository" in lowered and "not found" in lowered:
        return True
    return any(
        token in lowered
        for token in (
            "authentication failed",
            "could not read username",
            "permission denied (publickey)",
            "permission to ",
        )
    )


def _normalize_subprocess_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
