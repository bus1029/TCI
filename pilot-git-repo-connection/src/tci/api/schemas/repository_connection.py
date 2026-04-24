from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import Field

from tci.api.schemas._base import CamelModel
from tci.api.schemas.repository_scope import serialize_scope_rule


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


class CreateRepositorySnapshotRequest(CamelModel):
    reason: str = Field(default="manual_initial", min_length=1)


def serialize_repository_connection(connection) -> dict[str, object]:
    payload = {
        "id": str(connection.id),
        "provider": connection.provider.value,
        "remoteUrl": connection.remote_url,
        "transport": connection.transport.value,
        "defaultRefType": connection.default_ref_type.value,
        "defaultRefName": connection.default_ref_name,
        "status": connection.status.value,
        "lastVerifiedAt": _format_datetime(connection.last_verified_at),
    }
    if connection.provider.value == "gitlab_self_managed":
        payload.update(
            {
                "providerInstanceUrl": connection.provider_instance_url,
                "providerProjectPath": connection.provider_project_path,
            }
        )
    return payload


def serialize_repository_connection_detail(connection) -> dict[str, object]:
    payload = serialize_repository_connection(connection)
    planning_input_reference = connection.planning_input_reference
    latest_snapshot = getattr(connection, "latest_snapshot", None)
    latest_sync_run = getattr(connection, "latest_sync_run", None)
    latest_scope_rule = getattr(connection, "latest_scope_rule", None)
    last_processed_event = getattr(connection, "last_processed_event", None)
    if latest_scope_rule is None:
        latest_scope_rule = getattr(connection, "active_scope_rule_version", None)
    payload.update(
        {
            "latestScopeRule": (
                None
                if latest_scope_rule is None
                else serialize_scope_rule(latest_scope_rule)
            ),
            "lastSuccessfulSnapshotAt": _format_datetime(
                connection.last_successful_snapshot_at
            ),
            "lastFailedSyncAt": _format_datetime(connection.last_failed_sync_at),
            "lastProcessedEventAt": _format_datetime(
                connection.last_processed_event_at
            ),
            "lastProcessedEvent": _serialize_last_processed_event(last_processed_event),
            "latestSnapshot": _serialize_latest_snapshot_summary(latest_snapshot),
            "latestSyncRun": _serialize_latest_sync_run_summary(latest_sync_run),
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
                "latestEventId": _format_uuid(
                    getattr(connection, "last_processed_event_id", None)
                    if last_processed_event is None
                    else last_processed_event.id
                ),
                "latestSnapshotId": _format_uuid(
                    None if latest_snapshot is None else latest_snapshot.id
                ),
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
    webhook_health = _serialize_webhook_health(connection)
    if webhook_health is not None:
        payload["webhookHealth"] = webhook_health
    return payload


def serialize_verification_accepted(*, connection_id: uuid.UUID) -> dict[str, str]:
    return {
        "status": "verification_queued",
        "connectionId": str(connection_id),
    }


def serialize_sync_run_accepted(*, sync_run_id: uuid.UUID) -> dict[str, str]:
    return {
        "status": "sync_queued",
        "syncRunId": str(sync_run_id),
    }


def serialize_webhook_secret_issued(
    *,
    connection_id: uuid.UUID,
    webhook_secret: str,
    webhook_secret_revision_id: uuid.UUID,
    grace_until: datetime | None,
) -> dict[str, str | None]:
    return {
        "status": "secret_issued",
        "connectionId": str(connection_id),
        "webhookSecret": webhook_secret,
        "webhookSecretRevisionId": str(webhook_secret_revision_id),
        "graceUntil": _format_datetime(grace_until),
    }


def serialize_code_snapshot_detail(detail) -> dict[str, object]:
    snapshot = detail.snapshot
    planning_input_reference = detail.planning_input_reference
    return {
        "id": str(snapshot.id),
        "connectionId": str(snapshot.connection_id),
        "requestedRefType": snapshot.requested_ref_type.value,
        "requestedRefName": snapshot.requested_ref_name,
        "resolvedCommitSha": snapshot.resolved_commit_sha,
        "fileCount": snapshot.file_count,
        "totalBytes": snapshot.total_bytes,
        "archivePath": snapshot.archive_path,
        "scopeRuleVersionId": str(snapshot.scope_rule_version_id),
        "syncRunId": str(snapshot.sync_run_id),
        "triggerEventId": _format_uuid(detail.trigger_event_id),
        "files": [
            {
                "path": file.path,
                "extension": file.extension,
                "languageHint": file.language_hint,
                "sizeBytes": file.size_bytes,
                "contentSha256": file.content_sha256,
                "archiveBlobPath": file.archive_blob_path,
                "includedBy": file.included_by.value,
            }
            for file in snapshot.files
        ],
        "traceability": {
            "planningInputReference": {
                "id": str(planning_input_reference.id),
                "sourceType": planning_input_reference.source_type.value,
                "sourceReference": planning_input_reference.source_reference,
                "approvedSpecPath": planning_input_reference.approved_spec_path,
                "approvedPlanPath": planning_input_reference.approved_plan_path,
            },
            "scopeRuleVersionId": str(snapshot.scope_rule_version_id),
            "syncRunId": str(snapshot.sync_run_id),
            "triggerEventId": _format_uuid(detail.trigger_event_id),
        },
    }


def serialize_repository_event(event) -> dict[str, object]:
    return {
        "id": str(event.id),
        "providerDeliveryId": event.provider_delivery_id,
        "providerEventType": _enum_value(event.provider_event_type),
        "providerAction": event.provider_action,
        "targetKey": event.target_key,
        "targetHeadSha": event.target_head_sha,
        "signatureStatus": _enum_value(event.signature_status),
        "verifiedSecretRevisionStatus": _enum_value(
            getattr(event, "verified_secret_revision_status", None)
        ),
        "rejectionReason": _enum_value(getattr(event, "rejection_reason", None)),
        "processingDecision": _enum_value(event.processing_decision),
        "processingStatus": _enum_value(event.processing_status),
        "snapshotId": _format_uuid(getattr(event, "snapshot_id", None)),
        "syncRunId": _format_uuid(getattr(event, "sync_run_id", None)),
    }


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _format_uuid(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _serialize_latest_snapshot_summary(snapshot) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "id": str(snapshot.id),
        "requestedRefType": snapshot.requested_ref_type.value,
        "requestedRefName": snapshot.requested_ref_name,
        "resolvedCommitSha": snapshot.resolved_commit_sha,
        "createdAt": _format_datetime(snapshot.created_at),
    }


def _serialize_latest_sync_run_summary(sync_run) -> dict[str, object] | None:
    if sync_run is None:
        return None
    return {
        "id": str(sync_run.id),
        "status": sync_run.status.value,
        "requestedRefType": sync_run.requested_ref_type.value,
        "requestedRefName": sync_run.requested_ref_name,
        "resolvedCommitSha": sync_run.resolved_commit_sha,
        "failureCode": (
            None if sync_run.failure_code is None else sync_run.failure_code.value
        ),
        "failureMessage": sync_run.failure_message,
        "startedAt": _format_datetime(sync_run.started_at),
        "completedAt": _format_datetime(sync_run.completed_at),
    }


def _serialize_last_processed_event(event) -> dict[str, object] | None:
    if event is None:
        return None
    return {
        "id": str(event.id),
        "providerEventType": _enum_value(event.provider_event_type),
        "providerAction": event.provider_action,
        "targetKey": event.target_key,
        "processingDecision": _enum_value(event.processing_decision),
        "processedAt": _format_datetime(getattr(event, "processed_at", None)),
    }


def _serialize_webhook_health(connection) -> dict[str, object] | None:
    if (
        getattr(connection, "active_webhook_secret_revision_id", None) is None
        and getattr(connection, "last_webhook_rejection_reason", None) is None
        and getattr(connection, "last_processed_event_id", None) is None
    ):
        return None
    previous_secret_deliveries = getattr(
        connection, "previous_secret_deliveries_during_grace", 0
    )
    last_previous_secret_accepted_at = getattr(
        connection, "last_previous_secret_accepted_at", None
    )
    return {
        "status": _enum_value(getattr(connection, "webhook_health_state", None))
        or "healthy",
        "lastRejectedReason": _enum_value(
            getattr(connection, "last_webhook_rejection_reason", None)
        ),
        "lastRejectedAt": _format_datetime(
            getattr(connection, "last_webhook_rejected_at", None)
        ),
        "rotationState": _serialize_rotation_state(connection),
        "graceUntil": _format_datetime(
            getattr(connection, "webhook_secret_grace_until", None)
        ),
        "previousSecretDeliveriesDuringGrace": previous_secret_deliveries,
        "lastPreviousSecretAcceptedAt": _format_datetime(
            last_previous_secret_accepted_at
        ),
    }


def _serialize_rotation_state(connection) -> str:
    grace_until = getattr(connection, "webhook_secret_grace_until", None)
    if grace_until is None:
        return "not_rotating"
    if grace_until > datetime.now(tz=grace_until.tzinfo):
        return "grace_active"
    return "grace_expired"


def _enum_value(value) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)
