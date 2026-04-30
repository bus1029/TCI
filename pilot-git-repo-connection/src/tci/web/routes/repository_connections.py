from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import ValidationError

from tci.api.operator_auth import require_operator_auth
from tci.api.schemas.repository_connection import CreateRepositoryConnectionRequest
from tci.domain.services.create_repository_connection import (
    CreateRepositoryConnectionCommand,
    create_repository_connection,
)
from tci.domain.services.list_repository_candidates import list_repository_candidates
from tci.domain.services.list_repository_connections import list_repository_connections
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)

from ._common import (
    FormBodyTooLarge,
    build_template_context,
    enforce_same_origin,
    extract_workspace_id_from_query,
    parse_simple_form_body,
)


router = APIRouter(
    tags=["RepositoryConnectionsWeb"],
    include_in_schema=False,
    dependencies=[Depends(require_operator_auth)],
)


@router.get("/connections")
def repository_connections_page(request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id

    return _render_index(
        request=request,
        workspace_id=workspace_id,
        form_data=_default_form_data(),
        error_message=None,
        status_code=200,
    )


@router.post("/connections")
async def create_repository_connection_page(request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id
    same_origin_error = enforce_same_origin(request)
    if same_origin_error is not None:
        return same_origin_error

    try:
        form_data = await parse_simple_form_body(request)
    except FormBodyTooLarge:
        return PlainTextResponse("요청 본문이 너무 큽니다.", status_code=413)
    obsolete_error = _obsolete_planning_field_error(form_data)
    if obsolete_error is not None:
        return _render_index(
            request=request,
            workspace_id=workspace_id,
            form_data=_sanitize_form_data(form_data),
            error_message=obsolete_error,
            status_code=400,
        )
    form_data, candidate_error = _apply_selected_candidate_defaults(
        request=request,
        workspace_id=workspace_id,
        form_data=form_data,
    )
    if candidate_error is not None:
        return _render_index(
            request=request,
            workspace_id=workspace_id,
            form_data=_sanitize_form_data(form_data),
            error_message=candidate_error,
            status_code=400,
        )
    try:
        payload = CreateRepositoryConnectionRequest.model_validate(
            {
                "provider": form_data.get("provider"),
                "candidateId": form_data.get("candidateId") or None,
                "remoteUrl": form_data.get("remoteUrl"),
                "transport": form_data.get("transport"),
                "defaultRefType": form_data.get("defaultRefType"),
                "defaultRefName": form_data.get("defaultRefName"),
                "credential": {
                    "type": form_data.get("credentialType"),
                    "secret": form_data.get("credentialSecret"),
                    "fingerprint": form_data.get("credentialFingerprint"),
                },
            }
        )
    except ValidationError as error:
        return _render_index(
            request=request,
            workspace_id=workspace_id,
            form_data=_sanitize_form_data(form_data),
            error_message=error.errors()[0]["msg"],
            status_code=400,
        )

    try:
        connection = create_repository_connection(
            CreateRepositoryConnectionCommand(
                workspace_id=workspace_id,
                provider=payload.provider,
                remote_url=payload.remote_url,
                transport=payload.transport,
                default_ref_type=payload.default_ref_type,
                default_ref_name=payload.default_ref_name,
                credential_type=payload.credential.credential_type,
                credential_secret=payload.credential.secret,
                credential_fingerprint=payload.credential.fingerprint,
                candidate_id=payload.candidate_id,
            ),
            dependencies=request.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        return _render_index(
            request=request,
            workspace_id=workspace_id,
            form_data=_sanitize_form_data(form_data),
            error_message=error.detail,
            status_code=400,
        )

    return RedirectResponse(
        url=f"/connections/{connection.id}?workspaceId={workspace_id}",
        status_code=303,
    )


def _obsolete_planning_field_error(form_data: dict[str, str]) -> str | None:
    obsolete_fields = {
        "planningInputReferenceId",
        "planningInputReference",
        "planningTrace",
        "traceability",
        "approvedSpecPath",
        "approvedPlanPath",
        "specPath",
        "planPath",
    }
    if obsolete_fields.intersection(form_data):
        return "새 저장소 연결 생성 요청은 planning/spec/plan 참조 필드를 받을 수 없습니다."
    return None


def _apply_selected_candidate_defaults(
    *,
    request: Request,
    workspace_id,
    form_data: dict[str, str],
) -> tuple[dict[str, str], str | None]:
    candidate_id = form_data.get("candidateId") or ""
    if not candidate_id:
        return form_data, None

    candidates = list_repository_candidates(
        workspace_id=workspace_id,
        provider=None,
        dependencies=request.app.state.dependencies,
    )
    candidate_items = cast(list[dict[str, Any]], candidates["items"])
    selected_candidate = next(
        (candidate for candidate in candidate_items if candidate["id"] == candidate_id),
        None,
    )
    if selected_candidate is None:
        return form_data, "선택한 후보 저장소를 찾을 수 없습니다."
    if not selected_candidate["selectable"]:
        return form_data, "선택할 수 없는 후보 저장소입니다."
    remote_url = selected_candidate["remoteUrl"]
    if not remote_url:
        return form_data, "후보 저장소 URL을 사용할 수 없어 수동 URL 입력이 필요합니다."

    return {
        **form_data,
        "provider": str(selected_candidate["provider"]),
        "remoteUrl": str(remote_url),
    }, None


def _render_index(
    *,
    request: Request,
    workspace_id,
    form_data: dict[str, str],
    error_message: str | None,
    status_code: int,
):
    connections = list_repository_connections(
        workspace_id=workspace_id,
        dependencies=request.app.state.dependencies,
    )
    candidates = list_repository_candidates(
        workspace_id=workspace_id,
        provider=None,
        dependencies=request.app.state.dependencies,
    )
    template = request.app.state.templates
    return template.TemplateResponse(
        request=request,
        name="connections/index.html",
        context=build_template_context(
            request,
            workspace_id=workspace_id,
            connections=connections,
            candidates=candidates,
            error_message=error_message,
            form_data=form_data,
        ),
        status_code=status_code,
    )


def _default_form_data() -> dict[str, str]:
    return {
        "candidateId": "",
        "provider": "github_cloud",
        "remoteUrl": "",
        "transport": "https",
        "defaultRefType": "branch",
        "defaultRefName": "main",
        "credentialType": "https_pat",
        "credentialSecret": "",
        "credentialFingerprint": "",
    }


def _sanitize_form_data(form_data: dict[str, str]) -> dict[str, str]:
    sanitized = {**_default_form_data(), **form_data}
    sanitized["credentialSecret"] = ""
    if _remote_url_may_contain_secret(sanitized["remoteUrl"]):
        sanitized["remoteUrl"] = ""
    return sanitized


def _remote_url_may_contain_secret(remote_url: str) -> bool:
    try:
        parsed = urlsplit(remote_url)
    except ValueError:
        return True
    return bool(parsed.username or parsed.password or parsed.query or parsed.fragment)
