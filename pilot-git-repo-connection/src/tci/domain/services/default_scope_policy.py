from __future__ import annotations

from pathlib import PurePosixPath


V1_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
HARD_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        ".next",
        "coverage",
        "target",
        "vendor",
    }
)


def is_hard_excluded_path(path: str) -> bool:
    pure_path = PurePosixPath(path)
    return any(part in HARD_EXCLUDED_DIRECTORY_NAMES for part in pure_path.parts)


def is_binary_content(content: bytes) -> bool:
    return b"\x00" in content


def exceeds_v1_size_limit(*, size_bytes: int, max_file_size_bytes: int) -> bool:
    return size_bytes > max_file_size_bytes
