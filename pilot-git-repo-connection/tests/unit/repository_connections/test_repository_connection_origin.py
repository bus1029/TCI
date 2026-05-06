from __future__ import annotations

import uuid

from tci.api.schemas.repository_connection import serialize_connection_origin
from tests.support.repository_first_connection_testkit import (
    build_workspace_repository_connection,
)
from tests.support.repository_connection_testkit import seed_planning_input_reference
from tests.support.repository_connection_testkit import InMemoryRepositoryStore


def test_origin_for_workspace_repository_connection_without_legacy_trace() -> None:
    connection = build_workspace_repository_connection(planning_input_reference_id=None)

    assert serialize_connection_origin(connection) == {
        "kind": "workspace_repository",
        "hasLegacyPlanningTrace": False,
        "compatibilityState": "normal",
        "message": "워크스페이스에서 직접 생성된 저장소 연결입니다.",
    }


def test_origin_for_legacy_planning_connection_with_existing_workspace() -> None:
    store = InMemoryRepositoryStore()
    workspace_id = uuid.uuid4()
    planning_reference = seed_planning_input_reference(
        store,
        workspace_id=workspace_id,
    )
    connection = build_workspace_repository_connection(
        workspace_id=workspace_id,
        planning_input_reference_id=planning_reference.id,
    )
    connection.planning_input_reference = planning_reference

    assert serialize_connection_origin(connection)["kind"] == "legacy_planning"
    assert serialize_connection_origin(connection)["hasLegacyPlanningTrace"] is True
    assert (
        serialize_connection_origin(connection)["compatibilityState"]
        == "legacy_trace_preserved"
    )
