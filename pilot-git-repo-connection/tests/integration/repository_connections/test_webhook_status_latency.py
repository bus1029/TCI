from __future__ import annotations

from tests.support.measure_webhook_status_latency import (
    measure_webhook_status_projection_latency,
)


def test_webhook_status_projection_latency_stays_within_sla(
    tmp_path, monkeypatch
) -> None:
    result = measure_webhook_status_projection_latency(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        sample_size=5,
    )

    assert result.sample_count == 5
    assert result.completed_sample_count == result.sample_count
    assert result.max_seconds < 60
    assert result.p95_seconds < 60
