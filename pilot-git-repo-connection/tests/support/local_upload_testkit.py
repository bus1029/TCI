from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


@dataclass(frozen=True, slots=True)
class ZipFixtureEntry:
    path: str
    content: bytes = b""
    is_directory: bool = False


def build_zip_bytes(entries: tuple[ZipFixtureEntry, ...]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for entry in entries:
            path = _zip_path(entry.path, is_directory=entry.is_directory)
            if entry.is_directory:
                archive.writestr(path, b"")
            else:
                archive.writestr(path, entry.content)
    return buffer.getvalue()


def build_project_zip() -> bytes:
    return build_zip_bytes(
        (
            ZipFixtureEntry("project/README.md", b"# Example\n"),
            ZipFixtureEntry("project/src/main.py", b"print('hello')\n"),
            ZipFixtureEntry("project/.env.example", b"DEBUG=false\n"),
        )
    )


def build_zip_with_traversal_path() -> bytes:
    return build_zip_bytes((ZipFixtureEntry("../escape.py", b"pass\n"),))


def build_zip_with_absolute_path() -> bytes:
    return build_zip_bytes((ZipFixtureEntry("/tmp/escape.py", b"pass\n"),))


def build_zip_with_reserved_manifest() -> bytes:
    return build_zip_bytes((ZipFixtureEntry("manifest.json", b"{}"),))


def build_zip_with_duplicate_logical_paths() -> bytes:
    return build_zip_bytes(
        (
            ZipFixtureEntry("src/App.py", b"print('one')\n"),
            ZipFixtureEntry("src/app.py", b"print('two')\n"),
        )
    )


def build_encrypted_zip_header() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        info = ZipInfo("secret.txt")
        archive.writestr(info, b"secret")
    return _mark_first_zip_entry_encrypted(buffer.getvalue())


def _zip_path(path: str, *, is_directory: bool) -> str:
    normalized = PurePosixPath(path).as_posix()
    if is_directory and not normalized.endswith("/"):
        return f"{normalized}/"
    return normalized


def _mark_first_zip_entry_encrypted(zip_bytes: bytes) -> bytes:
    patched = bytearray(zip_bytes)
    local_header = patched.find(b"PK\x03\x04")
    central_header = patched.find(b"PK\x01\x02")
    if local_header == -1 or central_header == -1:
        raise ValueError("ZIP header signatures were not found.")

    _set_general_purpose_flag(patched, offset=local_header + 6)
    _set_general_purpose_flag(patched, offset=central_header + 8)
    return bytes(patched)


def _set_general_purpose_flag(buffer: bytearray, *, offset: int) -> None:
    current_value = int.from_bytes(buffer[offset : offset + 2], "little")
    buffer[offset : offset + 2] = (current_value | 0x1).to_bytes(2, "little")
