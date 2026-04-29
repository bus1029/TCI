from __future__ import annotations

from types import SimpleNamespace
from typing import cast
import uuid

from tci.api.schemas.repository_connection import serialize_code_snapshot_detail
from tci.domain.services.build_traceability_reference import (
    build_snapshot_traceability_reference,
)
from tci.infrastructure.persistence.models import RefType, SnapshotInclusionReason


def test_snapshot_traceability_builder_accepts_null_legacy_planning_reference() -> None:
    traceability = build_snapshot_traceability_reference(
        planning_input_reference_id=None,
        connection_id=uuid.uuid4(),
        scope_rule_version_id=uuid.uuid4(),
        sync_run_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
    )

    assert traceability.planning_input_reference_id is None


def test_snapshot_detail_serializes_null_planning_reference() -> None:
    snapshot = SimpleNamespace(
        id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        requested_ref_type=RefType.BRANCH,
        requested_ref_name="main",
        resolved_commit_sha="a" * 40,
        file_count=1,
        total_bytes=12,
        archive_path=".runtime/code-snapshots/test.tar",
        scope_rule_version_id=uuid.uuid4(),
        sync_run_id=uuid.uuid4(),
        files=[
            SimpleNamespace(
                path="src/main.py",
                extension=".py",
                language_hint=None,
                size_bytes=12,
                content_sha256="b" * 64,
                archive_blob_path="src/main.py",
                included_by=SnapshotInclusionReason.DEFAULT_POLICY,
            )
        ],
    )
    detail = SimpleNamespace(
        snapshot=snapshot,
        planning_input_reference=None,
        trigger_event_id=None,
    )

    payload = serialize_code_snapshot_detail(detail)
    traceability = cast(dict[str, object], payload["traceability"])

    assert traceability["planningInputReference"] is None
