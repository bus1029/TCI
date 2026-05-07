from __future__ import annotations

from datetime import datetime
import uuid


def serialize_local_upload(upload) -> dict[str, object]:
    return {
        "id": str(upload.id),
        "workspaceId": str(upload.workspace_id),
        "sourceKind": "local_upload",
        "status": upload.status.value,
        "originalFilename": upload.original_filename_display,
        "uploadedBy": upload.created_by,
        "uploadedAt": _format_datetime(upload.created_at),
        "compressedSizeBytes": upload.compressed_size_bytes,
        "uncompressedSizeBytes": upload.uncompressed_size_bytes,
        "fileCount": upload.file_count,
        "directoryCount": upload.directory_count,
        "latestSnapshotId": _format_uuid(upload.latest_snapshot_id),
        "failureCode": upload.failure_code,
        "failureMessage": upload.failure_message,
        "createdAt": _format_datetime(upload.created_at),
        "completedAt": _format_datetime(upload.completed_at),
    }


def serialize_local_upload_snapshot_detail(*, snapshot, upload) -> dict[str, object]:
    return {
        "id": str(snapshot.id),
        "workspaceId": str(snapshot.workspace_id),
        "connectionId": None,
        "source": {
            "kind": "local_upload",
            "localUploadId": str(upload.id),
            "originalFilename": upload.original_filename_display,
            "uploadedBy": upload.created_by,
            "uploadedAt": _format_datetime(upload.created_at),
        },
        "fileCount": snapshot.file_count,
        "totalBytes": snapshot.total_bytes,
        "archivePath": snapshot.archive_path,
        "files": [
            {
                "path": file.path,
                "extension": file.extension,
                "languageHint": file.language_hint,
                "sizeBytes": file.size_bytes,
                "contentSha256": file.content_sha256,
                "archiveBlobPath": file.archive_blob_path,
                "includedBy": file.included_by.value,
            }
            for file in sorted(snapshot.files, key=lambda item: item.path)
        ],
        "traceability": {
            "sourceKind": "local_upload",
            "localUploadId": str(upload.id),
            "workspaceId": str(snapshot.workspace_id),
            "planningInputReference": None,
        },
    }


def serialize_local_upload_accepted(*, upload) -> dict[str, object]:
    return serialize_local_upload(upload)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _format_uuid(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    return str(value)
