from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tci.infrastructure.persistence.models import (
    PlanningInputReference,
    PlanningInputSourceType,
    Workspace,
    WorkspaceStatus,
)


@dataclass(frozen=True, slots=True)
class PlanningInputReferenceDraft:
    workspace_id: uuid.UUID
    source_type: PlanningInputSourceType
    source_title: str
    source_reference: str
    approved_spec_path: str
    approved_plan_path: str


class PlanningInputReferenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, draft: PlanningInputReferenceDraft) -> PlanningInputReference:
        self._validate_feature_paths(
            spec_path=draft.approved_spec_path,
            plan_path=draft.approved_plan_path,
        )
        self._ensure_workspace(workspace_id=draft.workspace_id)

        reference = PlanningInputReference(
            workspace_id=draft.workspace_id,
            source_type=draft.source_type,
            source_title=draft.source_title,
            source_reference=draft.source_reference,
            approved_spec_path=draft.approved_spec_path,
            approved_plan_path=draft.approved_plan_path,
        )
        self._session.add(reference)
        self._session.flush()
        self._session.refresh(reference)
        return reference

    def _ensure_workspace(self, *, workspace_id: uuid.UUID) -> None:
        try:
            with self._session.begin_nested():
                self._session.add(Workspace(id=workspace_id))
                self._session.flush()
        except IntegrityError:
            pass
        workspace = self._session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        if not isinstance(workspace, Workspace):
            return
        if workspace.status is not WorkspaceStatus.ACTIVE:
            raise ValueError("Planning input reference requires an active workspace.")

    def get(
        self, *, workspace_id: uuid.UUID, reference_id: uuid.UUID
    ) -> PlanningInputReference | None:
        reference = self._session.get(PlanningInputReference, reference_id)
        if reference is None:
            return None
        if reference.workspace_id != workspace_id:
            return None
        return reference

    def get_any(self, *, reference_id: uuid.UUID) -> PlanningInputReference | None:
        return self._session.get(PlanningInputReference, reference_id)

    def delete_for_workspace(self, *, workspace_id: uuid.UUID) -> int:
        references = list(
            self._session.scalars(
                select(PlanningInputReference).where(
                    PlanningInputReference.workspace_id == workspace_id
                )
            )
        )
        for reference in references:
            self._session.delete(reference)
        self._session.flush()
        return len(references)

    @staticmethod
    def _validate_feature_paths(*, spec_path: str, plan_path: str) -> None:
        spec = PurePosixPath(spec_path)
        plan = PurePosixPath(plan_path)

        if spec.name != "spec.md":
            raise ValueError("승인된 spec 경로는 spec.md 파일이어야 합니다.")
        if plan.name != "plan.md":
            raise ValueError("승인된 plan 경로는 plan.md 파일이어야 합니다.")
        if not _is_repo_spec_path(spec) or not _is_repo_spec_path(plan):
            raise ValueError(
                "승인된 spec/plan 경로는 specs 디렉터리 아래의 기능 문서여야 합니다."
            )
        if spec.parent != plan.parent:
            raise ValueError(
                "승인된 spec/plan 경로는 같은 기능 디렉터리를 가리켜야 합니다."
            )


def _is_repo_spec_path(path: PurePosixPath) -> bool:
    parts = path.parts
    if any(part in {"..", "."} for part in parts):
        raise ValueError(
            "승인된 spec/plan 경로에는 경로 순회 세그먼트를 넣을 수 없습니다."
        )
    return len(parts) == 3 and parts[0] == "specs"
