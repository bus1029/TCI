from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from tci.api.routes.repository_connections import (
    router as repository_connections_router,
)
from tci.api.routes.repository_snapshots import router as repository_snapshots_router
from tci.domain.services.build_traceability_reference import (
    build_snapshot_traceability_reference,
)
from tci.infrastructure.persistence.code_snapshot_repository import CodeSnapshotRepository
from tci.infrastructure.git.git_mirror_manager import GitMirrorManager, _subprocess_git_runner
from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
from tci.infrastructure.git.git_ref_resolver import GitRefResolver
from tci.infrastructure.persistence.credential_revision_repository import (
    CredentialRevisionRepository,
)
from tci.infrastructure.persistence.planning_input_reference_repository import (
    PlanningInputReferenceRepository,
)
from tci.infrastructure.persistence.repository_connection_repository import (
    RepositoryConnectionRepository,
)
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunRepository,
)
from tci.infrastructure.persistence.session import build_session_factory
from tci.infrastructure.snapshots.snapshot_archive_store import SnapshotArchiveStore
from tci.infrastructure.snapshots.snapshot_manifest_writer import SnapshotManifestWriter
from tci.settings import Settings, get_settings
from tci.web.routes.repository_connection_detail import (
    router as repository_connection_detail_web_router,
)
from tci.web.routes.repository_connections import (
    router as repository_connections_web_router,
)


@dataclass(frozen=True, slots=True)
class AppDependencies:
    settings: Settings
    git_ref_resolver: GitRefResolver
    git_readonly_validator: GitReadonlyValidator
    git_mirror_manager: GitMirrorManager
    snapshot_archive_store: SnapshotArchiveStore
    snapshot_manifest_writer: SnapshotManifestWriter
    planning_input_reference_repository_factory: Callable[
        [Session], PlanningInputReferenceRepository
    ]
    snapshot_traceability_builder: Callable[..., object]
    session_factory: Callable[[], AbstractContextManager[Session]] | None
    repository_connection_repository_factory: Callable[
        [Session], RepositoryConnectionRepository
    ]
    credential_revision_repository_factory: Callable[
        [Session], CredentialRevisionRepository
    ]
    repository_sync_run_repository_factory: Callable[
        [Session], RepositorySyncRunRepository
    ]
    code_snapshot_repository_factory: Callable[[Session], CodeSnapshotRepository]


def build_app_dependencies(settings: Settings) -> AppDependencies:
    # Git 호출 동작을 한 곳으로 맞춰야 인증/타임아웃 가드가 서비스마다 어긋나지 않는다.
    git_runner = _subprocess_git_runner
    return AppDependencies(
        settings=settings,
        git_ref_resolver=GitRefResolver(runner=git_runner),
        git_readonly_validator=GitReadonlyValidator(runner=git_runner),
        git_mirror_manager=GitMirrorManager(settings=settings),
        snapshot_archive_store=SnapshotArchiveStore(settings=settings),
        snapshot_manifest_writer=SnapshotManifestWriter(),
        planning_input_reference_repository_factory=PlanningInputReferenceRepository,
        snapshot_traceability_builder=build_snapshot_traceability_reference,
        session_factory=build_session_factory(settings),
        repository_connection_repository_factory=RepositoryConnectionRepository,
        credential_revision_repository_factory=CredentialRevisionRepository,
        repository_sync_run_repository_factory=RepositorySyncRunRepository,
        code_snapshot_repository_factory=CodeSnapshotRepository,
    )


def _ensure_runtime_directories(settings: Settings) -> None:
    for directory in settings.runtime_directories():
        directory.mkdir(parents=True, exist_ok=True)


def create_app(
    *,
    settings: Settings | None = None,
    dependencies: AppDependencies | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_dependencies = dependencies or build_app_dependencies(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _ensure_runtime_directories(resolved_settings)
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.dependencies = resolved_dependencies
    app.state.templates = Jinja2Templates(
        directory=str(resolved_settings.template_root)
    )
    app.include_router(repository_connections_router)
    app.include_router(repository_snapshots_router)
    app.include_router(repository_connections_web_router)
    app.include_router(repository_connection_detail_web_router)
    return app
