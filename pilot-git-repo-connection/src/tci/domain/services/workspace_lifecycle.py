from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import uuid

from tci.infrastructure.persistence.models import Workspace, WorkspaceStatus


class WorkspaceRepositoryLike(Protocol):
    def get(self, *, workspace_id: uuid.UUID) -> Workspace | None: ...


@dataclass(frozen=True, slots=True)
class WorkspaceLifecycleProblem(Exception):
    code: str
    message: str
    remediation_action: str = "choose_active_workspace"
    status_code: int = 409

    def __str__(self) -> str:
        return self.message


def ensure_active_workspace(
    *,
    workspace_id: uuid.UUID,
    workspace_repository: WorkspaceRepositoryLike,
    lock_for_update: bool = False,
) -> Workspace:
    get_for_update = getattr(workspace_repository, "get_for_update", None)
    if lock_for_update and get_for_update is not None:
        workspace = get_for_update(workspace_id=workspace_id)
    else:
        workspace = workspace_repository.get(workspace_id=workspace_id)
    if workspace is None:
        raise WorkspaceLifecycleProblem(
            code="invalid_request",
            message="활성 워크스페이스에서만 작업을 시작할 수 있습니다.",
        )
    if workspace.status is WorkspaceStatus.ACTIVE:
        return workspace
    if workspace.status is WorkspaceStatus.DELETING:
        raise WorkspaceLifecycleProblem(
            code="workspace_deleting",
            message="삭제 중인 워크스페이스에서는 새 작업을 시작할 수 없습니다.",
        )
    raise WorkspaceLifecycleProblem(
        code="workspace_deleted",
        message="삭제된 워크스페이스에서는 새 작업을 시작할 수 없습니다.",
    )
