from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProblemCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_PROVIDER = "UNSUPPORTED_PROVIDER"
    READ_WRITE_CREDENTIAL_NOT_ALLOWED = "READ_WRITE_CREDENTIAL_NOT_ALLOWED"
    CONNECTION_AUTH_FAILED = "CONNECTION_AUTH_FAILED"
    DEFAULT_REF_NOT_FOUND = "DEFAULT_REF_NOT_FOUND"
    NO_INCLUDED_FILES = "NO_INCLUDED_FILES"
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"
    WEBHOOK_SECRET_MISSING = "WEBHOOK_SECRET_MISSING"
    WEBHOOK_SECRET_MISMATCH = "WEBHOOK_SECRET_MISMATCH"
    STALE_HEAD_SHA_SKIPPED = "STALE_HEAD_SHA_SKIPPED"


@dataclass(frozen=True, slots=True)
class ProblemDetailDefinition:
    code: ProblemCode
    status_code: int
    message: str


_PROBLEM_DETAILS = {
    ProblemCode.INVALID_INPUT: ProblemDetailDefinition(
        code=ProblemCode.INVALID_INPUT,
        status_code=400,
        message="입력값이 계약 조건을 만족하지 않습니다.",
    ),
    ProblemCode.UNSUPPORTED_PROVIDER: ProblemDetailDefinition(
        code=ProblemCode.UNSUPPORTED_PROVIDER,
        status_code=400,
        message="v1에서는 GitHub Cloud 저장소만 지원합니다.",
    ),
    ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED: ProblemDetailDefinition(
        code=ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED,
        status_code=400,
        message="읽기 전용이 아닌 저장소 자격 증명은 허용되지 않습니다.",
    ),
    ProblemCode.CONNECTION_AUTH_FAILED: ProblemDetailDefinition(
        code=ProblemCode.CONNECTION_AUTH_FAILED,
        status_code=400,
        message="저장소 자격 증명 검증에 실패했습니다.",
    ),
    ProblemCode.DEFAULT_REF_NOT_FOUND: ProblemDetailDefinition(
        code=ProblemCode.DEFAULT_REF_NOT_FOUND,
        status_code=400,
        message="기본 분석 대상 ref를 찾을 수 없습니다.",
    ),
    ProblemCode.NO_INCLUDED_FILES: ProblemDetailDefinition(
        code=ProblemCode.NO_INCLUDED_FILES,
        status_code=409,
        message="범위 규칙을 적용한 결과 수집 대상 파일이 없습니다.",
    ),
    ProblemCode.WEBHOOK_SIGNATURE_INVALID: ProblemDetailDefinition(
        code=ProblemCode.WEBHOOK_SIGNATURE_INVALID,
        status_code=401,
        message="webhook 서명 검증에 실패했습니다.",
    ),
    ProblemCode.WEBHOOK_SECRET_MISSING: ProblemDetailDefinition(
        code=ProblemCode.WEBHOOK_SECRET_MISSING,
        status_code=404,
        message="webhook secret이 아직 등록되지 않았습니다.",
    ),
    ProblemCode.WEBHOOK_SECRET_MISMATCH: ProblemDetailDefinition(
        code=ProblemCode.WEBHOOK_SECRET_MISMATCH,
        status_code=401,
        message="등록된 webhook secret과 요청 서명이 일치하지 않습니다.",
    ),
    ProblemCode.STALE_HEAD_SHA_SKIPPED: ProblemDetailDefinition(
        code=ProblemCode.STALE_HEAD_SHA_SKIPPED,
        status_code=409,
        message="최신 HEAD가 아닌 이벤트는 스냅샷 갱신 대상에서 제외됩니다.",
    ),
}


def problem_details_for(code: ProblemCode) -> ProblemDetailDefinition:
    return _PROBLEM_DETAILS[code]
