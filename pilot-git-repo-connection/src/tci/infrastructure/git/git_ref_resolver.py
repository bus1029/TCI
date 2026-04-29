from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import logging
import re

from tci.api.problem_details import ProblemCode
from tci.infrastructure.persistence.models import DefaultRefType, RefType

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GitCommandResult:
    returncode: int
    stdout: str
    stderr: str


GitCommandRunner = Callable[[Sequence[str]], GitCommandResult]


@dataclass(frozen=True, slots=True)
class ResolvedGitRef:
    ref_type: DefaultRefType
    ref_name: str
    commit_sha: str


class GitRefNotFoundError(RuntimeError):
    def __init__(self, ref_name: str) -> None:
        super().__init__(f"기본 분석 대상 ref를 찾을 수 없습니다: {ref_name}")
        self.problem_code = ProblemCode.DEFAULT_REF_NOT_FOUND


class GitConnectionAuthError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("저장소 자격 증명 검증에 실패했습니다.")
        self.problem_code = ProblemCode.CONNECTION_AUTH_FAILED


class GitRefResolver:
    def __init__(self, runner: GitCommandRunner) -> None:
        self._runner = runner

    def resolve(
        self,
        *,
        remote_url: str,
        ref_type: DefaultRefType | RefType | str,
        ref_name: str,
    ) -> ResolvedGitRef:
        normalized_ref_type = _normalize_ref_type(ref_type)
        refspecs = _build_refspecs(ref_type=normalized_ref_type, ref_name=ref_name)
        result = self._runner(("git", "ls-remote", remote_url, *refspecs))
        sanitized_remote_url = _sanitize_remote_url(remote_url)
        sanitized_stdout = _sanitize_git_io(result.stdout)
        sanitized_stderr = _sanitize_git_io(result.stderr)

        if result.returncode != 0:
            logger.warning(
                "git ls-remote failed remote_url=%s ref_type=%s ref_name=%s refspecs=%s "
                "returncode=%s stdout=%r stderr=%r",
                sanitized_remote_url,
                normalized_ref_type.value,
                ref_name,
                list(refspecs),
                result.returncode,
                sanitized_stdout,
                sanitized_stderr,
            )
            if _looks_like_auth_failure(result.stderr):
                raise GitConnectionAuthError()
            raise RuntimeError(
                _sanitize_git_error_detail(result.stderr).strip()
                or "git ls-remote 실행에 실패했습니다."
            )

        sha_by_ref: dict[str, str] = {}
        for line in result.stdout.splitlines():
            sha, _, resolved_ref = line.partition("\t")
            if sha and resolved_ref:
                sha_by_ref[resolved_ref] = sha

        commit_sha = _select_commit_sha(
            ref_type=normalized_ref_type,
            ref_name=ref_name,
            sha_by_ref=sha_by_ref,
        )
        if commit_sha is not None:
            return ResolvedGitRef(
                ref_type=normalized_ref_type,
                ref_name=ref_name,
                commit_sha=commit_sha,
            )

        logger.warning(
            "git ref not found after ls-remote remote_url=%s ref_type=%s ref_name=%s "
            "refspecs=%s returncode=%s stdout=%r stderr=%r",
            sanitized_remote_url,
            normalized_ref_type.value,
            ref_name,
            list(refspecs),
            result.returncode,
            sanitized_stdout,
            sanitized_stderr,
        )
        raise GitRefNotFoundError(ref_name)


def _build_refspecs(*, ref_type: DefaultRefType, ref_name: str) -> tuple[str, ...]:
    if ref_type == DefaultRefType.BRANCH:
        return (f"refs/heads/{ref_name}",)
    tag_ref = f"refs/tags/{ref_name}"
    return (tag_ref, f"{tag_ref}^{{}}")


def _select_commit_sha(
    *,
    ref_type: DefaultRefType,
    ref_name: str,
    sha_by_ref: dict[str, str],
) -> str | None:
    if ref_type == DefaultRefType.BRANCH:
        return sha_by_ref.get(f"refs/heads/{ref_name}")

    tag_ref = f"refs/tags/{ref_name}"
    return sha_by_ref.get(f"{tag_ref}^{{}}") or sha_by_ref.get(tag_ref)


def _normalize_ref_type(ref_type: DefaultRefType | RefType | str) -> DefaultRefType:
    raw_value = (
        ref_type.value if isinstance(ref_type, (DefaultRefType, RefType)) else ref_type
    )
    try:
        return DefaultRefType(raw_value)
    except ValueError as error:
        raise RuntimeError(f"지원하지 않는 ref 타입입니다: {raw_value}") from error


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
            "could not read from remote repository",
            "repository not found",
        )
    )


def _sanitize_git_error_detail(detail: str) -> str:
    sanitized = re.sub(
        r"(https?://x-access-token:)[^@\s]+@",
        r"\1[REDACTED]@",
        detail,
    )
    return re.sub(
        r"(authorization:\s*basic\s+)[A-Za-z0-9+/=]+",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )


def _sanitize_remote_url(remote_url: str) -> str:
    return _sanitize_git_error_detail(remote_url)


def _sanitize_git_io(detail: str, *, limit: int = 500) -> str:
    sanitized = _sanitize_git_error_detail(detail).strip()
    if len(sanitized) <= limit:
        return sanitized
    return f"{sanitized[:limit]}...(truncated)"
