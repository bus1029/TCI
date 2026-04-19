from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    parse_default_ref_type,
)
from tci.infrastructure.persistence.models import RepositoryConnectionStatus


@dataclass(frozen=True, slots=True)
class UpdateDefaultRefCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    default_ref_type: str
    default_ref_name: str


def update_default_ref(command, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("기본 ref를 수정하려면 데이터베이스 세션이 필요합니다.")

    default_ref_type = parse_default_ref_type(command.default_ref_type)

    try:
        dependencies.git_ref_resolver.resolve(
            remote_url=_get_remote_url(
                workspace_id=command.workspace_id,
                connection_id=command.connection_id,
                dependencies=dependencies,
            ),
            ref_type=default_ref_type,
            ref_name=command.default_ref_name,
        )
    except Exception as error:
        problem_code = getattr(error, "problem_code", None)
        raise RepositoryConnectionProblem(
            problem_code or ProblemCode.INVALID_INPUT,
            None if problem_code is not None else "기본 ref 검증에 실패했습니다.",
        ) from error

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        return connection_repository.update_default_ref(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            default_ref_type=default_ref_type,
            default_ref_name=command.default_ref_name,
            status=RepositoryConnectionStatus.ACTIVE,
            last_verified_at=datetime.now(tz=UTC),
        )


def _get_remote_url(*, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies) -> str:
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        connection = connection_repository.get(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection.remote_url
