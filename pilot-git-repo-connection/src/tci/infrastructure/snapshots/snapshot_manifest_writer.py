from __future__ import annotations

import json
from pathlib import Path
import uuid

from tci.domain.services.build_traceability_reference import SnapshotTraceabilityReference
from tci.infrastructure.snapshots.snapshot_archive_store import StoredSnapshotArchive


class SnapshotManifestWriter:
    def write(
        self,
        *,
        archive: StoredSnapshotArchive,
        traceability: SnapshotTraceabilityReference,
    ) -> Path:
        if archive.snapshot_id != traceability.snapshot_id:
            raise ValueError("archive와 traceability의 snapshot_id가 일치해야 합니다.")

        manifest_path = archive.absolute_path / "manifest.json"
        if manifest_path.exists():
            raise FileExistsError("manifest.json은 한 번만 생성할 수 있습니다.")
        temp_path = manifest_path.with_name(
            f"{manifest_path.name}.{uuid.uuid4().hex}.tmp"
        )

        payload = {
            "snapshotId": str(archive.snapshot_id),
            "archivePath": archive.archive_path,
            "traceability": {
                "planningInputReferenceId": str(traceability.planning_input_reference_id),
                "connectionId": str(traceability.connection_id),
                "scopeRuleVersionId": str(traceability.scope_rule_version_id),
                "syncRunId": str(traceability.sync_run_id),
                "snapshotId": str(traceability.snapshot_id),
            },
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
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
        temp_path.replace(manifest_path)
        return manifest_path
