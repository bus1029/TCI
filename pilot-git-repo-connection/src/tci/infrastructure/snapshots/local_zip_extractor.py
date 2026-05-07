from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import re
import stat
from zipfile import BadZipFile, ZipFile, ZipInfo

from tci.infrastructure.persistence.models import SnapshotInclusionReason
from tci.infrastructure.snapshots.snapshot_archive_store import (
    SnapshotArchiveEntryDraft,
)
from tci.settings import Settings


MAX_LOCAL_UPLOAD_COMPRESSION_RATIO = 100
_EOCD_SIGNATURE = b"PK\x05\x06"
_MAX_EOCD_SEARCH_BYTES = 65_557
_WINDOWS_DRIVE_PREFIX_PATTERN = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True, slots=True)
class LocalZipExtraction:
    entries: tuple[SnapshotArchiveEntryDraft, ...]
    directory_paths: tuple[str, ...]
    file_count: int
    directory_count: int
    total_uncompressed_bytes: int


class LocalZipValidationError(ValueError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def extract_local_zip(*, zip_bytes: bytes, settings: Settings) -> LocalZipExtraction:
    if len(zip_bytes) > settings.local_upload_max_compressed_bytes:
        _raise_limit("ZIP upload exceeds the compressed size limit.")
    _preflight_central_directory_count(zip_bytes=zip_bytes, settings=settings)

    try:
        with ZipFile(BytesIO(zip_bytes)) as archive:
            infos = archive.infolist()
            normalized = _validate_infos(infos=infos, settings=settings)
            entries = _read_entries(
                archive=archive,
                normalized=normalized,
                settings=settings,
            )
    except BadZipFile as error:
        raise LocalZipValidationError(
            code="corrupt_zip",
            message="ZIP 파일을 읽을 수 없습니다.",
        ) from error

    if not entries:
        raise LocalZipValidationError(
            code="empty_zip",
            message="ZIP 파일에 스냅샷으로 저장할 파일이 없습니다.",
        )

    directory_paths = _directory_paths(normalized)
    return LocalZipExtraction(
        entries=tuple(entry for _, entry in sorted(entries, key=lambda item: item[0])),
        directory_paths=tuple(sorted(directory_paths)),
        file_count=len(entries),
        directory_count=len(directory_paths),
        total_uncompressed_bytes=sum(len(entry.content) for _, entry in entries),
    )


def preflight_local_zip(*, zip_bytes: bytes, settings: Settings) -> None:
    if len(zip_bytes) > settings.local_upload_max_compressed_bytes:
        _raise_limit("ZIP upload exceeds the compressed size limit.")
    _preflight_central_directory_count(zip_bytes=zip_bytes, settings=settings)

    try:
        with ZipFile(BytesIO(zip_bytes)) as archive:
            normalized = _validate_infos(infos=archive.infolist(), settings=settings)
    except BadZipFile as error:
        raise LocalZipValidationError(
            code="corrupt_zip",
            message="ZIP 파일을 읽을 수 없습니다.",
        ) from error

    if not any(
        safe_path is not None and not info.is_dir() for info, safe_path in normalized
    ):
        raise LocalZipValidationError(
            code="empty_zip",
            message="ZIP 파일에 스냅샷으로 저장할 파일이 없습니다.",
        )


def _validate_infos(
    *, infos: list[ZipInfo], settings: Settings
) -> list[tuple[ZipInfo, PurePosixPath | None]]:
    normalized: list[tuple[ZipInfo, PurePosixPath | None]] = []
    seen_files: set[str] = set()
    seen_directories: set[str] = set()
    total_uncompressed = 0
    file_count = 0

    for info in infos:
        safe_path = _normalize_zip_path(info.filename)
        _reject_unsupported_entry(info)
        if _is_encrypted(info):
            raise LocalZipValidationError(
                code="encrypted_zip_entry",
                message="암호화된 ZIP 항목은 지원하지 않습니다.",
            )
        if len(safe_path.parts) > settings.local_upload_max_path_segments:
            _raise_limit("ZIP entry path exceeds the maximum nesting depth.")
        if safe_path.as_posix().casefold() == "manifest.json":
            raise LocalZipValidationError(
                code="reserved_manifest",
                message="manifest.json은 스냅샷 메타데이터 파일로 예약되어 있습니다.",
            )

        if info.is_dir():
            for index in range(1, len(safe_path.parts)):
                _add_directory_path(
                    seen_directories=seen_directories,
                    directory_path=PurePosixPath(*safe_path.parts[:index]),
                    settings=settings,
                )
            directory_key = _directory_key(safe_path)
            if directory_key in seen_files:
                raise LocalZipValidationError(
                    code="duplicate_zip_path",
                    message="ZIP 안에 파일과 디렉터리 경로가 충돌합니다.",
                )
            _add_directory_path(
                seen_directories=seen_directories,
                directory_path=safe_path,
                settings=settings,
            )
            normalized.append((info, safe_path))
            continue

        file_count += 1
        if file_count > settings.local_upload_max_file_count:
            _raise_limit("ZIP upload contains too many files.")
        if info.file_size > settings.local_upload_max_file_bytes:
            _raise_limit("ZIP entry exceeds the per-file size limit.")
        if _compression_ratio(info) > MAX_LOCAL_UPLOAD_COMPRESSION_RATIO:
            _raise_limit("ZIP entry compression ratio exceeds the safety limit.")
        total_uncompressed += info.file_size
        if total_uncompressed > settings.local_upload_max_uncompressed_bytes:
            _raise_limit("ZIP upload exceeds the uncompressed size limit.")
        if total_uncompressed > settings.local_upload_max_in_memory_bytes:
            _raise_limit("ZIP upload exceeds the in-memory processing limit.")
        for index in range(1, len(safe_path.parts)):
            parent_directory = PurePosixPath(*safe_path.parts[:index])
            if _directory_key(parent_directory) in seen_files:
                raise LocalZipValidationError(
                    code="duplicate_zip_path",
                    message="ZIP 안에 파일과 디렉터리 경로가 충돌합니다.",
                )
            _add_directory_path(
                seen_directories=seen_directories,
                directory_path=parent_directory,
                settings=settings,
            )

        collision_key = safe_path.as_posix().casefold()
        if collision_key in seen_files or collision_key in seen_directories:
            raise LocalZipValidationError(
                code="duplicate_zip_path",
                message="ZIP 안에 중복된 파일 경로가 있습니다.",
            )
        seen_files.add(collision_key)
        normalized.append((info, safe_path))

    return normalized


def _preflight_central_directory_count(*, zip_bytes: bytes, settings: Settings) -> None:
    tail = zip_bytes[-_MAX_EOCD_SEARCH_BYTES:]
    eocd_index = tail.rfind(_EOCD_SIGNATURE)
    if eocd_index < 0 or eocd_index + 22 > len(tail):
        return
    total_entries = int.from_bytes(tail[eocd_index + 10 : eocd_index + 12], "little")
    if total_entries == 0xFFFF:
        _raise_limit("ZIP64 archives with unbounded entry counts are not supported.")
    max_entries = settings.local_upload_max_file_count * 2
    if total_entries > max_entries:
        _raise_limit("ZIP upload contains too many entries.")


def _read_entries(
    *,
    archive: ZipFile,
    normalized: list[tuple[ZipInfo, PurePosixPath | None]],
    settings: Settings,
) -> list[tuple[str, SnapshotArchiveEntryDraft]]:
    entries: list[tuple[str, SnapshotArchiveEntryDraft]] = []
    total_read = 0

    for info, safe_path in normalized:
        if safe_path is None or info.is_dir():
            continue
        try:
            content = archive.read(info)
        except BadZipFile as error:
            raise LocalZipValidationError(
                code="corrupt_zip",
                message="ZIP 파일을 읽는 중 손상된 항목을 발견했습니다.",
            ) from error
        if len(content) > settings.local_upload_max_file_bytes:
            _raise_limit("ZIP entry exceeds the per-file size limit.")
        total_read += len(content)
        if total_read > settings.local_upload_max_uncompressed_bytes:
            _raise_limit("ZIP upload exceeds the uncompressed size limit.")
        if total_read > settings.local_upload_max_in_memory_bytes:
            _raise_limit("ZIP upload exceeds the in-memory processing limit.")
        entries.append(
            (
                safe_path.as_posix(),
                SnapshotArchiveEntryDraft(
                    path=safe_path.as_posix(),
                    content=content,
                    included_by=SnapshotInclusionReason.DEFAULT_POLICY,
                    extension=safe_path.suffix or None,
                    language_hint=_language_hint(safe_path),
                ),
            )
        )
    return entries


def _normalize_zip_path(raw_path: str) -> PurePosixPath:
    normalized_raw = raw_path.replace("\\", "/")
    path_without_trailing_slash = (
        normalized_raw[:-1] if normalized_raw.endswith("/") else normalized_raw
    )
    raw_parts = path_without_trailing_slash.split("/")
    if (
        "\x00" in normalized_raw
        or not path_without_trailing_slash
        or _WINDOWS_DRIVE_PREFIX_PATTERN.match(path_without_trailing_slash)
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise LocalZipValidationError(
            code="unsafe_zip_path",
            message="ZIP 항목 경로가 안전하지 않습니다.",
        )
    path = PurePosixPath(normalized_raw)
    if path.is_absolute():
        raise LocalZipValidationError(
            code="unsafe_zip_path",
            message="ZIP 항목 경로는 안전한 상대 경로여야 합니다.",
        )
    if path.parts and _WINDOWS_DRIVE_PREFIX_PATTERN.match(path.parts[0]):
        raise LocalZipValidationError(
            code="unsafe_zip_path",
            message="ZIP 항목 경로는 안전한 상대 경로여야 합니다.",
        )
    return path


def _reject_unsupported_entry(info: ZipInfo) -> None:
    mode = info.external_attr >> 16
    if mode == 0:
        return
    file_type = stat.S_IFMT(mode)
    if file_type in {0, stat.S_IFREG, stat.S_IFDIR}:
        return
    raise LocalZipValidationError(
        code="unsupported_zip_entry",
        message="ZIP 안의 특수 파일 항목은 지원하지 않습니다.",
    )


def _is_encrypted(info: ZipInfo) -> bool:
    return bool(info.flag_bits & 0x1)


def _compression_ratio(info: ZipInfo) -> float:
    if info.file_size == 0:
        return 0
    if info.compress_size == 0:
        return float("inf")
    return info.file_size / info.compress_size


def _add_directory_path(
    *,
    seen_directories: set[str],
    directory_path: PurePosixPath,
    settings: Settings,
) -> None:
    seen_directories.add(_directory_key(directory_path))
    if len(seen_directories) > settings.local_upload_max_file_count:
        _raise_limit("ZIP upload contains too many directories.")


def _directory_key(directory_path: PurePosixPath) -> str:
    return directory_path.as_posix().rstrip("/").casefold()


def _directory_paths(
    normalized: list[tuple[ZipInfo, PurePosixPath | None]]
) -> set[str]:
    directories: set[str] = set()
    for info, safe_path in normalized:
        if safe_path is None:
            continue
        if info.is_dir():
            for index in range(1, len(safe_path.parts)):
                directories.add(PurePosixPath(*safe_path.parts[:index]).as_posix())
            directories.add(safe_path.as_posix().rstrip("/"))
            continue
        for index in range(1, len(safe_path.parts)):
            directories.add(PurePosixPath(*safe_path.parts[:index]).as_posix())
    directories.discard("")
    return directories


def _language_hint(path: PurePosixPath) -> str | None:
    return {
        ".md": "markdown",
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(path.suffix.lower())


def _raise_limit(message: str) -> None:
    raise LocalZipValidationError(
        code="zip_limit_exceeded",
        message=message,
    )
