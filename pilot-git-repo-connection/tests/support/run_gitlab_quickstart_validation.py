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
    _run_manual_snapshot_sync_task,
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
from tests.support.run_quickstart_validation import (  # noqa: E402
    run_quickstart_validation,
)


@dataclass(frozen=True, slots=True)
class GitLabQuickstartValidationResult:
    gitlab_first_snapshot_seconds: float
    gitlab_manual_snapshot_id: str
    gitlab_latest_snapshot_id: str
    gitlab_webhook_snapshot_id: str
    gitlab_traceability_snapshot_id: str
    gitlab_push_event_decision: str
    gitlab_push_event_processing_status: str
    gitlab_merge_request_event_decision: str
    gitlab_merge_request_event_processing_status: str
    github_compatibility_passed: bool


def run_gitlab_quickstart_validation(
    *,
    tmp_path,
    monkeypatch,
) -> GitLabQuickstartValidationResult:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    task_recorder = _TaskRecorder()
    object.__setattr__(client.app.state.settings, "redis_url", "redis://example")
    monkeypatch.setattr(
        "tci.api.routes.repository_snapshots.create_celery_app",
        lambda settings: task_recorder,
    )
    monkeypatch.setattr(
        "tci.api.routes.gitlab_webhooks.create_celery_app",
        lambda settings: task_recorder,
    )
    monkeypatch.setattr(
        "tci.infrastructure.queue.repository_ingestion_tasks._build_snapshot_dependencies",
        lambda: client.app.state.dependencies,
    )

    started_at = time.perf_counter()
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
    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.status_code == 200
    gitlab_manual_snapshot_id = detail_response.json()["latestSnapshot"]["id"]
    first_snapshot_seconds = time.perf_counter() - started_at

    push_event_id = _post_push_webhook(
        client=client,
        task_recorder=task_recorder,
        store=store,
        connection_id=connection_id,
        delivery_id="gitlab-quickstart-push",
        after_sha="1" * 40,
    )
    merge_request_event_id = _post_merge_request_webhook(
        client=client,
        task_recorder=task_recorder,
        store=store,
        connection_id=connection_id,
        delivery_id="gitlab-quickstart-mr",
        source_branch="feature/gitlab-quickstart",
        head_sha="2" * 40,
    )

    detail_response = client.get(f"/api/repository-connections/{connection_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    events_response = client.get(f"/api/repository-connections/{connection_id}/events")
    assert events_response.status_code == 200
    events_by_id = {item["id"]: item for item in events_response.json()["items"]}

    github_result = run_quickstart_validation(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    return GitLabQuickstartValidationResult(
        gitlab_first_snapshot_seconds=first_snapshot_seconds,
        gitlab_manual_snapshot_id=gitlab_manual_snapshot_id,
        gitlab_latest_snapshot_id=detail_payload["latestSnapshot"]["id"],
        gitlab_webhook_snapshot_id=detail_payload["latestSnapshot"]["id"],
        gitlab_traceability_snapshot_id=detail_payload["traceability"][
            "latestSnapshotId"
        ],
        gitlab_push_event_decision=events_by_id[push_event_id]["processingDecision"],
        gitlab_push_event_processing_status=events_by_id[push_event_id][
            "processingStatus"
        ],
        gitlab_merge_request_event_decision=events_by_id[merge_request_event_id][
            "processingDecision"
        ],
        gitlab_merge_request_event_processing_status=events_by_id[
            merge_request_event_id
        ]["processingStatus"],
        github_compatibility_passed=(
            github_result.push_event_processing_status == "completed"
            and github_result.pull_request_event_processing_status == "completed"
            and github_result.traceability_snapshot_id
            == github_result.webhook_snapshot_id
        ),
    )


def _post_push_webhook(
    *,
    client,
    task_recorder: _TaskRecorder,
    store,
    connection_id: uuid.UUID,
    delivery_id: str,
    after_sha: str,
) -> str:
    store.resolved_ref_commits["main"] = after_sha
    payload = build_gitlab_push_payload(after_sha=after_sha)
    headers = build_gitlab_webhook_headers(
        token="gitlab-webhook-token",
        event_name="Push Hook",
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


def _post_merge_request_webhook(
    *,
    client,
    task_recorder: _TaskRecorder,
    store,
    connection_id: uuid.UUID,
    delivery_id: str,
    source_branch: str,
    head_sha: str,
) -> str:
    store.resolved_ref_commits[source_branch] = head_sha
    payload = build_gitlab_merge_request_payload(
        action="open",
        iid=101,
        source_branch=source_branch,
        last_commit_sha=head_sha,
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
    from tempfile import TemporaryDirectory

    from _pytest.monkeypatch import MonkeyPatch

    with TemporaryDirectory() as tmp_dir:
        monkeypatch = MonkeyPatch()
        try:
            result = run_gitlab_quickstart_validation(
                tmp_path=Path(tmp_dir),
                monkeypatch=monkeypatch,
            )
            print(
                "SC001_GITLAB_FIRST_SNAPSHOT_SECONDS="
                f"{result.gitlab_first_snapshot_seconds:.6f}"
            )
            print(f"GITLAB_MANUAL_SNAPSHOT_ID={result.gitlab_manual_snapshot_id}")
            print(f"GITLAB_LATEST_SNAPSHOT_ID={result.gitlab_latest_snapshot_id}")
            print(f"GITLAB_WEBHOOK_SNAPSHOT_ID={result.gitlab_webhook_snapshot_id}")
            print(
                "GITLAB_TRACEABILITY_SNAPSHOT_ID="
                f"{result.gitlab_traceability_snapshot_id}"
            )
            print(f"GITLAB_PUSH_DECISION={result.gitlab_push_event_decision}")
            print(
                "GITLAB_PUSH_PROCESSING_STATUS="
                f"{result.gitlab_push_event_processing_status}"
            )
            print(f"GITLAB_MR_DECISION={result.gitlab_merge_request_event_decision}")
            print(
                "GITLAB_MR_PROCESSING_STATUS="
                f"{result.gitlab_merge_request_event_processing_status}"
            )
            print(f"GITHUB_COMPATIBILITY_PASSED={result.github_compatibility_passed}")
        finally:
            monkeypatch.undo()


if __name__ == "__main__":
    main()
