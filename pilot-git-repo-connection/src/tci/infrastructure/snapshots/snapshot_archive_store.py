from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid

from tci.infrastructure.persistence.models import SnapshotInclusionReason
from tci.settings import Settings


@dataclass(frozen=True, slots=True)
class SnapshotArchiveEntryDraft:
    path: str
    content: bytes
    included_by: SnapshotInclusionReason
    extension: str | None = None
    language_hint: str | None = None
    archive_blob_path: str | None = None


@dataclass(frozen=True, slots=True)
class StoredSnapshotArchiveFile:
    path: str
    extension: str | None
    language_hint: str | None
    size_bytes: int
    content_sha256: str
    archive_blob_path: str
    included_by: SnapshotInclusionReason


@dataclass(frozen=True, slots=True)
class StoredSnapshotArchive:
    snapshot_id: uuid.UUID
    archive_path: str
    absolute_path: Path
    files: tuple[StoredSnapshotArchiveFile, ...]


class SnapshotArchiveStore:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def store(
        self,
        *,
        snapshot_id: uuid.UUID,
        entries: tuple[SnapshotArchiveEntryDraft, ...],
    ) -> StoredSnapshotArchive:
        if not entries:
            raise ValueError("스냅샷 아카이브에는 최소 한 개 이상의 파일이 필요합니다.")

        archive_root = self._settings.code_snapshot_root / str(snapshot_id)
        normalized_entries = _normalize_entries(entries)
        self._settings.code_snapshot_root.mkdir(parents=True, exist_ok=True)
        if archive_root.exists():
            raise FileExistsError("같은 snapshot_id의 아카이브가 이미 존재합니다.")
        temp_root = Path(
            tempfile.mkdtemp(
                prefix=f".{snapshot_id}.",
                dir=self._settings.code_snapshot_root,
            )
        )

        stored_files: list[StoredSnapshotArchiveFile] = []
        try:
            for logical_path, blob_path, entry in normalized_entries:
                file_path = temp_root / blob_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(entry.content)

                stored_files.append(
                    StoredSnapshotArchiveFile(
                        path=logical_path.as_posix(),
                        extension=entry.extension,
                        language_hint=entry.language_hint,
                        size_bytes=len(entry.content),
                        content_sha256=hashlib.sha256(entry.content).hexdigest(),
                        archive_blob_path=blob_path.as_posix(),
                        included_by=entry.included_by,
                    )
                )
            if archive_root.exists():
                raise FileExistsError("같은 snapshot_id의 아카이브가 이미 존재합니다.")
            temp_root.replace(archive_root)
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise

        return StoredSnapshotArchive(
            snapshot_id=snapshot_id,
            archive_path=_to_project_relative_path(
                project_root=self._settings.project_root,
                absolute_path=archive_root,
            ),
            absolute_path=archive_root,
            files=tuple(stored_files),
        )


def _validate_relative_path(
    raw_path: str, *, allow_reserved_root_manifest: bool = False
) -> PurePosixPath:
    if not raw_path.strip():
        raise ValueError("스냅샷 파일 경로는 안전한 상대 경로여야 합니다.")
    safe_path = PurePosixPath(raw_path)
    if safe_path.is_absolute() or any(part in {"", ".", ".."} for part in safe_path.parts):
        raise ValueError("스냅샷 파일 경로는 안전한 상대 경로여야 합니다.")
    if not allow_reserved_root_manifest and safe_path.as_posix() == "manifest.json":
        raise ValueError("manifest.json은 루트 메타데이터 파일로 예약되어 있습니다.")
    return safe_path


def _normalize_entries(
    entries: tuple[SnapshotArchiveEntryDraft, ...]
) -> list[tuple[PurePosixPath, PurePosixPath, SnapshotArchiveEntryDraft]]:
    normalized_entries: list[tuple[PurePosixPath, PurePosixPath, SnapshotArchiveEntryDraft]] = []
    seen_paths: set[str] = set()
    seen_blob_paths: set[str] = set()

    for entry in entries:
        logical_path = _validate_relative_path(
            entry.path,
            allow_reserved_root_manifest=entry.archive_blob_path is not None,
        )
        blob_path = _validate_relative_path(entry.archive_blob_path or entry.path)
        collision_key = logical_path.as_posix().casefold()
        if collision_key in seen_paths:
            raise ValueError("중복된 스냅샷 파일 경로는 허용되지 않습니다.")
        seen_paths.add(collision_key)
        blob_collision_key = blob_path.as_posix().casefold()
        if blob_collision_key in seen_blob_paths:
            raise ValueError("중복된 아카이브 저장 경로는 허용되지 않습니다.")
        seen_blob_paths.add(blob_collision_key)
        normalized_entries.append((logical_path, blob_path, entry))

    return normalized_entries


def _to_project_relative_path(*, project_root: Path, absolute_path: Path) -> str:
    try:
        return absolute_path.relative_to(project_root).as_posix()
    except ValueError as error:
        raise ValueError(
            "스냅샷 아카이브 경로는 프로젝트 루트 아래에 있어야 합니다."
        ) from error
