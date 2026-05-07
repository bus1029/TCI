from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from tci.api.operator_auth import require_operator_auth
from tci.api.routes.local_uploads import (
    _create_pending_upload,
    _mark_upload_failed_for_queue_staging,
    _mark_upload_failed,
    _read_multipart_zip,
    _validate_local_zip_for_queue,
    _write_temp_zip_for_queue,
)
from tci.domain.services.create_local_upload_snapshot import (
    CreateLocalUploadSnapshotCommand,
    create_local_upload_snapshot,
)
from tci.domain.services.workspace_lifecycle import (
    WorkspaceLifecycleProblem,
    ensure_active_workspace,
)
from tci.infrastructure.queue.repository_ingestion_tasks import (
    RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME,
)
from tci.workers.celery_app import create_celery_app

from ._common import (
    build_template_context,
    enforce_same_origin,
    extract_workspace_id_from_query,
)


router = APIRouter(
    tags=["LocalUploadsWeb"],
    include_in_schema=False,
    dependencies=[Depends(require_operator_auth)],
)


@router.get("/local-uploads")
def local_uploads_page(request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id
    return _render_local_uploads_page(
        request=request,
        workspace_id=workspace_id,
        selected_upload_id=None,
        error_message=None,
        status_code=200,
    )


@router.get("/local-uploads/{upload_id}")
def local_upload_status_page(upload_id: uuid.UUID, request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id
    return _render_local_uploads_page(
        request=request,
        workspace_id=workspace_id,
        selected_upload_id=upload_id,
        error_message=None,
        status_code=200,
    )


@router.post("/local-uploads")
async def create_local_upload_page(request: Request):
    workspace_id = extract_workspace_id_from_query(request)
    if isinstance(workspace_id, PlainTextResponse):
        return workspace_id
    same_origin_error = enforce_same_origin(request)
    if same_origin_error is not None:
        return same_origin_error

    parsed_file = await _read_multipart_zip(request)
    if not isinstance(parsed_file, tuple):
        return _render_local_uploads_page(
            request=request,
            workspace_id=workspace_id,
            selected_upload_id=None,
            error_message="ZIP 파일을 첨부해야 합니다.",
            status_code=400,
        )
    filename, zip_bytes = parsed_file
    local_upload_id = uuid.uuid4()
    try:
        _create_pending_upload(
            request=request,
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            filename=filename,
            zip_bytes=zip_bytes,
            created_by="operator",
        )
    except ValueError:
        return _render_local_uploads_page(
            request=request,
            workspace_id=workspace_id,
            selected_upload_id=None,
            error_message="활성 워크스페이스에서만 Local Upload를 시작할 수 있습니다.",
            status_code=409,
        )
    if request.app.state.settings.redis_url:
        validation_error = await _validate_local_zip_for_queue(
            request=request,
            workspace_id=workspace_id,
            local_upload_id=local_upload_id,
            zip_bytes=zip_bytes,
        )
        if validation_error is not None:
            return _render_local_uploads_page(
                request=request,
                workspace_id=workspace_id,
                selected_upload_id=local_upload_id,
                error_message="ZIP 파일을 처리할 수 없습니다.",
                status_code=400,
            )
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
            return _render_local_uploads_page(
                request=request,
                workspace_id=workspace_id,
                selected_upload_id=local_upload_id,
                error_message="Local Upload 처리 파일을 준비하지 못했습니다.",
                status_code=503,
            )
        try:
            await run_in_threadpool(
                lambda: create_celery_app(request.app.state.settings).send_task(
                    RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME,
                    kwargs={
                        "workspace_id": str(workspace_id),
                        "local_upload_id": str(local_upload_id),
                    },
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
            return _render_local_uploads_page(
                request=request,
                workspace_id=workspace_id,
                selected_upload_id=local_upload_id,
                error_message="Local Upload 처리 작업 큐에 연결할 수 없습니다.",
                status_code=503,
            )
        return RedirectResponse(
            url=f"/local-uploads/{local_upload_id}?workspaceId={workspace_id}",
            status_code=303,
        )
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
    if not result.succeeded:
        return _render_local_uploads_page(
            request=request,
            workspace_id=workspace_id,
            selected_upload_id=local_upload_id,
            error_message=result.failure_message,
            status_code=400,
        )
    return RedirectResponse(
        url=f"/local-uploads/{local_upload_id}?workspaceId={workspace_id}",
        status_code=303,
    )


def _render_local_uploads_page(
    *,
    request: Request,
    workspace_id: uuid.UUID,
    selected_upload_id: uuid.UUID | None,
    error_message: str | None,
    status_code: int,
):
    with request.app.state.dependencies.session_factory() as session:
        workspace_repository_factory = getattr(
            request.app.state.dependencies, "workspace_repository_factory", None
        )
        if workspace_repository_factory is not None:
            try:
                ensure_active_workspace(
                    workspace_id=workspace_id,
                    workspace_repository=workspace_repository_factory(session),
                )
            except WorkspaceLifecycleProblem:
                return request.app.state.templates.TemplateResponse(
                    request=request,
                    name="local_uploads/index.html",
                    context=build_template_context(
                        request,
                        workspace_id=workspace_id,
                        uploads=[],
                        selected_upload=None,
                        error_message=(
                            error_message
                            or "활성 워크스페이스에서만 Local Upload를 조회할 수 있습니다."
                        ),
                    ),
                    status_code=409,
                )
        repository = request.app.state.dependencies.local_upload_repository_factory(
            session
        )
        uploads = repository.list_for_workspace(workspace_id=workspace_id)
    selected_upload = next(
        (upload for upload in uploads if upload.id == selected_upload_id),
        None,
    )
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="local_uploads/index.html",
        context=build_template_context(
            request,
            workspace_id=workspace_id,
            uploads=uploads,
            selected_upload=selected_upload,
            error_message=error_message,
        ),
        status_code=status_code,
    )
