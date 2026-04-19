from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from cryptography.fernet import Fernet


DEFAULT_RUNTIME_DIRNAME = ".runtime"
DEFAULT_TEMPLATE_SUBPATH = Path("src") / "tci" / "web" / "templates"


def _resolve_path(raw_value: str | None, *, default: Path, base_dir: Path) -> Path:
    if not raw_value:
        return default

    candidate = Path(raw_value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    return (base_dir / candidate).resolve()


def _detect_project_root() -> Path:
    explicit_root = os.getenv("TCI_PROJECT_ROOT")
    if explicit_root:
        resolved_root = Path(explicit_root).expanduser().resolve()
        if not resolved_root.is_dir():
            raise RuntimeError(
                "TCI_PROJECT_ROOT는 존재하는 디렉터리를 가리켜야 합니다."
            )
        return resolved_root

    module_dir = Path(__file__).resolve().parent
    for candidate in (module_dir, *module_dir.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate

    current_dir = Path.cwd().resolve()
    for candidate in (current_dir, *current_dir.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate

    raise RuntimeError(
        "프로젝트 루트를 자동으로 찾을 수 없습니다. TCI_PROJECT_ROOT를 설정하세요."
    )


def _ensure_path_within_project_root(
    path: Path, *, label: str, project_root: Path
) -> Path:
    try:
        path.relative_to(project_root)
    except ValueError as error:
        raise RuntimeError(f"{label}는 프로젝트 루트 아래에 있어야 합니다.") from error
    return path


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    environment: str
    runtime_root: Path
    git_mirror_root: Path
    code_snapshot_root: Path
    template_root: Path
    database_url: str | None
    redis_url: str | None
    credential_encryption_key: str | None

    def runtime_directories(self) -> tuple[Path, Path, Path]:
        return (
            self.runtime_root,
            self.git_mirror_root,
            self.code_snapshot_root,
        )


def load_settings() -> Settings:
    project_root = _detect_project_root()
    runtime_root = _ensure_path_within_project_root(
        _resolve_path(
            os.getenv("TCI_RUNTIME_ROOT"),
            default=project_root / DEFAULT_RUNTIME_DIRNAME,
            base_dir=project_root,
        ),
        label="TCI_RUNTIME_ROOT",
        project_root=project_root,
    )
    git_mirror_root = _ensure_path_within_project_root(
        _resolve_path(
            os.getenv("TCI_GIT_MIRROR_ROOT"),
            default=runtime_root / "git-mirrors",
            base_dir=project_root,
        ),
        label="TCI_GIT_MIRROR_ROOT",
        project_root=project_root,
    )
    code_snapshot_root = _ensure_path_within_project_root(
        _resolve_path(
            os.getenv("TCI_CODE_SNAPSHOT_ROOT"),
            default=runtime_root / "code-snapshots",
            base_dir=project_root,
        ),
        label="TCI_CODE_SNAPSHOT_ROOT",
        project_root=project_root,
    )
    credential_encryption_key = _validate_credential_encryption_key(
        os.getenv("TCI_CREDENTIAL_ENCRYPTION_KEY")
    )

    return Settings(
        project_root=project_root,
        environment=os.getenv("TCI_ENV", "development"),
        runtime_root=runtime_root,
        git_mirror_root=git_mirror_root,
        code_snapshot_root=code_snapshot_root,
        template_root=_resolve_path(
            os.getenv("TCI_TEMPLATE_ROOT"),
            default=project_root / DEFAULT_TEMPLATE_SUBPATH,
            base_dir=project_root,
        ),
        database_url=os.getenv("TCI_DATABASE_URL"),
        redis_url=os.getenv("TCI_REDIS_URL"),
        credential_encryption_key=credential_encryption_key,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def _validate_credential_encryption_key(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    try:
        Fernet(raw_value.encode("utf-8"))
    except ValueError as error:
        raise RuntimeError(
            "TCI_CREDENTIAL_ENCRYPTION_KEY는 유효한 Fernet 키 형식이어야 합니다."
        ) from error
    return raw_value
