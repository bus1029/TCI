from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import time
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.default_scope_policy import is_hard_excluded_path
from tci.infrastructure.git.git_command_env import build_git_env
from tci.infrastructure.git.git_ref_resolver import GitCommandResult, GitCommandRunner
from tci.infrastructure.persistence.models import SnapshotInclusionReason
from tci.infrastructure.snapshots.snapshot_archive_store import (
    SnapshotArchiveEntryDraft,
)
from tci.settings import Settings


DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS = 600
MAX_SNAPSHOT_BLOB_BYTES = 5 * 1024 * 1024
MAX_SNAPSHOT_TOTAL_BYTES = 50 * 1024 * 1024
MAX_SNAPSHOT_ENTRY_COUNT = 10_000
MAX_SNAPSHOT_CANDIDATE_COUNT = 100_000
MAX_SNAPSHOT_TREE_ENTRY_COUNT = 250_000


@dataclass(frozen=True, slots=True)
class ManagedGitMirror:
    connection_id: uuid.UUID
    mirror_path: str
    absolute_path: Path


@dataclass(frozen=True, slots=True)
class MaterializedGitSnapshot:
    tree_sha: str
    entries: tuple[SnapshotArchiveEntryDraft, ...]


class GitMirrorSyncError(RuntimeError):
    pass


class GitMirrorAuthError(GitMirrorSyncError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.problem_code = ProblemCode.CONNECTION_AUTH_FAILED


def _subprocess_git_runner(command: Sequence[str]) -> GitCommandResult:
    env = build_git_env()
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
        restore_remote_url: str | None = None,
    ) -> ManagedGitMirror:
        absolute_path = self._settings.git_mirror_root / f"{connection_id}.git"
        self._settings.git_mirror_root.mkdir(parents=True, exist_ok=True)
        persisted_remote_url = restore_remote_url or remote_url

        if absolute_path.exists():
            self._ensure_existing_target_is_bare_mirror(absolute_path)
            self._configure_origin(
                absolute_path=absolute_path,
                remote_url=persisted_remote_url,
            )
            self._fetch_mirror(
                absolute_path=absolute_path,
                fetch_url=remote_url if restore_remote_url is not None else "origin",
            )
        else:
            temp_path = absolute_path.with_name(
                f".{connection_id}.{uuid.uuid4().hex}.tmp"
            )
            try:
                self._run_git(("git", "init", "--bare", str(temp_path)))
                self._configure_origin(
                    absolute_path=temp_path,
                    remote_url=persisted_remote_url,
                )
                self._fetch_mirror(
                    absolute_path=temp_path,
                    fetch_url=(
                        remote_url if restore_remote_url is not None else "origin"
                    ),
                )
                if absolute_path.exists():
                    shutil.rmtree(temp_path, ignore_errors=True)
                    return self.ensure_synced_mirror(
                        connection_id=connection_id,
                        remote_url=remote_url,
                        restore_remote_url=restore_remote_url,
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
        self._configure_origin(
            absolute_path=mirror.absolute_path, remote_url=remote_url
        )

    def read_snapshot_entries(
        self,
        *,
        mirror: ManagedGitMirror,
        commit_sha: str,
        include_binary: bool = False,
        include_paths: Sequence[str] = (),
        exclude_paths: Sequence[str] = (),
        allowed_file_types: Sequence[str] = (),
        blocked_file_types: Sequence[str] = (),
        max_file_size_bytes: int = MAX_SNAPSHOT_BLOB_BYTES,
    ) -> MaterializedGitSnapshot:
        tree_sha = self._run_git(
            (
                "git",
                f"--git-dir={mirror.absolute_path}",
                "rev-parse",
                f"{commit_sha}^{{tree}}",
            )
        ).stdout.strip()
        entries: list[SnapshotArchiveEntryDraft] = []
        candidate_count = 0
        total_bytes = 0
        max_allowed_blob_bytes = min(max_file_size_bytes, MAX_SNAPSHOT_BLOB_BYTES)
        tree_entry_count = 0
        for raw_entry in self._iter_git_tree_entries(
            absolute_path=mirror.absolute_path,
            commit_sha=commit_sha,
        ):
            if not raw_entry:
                continue
            tree_entry_count += 1
            if tree_entry_count > MAX_SNAPSHOT_TREE_ENTRY_COUNT:
                raise GitMirrorSyncError("Git tree entry 수가 제한을 초과했습니다.")
            metadata, path = raw_entry.split("\t", maxsplit=1)
            metadata_parts = metadata.split()
            _mode, object_type, blob_sha = metadata_parts[:3]
            if object_type != "blob":
                continue
            if is_hard_excluded_path(path):
                continue
            if _is_scope_prefiltered_path(
                path=path,
                include_paths=include_paths,
                exclude_paths=exclude_paths,
                allowed_file_types=allowed_file_types,
                blocked_file_types=blocked_file_types,
            ):
                continue
            candidate_count += 1
            if candidate_count > MAX_SNAPSHOT_CANDIDATE_COUNT:
                raise GitMirrorSyncError("스냅샷 후보 파일 수가 제한을 초과했습니다.")
            raw_size = metadata_parts[3] if len(metadata_parts) > 3 else "-"
            if _parse_ls_tree_size(raw_size) > max_allowed_blob_bytes:
                continue
            content = self._read_git_blob_bytes(
                absolute_path=mirror.absolute_path,
                blob_sha=blob_sha,
                include_binary=include_binary,
                max_blob_bytes=max_allowed_blob_bytes,
            )
            if content is None:
                continue
            total_bytes += len(content)
            if total_bytes > MAX_SNAPSHOT_TOTAL_BYTES:
                raise GitMirrorSyncError(
                    "스냅샷 후보 파일의 총 크기가 제한을 초과했습니다."
                )
            if len(entries) >= MAX_SNAPSHOT_ENTRY_COUNT:
                raise GitMirrorSyncError("스냅샷 후보 파일 수가 제한을 초과했습니다.")
            entries.append(
                SnapshotArchiveEntryDraft(
                    path=path,
                    content=content,
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=Path(path).suffix or None,
                    language_hint=None,
                    archive_blob_path=(
                        "__tci_snapshot_reserved__/root-manifest.json"
                        if path == "manifest.json"
                        else None
                    ),
                )
            )

        return MaterializedGitSnapshot(tree_sha=tree_sha, entries=tuple(entries))

    def _iter_git_tree_entries(
        self, *, absolute_path: Path, commit_sha: str
    ) -> Iterator[str]:
        process = subprocess.Popen(
            [
                "git",
                f"--git-dir={absolute_path}",
                "ls-tree",
                "-r",
                "-l",
                "-z",
                commit_sha,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=build_git_env(),
        )
        if process.stdout is None:
            process.kill()
            process.communicate()
            raise GitMirrorSyncError("Git tree 출력 스트림을 열 수 없습니다.")

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS
        buffer = b""
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    process.communicate()
                    raise GitMirrorSyncError(
                        "Git tree를 읽는 중 제한 시간을 초과했습니다."
                    )
                events = selector.select(timeout=remaining)
                if not events:
                    if process.poll() is not None:
                        break
                    process.kill()
                    process.communicate()
                    raise GitMirrorSyncError(
                        "Git tree를 읽는 중 제한 시간을 초과했습니다."
                    )
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\0" in buffer:
                    record, buffer = buffer.split(b"\0", maxsplit=1)
                    if record:
                        yield record.decode("utf-8", errors="replace")
            process.communicate(timeout=max(deadline - time.monotonic(), 0.001))
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.communicate()
            raise GitMirrorSyncError(
                "Git tree를 읽는 중 제한 시간을 초과했습니다."
            ) from error
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
                process.communicate()
        if process.returncode != 0:
            raise GitMirrorSyncError("Git tree를 읽는 중 오류가 발생했습니다.")
        if buffer:
            raise GitMirrorSyncError("Git tree 목록 형식이 유효하지 않습니다.")

    def _ensure_existing_target_is_bare_mirror(self, absolute_path: Path) -> None:
        result = self._runner(
            ("git", f"--git-dir={absolute_path}", "rev-parse", "--is-bare-repository")
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise GitMirrorSyncError("기존 미러 경로가 유효한 bare mirror가 아닙니다.")

    def _get_origin_url(self, *, absolute_path: Path) -> str | None:
        result = self._runner(
            (
                "git",
                f"--git-dir={absolute_path}",
                "config",
                "--get",
                "remote.origin.url",
            )
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def _set_origin_url(self, *, absolute_path: Path, remote_url: str) -> None:
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

    def _configure_origin(self, *, absolute_path: Path, remote_url: str) -> None:
        if self._get_origin_url(absolute_path=absolute_path) is None:
            self._run_git(
                (
                    "git",
                    f"--git-dir={absolute_path}",
                    "remote",
                    "add",
                    "origin",
                    remote_url,
                )
            )
        else:
            self._set_origin_url(absolute_path=absolute_path, remote_url=remote_url)
        self._run_git(
            (
                "git",
                f"--git-dir={absolute_path}",
                "config",
                "remote.origin.fetch",
                "+refs/*:refs/*",
            )
        )
        self._run_git(
            (
                "git",
                f"--git-dir={absolute_path}",
                "config",
                "remote.origin.mirror",
                "true",
            )
        )

    def _fetch_mirror(self, *, absolute_path: Path, fetch_url: str) -> None:
        self._run_git(
            (
                "git",
                f"--git-dir={absolute_path}",
                "fetch",
                "--prune",
                fetch_url,
                "+refs/*:refs/*",
            )
        )

    def _run_git(self, command: Sequence[str]) -> GitCommandResult:
        result = self._runner(command)
        if result.returncode == 0:
            return result
        if _looks_like_auth_failure(result.stderr):
            raise GitMirrorAuthError(
                _sanitize_git_error_detail(result.stderr).strip()
                or "저장소 자격 증명 검증에 실패했습니다."
            )
        raise GitMirrorSyncError(
            _sanitize_git_error_detail(result.stderr).strip()
            or "Git mirror 동기화에 실패했습니다."
        )

    def _read_git_blob_bytes(
        self,
        *,
        absolute_path: Path,
        blob_sha: str,
        include_binary: bool,
        max_blob_bytes: int,
    ) -> bytes | None:
        try:
            completed = subprocess.run(
                [
                    "git",
                    f"--git-dir={absolute_path}",
                    "cat-file",
                    "-p",
                    blob_sha,
                ],
                capture_output=True,
                check=False,
                env=build_git_env(),
                timeout=DEFAULT_GIT_COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            raise GitMirrorSyncError(
                "Git blob을 읽는 중 제한 시간을 초과했습니다."
            ) from error
        if completed.returncode != 0:
            detail = _normalize_subprocess_output(completed.stderr).strip()
            raise GitMirrorSyncError(
                _sanitize_git_error_detail(detail)
                or "Git blob을 읽는 중 오류가 발생했습니다."
            )
        if len(completed.stdout) > max_blob_bytes:
            return None
        if not include_binary and b"\x00" in completed.stdout:
            return None
        return completed.stdout

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


def _sanitize_git_error_detail(detail: str) -> str:
    sanitized = re.sub(
        r"https://x-access-token:[^@\s]+@",
        "https://x-access-token:[REDACTED]@",
        detail,
    )
    return re.sub(
        r"(authorization:\s*basic\s+)[A-Za-z0-9+/=]+",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )


def _parse_ls_tree_size(raw_size: str) -> int:
    if raw_size == "-":
        return 0
    try:
        return int(raw_size)
    except ValueError:
        return 0


def _is_scope_prefiltered_path(
    *,
    path: str,
    include_paths: Sequence[str],
    exclude_paths: Sequence[str],
    allowed_file_types: Sequence[str],
    blocked_file_types: Sequence[str],
) -> bool:
    if include_paths and not _matches_any_path(path, include_paths):
        return True
    if _matches_any_path(path, exclude_paths):
        return True
    if blocked_file_types and _matches_file_type(path, blocked_file_types):
        return True
    return bool(allowed_file_types and not _matches_file_type(path, allowed_file_types))


def _matches_any_path(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _matches_file_type(path: str, file_types: Sequence[str]) -> bool:
    lowered_path = path.lower()
    for file_type in file_types:
        normalized = file_type.lower()
        if normalized.startswith(".") and lowered_path.endswith(normalized):
            return True
        if not normalized.startswith(".") and lowered_path.endswith(f".{normalized}"):
            return True
    return False
