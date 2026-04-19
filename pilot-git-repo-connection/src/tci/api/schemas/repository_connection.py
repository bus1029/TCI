from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class CredentialInput(CamelModel):
    credential_type: str = Field(alias="type")
    secret: str = Field(min_length=1, max_length=16384)
    fingerprint: str | None = Field(default=None, max_length=255)


class CreateRepositoryConnectionRequest(CamelModel):
    planning_input_reference_id: uuid.UUID = Field(alias="planningInputReferenceId")
    provider: str = Field(min_length=1, max_length=64)
    remote_url: str = Field(alias="remoteUrl", min_length=1, max_length=2048)
    transport: str = Field(min_length=1, max_length=32)
    default_ref_type: str = Field(alias="defaultRefType", min_length=1, max_length=32)
    default_ref_name: str = Field(alias="defaultRefName", min_length=1, max_length=255)
    credential: CredentialInput


class UpdateRepositoryConnectionRequest(CamelModel):
    default_ref_type: str | None = Field(
        default=None,
        alias="defaultRefType",
        min_length=1,
        max_length=32,
    )
    default_ref_name: str | None = Field(
        default=None,
        alias="defaultRefName",
        min_length=1,
        max_length=255,
    )


def serialize_repository_connection(connection) -> dict[str, object]:
    return {
        "id": str(connection.id),
        "provider": connection.provider.value,
        "remoteUrl": connection.remote_url,
        "transport": connection.transport.value,
        "defaultRefType": connection.default_ref_type.value,
        "defaultRefName": connection.default_ref_name,
        "status": connection.status.value,
        "lastVerifiedAt": _format_datetime(connection.last_verified_at),
    }


def serialize_repository_connection_detail(connection) -> dict[str, object]:
    payload = serialize_repository_connection(connection)
    planning_input_reference = connection.planning_input_reference
    payload.update(
        {
            "lastSuccessfulSnapshotAt": _format_datetime(
                connection.last_successful_snapshot_at
            ),
            "lastFailedSyncAt": _format_datetime(connection.last_failed_sync_at),
            "lastProcessedEventAt": None,
            "lastProcessedEvent": None,
            "latestSnapshot": None,
            "traceability": {
                "planningInputReference": {
                    "id": str(planning_input_reference.id),
                    "sourceType": planning_input_reference.source_type.value,
                    "sourceReference": planning_input_reference.source_reference,
                    "approvedSpecPath": planning_input_reference.approved_spec_path,
                    "approvedPlanPath": planning_input_reference.approved_plan_path,
                },
                "activeScopeRuleVersionId": _format_uuid(
                    connection.active_scope_rule_version_id
                ),
                "latestEventId": None,
                "latestSnapshotId": None,
            },
            "additionalRefGuidance": {
                "message": "이 연결은 기본 ref 1개만 지원합니다.",
                "options": [
                    {
                        "action": "create_new_connection",
                        "label": "새 연결 생성",
                    },
                    {
                        "action": "replace_default_ref",
                        "label": "기본 ref 교체",
                    },
                ],
            },
        }
    )
    return payload


def serialize_verification_accepted(*, connection_id: uuid.UUID) -> dict[str, str]:
    return {
        "status": "verification_queued",
        "connectionId": str(connection_id),
    }


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _format_uuid(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    return str(value)
