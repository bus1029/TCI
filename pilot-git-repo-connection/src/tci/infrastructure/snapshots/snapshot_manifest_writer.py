from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import uuid

from tci.domain.services.build_traceability_reference import (
    SnapshotTraceabilityReference,
)
from tci.infrastructure.snapshots.snapshot_archive_store import StoredSnapshotArchive


@dataclass(frozen=True, slots=True)
class LocalUploadManifestSource:
    local_upload_id: uuid.UUID
    original_filename_display: str
    upload_sha256: str
    file_count: int
    directory_count: int
    directory_paths: tuple[str, ...]
    total_uncompressed_bytes: int


class SnapshotManifestWriter:
    def write(
        self,
        *,
        archive: StoredSnapshotArchive,
        traceability: SnapshotTraceabilityReference | None = None,
        local_upload_source: LocalUploadManifestSource | None = None,
    ) -> Path:
        if traceability is not None and archive.snapshot_id != traceability.snapshot_id:
            raise ValueError("archive와 traceability의 snapshot_id가 일치해야 합니다.")

        manifest_path = archive.absolute_path / "manifest.json"
        if manifest_path.exists():
            raise FileExistsError("manifest.json은 한 번만 생성할 수 있습니다.")
        temp_path = manifest_path.with_name(
            f"{manifest_path.name}.{uuid.uuid4().hex}.tmp"
        )

        payload: dict[str, Any] = {
            "snapshotId": str(archive.snapshot_id),
            "archivePath": archive.archive_path,
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
                for file in archive.files
            ],
        }
        if traceability is not None:
            payload["traceability"] = {
                "planningInputReferenceId": (
                    None
                    if traceability.planning_input_reference_id is None
                    else str(traceability.planning_input_reference_id)
                ),
                "connectionId": str(traceability.connection_id),
                "scopeRuleVersionId": str(traceability.scope_rule_version_id),
                "syncRunId": str(traceability.sync_run_id),
                "snapshotId": str(traceability.snapshot_id),
            }
        if local_upload_source is not None:
            payload["source"] = {
                "kind": "local_upload",
                "localUploadId": str(local_upload_source.local_upload_id),
                "originalFilename": local_upload_source.original_filename_display,
                "uploadSha256": local_upload_source.upload_sha256,
                "fileCount": local_upload_source.file_count,
                "directoryCount": local_upload_source.directory_count,
                "directories": list(local_upload_source.directory_paths),
                "totalUncompressedBytes": (
                    local_upload_source.total_uncompressed_bytes
                ),
            }
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
        temp_path.replace(manifest_path)
        return manifest_path
