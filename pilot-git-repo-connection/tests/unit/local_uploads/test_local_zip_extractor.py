from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from tests.support.local_upload_testkit import (
    ZipFixtureEntry,
    build_corrupt_zip,
    build_empty_zip,
    build_encrypted_zip_header,
    build_project_zip,
    build_zip_bytes,
    build_zip_with_absolute_path,
    build_zip_with_duplicate_logical_paths,
    build_zip_with_reserved_manifest,
    build_zip_with_traversal_path,
)
from tci.settings import Settings


def _settings(tmp_path: Path, **overrides: int) -> Settings:
    runtime_root = tmp_path / ".runtime"
    return Settings(
        project_root=tmp_path,
        environment="test",
        runtime_root=runtime_root,
        git_mirror_root=runtime_root / "git-mirrors",
        code_snapshot_root=runtime_root / "code-snapshots",
        template_root=tmp_path / "src" / "tci" / "web" / "templates",
        database_url=None,
        redis_url=None,
        credential_encryption_key=None,
        operator_api_token="test-operator-token",
        operator_id="operator",
        operator_role="admin",
        gitlab_self_managed_allowed_hosts=(),
        gitlab_webhook_trusted_proxy_hosts=(),
        allow_insecure_gitlab_http=False,
        local_upload_max_compressed_bytes=overrides.get("compressed", 10_000),
        local_upload_max_uncompressed_bytes=overrides.get("uncompressed", 10_000),
        local_upload_max_file_count=overrides.get("file_count", 100),
        local_upload_max_file_bytes=overrides.get("file_bytes", 10_000),
        local_upload_max_path_segments=overrides.get("path_segments", 50),
        local_upload_max_in_memory_bytes=overrides.get("memory", 10_000),
    )


def test_local_zip_extractor_returns_snapshot_entry_drafts(tmp_path: Path) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import extract_local_zip

    result = extract_local_zip(
        zip_bytes=build_zip_bytes(
            (
                ZipFixtureEntry("project/empty/", is_directory=True),
                ZipFixtureEntry("project/README.md", b"# Example\n"),
                ZipFixtureEntry("project/src/main.py", b"print('hello')\n"),
                ZipFixtureEntry("project/.env.example", b"DEBUG=false\n"),
            )
        ),
        settings=_settings(tmp_path),
    )

    assert result.file_count == 3
    assert result.directory_count == 3
    assert result.directory_paths == ("project", "project/empty", "project/src")
    assert result.total_uncompressed_bytes == 37
    assert [entry.path for entry in result.entries] == [
        "project/.env.example",
        "project/README.md",
        "project/src/main.py",
    ]
    assert result.entries[2].extension == ".py"
    assert result.entries[2].content == b"print('hello')\n"


def test_local_zip_preflight_validates_metadata_without_reading_file_content(
    monkeypatch, tmp_path: Path
) -> None:
    import tci.infrastructure.snapshots.local_zip_extractor as extractor

    def fail_read(*args, **kwargs):
        raise AssertionError("preflight should not read ZIP entry content")

    monkeypatch.setattr(extractor.ZipFile, "read", fail_read)

    extractor.preflight_local_zip(
        zip_bytes=build_project_zip(),
        settings=_settings(tmp_path),
    )


@pytest.mark.parametrize(
    ("zip_bytes", "code"),
    (
        (build_corrupt_zip(), "corrupt_zip"),
        (build_zip_with_traversal_path(), "unsafe_zip_path"),
        (build_zip_with_absolute_path(), "unsafe_zip_path"),
        (build_encrypted_zip_header(), "encrypted_zip_entry"),
        (build_zip_with_duplicate_logical_paths(), "duplicate_zip_path"),
        (build_zip_with_reserved_manifest(), "reserved_manifest"),
        (build_empty_zip(), "empty_zip"),
    ),
)
def test_local_zip_extractor_rejects_invalid_archives(
    tmp_path: Path, zip_bytes: bytes, code: str
) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import (
        LocalZipValidationError,
        extract_local_zip,
    )

    with pytest.raises(LocalZipValidationError) as error:
        extract_local_zip(zip_bytes=zip_bytes, settings=_settings(tmp_path))

    assert error.value.code == code


@pytest.mark.parametrize(
    ("zip_bytes", "overrides"),
    (
        (
            build_zip_bytes((ZipFixtureEntry("big.txt", b"12345"),)),
            {"file_bytes": 4},
        ),
        (
            build_zip_bytes(
                (
                    ZipFixtureEntry("one.txt", b"1"),
                    ZipFixtureEntry("two.txt", b"2"),
                )
            ),
            {"file_count": 1},
        ),
        (
            build_zip_bytes((ZipFixtureEntry("one.txt", b"12345"),)),
            {"uncompressed": 4},
        ),
        (
            build_zip_bytes((ZipFixtureEntry("a/b/c/d.txt", b"1"),)),
            {"path_segments": 3},
        ),
        (
            build_zip_bytes(
                (
                    ZipFixtureEntry("one/", is_directory=True),
                    ZipFixtureEntry("two/", is_directory=True),
                    ZipFixtureEntry("file.txt", b"1"),
                )
            ),
            {"file_count": 1},
        ),
    ),
)
def test_local_zip_extractor_enforces_configured_limits(
    tmp_path: Path, zip_bytes: bytes, overrides: dict[str, int]
) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import (
        LocalZipValidationError,
        extract_local_zip,
    )

    with pytest.raises(LocalZipValidationError) as error:
        extract_local_zip(
            zip_bytes=zip_bytes,
            settings=_settings(tmp_path, **overrides),
        )

    assert error.value.code == "zip_limit_exceeded"


def test_local_zip_extractor_rejects_compressed_upload_limit(tmp_path: Path) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import (
        LocalZipValidationError,
        extract_local_zip,
    )

    with pytest.raises(LocalZipValidationError) as error:
        extract_local_zip(
            zip_bytes=build_project_zip(),
            settings=_settings(tmp_path, compressed=10),
        )

    assert error.value.code == "zip_limit_exceeded"


@pytest.mark.parametrize(
    "entry_path",
    ("", ".", "./file.txt", "dir/.", "dir//file.txt", "C:foo/bar.txt"),
)
def test_local_zip_extractor_rejects_empty_or_dot_path_segments(
    tmp_path: Path, entry_path: str
) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import (
        LocalZipValidationError,
        extract_local_zip,
    )

    with pytest.raises(LocalZipValidationError) as error:
        extract_local_zip(
            zip_bytes=_build_raw_zip(entry_path, b"bad"),
            settings=_settings(tmp_path),
        )

    assert error.value.code == "unsafe_zip_path"


def test_local_zip_extractor_rejects_excessive_compression_ratio(
    tmp_path: Path,
) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import (
        LocalZipValidationError,
        extract_local_zip,
    )

    with pytest.raises(LocalZipValidationError) as error:
        extract_local_zip(
            zip_bytes=build_zip_bytes((ZipFixtureEntry("bomb.txt", b"a" * 20_000),)),
            settings=_settings(tmp_path, uncompressed=30_000, file_bytes=30_000),
        )

    assert error.value.code == "zip_limit_exceeded"


def _build_raw_zip(path: str, content: bytes) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(path, content)
    return buffer.getvalue()


def test_local_zip_extractor_rejects_in_memory_limit(tmp_path: Path) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import (
        LocalZipValidationError,
        extract_local_zip,
    )

    with pytest.raises(LocalZipValidationError) as error:
        extract_local_zip(
            zip_bytes=build_zip_bytes((ZipFixtureEntry("file.txt", b"12345"),)),
            settings=_settings(tmp_path, memory=4),
        )

    assert error.value.code == "zip_limit_exceeded"


@pytest.mark.parametrize(
    "entries",
    (
        (
            ZipFixtureEntry("project", b"file"),
            ZipFixtureEntry("project/main.py", b"print('hello')\n"),
        ),
        (
            ZipFixtureEntry("project/", is_directory=True),
            ZipFixtureEntry("project", b"file"),
        ),
    ),
)
def test_local_zip_extractor_rejects_file_directory_path_collisions(
    tmp_path: Path, entries: tuple[ZipFixtureEntry, ...]
) -> None:
    from tci.infrastructure.snapshots.local_zip_extractor import (
        LocalZipValidationError,
        extract_local_zip,
    )

    with pytest.raises(LocalZipValidationError) as error:
        extract_local_zip(
            zip_bytes=build_zip_bytes(entries),
            settings=_settings(tmp_path),
        )

    assert error.value.code == "duplicate_zip_path"
