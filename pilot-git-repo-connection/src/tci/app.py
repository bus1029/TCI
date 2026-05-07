from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from tci.api.routes.planning_input_references import (
    router as planning_input_references_router,
)
from tci.api.routes.repository_connections import (
    router as repository_connections_router,
)
from tci.api.routes.repository_candidates import (
    router as repository_candidates_router,
)
from tci.api.routes.repository_scope import router as repository_scope_router
from tci.api.routes.repository_snapshots import router as repository_snapshots_router
from tci.domain.services.build_traceability_reference import (
    build_snapshot_traceability_reference,
)
from tci.domain.services.list_repository_candidates import RepositoryCandidateSource
from tci.infrastructure.persistence.code_snapshot_repository import (
    CodeSnapshotRepository,
)
from tci.infrastructure.persistence.local_upload_repository import (
    LocalUploadRepository,
)
from tci.infrastructure.persistence.workspace_repository import WorkspaceRepository
from tci.infrastructure.git.git_mirror_manager import (
    GitMirrorManager,
    _subprocess_git_runner,
)
from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator
from tci.infrastructure.git.gitlab_readonly_validator import GitLabReadonlyValidator
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
from tci.infrastructure.persistence.scope_rule_repository import ScopeRuleRepository
from tci.infrastructure.persistence.webhook_secret_repository import (
    WebhookSecretRepository,
)
from tci.infrastructure.persistence.repository_event_repository import (
    RepositoryEventRepository,
)
from tci.infrastructure.persistence.repository_event_cursor_repository import (
    RepositoryEventCursorRepository,
)
from tci.infrastructure.persistence.repository_sync_run_repository import (
    RepositorySyncRunRepository,
)
from tci.infrastructure.persistence.session import build_session_factory
from tci.infrastructure.snapshots.snapshot_archive_store import SnapshotArchiveStore
from tci.infrastructure.snapshots.snapshot_manifest_writer import SnapshotManifestWriter
from tci.settings import Settings, get_settings
from tci.api.problem_details import ProblemCode
from tci.web.routes.repository_connection_detail import (
    router as repository_connection_detail_web_router,
)
from tci.web.routes.repository_connections import (
    router as repository_connections_web_router,
)
from tci.api.routes.repository_events import router as repository_events_router
from tci.api.routes.github_webhooks import router as github_webhooks_router
from tci.api.routes.gitlab_webhooks import router as gitlab_webhooks_router
from tci.web.routes.repository_scope import router as repository_scope_web_router
from tci.web.routes.repository_events import router as repository_events_web_router
from tci.web.routes.operator_session import router as operator_session_web_router


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
    scope_rule_repository_factory: Callable[[Session], ScopeRuleRepository]
    credential_revision_repository_factory: Callable[
        [Session], CredentialRevisionRepository
    ]
    webhook_secret_repository_factory: Callable[[Session], WebhookSecretRepository]
    repository_event_repository_factory: Callable[[Session], RepositoryEventRepository]
    repository_event_cursor_repository_factory: Callable[
        [Session], RepositoryEventCursorRepository
    ]
    repository_sync_run_repository_factory: Callable[
        [Session], RepositorySyncRunRepository
    ]
    code_snapshot_repository_factory: Callable[[Session], CodeSnapshotRepository]
    workspace_repository_factory: Callable[[Session], WorkspaceRepository]
    local_upload_repository_factory: Callable[[Session], LocalUploadRepository]
    repository_candidate_source: RepositoryCandidateSource | None = None


def build_app_dependencies(settings: Settings) -> AppDependencies:
    # Git 호출 동작을 한 곳으로 맞춰야 인증/타임아웃 가드가 서비스마다 어긋나지 않는다.
    git_runner = _subprocess_git_runner
    return AppDependencies(
        settings=settings,
        git_ref_resolver=GitRefResolver(runner=git_runner),
        git_readonly_validator=GitLabReadonlyValidator(runner=git_runner),
        git_mirror_manager=GitMirrorManager(settings=settings),
        snapshot_archive_store=SnapshotArchiveStore(settings=settings),
        snapshot_manifest_writer=SnapshotManifestWriter(),
        planning_input_reference_repository_factory=PlanningInputReferenceRepository,
        snapshot_traceability_builder=build_snapshot_traceability_reference,
        session_factory=build_session_factory(settings),
        repository_connection_repository_factory=RepositoryConnectionRepository,
        scope_rule_repository_factory=ScopeRuleRepository,
        credential_revision_repository_factory=CredentialRevisionRepository,
        webhook_secret_repository_factory=WebhookSecretRepository,
        repository_event_repository_factory=RepositoryEventRepository,
        repository_event_cursor_repository_factory=RepositoryEventCursorRepository,
        repository_sync_run_repository_factory=RepositorySyncRunRepository,
        code_snapshot_repository_factory=CodeSnapshotRepository,
        workspace_repository_factory=WorkspaceRepository,
        local_upload_repository_factory=LocalUploadRepository,
        repository_candidate_source=None,
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
    app.add_exception_handler(RequestValidationError, _request_validation_handler)
    app.state.settings = resolved_settings
    app.state.dependencies = resolved_dependencies
    app.state.templates = Jinja2Templates(
        directory=str(resolved_settings.template_root)
    )
    app.include_router(planning_input_references_router)
    app.include_router(repository_candidates_router)
    app.include_router(repository_connections_router)
    app.include_router(repository_events_router)
    app.include_router(github_webhooks_router)
    app.include_router(gitlab_webhooks_router)
    app.include_router(repository_scope_router)
    app.include_router(repository_snapshots_router)
    app.include_router(repository_connections_web_router)
    app.include_router(repository_connection_detail_web_router)
    app.include_router(repository_scope_web_router)
    app.include_router(repository_events_web_router)
    app.include_router(operator_session_web_router)
    app.openapi = lambda: _custom_openapi(app)  # type: ignore[method-assign]
    return app


async def _request_validation_handler(
    request: Request, error: Exception
) -> JSONResponse:
    validation_error = cast(RequestValidationError, error)
    is_repository_create = request.url.path == "/api/repository-connections"
    if is_repository_create and _has_obsolete_planning_field_error(validation_error):
        message = (
            "새 저장소 연결 생성 요청은 planning/spec/plan 참조 필드를 "
            "받을 수 없습니다."
        )
        return JSONResponse(
            status_code=400,
            content={
                "code": ProblemCode.INVALID_INPUT.value,
                "message": message,
            },
        )
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitize_validation_errors(validation_error)},
    )


def _sanitize_validation_errors(error: RequestValidationError) -> list[dict[str, Any]]:
    sanitized_errors: list[dict[str, Any]] = []
    for item in error.errors():
        sanitized_errors.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"input", "ctx", "url"}
            }
        )
    return sanitized_errors


def _has_obsolete_planning_field_error(error: RequestValidationError) -> bool:
    obsolete_fields = {
        "planningInputReferenceId",
        "planningInputReference",
        "planningTrace",
        "traceability",
        "approvedSpecPath",
        "approvedPlanPath",
        "specPath",
        "planPath",
    }
    for item in error.errors():
        location = item.get("loc", ())
        if (
            item.get("type") == "extra_forbidden"
            and isinstance(location, tuple)
            and len(location) >= 2
            and location[0] == "body"
            and location[1] in obsolete_fields
        ):
            return True
    return False


def _custom_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    schemas = components.setdefault("schemas", {})
    security_schemes.update(
        {
            "OperatorHeaderToken": {
                "type": "apiKey",
                "in": "header",
                "name": "X-TCI-Operator-Token",
                "description": (
                    "Management API operator token configured by "
                    "TCI_OPERATOR_API_TOKEN."
                ),
            },
            "OperatorBearerToken": {
                "type": "http",
                "scheme": "bearer",
                "description": (
                    "Same operator token supplied as an Authorization bearer token."
                ),
            },
            "OperatorCookieToken": {
                "type": "apiKey",
                "in": "cookie",
                "name": "tci_operator_token",
                "description": (
                    "Short-lived signed browser operator session cookie issued by "
                    "/operator/session."
                ),
            },
        }
    )
    operator_security: list[dict[str, list[str]]] = [
        {"OperatorHeaderToken": []},
        {"OperatorBearerToken": []},
        {"OperatorCookieToken": []},
    ]
    schema.setdefault("security", operator_security)
    schemas["WebhookHealth"] = {
        "type": "object",
        "properties": {
            "webhookStatus": {
                "type": "string",
                "enum": [
                    "healthy",
                    "missing_secret",
                    "secret_mismatch_detected",
                    "signature_invalid_recently",
                ],
            },
            "providerReachabilityStatus": {
                "type": "string",
                "enum": [
                    "reachable",
                    "unreachable_recently",
                    "tls_failed_recently",
                    "dns_failed_recently",
                ],
            },
            "lastRejectionReason": {
                "type": "string",
                "enum": ["secret_missing", "secret_mismatch", "signature_invalid"],
                "nullable": True,
            },
            "lastRejectionAt": {
                "type": "string",
                "format": "date-time",
                "nullable": True,
            },
            "rotationState": {
                "type": "string",
                "enum": ["not_rotating", "grace_active", "grace_expired"],
            },
            "graceUntil": {
                "type": "string",
                "format": "date-time",
                "nullable": True,
            },
            "previousSecretDeliveriesDuringGrace": {
                "type": "integer",
                "minimum": 0,
            },
            "lastPreviousSecretAcceptedAt": {
                "type": "string",
                "format": "date-time",
                "nullable": True,
            },
        },
    }
    detail_schema = schemas.get("RepositoryConnectionDetailResponse")
    if isinstance(detail_schema, dict):
        detail_properties = detail_schema.get("properties")
        if isinstance(detail_properties, dict):
            detail_properties["webhookHealth"] = {
                "anyOf": [
                    {"$ref": "#/components/schemas/WebhookHealth"},
                    {"type": "null"},
                ],
                "title": "Webhookhealth",
            }
    paths = schema.get("paths", {})
    if isinstance(paths, dict):
        for path, operations in paths.items():
            if not path.startswith("/api/"):
                continue
            if not isinstance(operations, dict):
                continue
            for operation in operations.values():
                if isinstance(operation, dict):
                    if path.startswith("/api/webhooks/"):
                        operation["security"] = []
                    else:
                        operation.setdefault("security", operator_security)
    app.openapi_schema = schema
    return app.openapi_schema
