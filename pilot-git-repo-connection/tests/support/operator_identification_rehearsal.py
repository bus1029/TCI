from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True, slots=True)
class OperatorIdentificationConnection:
    id: uuid.UUID
    provider: str
    repository_owner: str
    repository_name: str
    provider_project_path: str
    origin_kind: str


@dataclass(frozen=True, slots=True)
class OperatorIdentificationTask:
    task_id: str
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    prompt: str
    expected_provider: str
    expected_repository_owner: str
    expected_repository_name: str
    expected_provider_project_path: str
    expected_origin_kind: str
    success_criterion_id: str = "SC-004"


def build_mixed_provider_identification_tasks(
    *,
    workspace_id: uuid.UUID,
    connections: tuple[OperatorIdentificationConnection, ...],
    repetitions_per_connection: int,
) -> tuple[OperatorIdentificationTask, ...]:
    tasks: list[OperatorIdentificationTask] = []
    for connection_index, connection in enumerate(connections, start=1):
        for repetition in range(1, repetitions_per_connection + 1):
            tasks.append(
                OperatorIdentificationTask(
                    task_id=f"SC-004-{connection_index:02d}-{repetition:02d}",
                    workspace_id=workspace_id,
                    connection_id=connection.id,
                    prompt=(
                        "Identify provider, repository, project path, and origin "
                        f"for connection {connection.id}."
                    ),
                    expected_provider=connection.provider,
                    expected_repository_owner=connection.repository_owner,
                    expected_repository_name=connection.repository_name,
                    expected_provider_project_path=connection.provider_project_path,
                    expected_origin_kind=connection.origin_kind,
                )
            )
    return tuple(tasks)
