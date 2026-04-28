from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import uuid


@dataclass(frozen=True, slots=True)
class GitLabDeliveryId:
    delivery_id: str
    idempotency_source: str


def extract_gitlab_delivery_id(
    *,
    connection_id: uuid.UUID,
    event_name: str,
    headers: dict[str, str],
    payload: dict[str, object],
    raw_body: bytes,
) -> GitLabDeliveryId:
    _ = raw_body
    idempotency_key = _header_value(headers, "Idempotency-Key")
    if idempotency_key:
        return GitLabDeliveryId(
            delivery_id=idempotency_key,
            idempotency_source="delivery_header",
        )
    webhook_uuid = _header_value(headers, "X-Gitlab-Webhook-UUID")
    if webhook_uuid:
        return GitLabDeliveryId(
            delivery_id=webhook_uuid,
            idempotency_source="uuid_header",
        )
    basis = {
        "connection_id": str(connection_id),
        "event_name": event_name,
        "object_kind": payload.get("object_kind"),
        "object_id": _object_id(payload),
        "before": payload.get("before"),
        "ref": payload.get("ref") or _source_branch(payload),
        "head_sha": _head_sha(payload),
        "occurred_at": _occurred_at(payload),
    }
    digest = hashlib.sha256(
        json.dumps(basis, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return GitLabDeliveryId(
        delivery_id=f"gitlab:{digest}",
        idempotency_source="derived_hash",
    )


def _header_value(headers: dict[str, str], name: str) -> str | None:
    lowered_name = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered_name and value:
            return value
    return None


def _object_id(payload: dict[str, object]) -> object:
    attributes = payload.get("object_attributes")
    if isinstance(attributes, dict):
        return attributes.get("id") or attributes.get("iid")
    return payload.get("project_id")


def _head_sha(payload: dict[str, object]) -> object:
    attributes = payload.get("object_attributes")
    if isinstance(attributes, dict):
        last_commit = attributes.get("last_commit")
        if isinstance(last_commit, dict):
            return last_commit.get("id")
    return payload.get("checkout_sha") or payload.get("after")


def _source_branch(payload: dict[str, object]) -> object:
    attributes = payload.get("object_attributes")
    if isinstance(attributes, dict):
        return attributes.get("source_branch")
    return None


def _occurred_at(payload: dict[str, object]) -> object:
    attributes = payload.get("object_attributes")
    if isinstance(attributes, dict):
        return attributes.get("updated_at") or attributes.get("created_at")
    return None
