from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import time
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tci.infrastructure.queue.repository_ingestion_tasks import (  # noqa: E402
    _run_webhook_sync_task,
)
from tests.support.repository_connection_testkit import (  # noqa: E402
    build_gitlab_merge_request_payload,
    build_gitlab_push_payload,
    build_gitlab_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
    serialize_gitlab_webhook_payload,
)


@dataclass(frozen=True, slots=True)
class GitLabWebhookStatusLatencyMeasurement:
    sample_count: int
    completed_sample_count: int
    max_seconds: float
    p95_seconds: float
    samples_seconds: tuple[float, ...]


def measure_gitlab_webhook_status_projection_latency(
    *,
    tmp_path,
    monkeypatch,
    sample_size: int = 5,
    timeout_seconds: float = 5.0,
) -> GitLabWebhookStatusLatencyMeasurement:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(
            provider="gitlab_self_managed",
            remote_url="https://gitlab.example.com/group/sample-repo.git",
        ),
    )
    assert create_response.status_code == 201
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store,
        connection_id=connection_id,
        secret="gitlab-webhook-token",
    )

    task_recorder = _TaskRecorder()
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: task_recorder,
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: client.app.state.dependencies,
    )

    samples_seconds: list[float] = []
    completed_sample_count = 0
    for sample_index in range(sample_size):
        target_sha = f"{sample_index + 1:040x}"
        delivery_id = f"gitlab-latency-{sample_index + 1:03d}"
        started_at = time.perf_counter()
        event_id = _post_latency_webhook(
            client=client,
            task_recorder=task_recorder,
            store=store,
            connection_id=connection_id,
            delivery_id=delivery_id,
            sample_index=sample_index,
            target_sha=target_sha,
        )
        if _wait_for_projection_visibility(
            client=client,
            connection_id=connection_id,
            event_id=event_id,
            timeout_seconds=timeout_seconds,
        ):
            completed_sample_count += 1
        samples_seconds.append(time.perf_counter() - started_at)

    ordered_samples = tuple(sorted(samples_seconds))
    p95_index = max(0, ((len(ordered_samples) * 95 + 99) // 100) - 1)
    return GitLabWebhookStatusLatencyMeasurement(
        sample_count=len(samples_seconds),
        completed_sample_count=completed_sample_count,
        max_seconds=max(samples_seconds, default=0.0),
        p95_seconds=ordered_samples[p95_index] if ordered_samples else 0.0,
        samples_seconds=tuple(samples_seconds),
    )


def _post_latency_webhook(
    *,
    client,
    task_recorder: _TaskRecorder,
    store,
    connection_id: uuid.UUID,
    delivery_id: str,
    sample_index: int,
    target_sha: str,
) -> str:
    if sample_index % 2 == 0:
        store.resolved_ref_commits["main"] = target_sha
        payload = build_gitlab_push_payload(after_sha=target_sha)
        headers = build_gitlab_webhook_headers(
            token="gitlab-webhook-token",
            event_name="Push Hook",
            idempotency_key=delivery_id,
        )
    else:
        source_branch = f"feature/gitlab-latency-{sample_index}"
        store.resolved_ref_commits[source_branch] = target_sha
        payload = build_gitlab_merge_request_payload(
            action="open",
            iid=200 + sample_index,
            source_branch=source_branch,
            last_commit_sha=target_sha,
        )
        headers = build_gitlab_webhook_headers(
            token="gitlab-webhook-token",
            event_name="Merge Request Hook",
            idempotency_key=delivery_id,
        )
    headers["content-type"] = "application/json"
    response = client.post(
        f"/api/webhooks/gitlab/{connection_id}",
        content=serialize_gitlab_webhook_payload(payload),
        headers=headers,
    )
    assert response.status_code == 202
    event_id = response.json()["eventId"]
    _run_webhook_sync_task(**task_recorder.pop_latest_kwargs())
    return event_id


def _wait_for_projection_visibility(
    *,
    client,
    connection_id: uuid.UUID,
    event_id: str,
    timeout_seconds: float,
) -> bool:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        detail_response = client.get(f"/api/repository-connections/{connection_id}")
        events_response = client.get(
            f"/api/repository-connections/{connection_id}/events"
        )
        assert detail_response.status_code == 200
        assert events_response.status_code == 200

        detail_payload = detail_response.json()
        events_payload = events_response.json()
        last_processed_event = detail_payload.get("lastProcessedEvent")
        matching_event = next(
            (
                item
                for item in events_payload.get("items", [])
                if isinstance(item, dict) and item.get("id") == event_id
            ),
            None,
        )
        if (
            isinstance(last_processed_event, dict)
            and last_processed_event.get("id") == event_id
            and isinstance(matching_event, dict)
            and matching_event.get("processingStatus") == "completed"
            and matching_event.get("snapshotId") is not None
        ):
            return True
        time.sleep(0.01)

    raise AssertionError(
        f"event {event_id} did not become visible in connection detail and events within "
        f"{timeout_seconds} seconds"
    )


class _TaskRecorder:
    def __init__(self) -> None:
        self._calls: list[dict[str, str]] = []

    def send_task(self, name: str, kwargs: dict[str, str]) -> None:
        self._calls.append(dict(kwargs))

    def pop_latest_kwargs(self) -> dict[str, str]:
        if not self._calls:
            raise AssertionError("expected queued webhook sync task")
        return self._calls.pop(0)


def main() -> None:
    from tempfile import TemporaryDirectory

    from _pytest.monkeypatch import MonkeyPatch

    with TemporaryDirectory() as tmp_dir:
        monkeypatch = MonkeyPatch()
        try:
            result = measure_gitlab_webhook_status_projection_latency(
                tmp_path=Path(tmp_dir),
                monkeypatch=monkeypatch,
                sample_size=5,
            )
            print(f"SC002_GITLAB_SAMPLE_COUNT={result.sample_count}")
            print(
                "SC002_GITLAB_COMPLETED_SAMPLE_COUNT="
                f"{result.completed_sample_count}"
            )
            print(f"SC002_GITLAB_MAX_SECONDS={result.max_seconds:.6f}")
            print(f"SC002_GITLAB_P95_SECONDS={result.p95_seconds:.6f}")
            print(
                "SC002_GITLAB_SAMPLES="
                + ",".join(f"{sample:.6f}" for sample in result.samples_seconds)
            )
        finally:
            monkeypatch.undo()


if __name__ == "__main__":
    main()
