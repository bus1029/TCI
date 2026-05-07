from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from tci.api.operator_auth import operator_principal_from_request, require_operator_auth
from tci.domain.services.delete_workspace import (
    DeleteWorkspaceCommand,
    WorkspaceDeleteProblem,
    delete_workspace,
    get_deleted_workspace_status,
    get_workspace_deletion_impact,
)

from ._common import build_template_context, enforce_same_origin
from ._common import FormBodyTooLarge, parse_simple_form_body


router = APIRouter(
    tags=["WorkspacesWeb"],
    include_in_schema=False,
    dependencies=[Depends(require_operator_auth)],
)


@router.get("/workspaces/{workspace_id}/delete")
def workspace_delete_page(workspace_id: uuid.UUID, request: Request):
    principal = operator_principal_from_request(request)
    try:
        impact = get_workspace_deletion_impact(
            workspace_id=workspace_id,
            operator_role=principal.role,
            dependencies=request.app.state.dependencies,
        )
    except WorkspaceDeleteProblem as error:
        return PlainTextResponse(error.message, status_code=error.status_code)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="workspaces/delete.html",
        context=build_template_context(
            request, workspace_id=workspace_id, impact=impact
        ),
    )


@router.post("/workspaces/{workspace_id}/delete")
async def delete_workspace_page(
    workspace_id: uuid.UUID,
    request: Request,
):
    same_origin_error = enforce_same_origin(request)
    if same_origin_error is not None:
        return same_origin_error
    try:
        form = await parse_simple_form_body(request)
    except FormBodyTooLarge:
        return PlainTextResponse("요청 본문이 너무 큽니다.", status_code=413)
    principal = operator_principal_from_request(request)
    try:
        await run_in_threadpool(
            lambda: delete_workspace(
                DeleteWorkspaceCommand(
                    workspace_id=workspace_id,
                    confirmation=form.get("confirmation", ""),
                    deleted_by=principal.operator_id,
                    operator_role=principal.role,
                    reason=form.get("reason"),
                ),
                dependencies=request.app.state.dependencies,
            ),
        )
    except WorkspaceDeleteProblem as error:
        return PlainTextResponse(error.message, status_code=error.status_code)
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/deleted",
        status_code=303,
    )


@router.get("/workspaces/{workspace_id}/deleted")
def deleted_workspace_page(workspace_id: uuid.UUID, request: Request):
    try:
        get_deleted_workspace_status(
            workspace_id=workspace_id,
            dependencies=request.app.state.dependencies,
        )
    except WorkspaceDeleteProblem as error:
        return PlainTextResponse(error.message, status_code=error.status_code)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="workspaces/deleted.html",
        context=build_template_context(request, workspace_id=workspace_id),
    )
