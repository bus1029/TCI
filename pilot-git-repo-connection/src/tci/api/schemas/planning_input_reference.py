from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import Field

from tci.api.schemas._base import CamelModel


class CreatePlanningInputReferenceRequest(CamelModel):
    workspace_id: uuid.UUID = Field(alias="workspaceId")
    source_type: str = Field(alias="sourceType", min_length=1, max_length=64)
    source_title: str = Field(alias="sourceTitle", min_length=1, max_length=255)
    source_reference: str = Field(alias="sourceReference", min_length=1, max_length=1024)
    approved_spec_path: str = Field(alias="approvedSpecPath", min_length=1, max_length=1024)
    approved_plan_path: str = Field(alias="approvedPlanPath", min_length=1, max_length=1024)


class PlanningInputReferenceResponse(CamelModel):
    id: uuid.UUID
    workspace_id: uuid.UUID = Field(alias="workspaceId")
    source_type: str = Field(alias="sourceType")
    source_title: str = Field(alias="sourceTitle")
    source_reference: str = Field(alias="sourceReference")
    approved_spec_path: str = Field(alias="approvedSpecPath")
    approved_plan_path: str = Field(alias="approvedPlanPath")
    created_at: datetime = Field(alias="createdAt")


def serialize_planning_input_reference(reference) -> dict[str, str]:
    return {
        "id": str(reference.id),
        "workspaceId": str(reference.workspace_id),
        "sourceType": reference.source_type.value,
        "sourceTitle": reference.source_title,
        "sourceReference": reference.source_reference,
        "approvedSpecPath": reference.approved_spec_path,
        "approvedPlanPath": reference.approved_plan_path,
        "createdAt": _format_datetime(reference.created_at),
    }


def _format_datetime(value: datetime) -> str:
    return value.isoformat()
