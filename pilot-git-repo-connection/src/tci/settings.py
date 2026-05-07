from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import secrets

from cryptography.fernet import Fernet


DEFAULT_RUNTIME_DIRNAME = ".runtime"
DEFAULT_TEMPLATE_SUBPATH = Path("src") / "tci" / "web" / "templates"
DEFAULT_LOCAL_UPLOAD_MAX_COMPRESSED_BYTES = 250 * 1024 * 1024
DEFAULT_LOCAL_UPLOAD_MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
DEFAULT_LOCAL_UPLOAD_MAX_FILE_COUNT = 25_000
DEFAULT_LOCAL_UPLOAD_MAX_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_LOCAL_UPLOAD_MAX_PATH_SEGMENTS = 50
DEFAULT_LOCAL_UPLOAD_MAX_IN_MEMORY_BYTES = DEFAULT_LOCAL_UPLOAD_MAX_UNCOMPRESSED_BYTES


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
    operator_api_token: str | None
    operator_id: str
    operator_role: str
    gitlab_self_managed_allowed_hosts: tuple[str, ...]
    gitlab_webhook_trusted_proxy_hosts: tuple[str, ...]
    allow_insecure_gitlab_http: bool
    local_upload_max_compressed_bytes: int = DEFAULT_LOCAL_UPLOAD_MAX_COMPRESSED_BYTES
    local_upload_max_uncompressed_bytes: int = (
        DEFAULT_LOCAL_UPLOAD_MAX_UNCOMPRESSED_BYTES
    )
    local_upload_max_file_count: int = DEFAULT_LOCAL_UPLOAD_MAX_FILE_COUNT
    local_upload_max_file_bytes: int = DEFAULT_LOCAL_UPLOAD_MAX_FILE_BYTES
    local_upload_max_path_segments: int = DEFAULT_LOCAL_UPLOAD_MAX_PATH_SEGMENTS
    local_upload_max_in_memory_bytes: int = DEFAULT_LOCAL_UPLOAD_MAX_IN_MEMORY_BYTES

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

    environment = os.getenv("TCI_ENV", "development")
    return Settings(
        project_root=project_root,
        environment=environment,
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
        operator_api_token=_validate_operator_api_token(
            os.getenv("TCI_OPERATOR_API_TOKEN"),
            environment=environment,
        ),
        operator_id=_validate_operator_identity(
            os.getenv("TCI_OPERATOR_ID"),
            default="operator",
            label="TCI_OPERATOR_ID",
        ),
        operator_role=_validate_operator_role(os.getenv("TCI_OPERATOR_ROLE")),
        gitlab_self_managed_allowed_hosts=_parse_allowed_hosts(
            os.getenv("TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS")
        ),
        gitlab_webhook_trusted_proxy_hosts=_parse_allowed_hosts(
            os.getenv("TCI_GITLAB_WEBHOOK_TRUSTED_PROXY_HOSTS"),
            strip_port=True,
        ),
        allow_insecure_gitlab_http=_parse_bool(
            os.getenv("TCI_ALLOW_INSECURE_GITLAB_HTTP")
        ),
        local_upload_max_compressed_bytes=_parse_positive_int(
            os.getenv("TCI_LOCAL_UPLOAD_MAX_COMPRESSED_BYTES"),
            default=DEFAULT_LOCAL_UPLOAD_MAX_COMPRESSED_BYTES,
            label="TCI_LOCAL_UPLOAD_MAX_COMPRESSED_BYTES",
        ),
        local_upload_max_uncompressed_bytes=_parse_positive_int(
            os.getenv("TCI_LOCAL_UPLOAD_MAX_UNCOMPRESSED_BYTES"),
            default=DEFAULT_LOCAL_UPLOAD_MAX_UNCOMPRESSED_BYTES,
            label="TCI_LOCAL_UPLOAD_MAX_UNCOMPRESSED_BYTES",
        ),
        local_upload_max_file_count=_parse_positive_int(
            os.getenv("TCI_LOCAL_UPLOAD_MAX_FILE_COUNT"),
            default=DEFAULT_LOCAL_UPLOAD_MAX_FILE_COUNT,
            label="TCI_LOCAL_UPLOAD_MAX_FILE_COUNT",
        ),
        local_upload_max_file_bytes=_parse_positive_int(
            os.getenv("TCI_LOCAL_UPLOAD_MAX_FILE_BYTES"),
            default=DEFAULT_LOCAL_UPLOAD_MAX_FILE_BYTES,
            label="TCI_LOCAL_UPLOAD_MAX_FILE_BYTES",
        ),
        local_upload_max_path_segments=_parse_positive_int(
            os.getenv("TCI_LOCAL_UPLOAD_MAX_PATH_SEGMENTS"),
            default=DEFAULT_LOCAL_UPLOAD_MAX_PATH_SEGMENTS,
            label="TCI_LOCAL_UPLOAD_MAX_PATH_SEGMENTS",
        ),
        local_upload_max_in_memory_bytes=_parse_positive_int(
            os.getenv("TCI_LOCAL_UPLOAD_MAX_IN_MEMORY_BYTES"),
            default=DEFAULT_LOCAL_UPLOAD_MAX_IN_MEMORY_BYTES,
            label="TCI_LOCAL_UPLOAD_MAX_IN_MEMORY_BYTES",
        ),
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


def _validate_operator_api_token(
    raw_value: str | None, *, environment: str = "development"
) -> str | None:
    if raw_value is None:
        return None
    token = raw_value.strip()
    if not token:
        return None
    if len(token) < 16:
        raise RuntimeError("TCI_OPERATOR_API_TOKEN은 16자 이상이어야 합니다.")
    if not secrets.compare_digest(token, raw_value):
        raise RuntimeError("TCI_OPERATOR_API_TOKEN에는 앞뒤 공백을 사용할 수 없습니다.")
    if environment != "development":
        allowed_characters = (
            "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "-_"
        )
        if len(token) < 43 or any(
            character not in allowed_characters for character in token
        ):
            raise RuntimeError(
                "production TCI_OPERATOR_API_TOKEN은 32바이트 이상 난수의 "
                "base64url 인코딩 값이어야 합니다."
            )
    return token


def _validate_operator_identity(
    raw_value: str | None, *, default: str, label: str
) -> str:
    value = default if raw_value is None else raw_value.strip()
    if not value:
        raise RuntimeError(f"{label}는 비워둘 수 없습니다.")
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise RuntimeError(f"{label}에는 공백 또는 제어 문자를 사용할 수 없습니다.")
    return value


def _validate_operator_role(raw_value: str | None) -> str:
    value = "viewer" if raw_value is None else raw_value.strip().lower()
    if value not in {"viewer", "owner", "admin"}:
        raise RuntimeError(
            "TCI_OPERATOR_ROLE은 viewer, owner, admin 중 하나여야 합니다."
        )
    return value


def _parse_allowed_hosts(
    raw_value: str | None, *, strip_port: bool = False
) -> tuple[str, ...]:
    if not raw_value:
        return ()
    return tuple(
        _normalize_allowed_host(host, strip_port=strip_port)
        for host in raw_value.split(",")
        if host.strip()
    )


def _normalize_allowed_host(raw_host: str, *, strip_port: bool = False) -> str:
    host = raw_host.strip().lower()
    if host.startswith("["):
        bracket_end = host.find("]")
        if bracket_end != -1:
            address = host[1:bracket_end].rstrip(".")
            suffix = host[bracket_end + 1 :]
            if strip_port or not suffix:
                return address
            if suffix.startswith(":") and suffix[1:].isdecimal():
                return f"{address}:{suffix[1:]}"
    hostname, separator, port = host.rpartition(":")
    if separator and port.isdecimal() and host.count(":") == 1:
        if strip_port:
            return hostname.rstrip(".")
        return f"{hostname.rstrip('.')}:{port}"
    return host.rstrip(".")


def _parse_bool(raw_value: str | None) -> bool:
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_positive_int(raw_value: str | None, *, default: int, label: str) -> int:
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{label}는 양의 정수여야 합니다.") from error
    if value <= 0:
        raise RuntimeError(f"{label}는 양의 정수여야 합니다.")
    return value
