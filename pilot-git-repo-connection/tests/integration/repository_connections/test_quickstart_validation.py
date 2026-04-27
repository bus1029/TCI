from __future__ import annotations

from tests.support.run_quickstart_validation import run_quickstart_validation


def test_quickstart_validation_covers_release_scope_flow(
    tmp_path, monkeypatch
) -> None:
    result = run_quickstart_validation(tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert result.first_snapshot_seconds < 600
    assert result.latest_snapshot_id is not None
    assert result.webhook_snapshot_id is not None
    assert result.webhook_snapshot_id != result.manual_snapshot_id
    assert result.push_event_decision == "queued"
    assert result.push_event_processing_status == "completed"
    assert result.pull_request_event_decision == "queued"
    assert result.pull_request_event_processing_status == "completed"
    assert result.grace_period_previous_secret_accepted is True
    assert result.expired_previous_secret_public_status == "accepted"
    assert result.traceability_snapshot_id == result.webhook_snapshot_id
