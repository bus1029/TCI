from __future__ import annotations

from dataclasses import dataclass
import re
from typing import ClassVar

from tci.api.problem_details import ProblemCode
from tci.infrastructure.git.git_ref_resolver import GitCommandRunner


@dataclass(frozen=True, slots=True)
class ReadonlyProbeResult:
    is_read_only: bool
    problem_code: ProblemCode | None
    detail: str


class GitReadonlyValidator:
    auth_failure_tokens: ClassVar[tuple[str, ...]] = (
        "authentication failed",
        "could not read username",
        "permission denied (publickey)",
    )
    read_only_tokens: ClassVar[tuple[str, ...]] = (
        "write access to repository not granted",
        "read-only",
        "does not have write access",
        "permission to ",
        "not allowed to upload code",
        "could not read from remote repository",
    )

    def __init__(self, runner: GitCommandRunner) -> None:
        self._runner = runner

    def probe(self, *, remote_url: str) -> ReadonlyProbeResult:
        # 실제 저장소를 바꾸지 않기 위해 dry-run push 결과를 읽기 전용 판별 신호로만 사용한다.
        result = self._runner(
            (
                "git",
                "push",
                "--dry-run",
                remote_url,
                "HEAD:refs/heads/tci-readonly-probe",
            )
        )
        lowered_error = result.stderr.lower()

        if result.returncode == 0:
            return ReadonlyProbeResult(
                is_read_only=False,
                problem_code=ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED,
                detail=_sanitize_git_error_detail(result.stderr).strip()
                or "쓰기 가능한 자격 증명입니다.",
            )

        if any(token in lowered_error for token in self.auth_failure_tokens):
            return ReadonlyProbeResult(
                is_read_only=False,
                problem_code=ProblemCode.CONNECTION_AUTH_FAILED,
                detail=_sanitize_git_error_detail(result.stderr).strip()
                or "저장소 인증에 실패했습니다.",
            )

        if any(token in lowered_error for token in self.read_only_tokens):
            # 이 판별은 사전에 ls-remote 같은 읽기 검증이 끝났다는 전제를 둔다.
            # 그 뒤 push만 거부되면 읽기 전용 자격 증명으로 간주하는 것이 운영 의도에 맞다.
            return ReadonlyProbeResult(
                is_read_only=True,
                problem_code=None,
                detail=_sanitize_git_error_detail(result.stderr).strip()
                or "읽기 전용 자격 증명입니다.",
            )

        return ReadonlyProbeResult(
            is_read_only=False,
            problem_code=None,
            detail=_sanitize_git_error_detail(result.stderr).strip()
            or "자격 증명 상태를 확인할 수 없습니다.",
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
