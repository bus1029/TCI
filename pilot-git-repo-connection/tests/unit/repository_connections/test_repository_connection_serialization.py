from __future__ import annotations

import uuid
from typing import cast

from tci.api.schemas.repository_connection import serialize_repository_connection_detail
from tests.support.repository_first_connection_testkit import (
    build_workspace_repository_connection,
)
from tests.support.repository_connection_testkit import (
    InMemoryRepositoryStore,
    seed_planning_input_reference,
)


def test_connection_detail_serializes_null_planning_reference_for_new_connection() -> (
    None
):
    connection = build_workspace_repository_connection(planning_input_reference_id=None)
    connection.planning_input_reference = None

    payload = serialize_repository_connection_detail(connection)
    traceability = cast(dict[str, object], payload["traceability"])
    origin = cast(dict[str, object], payload["origin"])

    assert traceability["planningInputReference"] is None
    assert origin["kind"] == "workspace_repository"


def test_connection_detail_preserves_legacy_planning_reference() -> None:
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

    payload = serialize_repository_connection_detail(connection)
    traceability = cast(dict[str, object], payload["traceability"])
    planning_reference_payload = cast(
        dict[str, object],
        traceability["planningInputReference"],
    )
    origin = cast(dict[str, object], payload["origin"])

    assert planning_reference_payload["id"] == str(planning_reference.id)
    assert origin["kind"] == "legacy_planning"
