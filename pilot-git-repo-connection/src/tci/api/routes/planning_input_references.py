from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from tci.api.problem_details import ProblemCode, problem_details_for
from tci.api.schemas.planning_input_reference import (
    CreatePlanningInputReferenceRequest,
    PlanningInputReferenceResponse,
    serialize_planning_input_reference,
)
from tci.domain.services.create_planning_input_reference import (
    CreatePlanningInputReferenceCommand,
    create_planning_input_reference,
)
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem


router = APIRouter(prefix="/api/planning-input-references", tags=["PlanningInputReferences"])


@router.post(
    "",
    status_code=201,
    response_model=PlanningInputReferenceResponse,
    openapi_extra={
        "parameters": [
            {
                "name": "X-TCI-Workspace-Id",
                "in": "header",
                "required": True,
                "schema": {
                    "type": "string",
                    "title": "X-Tci-Workspace-Id",
                    "description": "워크스페이스 UUID",
                },
                "description": "워크스페이스 UUID",
            }
        ]
    },
)
def create_planning_input_reference_route(
    payload: CreatePlanningInputReferenceRequest,
    request: Request,
    workspace_header: str | None = Header(
        default=None,
        alias="X-TCI-Workspace-Id",
        description="워크스페이스 UUID",
        include_in_schema=False,
    ),
):
    parsed_workspace_id = _extract_workspace_id(workspace_header)
    if isinstance(parsed_workspace_id, JSONResponse):
        return parsed_workspace_id
    if parsed_workspace_id != payload.workspace_id:
        return JSONResponse(
            status_code=400,
            content={
                "code": ProblemCode.INVALID_INPUT.value,
                "message": "workspaceId 본문 값과 X-TCI-Workspace-Id 헤더가 일치해야 합니다.",
            },
        )
    try:
        reference = create_planning_input_reference(
            CreatePlanningInputReferenceCommand(
                workspace_id=parsed_workspace_id,
                source_type=payload.source_type,
                source_title=payload.source_title,
                source_reference=payload.source_reference,
                approved_spec_path=payload.approved_spec_path,
                approved_plan_path=payload.approved_plan_path,
            ),
            dependencies=request.app.state.dependencies,
        )
    except RepositoryConnectionProblem as error:
        return _problem_response(error)
    except RuntimeError:
        return _service_unavailable_response()
    except OperationalError:
        return _service_unavailable_response()

    return serialize_planning_input_reference(reference)


def _problem_response(error: RepositoryConnectionProblem) -> JSONResponse:
    definition = problem_details_for(error.problem_code)
    return JSONResponse(
        status_code=definition.status_code,
        content={
            "code": error.problem_code.value,
            "message": error.detail or definition.message,
        },
    )


def _service_unavailable_response() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "planning input reference를 생성하려면 데이터베이스를 사용할 수 있어야 합니다."
        },
    )


def _extract_workspace_id(
    raw_workspace_id: str | None,
) -> uuid.UUID | JSONResponse:
    if not raw_workspace_id:
        return JSONResponse(
            status_code=400,
            content={
                "code": ProblemCode.INVALID_INPUT.value,
                "message": "X-TCI-Workspace-Id 헤더가 필요합니다.",
            },
        )
    try:
        return uuid.UUID(raw_workspace_id)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={
                "code": ProblemCode.INVALID_INPUT.value,
                "message": "X-TCI-Workspace-Id는 UUID 형식이어야 합니다.",
            },
        )
