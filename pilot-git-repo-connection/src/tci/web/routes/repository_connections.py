from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import ValidationError

from tci.api.schemas.repository_connection import CreateRepositoryConnectionRequest
from tci.domain.services.create_repository_connection import (
    CreateRepositoryConnectionCommand,
    create_repository_connection,
)
from tci.domain.services.list_repository_connections import list_repository_connections
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem

from ._common import (
    build_template_context,
    enforce_same_origin,
    extract_workspace_id_from_query,
    parse_simple_form_body,
)


router = APIRouter(tags=["RepositoryConnectionsWeb"], include_in_schema=False)


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

    form_data = await parse_simple_form_body(request)
    try:
        payload = CreateRepositoryConnectionRequest.model_validate(
            {
                "planningInputReferenceId": form_data.get("planningInputReferenceId"),
                "provider": form_data.get("provider"),
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
                planning_input_reference_id=payload.planning_input_reference_id,
                provider=payload.provider,
                remote_url=payload.remote_url,
                transport=payload.transport,
                default_ref_type=payload.default_ref_type,
                default_ref_name=payload.default_ref_name,
                credential_type=payload.credential.credential_type,
                credential_secret=payload.credential.secret,
                credential_fingerprint=payload.credential.fingerprint,
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
    template = request.app.state.templates
    return template.TemplateResponse(
        request=request,
        name="connections/index.html",
        context=build_template_context(
            request,
            workspace_id=workspace_id,
            connections=connections,
            error_message=error_message,
            form_data=form_data,
        ),
        status_code=status_code,
    )


def _default_form_data() -> dict[str, str]:
    return {
        "provider": "github_cloud",
        "remoteUrl": "",
        "transport": "https",
        "defaultRefType": "branch",
        "defaultRefName": "main",
        "credentialType": "https_pat",
        "credentialSecret": "",
        "credentialFingerprint": "",
        "planningInputReferenceId": "",
    }


def _sanitize_form_data(form_data: dict[str, str]) -> dict[str, str]:
    sanitized = {**_default_form_data(), **form_data}
    sanitized["credentialSecret"] = ""
    return sanitized
