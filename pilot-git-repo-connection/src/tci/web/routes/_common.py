from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs
import uuid

from fastapi import Request
from fastapi.responses import PlainTextResponse


def extract_workspace_id_from_query(request: Request) -> uuid.UUID | PlainTextResponse:
    raw_workspace_id = request.query_params.get("workspaceId")
    if not raw_workspace_id:
        return PlainTextResponse(
            "workspaceId 쿼리 파라미터가 필요합니다.",
            status_code=400,
        )

    try:
        return uuid.UUID(raw_workspace_id)
    except ValueError:
        return PlainTextResponse(
            "workspaceId는 UUID 형식이어야 합니다.",
            status_code=400,
        )


def enforce_same_origin(request: Request) -> PlainTextResponse | None:
    base_origin = str(request.base_url).rstrip("/")
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    # 브라우저 관리 화면은 세션 보호가 붙기 전이라도 최소한의 동일 출처 검사로 교차 사이트 제출을 줄인다.
    if origin and origin.rstrip("/") != base_origin:
        return PlainTextResponse("허용되지 않은 요청 출처입니다.", status_code=403)
    if not origin and referer and not referer.startswith(f"{base_origin}/"):
        return PlainTextResponse("허용되지 않은 요청 출처입니다.", status_code=403)
    return None


async def parse_simple_form_body(request: Request) -> dict[str, str]:
    # 운영 화면은 단순한 기본 폼만 다루므로 multipart 의존성 없이 urlencoded body만 파싱한다.
    raw_body = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw_body, keep_blank_values=True)
    return {key: values[0] if values else "" for key, values in parsed.items()}


def build_template_context(
    request: Request, *, workspace_id: uuid.UUID, **extra: Any
) -> dict[str, Any]:
    return {
        "request": request,
        "workspace_id": str(workspace_id),
        **extra,
    }
