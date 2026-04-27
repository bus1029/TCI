from __future__ import annotations

from tests.support.run_gitlab_quickstart_validation import (
    run_gitlab_quickstart_validation,
)


def test_gitlab_quickstart_validation_covers_primary_and_github_compatibility(
    tmp_path, monkeypatch
) -> None:
    result = run_gitlab_quickstart_validation(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    assert result.gitlab_first_snapshot_seconds < 900
    assert result.gitlab_latest_snapshot_id is not None
    assert result.gitlab_webhook_snapshot_id is not None
    assert result.gitlab_webhook_snapshot_id != result.gitlab_manual_snapshot_id
    assert result.gitlab_push_event_decision == "queued"
    assert result.gitlab_push_event_processing_status == "completed"
    assert result.gitlab_merge_request_event_decision == "queued"
    assert result.gitlab_merge_request_event_processing_status == "completed"
    assert result.gitlab_traceability_snapshot_id == result.gitlab_webhook_snapshot_id
    assert result.github_compatibility_passed is True
