from __future__ import annotations

import logging
import uuid

import pytest


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


def test_run_manual_snapshot_sync_task_logs_failure_context(
    monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    from tci.infrastructure.queue import repository_ingestion_tasks as tasks

    workspace_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    sync_run_id = uuid.uuid4()

    def broken_build_snapshot(command, *, dependencies):
        raise RuntimeError("boom")

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
            broken_build_snapshot,
        ),
    )

    with caplog.at_level(
        logging.INFO, logger="tci.infrastructure.queue.repository_ingestion_tasks"
    ):
        with pytest.raises(RuntimeError, match="boom"):
            tasks._run_manual_snapshot_sync_task(
                workspace_id=str(workspace_id),
                connection_id=str(connection_id),
                sync_run_id=str(sync_run_id),
            )

    assert "starting manual snapshot sync" in caplog.text
    assert "manual snapshot sync failed" in caplog.text
    assert str(sync_run_id) in caplog.text
    assert "RuntimeError: boom" in caplog.text


def test_run_manual_snapshot_sync_task_marks_sync_run_failed_when_dependency_loading_breaks(
    tmp_path, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    from tci.domain.services.create_initial_snapshot import (
        CreateInitialSnapshotCommand,
        create_initial_snapshot,
    )
    from tci.infrastructure.queue import repository_ingestion_tasks as tasks
    from tests.support.repository_connection_testkit import (
        create_connection_payload,
        create_test_client,
        seed_planning_input_reference,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=client.app.state.dependencies,
    )

    monkeypatch.setattr(
        tasks,
        "_build_snapshot_dependencies",
        lambda: (_ for _ in ()).throw(RuntimeError("deps failed")),
    )
    monkeypatch.setattr(
        tasks,
        "_build_manual_snapshot_failure_dependencies",
        lambda: client.app.state.dependencies,
    )

    with caplog.at_level(
        logging.INFO, logger="tci.infrastructure.queue.repository_ingestion_tasks"
    ):
        with pytest.raises(RuntimeError, match="deps failed"):
            tasks._run_manual_snapshot_sync_task(
                workspace_id=str(workspace_id),
                connection_id=str(connection_id),
                sync_run_id=str(sync_run.id),
            )

    assert "manual snapshot sync failed" in caplog.text
    assert str(sync_run.id) in caplog.text
    assert "deps failed" in caplog.text
    assert "RuntimeError: deps failed" in caplog.text
    assert store.sync_runs[sync_run.id].status.value == "failed"
    assert store.sync_runs[sync_run.id].failure_code.value == "SNAPSHOT_WRITE_FAILED"
    assert store.sync_runs[sync_run.id].completed_at is not None


def test_run_manual_snapshot_sync_task_marks_sync_run_failed_when_service_loading_breaks(
    tmp_path, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    from tci.domain.services.create_initial_snapshot import (
        CreateInitialSnapshotCommand,
        create_initial_snapshot,
    )
    from tci.infrastructure.queue import repository_ingestion_tasks as tasks
    from tests.support.repository_connection_testkit import (
        create_connection_payload,
        create_test_client,
        seed_planning_input_reference,
    )

    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    reference = seed_planning_input_reference(store, workspace_id=workspace_id)
    create_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(planning_input_reference_id=reference.id),
    )
    connection_id = uuid.UUID(create_response.json()["id"])
    sync_run = create_initial_snapshot(
        CreateInitialSnapshotCommand(
            workspace_id=workspace_id,
            connection_id=connection_id,
        ),
        dependencies=client.app.state.dependencies,
    )

    monkeypatch.setattr(tasks, "_build_snapshot_dependencies", lambda: client.app.state.dependencies)
    monkeypatch.setattr(
        tasks,
        "_load_build_snapshot_service",
        lambda: (_ for _ in ()).throw(RuntimeError("service load failed")),
    )

    with caplog.at_level(
        logging.INFO, logger="tci.infrastructure.queue.repository_ingestion_tasks"
    ):
        with pytest.raises(RuntimeError, match="service load failed"):
            tasks._run_manual_snapshot_sync_task(
                workspace_id=str(workspace_id),
                connection_id=str(connection_id),
                sync_run_id=str(sync_run.id),
            )

    assert "manual snapshot sync failed" in caplog.text
    assert store.sync_runs[sync_run.id].status.value == "failed"
    assert store.sync_runs[sync_run.id].failure_code.value == "SNAPSHOT_WRITE_FAILED"
    assert store.sync_runs[sync_run.id].completed_at is not None


def test_manual_snapshot_failure_dependencies_builder_only_wires_persistence_primitives(
    monkeypatch,
) -> None:
    from tci.infrastructure.queue import repository_ingestion_tasks as tasks

    sentinel_settings = object()
    sentinel_session_factory = object()

    class SentinelConnectionRepository:
        pass

    class SentinelSyncRunRepository:
        pass

    monkeypatch.setattr(
        "tci.settings.get_settings",
        lambda: sentinel_settings,
    )
    monkeypatch.setattr(
        "tci.infrastructure.persistence.session.build_session_factory",
        lambda settings: (
            sentinel_session_factory if settings is sentinel_settings else None
        ),
    )
    monkeypatch.setattr(
        "tci.infrastructure.persistence.repository_connection_repository.RepositoryConnectionRepository",
        SentinelConnectionRepository,
    )
    monkeypatch.setattr(
        "tci.infrastructure.persistence.repository_sync_run_repository.RepositorySyncRunRepository",
        SentinelSyncRunRepository,
    )

    dependencies = tasks._build_manual_snapshot_failure_dependencies()

    assert dependencies.session_factory is sentinel_session_factory
    assert (
        dependencies.repository_connection_repository_factory
        is SentinelConnectionRepository
    )
    assert dependencies.repository_sync_run_repository_factory is SentinelSyncRunRepository
    assert not hasattr(dependencies, "git_ref_resolver")
    assert not hasattr(dependencies, "git_mirror_manager")


def test_manual_snapshot_failure_logs_fallback_builder_failure(monkeypatch, caplog) -> None:
    from tci.infrastructure.queue import repository_ingestion_tasks as tasks

    monkeypatch.setattr(
        tasks,
        "_build_manual_snapshot_failure_dependencies",
        lambda: (_ for _ in ()).throw(RuntimeError("fallback init failed")),
    )

    with caplog.at_level(
        logging.WARNING, logger="tci.infrastructure.queue.repository_ingestion_tasks"
    ):
        tasks._mark_manual_snapshot_sync_failed(
            dependencies=None,
            workspace_id=uuid.uuid4(),
            connection_id=uuid.uuid4(),
            sync_run_id=uuid.uuid4(),
            error=RuntimeError("primary failure"),
        )

    assert "manual snapshot failure fallback init failed" in caplog.text
    assert "RuntimeError: fallback init failed" in caplog.text
