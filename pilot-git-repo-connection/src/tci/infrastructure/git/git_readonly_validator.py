from __future__ import annotations

from dataclasses import dataclass

from tci.api.problem_details import ProblemCode
from tci.infrastructure.git.git_ref_resolver import GitCommandRunner


@dataclass(frozen=True, slots=True)
class ReadonlyProbeResult:
    is_read_only: bool
    problem_code: ProblemCode | None
    detail: str


class GitReadonlyValidator:
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
                detail=result.stderr.strip() or "쓰기 가능한 자격 증명입니다.",
            )

        if any(
            token in lowered_error
            for token in (
                "authentication failed",
                "could not read username",
                "permission denied (publickey)",
            )
        ):
            return ReadonlyProbeResult(
                is_read_only=False,
                problem_code=ProblemCode.CONNECTION_AUTH_FAILED,
                detail=result.stderr.strip() or "저장소 인증에 실패했습니다.",
            )

        if any(
            token in lowered_error
            for token in (
                "write access to repository not granted",
                "read-only",
                "does not have write access",
                "permission to ",
                "could not read from remote repository",
            )
        ):
            # 이 판별은 사전에 ls-remote 같은 읽기 검증이 끝났다는 전제를 둔다.
            # 그 뒤 push만 거부되면 읽기 전용 자격 증명으로 간주하는 것이 운영 의도에 맞다.
            return ReadonlyProbeResult(
                is_read_only=True,
                problem_code=None,
                detail=result.stderr.strip() or "읽기 전용 자격 증명입니다.",
            )

        return ReadonlyProbeResult(
            is_read_only=False,
            problem_code=None,
            detail=result.stderr.strip() or "자격 증명 상태를 확인할 수 없습니다.",
        )
