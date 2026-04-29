from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
import uuid
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tci.infrastructure.queue.repository_ingestion_tasks import (  # noqa: E402
    _run_webhook_sync_task,
)
from tests.support.repository_connection_testkit import (  # noqa: E402
    build_github_push_payload,
    build_github_webhook_headers,
    create_connection_payload,
    create_test_client,
    seed_active_webhook_secret,
    seed_planning_input_reference,
    serialize_github_webhook_payload,
)


@dataclass(frozen=True, slots=True)
class WebhookStatusLatencyMeasurement:
    sample_count: int
    completed_sample_count: int
    max_seconds: float
    p95_seconds: float
    samples_seconds: tuple[float, ...]


def measure_webhook_status_projection_latency(
    *,
    tmp_path,
    monkeypatch,
    sample_size: int = 5,
    timeout_seconds: float = 5.0,
) -> WebhookStatusLatencyMeasurement:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    seed_active_webhook_secret(
        store, connection_id=connection_id, secret="current-secret"
    )

    task_recorder = _TaskRecorder()
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.github_webhooks.create_celery_app",
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
        delivery_id = f"delivery-latency-{sample_index + 1:03d}"
        store.resolved_ref_commits["main"] = target_sha
        payload = build_github_push_payload(after_sha=target_sha)
        headers = build_github_webhook_headers(
            secret="current-secret",
            payload=payload,
            delivery_id=delivery_id,
            event_name="push",
        )
        headers["content-type"] = "application/json"

        started_at = time.perf_counter()
        webhook_response = client.post(
            f"/api/webhooks/github/{connection_id}",
            content=serialize_github_webhook_payload(payload),
            headers=headers,
        )
        assert webhook_response.status_code == 202
        event_id = webhook_response.json()["eventId"]
        task_kwargs = task_recorder.pop_latest_kwargs()
        _run_webhook_sync_task(**task_kwargs)

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
    return WebhookStatusLatencyMeasurement(
        sample_count=len(samples_seconds),
        completed_sample_count=completed_sample_count,
        max_seconds=max(samples_seconds, default=0.0),
        p95_seconds=ordered_samples[p95_index] if ordered_samples else 0.0,
        samples_seconds=tuple(samples_seconds),
    )


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
        event_items = events_payload.get("items", [])
        matching_event = next(
            (
                item
                for item in event_items
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
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from _pytest.monkeypatch import MonkeyPatch

    with TemporaryDirectory() as tmp_dir:
        monkeypatch = MonkeyPatch()
        try:
            result = measure_webhook_status_projection_latency(
                tmp_path=Path(tmp_dir),
                monkeypatch=monkeypatch,
                sample_size=5,
            )
            print(f"SC002_SAMPLE_COUNT={result.sample_count}")
            print(f"SC002_COMPLETED_SAMPLE_COUNT={result.completed_sample_count}")
            print(f"SC002_MAX_SECONDS={result.max_seconds:.6f}")
            print(f"SC002_P95_SECONDS={result.p95_seconds:.6f}")
            print(
                "SC002_SAMPLES="
                + ",".join(f"{sample:.6f}" for sample in result.samples_seconds)
            )
        finally:
            monkeypatch.undo()


if __name__ == "__main__":
    main()
