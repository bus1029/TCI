from __future__ import annotations

import uuid

from tests.support.operator_identification_rehearsal import (
    OperatorIdentificationConnection,
    build_mixed_provider_identification_tasks,
)


def test_sc004_identification_rehearsal_fixture_builds_sixty_tasks() -> None:
    workspace_id = uuid.uuid4()
    github_id = uuid.uuid4()
    gitlab_id = uuid.uuid4()
    tasks = build_mixed_provider_identification_tasks(
        workspace_id=workspace_id,
        connections=(
            OperatorIdentificationConnection(
                id=github_id,
                provider="github_cloud",
                repository_owner="acme",
                repository_name="sample-repo",
                provider_project_path="acme/sample-repo",
                origin_kind="workspace_repository",
            ),
            OperatorIdentificationConnection(
                id=gitlab_id,
                provider="gitlab_self_managed",
                repository_owner="group",
                repository_name="sample-repo",
                provider_project_path="group/sample-repo",
                origin_kind="legacy_planning",
            ),
        ),
        repetitions_per_connection=30,
    )

    assert len(tasks) == 60
    assert {task.workspace_id for task in tasks} == {workspace_id}
    assert {task.connection_id for task in tasks} == {github_id, gitlab_id}
    assert sum(task.expected_provider == "github_cloud" for task in tasks) == 30
    assert sum(task.expected_provider == "gitlab_self_managed" for task in tasks) == 30
    assert all(task.success_criterion_id == "SC-004" for task in tasks)
    assert all(task.expected_repository_name == "sample-repo" for task in tasks)
    assert all(task.expected_origin_kind for task in tasks)
    assert len({task.task_id for task in tasks}) == 60
