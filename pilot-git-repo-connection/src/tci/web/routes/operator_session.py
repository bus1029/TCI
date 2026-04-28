from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from tci.api.operator_auth import (
    OPERATOR_SESSION_COOKIE_MAX_AGE_SECONDS,
    OPERATOR_SESSION_COOKIE_NAME,
    consume_operator_auth_failure_budget,
    create_operator_session_cookie,
    is_valid_operator_token,
)


router = APIRouter(tags=["OperatorSessionWeb"], include_in_schema=False)
MAX_OPERATOR_SESSION_BODY_BYTES = 8 * 1024


@router.post("/operator/session")
async def operator_session_page(request: Request):
    expected_token = getattr(request.app.state.settings, "operator_api_token", None)
    if expected_token is None:
        return PlainTextResponse(
            "운영 API 토큰이 설정되지 않았습니다.",
            status_code=503,
        )
    if _is_oversized_content_length(request.headers.get("content-length")):
        return PlainTextResponse("요청 본문이 너무 큽니다.", status_code=413)
    try:
        form = _parse_urlencoded_form(await _read_limited_body(request))
    except UnicodeDecodeError:
        return PlainTextResponse("요청 본문 형식이 올바르지 않습니다.", status_code=400)
    except ValueError:
        return PlainTextResponse("요청 본문이 너무 큽니다.", status_code=413)
    token = form.get("operatorToken")
    if is_valid_operator_token(
        expected_token=expected_token,
        supplied_token=token,
    ):
        redirect_to = _safe_redirect_path(form.get("next"))
        response = RedirectResponse(url=redirect_to, status_code=303)
        response.set_cookie(
            OPERATOR_SESSION_COOKIE_NAME,
            create_operator_session_cookie(expected_token=expected_token),
            httponly=True,
            max_age=OPERATOR_SESSION_COOKIE_MAX_AGE_SECONDS,
            secure=_should_secure_cookie(request),
            samesite="lax",
        )
        return response

    if not consume_operator_auth_failure_budget(request):
        return PlainTextResponse("운영 API 토큰 시도가 너무 많습니다.", status_code=429)
    return PlainTextResponse("운영 API 토큰이 필요합니다.", status_code=401)


def _is_oversized_content_length(content_length: str | None) -> bool:
    if content_length is None:
        return False
    try:
        return int(content_length) > MAX_OPERATOR_SESSION_BODY_BYTES
    except ValueError:
        return False


def _parse_urlencoded_form(raw_body: bytes) -> dict[str, str]:
    parsed = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    return {
        key: values[0]
        for key, values in parsed.items()
        if values and isinstance(values[0], str)
    }


async def _read_limited_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_OPERATOR_SESSION_BODY_BYTES:
            raise ValueError("operator session body is too large")
        body.extend(chunk)
    return bytes(body)


def _safe_redirect_path(raw_next: str | None) -> str:
    if not raw_next:
        return "/connections"
    parsed = urlsplit(raw_next)
    if parsed.scheme or parsed.netloc or not raw_next.startswith("/"):
        return "/connections"
    return raw_next


def _should_secure_cookie(request: Request) -> bool:
    settings = request.app.state.settings
    if getattr(settings, "environment", "development") != "development":
        return True
    if request.url.scheme == "https":
        return True
    direct_host = "unknown" if request.client is None else request.client.host
    trusted_proxy_hosts = getattr(settings, "gitlab_webhook_trusted_proxy_hosts", ())
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    return direct_host in trusted_proxy_hosts and forwarded_proto.lower() == "https"
