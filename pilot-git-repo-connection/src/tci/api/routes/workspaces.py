from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from tci.api.operator_auth import operator_principal_from_request, require_operator_auth
from tci.api.routes.local_uploads import _reject_cookie_cross_origin
from tci.api.schemas.workspace import (
    DeleteWorkspaceRequest,
    serialize_workspace_deletion_impact,
    serialize_workspace_deletion_response,
)
from tci.domain.services.delete_workspace import (
    DeleteWorkspaceCommand,
    WorkspaceDeleteProblem,
    delete_workspace,
    get_workspace_deletion_impact,
)


router = APIRouter(
    prefix="/api/workspaces",
    tags=["Workspaces"],
    dependencies=[Depends(require_operator_auth)],
)


@router.get("/{workspace_id}/deletion-impact")
def get_workspace_deletion_impact_route(
    workspace_id: uuid.UUID,
    request: Request,
):
    principal = operator_principal_from_request(request)
    try:
        impact = get_workspace_deletion_impact(
            workspace_id=workspace_id,
            operator_role=principal.role,
            dependencies=request.app.state.dependencies,
        )
    except WorkspaceDeleteProblem as error:
        return _workspace_delete_problem_response(error)
    return serialize_workspace_deletion_impact(impact)


@router.delete("/{workspace_id}")
def delete_workspace_route(
    workspace_id: uuid.UUID,
    payload: DeleteWorkspaceRequest,
    request: Request,
):
    same_origin_error = _reject_cookie_cross_origin(request)
    if same_origin_error is not None:
        return same_origin_error
    principal = operator_principal_from_request(request)
    try:
        result = delete_workspace(
            DeleteWorkspaceCommand(
                workspace_id=workspace_id,
                confirmation=payload.confirmation,
                deleted_by=principal.operator_id,
                operator_role=principal.role,
                reason=payload.reason,
            ),
            dependencies=request.app.state.dependencies,
        )
    except WorkspaceDeleteProblem as error:
        return _workspace_delete_problem_response(error)
    return JSONResponse(
        status_code=result.status_code,
        content=serialize_workspace_deletion_response(result),
    )


def _workspace_delete_problem_response(error: WorkspaceDeleteProblem) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "code": error.code,
            "message": error.message,
            "remediationAction": error.remediation_action,
        },
    )
