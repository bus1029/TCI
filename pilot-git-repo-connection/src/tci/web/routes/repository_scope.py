from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import ValidationError

from tci.api.schemas.repository_connection import serialize_repository_connection_detail
from tci.api.schemas.repository_scope import SaveScopeRulesRequest
from tci.domain.services.get_repository_connection_detail import (
    get_repository_connection_detail,
)
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.domain.services.save_scope_rules import SaveScopeRulesCommand, save_scope_rules

from ._common import (
    build_template_context,
    enforce_same_origin,
    extract_workspace_id_from_query,
    parse_simple_form_body,
)


router = APIRouter(tags=["RepositoryScopeWeb"], include_in_schema=False)


@router.get("/connections/{connection_id}/scope")
def repository_scope_page(connection_id: uuid.UUID, request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id

    try:
        connection = get_repository_connection_detail(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return PlainTextResponse("저장소 연결을 찾을 수 없습니다.", status_code=404)

    serialized_connection = serialize_repository_connection_detail(connection)
    return _render_scope_page(
        request=request,
        workspace_id=workspace_id,
        connection=serialized_connection,
        form_data=_build_scope_form_data(serialized_connection),
        error_message=None,
        status_code=200,
    )


@router.post("/connections/{connection_id}/scope")
async def save_repository_scope_page(connection_id: uuid.UUID, request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id
    same_origin_error = enforce_same_origin(request)
    if same_origin_error is not None:
        return same_origin_error

    form_data = await parse_simple_form_body(request)
    try:
        payload = SaveScopeRulesRequest.model_validate(
            {
                "includePaths": _split_list_field(form_data.get("includePaths", "")),
                "excludePaths": _split_list_field(form_data.get("excludePaths", "")),
                "allowedFileTypes": _split_list_field(
                    form_data.get("allowedFileTypes", "")
                ),
                "blockedFileTypes": _split_list_field(
                    form_data.get("blockedFileTypes", "")
                ),
                "maxFileSizeBytes": form_data.get("maxFileSizeBytes", 5 * 1024 * 1024),
            }
        )
    except ValidationError as error:
        return _render_scope_error(
            request=request,
            workspace_id=workspace_id,
            connection_id=connection_id,
            form_data=form_data,
            error_message=error.errors()[0]["msg"],
            status_code=400,
        )

    try:
        save_scope_rules(
            SaveScopeRulesCommand(
                workspace_id=workspace_id,
                connection_id=connection_id,
                include_paths=tuple(payload.include_paths),
                exclude_paths=tuple(payload.exclude_paths),
                allowed_file_types=tuple(payload.allowed_file_types),
                blocked_file_types=tuple(payload.blocked_file_types),
                max_file_size_bytes=payload.max_file_size_bytes,
            ),
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return PlainTextResponse("저장소 연결을 찾을 수 없습니다.", status_code=404)
    except RepositoryConnectionProblem as error:
        return _render_scope_error(
            request=request,
            workspace_id=workspace_id,
            connection_id=connection_id,
            form_data=form_data,
            error_message=error.detail,
            status_code=400,
        )

    return RedirectResponse(
        url=f"/connections/{connection_id}/scope?workspaceId={workspace_id}",
        status_code=303,
    )


def _render_scope_page(
    *,
    request: Request,
    workspace_id,
    connection: dict[str, object],
    form_data: dict[str, str],
    error_message: str | None,
    status_code: int,
):
    template = request.app.state.templates
    return template.TemplateResponse(
        request=request,
        name="connections/scope.html",
        context=build_template_context(
            request,
            workspace_id=workspace_id,
            connection=connection,
            form_data=form_data,
            error_message=error_message,
        ),
        status_code=status_code,
    )


def _build_scope_form_data(connection) -> dict[str, str]:
    latest_scope_rule = connection.get("latestScopeRule") or {}
    return {
        "includePaths": ", ".join(latest_scope_rule.get("includePaths", [])),
        "excludePaths": ", ".join(latest_scope_rule.get("excludePaths", [])),
        "allowedFileTypes": ", ".join(latest_scope_rule.get("allowedFileTypes", [])),
        "blockedFileTypes": ", ".join(latest_scope_rule.get("blockedFileTypes", [])),
        "maxFileSizeBytes": str(latest_scope_rule.get("maxFileSizeBytes", 5 * 1024 * 1024)),
    }


def _split_list_field(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _render_scope_error(
    *,
    request: Request,
    workspace_id,
    connection_id: uuid.UUID,
    form_data: dict[str, str],
    error_message: str,
    status_code: int,
):
    try:
        connection = get_repository_connection_detail(
            workspace_id=workspace_id,
            connection_id=connection_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return PlainTextResponse("저장소 연결을 찾을 수 없습니다.", status_code=404)

    return _render_scope_page(
        request=request,
        workspace_id=workspace_id,
        connection=serialize_repository_connection_detail(connection),
        form_data={
            "includePaths": form_data.get("includePaths", ""),
            "excludePaths": form_data.get("excludePaths", ""),
            "allowedFileTypes": form_data.get("allowedFileTypes", ""),
            "blockedFileTypes": form_data.get("blockedFileTypes", ""),
            "maxFileSizeBytes": form_data.get("maxFileSizeBytes", str(5 * 1024 * 1024)),
        },
        error_message=error_message,
        status_code=status_code,
    )
