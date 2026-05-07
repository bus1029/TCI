from __future__ import annotations

import hashlib
from email.parser import BytesParser
import os
import time
import uuid

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from tci.api.operator_auth import require_operator_auth
from tci.api.routes.repository_connections import _extract_workspace_id
from tci.api.schemas.local_upload import (
    serialize_local_upload,
)
from tci.api.schemas.repository_connection import serialize_code_snapshot_detail
from tci.domain.services.create_local_upload_snapshot import (
    CreateLocalUploadSnapshotCommand,
    create_local_upload_snapshot,
)
from tci.domain.services.failure_messages import bounded_display_filename
from tci.domain.services.get_code_snapshot_detail import (
    get_local_upload_snapshot_detail,
)
from tci.domain.services.workspace_lifecycle import (
    WorkspaceLifecycleProblem,
    ensure_active_workspace,
)
from tci.infrastructure.persistence.local_upload_repository import LocalUploadDraft
from tci.infrastructure.queue.repository_ingestion_tasks import (
    RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME,
    _local_upload_queue_zip_path,
)
from tci.infrastructure.snapshots.local_zip_extractor import (
    LocalZipValidationError,
    preflight_local_zip,
)
from tci.workers.celery_app import create_celery_app


MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024
LOCAL_UPLOAD_QUEUE_TTL_SECONDS = 24 * 60 * 60


router = APIRouter(
    prefix="/api/local-uploads",
    tags=["LocalUploads"],
    dependencies=[Depends(require_operator_auth)],
)


@router.post("")
async def create_local_upload_route(
    request: Request,
    workspace_header: str | None = Header(
        default=None,
        alias="X-TCI-Workspace-Id",
        description="워크스페이스 UUID",
    ),
    operator_id: str | None = Header(default=None, alias="X-TCI-Operator-Id"),
):
    workspace_id = _extract_workspace_id(workspace_header)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id
    same_origin_error = _reject_cookie_cross_origin(request)
    if same_origin_error is not None:
        return same_origin_error

    parsed_file = await _read_multipart_zip(request)
    if isinstance(parsed_file, JSONResponse):
        return parsed_file
    filename, zip_bytes = parsed_file
    local_upload_id = uuid.uuid4()
    created_by = _display_operator(operator_id)
    try:
        upload = _create_pending_upload(
            request=request,
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            filename=filename,
            zip_bytes=zip_bytes,
            created_by=created_by,
        )
    except ValueError:
        return _local_upload_problem(
            status_code=409,
            code="WORKSPACE_NOT_ACTIVE",
            message="활성 워크스페이스에서만 Local Upload를 시작할 수 있습니다.",
            remediation_action="choose_active_workspace",
        )

    if request.app.state.settings.redis_url:
        validation_error = await _validate_local_zip_for_queue(
            request=request,
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=zip_bytes,
        )
        if validation_error is not None:
            return validation_error
        try:
            temp_zip_path = await run_in_threadpool(
                lambda: _write_temp_zip_for_queue(
                    request=request,
                    local_upload_id=local_upload_id,
                    zip_bytes=zip_bytes,
                )
            )
        except OSError:
            _mark_upload_failed_for_queue_staging(
                request=request,
                workspace_id=workspace_id,
                local_upload_id=local_upload_id,
            )
            return _local_upload_problem(
                status_code=503,
                code="queue_staging_failed",
                message="Local Upload 처리 파일을 준비하지 못했습니다.",
                remediation_action="retry_upload",
            )
        try:
            await run_in_threadpool(
                lambda: _enqueue_local_upload_snapshot(
                    request=request,
                    workspace_id=workspace_id,
                    local_upload_id=local_upload_id,
                )
            )
        except Exception:
            temp_zip_path.unlink(missing_ok=True)
            _mark_upload_failed(
                request=request,
                workspace_id=workspace_id,
                local_upload_id=local_upload_id,
                failure_code="queue_unavailable",
                failure_message="Local Upload 처리 작업 큐에 연결할 수 없습니다.",
            )
            return _local_upload_problem(
                status_code=503,
                code="queue_unavailable",
                message="Local Upload 처리 작업 큐에 연결할 수 없습니다.",
                remediation_action="none",
            )
        return JSONResponse(status_code=202, content=serialize_local_upload(upload))

    result = await run_in_threadpool(
        lambda: create_local_upload_snapshot(
            CreateLocalUploadSnapshotCommand(
                workspace_id=workspace_id,
                local_upload_id=local_upload_id,
                zip_bytes=zip_bytes,
            ),
            dependencies=request.app.state.dependencies,
        )
    )
    upload = _get_upload(
        request=request, workspace_id=workspace_id, local_upload_id=local_upload_id
    )
    if not result.succeeded:
        return _local_upload_failure_response(
            result.failure_code or "invalid_zip",
            result.failure_message or "Local Upload 스냅샷 생성에 실패했습니다.",
            request=request,
        )
    return JSONResponse(status_code=201, content=serialize_local_upload(upload))


@router.get("/{upload_id}")
def get_local_upload_route(
    upload_id: uuid.UUID,
    request: Request,
    workspace_header: str | None = Header(
        default=None,
        alias="X-TCI-Workspace-Id",
        description="워크스페이스 UUID",
    ),
):
    workspace_id = _extract_workspace_id(workspace_header)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id
    lifecycle_error = _ensure_active_workspace_for_read(
        request=request, workspace_id=workspace_id
    )
    if lifecycle_error is not None:
        return lifecycle_error
    upload = _get_upload(
        request=request, workspace_id=workspace_id, local_upload_id=upload_id
    )
    if upload is None:
        return _local_upload_problem(
            status_code=404,
            code="local_upload_not_found",
            message="Local Upload를 찾을 수 없습니다.",
            remediation_action="none",
        )
    return serialize_local_upload(upload)


@router.get("/{upload_id}/snapshots/{snapshot_id}")
def get_local_upload_snapshot_route(
    upload_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    request: Request,
    workspace_header: str | None = Header(
        default=None,
        alias="X-TCI-Workspace-Id",
        description="워크스페이스 UUID",
    ),
):
    workspace_id = _extract_workspace_id(workspace_header)
    if isinstance(workspace_id, JSONResponse):
        return workspace_id
    lifecycle_error = _ensure_active_workspace_for_read(
        request=request, workspace_id=workspace_id
    )
    if lifecycle_error is not None:
        return lifecycle_error
    upload = _get_upload(
        request=request, workspace_id=workspace_id, local_upload_id=upload_id
    )
    if upload is None:
        return _local_upload_problem(
            status_code=404,
            code="local_upload_not_found",
            message="Local Upload를 찾을 수 없습니다.",
            remediation_action="none",
        )
    try:
        detail = get_local_upload_snapshot_detail(
            workspace_id=workspace_id,
            local_upload_id=upload_id,
            snapshot_id=snapshot_id,
            dependencies=request.app.state.dependencies,
        )
    except LookupError:
        return _local_upload_problem(
            status_code=404,
            code="snapshot_not_found",
            message="Local Upload 스냅샷을 찾을 수 없습니다.",
            remediation_action="none",
        )
    return serialize_code_snapshot_detail(detail)


def _create_pending_upload(
    *,
    request: Request,
    workspace_id: uuid.UUID,
    local_upload_id: uuid.UUID,
    filename: str,
    zip_bytes: bytes,
    created_by: str,
):
    with request.app.state.dependencies.session_factory() as session:
        repository = request.app.state.dependencies.local_upload_repository_factory(
            session
        )
        return repository.create(
            LocalUploadDraft(
                id=local_upload_id,
                workspace_id=workspace_id,
                original_filename_display=bounded_display_filename(filename),
                upload_sha256=hashlib.sha256(zip_bytes).hexdigest(),
                compressed_size_bytes=len(zip_bytes),
                created_by=created_by,
            )
        )


def _ensure_active_workspace_for_read(
    *, request: Request, workspace_id: uuid.UUID
) -> JSONResponse | None:
    workspace_repository_factory = getattr(
        request.app.state.dependencies, "workspace_repository_factory", None
    )
    if workspace_repository_factory is None:
        return None
    with request.app.state.dependencies.session_factory() as session:
        try:
            ensure_active_workspace(
                workspace_id=workspace_id,
                workspace_repository=workspace_repository_factory(session),
            )
        except WorkspaceLifecycleProblem as error:
            return _local_upload_problem(
                status_code=error.status_code,
                code=error.code,
                message=error.message,
                remediation_action=error.remediation_action,
            )
    return None


async def _read_multipart_zip(request: Request) -> tuple[str, bytes] | JSONResponse:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return _local_upload_problem(
            status_code=400,
            code="invalid_request",
            message="multipart/form-data 형식의 ZIP 파일이 필요합니다.",
            remediation_action="upload_valid_zip",
        )
    body_limit = (
        request.app.state.settings.local_upload_max_compressed_bytes
        + MAX_MULTIPART_OVERHEAD_BYTES
    )
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > body_limit:
                return _multipart_size_problem(request)
        except ValueError:
            return _local_upload_problem(
                status_code=400,
                code="invalid_request",
                message="Content-Length 헤더가 올바르지 않습니다.",
                remediation_action="upload_valid_zip",
            )
    try:
        body = await _read_limited_body(request, limit=body_limit)
    except ValueError:
        return _multipart_size_problem(request)
    message = BytesParser().parsebytes(
        b"Content-Type: "
        + content_type.encode("utf-8")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + body
    )
    if not message.is_multipart():
        return _local_upload_problem(
            status_code=400,
            code="invalid_request",
            message="multipart/form-data 형식의 ZIP 파일이 필요합니다.",
            remediation_action="upload_valid_zip",
        )
    for part in message.walk():
        if part.is_multipart():
            continue
        if part.get_param("name", header="content-disposition") != "file":
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            break
        if len(payload) > request.app.state.settings.local_upload_max_compressed_bytes:
            return _multipart_size_problem(request)
        filename = part.get_filename() or "upload.zip"
        return filename, payload
    return _local_upload_problem(
        status_code=400,
        code="invalid_request",
        message="file 필드에 ZIP 파일을 첨부해야 합니다.",
        remediation_action="upload_valid_zip",
    )


async def _read_limited_body(request: Request, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    async for chunk in request.stream():
        total_size += len(chunk)
        if total_size > limit:
            raise ValueError("multipart body exceeds configured Local Upload limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def _multipart_size_problem(request: Request) -> JSONResponse:
    return _local_upload_problem(
        status_code=400,
        code="zip_limit_exceeded",
        message="ZIP 업로드가 허용된 압축 크기 한도를 초과했습니다. 허용 한도 안으로 줄인 뒤 다시 업로드하세요.",
        remediation_action="reduce_zip_size",
        extra={"allowedLimits": _allowed_limits(request)},
    )


def _reject_cookie_cross_origin(request: Request) -> JSONResponse | None:
    if "X-TCI-Operator-Token" in request.headers or "Authorization" in request.headers:
        return None
    if "tci_operator_token" not in request.cookies:
        return None
    base_origin = str(request.base_url).rstrip("/")
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if not origin and not referer:
        return _local_upload_problem(
            status_code=403,
            code="invalid_request",
            message="허용되지 않은 요청 출처입니다.",
            remediation_action="none",
        )
    if origin and origin.rstrip("/") != base_origin:
        return _local_upload_problem(
            status_code=403,
            code="invalid_request",
            message="허용되지 않은 요청 출처입니다.",
            remediation_action="none",
        )
    if not origin and referer and not referer.startswith(f"{base_origin}/"):
        return _local_upload_problem(
            status_code=403,
            code="invalid_request",
            message="허용되지 않은 요청 출처입니다.",
            remediation_action="none",
        )
    return None


def _get_upload(
    *, request: Request, workspace_id: uuid.UUID, local_upload_id: uuid.UUID
):
    with request.app.state.dependencies.session_factory() as session:
        repository = request.app.state.dependencies.local_upload_repository_factory(
            session
        )
        return repository.get(
            workspace_id=workspace_id, local_upload_id=local_upload_id
        )


async def _validate_local_zip_for_queue(
    *,
    request: Request,
    workspace_id: uuid.UUID,
    local_upload_id: uuid.UUID,
    zip_bytes: bytes,
) -> JSONResponse | None:
    try:
        await run_in_threadpool(
            lambda: preflight_local_zip(
                zip_bytes=zip_bytes,
                settings=request.app.state.settings,
            )
        )
    except LocalZipValidationError as error:
        _mark_upload_failed(
            request=request,
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            failure_code=error.code,
            failure_message=error.message,
        )
        return _local_upload_failure_response(
            error.code,
            error.message,
            request=request,
        )
    return None


def _mark_upload_failed_for_queue_staging(
    *,
    request: Request,
    workspace_id: uuid.UUID,
    local_upload_id: uuid.UUID,
) -> None:
    _mark_upload_failed(
        request=request,
        workspace_id=workspace_id,
        local_upload_id=local_upload_id,
        failure_code="queue_staging_failed",
        failure_message="Local Upload 처리 파일을 준비하지 못했습니다.",
    )


def _enqueue_local_upload_snapshot(
    *,
    request: Request,
    workspace_id: uuid.UUID,
    local_upload_id: uuid.UUID,
) -> None:
    create_celery_app(request.app.state.settings).send_task(
        RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME,
        kwargs={
            "workspace_id": str(workspace_id),
            "local_upload_id": str(local_upload_id),
        },
    )


def _mark_upload_failed(
    *,
    request: Request,
    workspace_id: uuid.UUID,
    local_upload_id: uuid.UUID,
    failure_code: str,
    failure_message: str,
) -> None:
    with request.app.state.dependencies.session_factory() as session:
        repository = request.app.state.dependencies.local_upload_repository_factory(
            session
        )
        repository.mark_failed(
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            failure_code=failure_code,
            failure_message=failure_message,
        )


def _write_temp_zip_for_queue(
    *, request: Request, local_upload_id: uuid.UUID, zip_bytes: bytes
):
    runtime_root = request.app.state.settings.runtime_root
    temp_path = _local_upload_queue_zip_path(
        runtime_root=runtime_root,
        local_upload_id=local_upload_id,
    )
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    _purge_stale_local_upload_queue_files(runtime_root=runtime_root)
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as file_handle:
            file_handle.write(zip_bytes)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _purge_stale_local_upload_queue_files(*, runtime_root) -> None:
    queue_dir = runtime_root / "local-upload-queue"
    if not queue_dir.exists():
        return
    stale_before = time.time() - LOCAL_UPLOAD_QUEUE_TTL_SECONDS
    for candidate in queue_dir.glob("*.zip"):
        try:
            if candidate.is_symlink():
                continue
            if candidate.stat().st_mtime < stale_before:
                candidate.unlink(missing_ok=True)
        except OSError:
            continue


def _local_upload_failure_response(
    failure_code: str, failure_message: str, *, request: Request
) -> JSONResponse:
    if failure_code == "zip_limit_exceeded":
        return _local_upload_problem(
            status_code=400,
            code="zip_limit_exceeded",
            message=f"{failure_message} 허용 한도 안으로 줄인 뒤 다시 업로드하세요.",
            remediation_action="reduce_zip_size",
            extra={"allowedLimits": _allowed_limits(request)},
        )
    if failure_code == "unsafe_zip_path":
        return _local_upload_problem(
            status_code=400,
            code="unsafe_zip_path",
            message=failure_message,
            remediation_action="remove_unsafe_paths",
        )
    if failure_code in {"corrupt_zip", "invalid_zip"}:
        return _local_upload_problem(
            status_code=400,
            code="invalid_zip",
            message=failure_message,
            remediation_action="upload_valid_zip",
        )
    return _local_upload_problem(
        status_code=400,
        code=failure_code,
        message=failure_message,
        remediation_action="upload_valid_zip",
    )


def _allowed_limits(request: Request) -> dict[str, int]:
    settings = request.app.state.settings
    return {
        "maxCompressedBytes": settings.local_upload_max_compressed_bytes,
        "maxUncompressedBytes": settings.local_upload_max_uncompressed_bytes,
        "maxFileCount": settings.local_upload_max_file_count,
        "maxFileBytes": settings.local_upload_max_file_bytes,
        "maxPathSegments": settings.local_upload_max_path_segments,
    }


def _local_upload_problem(
    *,
    status_code: int,
    code: str,
    message: str,
    remediation_action: str,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {
        "code": code,
        "message": message,
        "remediationAction": remediation_action,
    }
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


def _display_operator(operator_id: str | None) -> str:
    return bounded_display_filename(operator_id or "operator")
