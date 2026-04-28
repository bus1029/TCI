from __future__ import annotations

from dataclasses import dataclass

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import RepositoryConnectionProblem
from tci.infrastructure.persistence.models import PlanningInputSourceType
from tci.infrastructure.persistence.planning_input_reference_repository import (
    PlanningInputReferenceDraft,
)


@dataclass(frozen=True, slots=True)
class CreatePlanningInputReferenceCommand:
    workspace_id: object
    source_type: str
    source_title: str
    source_reference: str
    approved_spec_path: str
    approved_plan_path: str


def create_planning_input_reference(command, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("planning input reference를 생성하려면 데이터베이스 세션이 필요합니다.")

    source_type = _parse_source_type(command.source_type)

    with dependencies.session_factory() as session:
        repository = dependencies.planning_input_reference_repository_factory(session)
        try:
            return repository.create(
                PlanningInputReferenceDraft(
                    workspace_id=command.workspace_id,
                    source_type=source_type,
                    source_title=command.source_title,
                    source_reference=command.source_reference,
                    approved_spec_path=command.approved_spec_path,
                    approved_plan_path=command.approved_plan_path,
                )
            )
        except ValueError as error:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                str(error),
            ) from error


def _parse_source_type(raw_value: str) -> PlanningInputSourceType:
    try:
        return PlanningInputSourceType(raw_value)
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "sourceType은 user_request, planning_brief, imported_note 중 하나여야 합니다.",
        ) from error
