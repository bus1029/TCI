from __future__ import annotations

from dataclasses import dataclass
import uuid

import pytest

from tci.domain.services.workspace_lifecycle import (
    WorkspaceLifecycleProblem,
    ensure_active_workspace,
)
from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus


@dataclass(slots=True)
class StubWorkspaceRepository:
    workspace: Workspace | None

    def get(self, *, workspace_id: uuid.UUID) -> Workspace | None:
        if self.workspace is not None and self.workspace.id == workspace_id:
            return self.workspace
        return None


def _workspace(status: WorkspaceStatus) -> Workspace:
    return Workspace(id=uuid.uuid4(), status=status)


def test_ensure_active_workspace_returns_active_workspace() -> None:
    workspace = _workspace(WorkspaceStatus.ACTIVE)

    assert (
        ensure_active_workspace(
            workspace_id=workspace.id,
            workspace_repository=StubWorkspaceRepository(workspace),
        )
        is workspace
    )


@pytest.mark.parametrize(
    ("status", "expected_code"),
    (
        (WorkspaceStatus.DELETING, "workspace_deleting"),
        (WorkspaceStatus.DELETED, "workspace_deleted"),
    ),
)
def test_ensure_active_workspace_rejects_non_active_workspace(
    status: WorkspaceStatus,
    expected_code: str,
) -> None:
    workspace = _workspace(status)

    with pytest.raises(WorkspaceLifecycleProblem) as exc_info:
        ensure_active_workspace(
            workspace_id=workspace.id,
            workspace_repository=StubWorkspaceRepository(workspace),
        )

    assert exc_info.value.code == expected_code
    assert exc_info.value.remediation_action == "choose_active_workspace"
    assert str(workspace.id) not in exc_info.value.message


def test_ensure_active_workspace_rejects_missing_workspace_with_bounded_problem() -> (
    None
):
    workspace_id = uuid.uuid4()

    with pytest.raises(WorkspaceLifecycleProblem) as exc_info:
        ensure_active_workspace(
            workspace_id=workspace_id,
            workspace_repository=StubWorkspaceRepository(None),
        )

    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.remediation_action == "choose_active_workspace"
    assert str(workspace_id) not in exc_info.value.message
