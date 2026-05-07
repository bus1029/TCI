from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
import hashlib
import shutil
import uuid

from sqlalchemy.orm import Session

from tci.domain.services.failure_messages import bounded_failure_message
from tci.infrastructure.persistence.code_snapshot_repository import (
    CodeSnapshotFileDraft,
    CodeSnapshotLocalUploadDraft,
)
from tci.infrastructure.snapshots.local_zip_extractor import (
    LocalZipValidationError,
    extract_local_zip,
)
from tci.infrastructure.snapshots.snapshot_manifest_writer import (
    LocalUploadManifestSource,
)


@dataclass(frozen=True, slots=True)
class CreateLocalUploadSnapshotCommand:
    workspace_id: uuid.UUID
    local_upload_id: uuid.UUID
    zip_bytes: bytes


@dataclass(frozen=True, slots=True)
class CreateLocalUploadSnapshotResult:
    succeeded: bool
    local_upload_id: uuid.UUID
    snapshot_id: uuid.UUID | None = None
    failure_code: str | None = None
    failure_message: str | None = None


def create_local_upload_snapshot(
    command: CreateLocalUploadSnapshotCommand,
    *,
    dependencies: object,
) -> CreateLocalUploadSnapshotResult:
    session_factory = _require_session_factory(dependencies)
    snapshot_id: uuid.UUID | None = None

    with session_factory() as session:
        local_upload_repository = dependencies.local_upload_repository_factory(  # type: ignore[attr-defined]
            session
        )
        upload = local_upload_repository.mark_processing(
            workspace_id=command.workspace_id,
            local_upload_id=command.local_upload_id,
        )

    try:
        upload_sha256 = hashlib.sha256(command.zip_bytes).hexdigest()
        if upload_sha256 != upload.upload_sha256:
            return _fail_local_upload_snapshot(
                command=command,
                dependencies=dependencies,
                failure_code="upload_hash_mismatch",
                failure_message="Local Upload content hash does not match accepted metadata.",
                snapshot_id=None,
                result_failure_message="Local Upload 업로드 무결성 검증에 실패했습니다.",
            )
        extraction = extract_local_zip(
            zip_bytes=command.zip_bytes,
            settings=dependencies.settings,  # type: ignore[attr-defined]
        )
        snapshot_id = uuid.uuid4()
        archive = dependencies.snapshot_archive_store.store(  # type: ignore[attr-defined]
            snapshot_id=snapshot_id,
            entries=extraction.entries,
        )
        dependencies.snapshot_manifest_writer.write(  # type: ignore[attr-defined]
            archive=archive,
            local_upload_source=LocalUploadManifestSource(
                local_upload_id=command.local_upload_id,
                original_filename_display=upload.original_filename_display,
                upload_sha256=upload.upload_sha256,
                file_count=extraction.file_count,
                directory_count=extraction.directory_count,
                directory_paths=extraction.directory_paths,
                total_uncompressed_bytes=extraction.total_uncompressed_bytes,
            ),
        )

        with session_factory() as session:
            snapshot_repository = dependencies.code_snapshot_repository_factory(  # type: ignore[attr-defined]
                session
            )
            local_upload_repository = dependencies.local_upload_repository_factory(  # type: ignore[attr-defined]
                session
            )
            snapshot = snapshot_repository.create_for_local_upload(
                draft=CodeSnapshotLocalUploadDraft(
                    id=snapshot_id,
                    workspace_id=command.workspace_id,
                    local_upload_id=command.local_upload_id,
                    archive_path=archive.archive_path,
                    file_count=extraction.file_count,
                    total_bytes=extraction.total_uncompressed_bytes,
                ),
                files=tuple(
                    CodeSnapshotFileDraft(
                        path=file.path,
                        extension=file.extension,
                        language_hint=file.language_hint,
                        size_bytes=file.size_bytes,
                        content_sha256=file.content_sha256,
                        archive_blob_path=file.archive_blob_path,
                        included_by=file.included_by,
                    )
                    for file in archive.files
                ),
            )
            local_upload_repository.mark_succeeded(
                workspace_id=command.workspace_id,
                local_upload_id=command.local_upload_id,
                latest_snapshot_id=snapshot.id,
                uncompressed_size_bytes=extraction.total_uncompressed_bytes,
                file_count=extraction.file_count,
                directory_count=extraction.directory_count,
            )
        return CreateLocalUploadSnapshotResult(
            succeeded=True,
            local_upload_id=command.local_upload_id,
            snapshot_id=snapshot_id,
        )
    except LocalZipValidationError as error:
        return _fail_local_upload_snapshot(
            command=command,
            dependencies=dependencies,
            failure_code=error.code,
            failure_message=error.message,
            snapshot_id=snapshot_id,
        )
    except Exception as error:
        return _fail_local_upload_snapshot(
            command=command,
            dependencies=dependencies,
            failure_code="snapshot_write_failed",
            failure_message=str(error) or "Local Upload 스냅샷 저장에 실패했습니다.",
            snapshot_id=snapshot_id,
            result_failure_message="Local Upload 스냅샷 저장에 실패했습니다.",
        )


def _fail_local_upload_snapshot(
    *,
    command: CreateLocalUploadSnapshotCommand,
    dependencies: object,
    failure_code: str,
    failure_message: str,
    snapshot_id: uuid.UUID | None,
    result_failure_message: str | None = None,
) -> CreateLocalUploadSnapshotResult:
    if snapshot_id is not None:
        archive_store = dependencies.snapshot_archive_store  # type: ignore[attr-defined]
        if hasattr(archive_store, "remove"):
            archive_store.remove(snapshot_id=snapshot_id)
        else:
            shutil.rmtree(
                dependencies.settings.code_snapshot_root / str(snapshot_id),  # type: ignore[attr-defined]
                ignore_errors=True,
            )
    session_factory = _require_session_factory(dependencies)
    try:
        with session_factory() as session:
            local_upload_repository = dependencies.local_upload_repository_factory(  # type: ignore[attr-defined]
                session
            )
            local_upload_repository.mark_failed(
                workspace_id=command.workspace_id,
                local_upload_id=command.local_upload_id,
                failure_code=failure_code,
                failure_message=failure_message,
            )
    except Exception as error:
        raise RuntimeError(
            "Local Upload failure status could not be recorded."
        ) from error
    return CreateLocalUploadSnapshotResult(
        succeeded=False,
        local_upload_id=command.local_upload_id,
        failure_code=failure_code,
        failure_message=bounded_failure_message(
            result_failure_message or failure_message
        ),
    )


def _require_session_factory(
    dependencies: object,
) -> Callable[[], AbstractContextManager[Session]]:
    session_factory = getattr(dependencies, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("Local Upload snapshot creation requires a session factory.")
    return session_factory
