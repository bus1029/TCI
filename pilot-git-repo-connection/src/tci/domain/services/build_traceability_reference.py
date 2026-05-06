from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True, slots=True)
class SnapshotTraceabilityReference:
    planning_input_reference_id: uuid.UUID | None
    connection_id: uuid.UUID
    scope_rule_version_id: uuid.UUID
    sync_run_id: uuid.UUID
    snapshot_id: uuid.UUID


def build_snapshot_traceability_reference(
    *,
    planning_input_reference_id: uuid.UUID | None,
    connection_id: uuid.UUID,
    scope_rule_version_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    snapshot_id: uuid.UUID,
) -> SnapshotTraceabilityReference:
    return SnapshotTraceabilityReference(
        planning_input_reference_id=planning_input_reference_id,
        connection_id=connection_id,
        scope_rule_version_id=scope_rule_version_id,
        sync_run_id=sync_run_id,
        snapshot_id=snapshot_id,
    )
