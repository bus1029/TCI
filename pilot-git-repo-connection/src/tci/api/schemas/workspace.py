from __future__ import annotations

from pydantic import BaseModel, Field


class DeleteWorkspaceRequest(BaseModel):
    confirmation: str
    reason: str | None = Field(default=None, max_length=500)


def serialize_workspace_deletion_impact(impact) -> dict[str, object]:
    return {
        "workspaceId": str(impact.workspace_id),
        "repositoryConnectionCount": impact.repository_connection_count,
        "localUploadCount": impact.local_upload_count,
        "snapshotCount": impact.snapshot_count,
        "projectContentWillBeRemoved": impact.project_content_will_be_removed,
        "auditMetadataWillRemain": impact.audit_metadata_will_remain,
        "confirmation": impact.confirmation,
    }


def serialize_workspace_deletion_response(result) -> dict[str, object]:
    return {
        "workspaceId": str(result.workspace_id),
        "status": result.status,
        "deletionRecordId": (
            None
            if result.deletion_record_id is None
            else str(result.deletion_record_id)
        ),
        "auditMetadataRetained": result.audit_metadata_retained,
        "projectContentRemoved": result.project_content_removed,
        "message": result.message,
    }
