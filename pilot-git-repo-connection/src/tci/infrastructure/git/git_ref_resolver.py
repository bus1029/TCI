from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tci.api.problem_details import ProblemCode
from tci.infrastructure.persistence.models import DefaultRefType


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
        ref_type: DefaultRefType,
        ref_name: str,
    ) -> ResolvedGitRef:
        refspecs = _build_refspecs(ref_type=ref_type, ref_name=ref_name)
        result = self._runner(("git", "ls-remote", remote_url, *refspecs))

        if result.returncode != 0:
            if _looks_like_auth_failure(result.stderr):
                raise GitConnectionAuthError()
            raise RuntimeError(result.stderr.strip() or "git ls-remote 실행에 실패했습니다.")

        sha_by_ref: dict[str, str] = {}
        for line in result.stdout.splitlines():
            sha, _, resolved_ref = line.partition("\t")
            if sha and resolved_ref:
                sha_by_ref[resolved_ref] = sha

        commit_sha = _select_commit_sha(
            ref_type=ref_type,
            ref_name=ref_name,
            sha_by_ref=sha_by_ref,
        )
        if commit_sha is not None:
            return ResolvedGitRef(
                ref_type=ref_type,
                ref_name=ref_name,
                commit_sha=commit_sha,
            )

        raise GitRefNotFoundError(ref_name)


def _build_refspecs(*, ref_type: DefaultRefType, ref_name: str) -> tuple[str, ...]:
    if ref_type is DefaultRefType.BRANCH:
        return (f"refs/heads/{ref_name}",)
    tag_ref = f"refs/tags/{ref_name}"
    return (tag_ref, f"{tag_ref}^{{}}")


def _select_commit_sha(
    *,
    ref_type: DefaultRefType,
    ref_name: str,
    sha_by_ref: dict[str, str],
) -> str | None:
    if ref_type is DefaultRefType.BRANCH:
        return sha_by_ref.get(f"refs/heads/{ref_name}")

    tag_ref = f"refs/tags/{ref_name}"
    return sha_by_ref.get(f"{tag_ref}^{{}}") or sha_by_ref.get(tag_ref)


def _looks_like_auth_failure(stderr: str) -> bool:
    lowered = stderr.lower()
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
