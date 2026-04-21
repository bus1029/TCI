from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import time
import uuid
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tci.domain.services.rotate_webhook_secret import (
    RotateWebhookSecretCommand,
    rotate_webhook_secret,
)
from tci.infrastructure.queue.repository_ingestion_tasks import (
    _run_manual_snapshot_sync_task,
    _run_webhook_sync_task,
)
from tests.support.repository_connection_testkit import (
    build_github_pull_request_payload,
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_planning_input_reference,
    serialize_github_webhook_payload,
)


@dataclass(frozen=True, slots=True)
class QuickstartValidationResult:
    first_snapshot_seconds: float
    manual_snapshot_id: str
    latest_snapshot_id: str
    webhook_snapshot_id: str
    traceability_snapshot_id: str
    push_event_decision: str
    push_event_processing_status: str
    pull_request_event_decision: str
    pull_request_event_processing_status: str
    grace_period_previous_secret_accepted: bool
    expired_previous_secret_rejection_code: str


def run_quickstart_validation(*, tmp_path, monkeypatch) -> QuickstartValidationResult:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    task_recorder = _TaskRecorder()
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: task_recorder,
    )
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
        lambda settings: task_recorder,
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: client.app.state.dependencies,
    )

    started_at = time.perf_counter()
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    assert create_response.status_code == 201
    connection_id = uuid.UUID(create_response.json()["id"])

    scope_response = client.post(
        f"/api/repository-connections/{connection_id}/scope-rules",
        json={
            "includePaths": ["src/**"],
            "excludePaths": [],
            "allowedFileTypes": [".py"],
            "blockedFileTypes": [],
            "maxFileSizeBytes": 5 * 1024 * 1024,
        },
    )
    assert scope_response.status_code == 200

    manual_snapshot_response = client.post(
        f"/api/repository-connections/{connection_id}/snapshots",
        json={"reason": "manual_initial"},
    )
    assert manual_snapshot_response.status_code == 202
    manual_sync_task_kwargs = task_recorder.pop_latest_kwargs()
    _run_manual_snapshot_sync_task(
        workspace_id=manual_sync_task_kwargs["workspace_id"],
        connection_id=manual_sync_task_kwargs["connection_id"],
        sync_run_id=manual_sync_task_kwargs["sync_run_id"],
    )
    connection_detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert connection_detail_response.status_code == 200
    manual_snapshot_id = connection_detail_response.json()["latestSnapshot"]["id"]
    snapshot_detail_response = client.get(
        f"/api/repository-connections/{connection_id}/snapshots/{manual_snapshot_id}"
    )
    assert snapshot_detail_response.status_code == 200
    first_snapshot_seconds = time.perf_counter() - started_at

    rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="current-secret",
            rotated_at=datetime.now(tz=UTC) - timedelta(minutes=10),
        ),
        dependencies=client.app.state.dependencies,
    )

    push_event_id = _post_push_webhook(
        client=client,
        task_recorder=task_recorder,
        store=store,
        connection_id=connection_id,
        secret="current-secret",
        delivery_id="delivery-quickstart-push",
        after_sha="1" * 40,
    )
    pull_request_event_id = _post_pull_request_webhook(
        client=client,
        task_recorder=task_recorder,
        store=store,
        connection_id=connection_id,
        secret="current-secret",
        delivery_id="delivery-quickstart-pr",
        head_ref="feature/quickstart",
        head_sha="2" * 40,
    )

    rotate_webhook_secret(
        RotateWebhookSecretCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
            plaintext_secret="next-secret",
            rotated_at=datetime.now(tz=UTC),
        ),
        dependencies=client.app.state.dependencies,
    )
    previous_secret_event_id = _post_push_webhook(
        client=client,
        task_recorder=task_recorder,
        store=store,
        connection_id=connection_id,
        secret="current-secret",
        delivery_id="delivery-quickstart-grace",
        after_sha="3" * 40,
    )
    grace_period_previous_secret_accepted = _event_has_verified_secret_status(
        client=client,
        connection_id=connection_id,
        event_id=previous_secret_event_id,
        expected_status="previous_grace",
    )

    previous_revision = next(
        revision
        for revision in store.webhook_secret_revisions.values()
        if revision.connection_id == connection_id and revision.status == "previous_grace"
    )
    previous_revision.grace_until = datetime.now(tz=UTC) - timedelta(minutes=1)

    expired_secret_response = _post_push_webhook_response(
        client=client,
        store=store,
        connection_id=connection_id,
        secret="current-secret",
        delivery_id="delivery-quickstart-expired",
        after_sha="4" * 40,
    )
    assert expired_secret_response.status_code == 401

    connection_detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert connection_detail_response.status_code == 200
    connection_detail = connection_detail_response.json()
    events_response = client.get(f"/api/repository-connections/{connection_id}/events")
    assert events_response.status_code == 200
    events_by_id = {
        item["id"]: item for item in events_response.json()["items"]
    }

    return QuickstartValidationResult(
        first_snapshot_seconds=first_snapshot_seconds,
        manual_snapshot_id=manual_snapshot_id,
        latest_snapshot_id=connection_detail["latestSnapshot"]["id"],
        webhook_snapshot_id=connection_detail["latestSnapshot"]["id"],
        traceability_snapshot_id=connection_detail["traceability"]["latestSnapshotId"],
        push_event_decision=events_by_id[push_event_id]["processingDecision"],
        push_event_processing_status=events_by_id[push_event_id]["processingStatus"],
        pull_request_event_decision=events_by_id[pull_request_event_id][
            "processingDecision"
        ],
        pull_request_event_processing_status=events_by_id[pull_request_event_id][
            "processingStatus"
        ],
        grace_period_previous_secret_accepted=grace_period_previous_secret_accepted,
        expired_previous_secret_rejection_code=expired_secret_response.json()["code"],
    )


def _post_push_webhook(
    *,
    client,
    task_recorder,
    store,
    connection_id: uuid.UUID,
    secret: str,
    delivery_id: str,
    after_sha: str,
) -> str:
    response = _post_push_webhook_response(
        client=client,
        store=store,
        connection_id=connection_id,
        secret=secret,
        delivery_id=delivery_id,
        after_sha=after_sha,
    )
    assert response.status_code == 202
    event_id = response.json()["eventId"]
    webhook_task_kwargs = task_recorder.pop_latest_kwargs()
    _run_webhook_sync_task(**webhook_task_kwargs)
    return event_id


def _post_push_webhook_response(
    *,
    client,
    store,
    connection_id: uuid.UUID,
    secret: str,
    delivery_id: str,
    after_sha: str,
):
    store.resolved_ref_commits["main"] = after_sha
    payload = build_github_push_payload(after_sha=after_sha)
    headers = build_github_webhook_headers(
        secret=secret,
        payload=payload,
        delivery_id=delivery_id,
        event_name="push",
    )
    headers["content-type"] = "application/json"
    return client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )


def _post_pull_request_webhook(
    *,
    client,
    task_recorder,
    store,
    connection_id: uuid.UUID,
    secret: str,
    delivery_id: str,
    head_ref: str,
    head_sha: str,
) -> str:
    store.resolved_ref_commits[head_ref] = head_sha
    payload = build_github_pull_request_payload(
        action="synchronize",
        number=101,
        head_ref=head_ref,
        head_sha=head_sha,
    )
    headers = build_github_webhook_headers(
        secret=secret,
        payload=payload,
        delivery_id=delivery_id,
        event_name="pull_request",
    )
    headers["content-type"] = "application/json"
    response = client.post(
        f"/api/webhooks/github/{connection_id}",
        content=serialize_github_webhook_payload(payload),
        headers=headers,
    )
    assert response.status_code == 202
    event_id = response.json()["eventId"]
    webhook_task_kwargs = task_recorder.pop_latest_kwargs()
    _run_webhook_sync_task(**webhook_task_kwargs)
    return event_id


def _event_has_verified_secret_status(
    *,
    client,
    connection_id: uuid.UUID,
    event_id: str,
    expected_status: str,
) -> bool:
    response = client.get(f"/api/repository-connections/{connection_id}/events")
    assert response.status_code == 200
    return any(
        item["id"] == event_id and item["verifiedSecretRevisionStatus"] == expected_status
        for item in response.json()["items"]
    )


class _TaskRecorder:
    def __init__(self) -> None:
        self._calls: list[dict[str, str]] = []

    def send_task(self, name: str, kwargs: dict[str, str]) -> None:
        self._calls.append(dict(kwargs))

    def pop_latest_kwargs(self) -> dict[str, str]:
        if not self._calls:
            raise AssertionError("expected queued repository ingestion task")
        return self._calls.pop(0)


def main() -> None:
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from _pytest.monkeypatch import MonkeyPatch

    with TemporaryDirectory() as tmp_dir:
        monkeypatch = MonkeyPatch()
        try:
            result = run_quickstart_validation(
                tmp_path=Path(tmp_dir),
                monkeypatch=monkeypatch,
            )
            print(f"SC001_FIRST_SNAPSHOT_SECONDS={result.first_snapshot_seconds:.6f}")
            print(f"MANUAL_SNAPSHOT_ID={result.manual_snapshot_id}")
            print(f"LATEST_SNAPSHOT_ID={result.latest_snapshot_id}")
            print(f"WEBHOOK_SNAPSHOT_ID={result.webhook_snapshot_id}")
            print(f"TRACEABILITY_SNAPSHOT_ID={result.traceability_snapshot_id}")
            print(f"PUSH_EVENT_DECISION={result.push_event_decision}")
            print(f"PUSH_EVENT_PROCESSING_STATUS={result.push_event_processing_status}")
            print(f"PR_EVENT_DECISION={result.pull_request_event_decision}")
            print(
                f"PR_EVENT_PROCESSING_STATUS={result.pull_request_event_processing_status}"
            )
            print(f"GRACE_ACCEPTED={result.grace_period_previous_secret_accepted}")
            print(f"EXPIRED_REJECTION_CODE={result.expired_previous_secret_rejection_code}")
        finally:
            monkeypatch.undo()


if __name__ == "__main__":
    main()
