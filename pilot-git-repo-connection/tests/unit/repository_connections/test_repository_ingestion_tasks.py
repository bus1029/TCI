from __future__ import annotations

import uuid


def test_repository_ingestion_tasks_expose_stable_task_names_and_queue_names() -> None:
    from tci.infrastructure.queue.repository_ingestion_tasks import (
        REPOSITORY_INGESTION_QUEUE_NAME,
        REPOSITORY_INGESTION_TASK_ROUTES,
        RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME,
        RUN_WEBHOOK_SYNC_TASK_NAME,
        VERIFY_REPOSITORY_CONNECTION_TASK_NAME,
    )

    assert REPOSITORY_INGESTION_QUEUE_NAME == "repository_ingestion"
    assert VERIFY_REPOSITORY_CONNECTION_TASK_NAME == (
        "tci.repository_ingestion.verify_repository_connection"
    )
    assert RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME == (
        "tci.repository_ingestion.run_manual_snapshot_sync"
    )
    assert RUN_WEBHOOK_SYNC_TASK_NAME == "tci.repository_ingestion.run_webhook_sync"
    assert REPOSITORY_INGESTION_TASK_ROUTES == {
        VERIFY_REPOSITORY_CONNECTION_TASK_NAME: {
            "queue": REPOSITORY_INGESTION_QUEUE_NAME
        },
        RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME: {
            "queue": REPOSITORY_INGESTION_QUEUE_NAME
        },
        RUN_WEBHOOK_SYNC_TASK_NAME: {
            "queue": REPOSITORY_INGESTION_QUEUE_NAME
        },
    }


def test_verify_repository_connection_task_delegates_to_domain_service(
    monkeypatch,
) -> None:
    from tci.infrastructure.persistence.models import RepositoryConnectionStatus
    from tci.infrastructure.queue import repository_ingestion_tasks as tasks

    workspace_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    captured: dict[str, object] = {}

    def fake_verify(command, *, dependencies):
        captured["workspace_id"] = command.workspace_id
        captured["connection_id"] = command.connection_id
        captured["dependencies"] = dependencies
        return type(
            "VerifiedConnection",
            (),
            {"status": RepositoryConnectionStatus.ACTIVE},
        )()

    monkeypatch.setattr(tasks, "_build_verify_dependencies", lambda: "deps")
    monkeypatch.setattr(
        tasks,
        "_load_verify_service",
        lambda: (
            type("VerifyCommand", (), {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)}),
            fake_verify,
        ),
    )

    result = tasks._verify_repository_connection_task(
        workspace_id=str(workspace_id),
        connection_id=str(connection_id),
    )

    assert captured == {
        "workspace_id": workspace_id,
        "connection_id": connection_id,
        "dependencies": "deps",
    }
    assert result == {
        "status": "active",
        "task_name": "tci.repository_ingestion.verify_repository_connection",
        "connection_id": str(connection_id),
    }


def test_run_manual_snapshot_sync_task_delegates_to_snapshot_builder(monkeypatch) -> None:
    from tci.infrastructure.queue import repository_ingestion_tasks as tasks

    workspace_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()
    captured: dict[str, object] = {}

    def fake_build_snapshot(command, *, dependencies):
        captured["workspace_id"] = command.workspace_id
        captured["connection_id"] = command.connection_id
        captured["sync_run_id"] = command.sync_run_id
        captured["dependencies"] = dependencies
        return type(
            "BuiltSnapshot",
            (),
            {"id": uuid.uuid4()},
        )()

    monkeypatch.setattr(tasks, "_build_snapshot_dependencies", lambda: "deps")
    monkeypatch.setattr(
        tasks,
        "_load_build_snapshot_service",
        lambda: (
            type(
                "BuildSnapshotCommand",
                (),
                {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)},
            ),
            fake_build_snapshot,
        ),
    )

    result = tasks._run_manual_snapshot_sync_task(
        workspace_id=str(workspace_id),
        connection_id=str(connection_id),
        sync_run_id=str(sync_run_id),
    )

    assert captured == {
        "workspace_id": workspace_id,
        "connection_id": connection_id,
        "sync_run_id": sync_run_id,
        "dependencies": "deps",
    }
    assert result == {
        "status": "completed",
        "task_name": "tci.repository_ingestion.run_manual_snapshot_sync",
        "connection_id": str(connection_id),
        "sync_run_id": str(sync_run_id),
    }
