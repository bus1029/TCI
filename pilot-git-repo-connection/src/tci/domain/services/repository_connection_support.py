from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import logging
import os
import re
import secrets
import shlex
import socket
import subprocess
import tempfile
import textwrap
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Protocol
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

from tci.api.problem_details import ProblemCode
from tci.infrastructure.git.git_command_env import git_command_environment
from tci.infrastructure.persistence.models import (
    CredentialRevisionStatus,
    CredentialType,
    DefaultRefType,
    RepositoryProvider,
    RepositoryTransport,
)


class RepositoryConnectionProblem(RuntimeError):
    def __init__(self, code: ProblemCode, message: str | None = None) -> None:
        definition_message = message or None
        super().__init__(definition_message or code.value)
        self.problem_code = code
        self.detail = message


ConnectionOrigin = dict[str, object]


@dataclass(frozen=True, slots=True)
class RepositoryIdentity:
    provider: RepositoryProvider
    provider_instance_url: str | None
    provider_project_path: str
    canonical_key: str


@dataclass(frozen=True, slots=True)
class OperationCredential:
    credential_type: CredentialType
    encrypted_secret: str


class OperationCredentialRevision(Protocol):
    credential_type: CredentialType
    encrypted_secret: str
    read_only_validated: bool
    status: CredentialRevisionStatus


_SSH_CREDENTIAL_BIND_LOCK = Lock()
_ASKPASS_READY_TIMEOUT_SECONDS = 1.0
_LOGGER = logging.getLogger(__name__)


def build_connection_origin(connection) -> ConnectionOrigin:
    planning_input_reference_id = getattr(
        connection, "planning_input_reference_id", None
    )
    planning_input_reference = matching_workspace_planning_input_reference(connection)
    if planning_input_reference_id is None:
        return {
            "kind": "workspace_repository",
            "hasLegacyPlanningTrace": False,
            "compatibilityState": "normal",
            "message": "워크스페이스에서 직접 생성된 저장소 연결입니다.",
        }
    if planning_input_reference is not None:
        return {
            "kind": "legacy_planning",
            "hasLegacyPlanningTrace": True,
            "compatibilityState": "legacy_trace_preserved",
            "message": "기존 planning trace가 보존된 저장소 연결입니다.",
        }
    return {
        "kind": "legacy_unassigned",
        "hasLegacyPlanningTrace": False,
        "compatibilityState": "workspace_assignment_unclear",
        "message": "기존 planning trace를 확인할 수 없어 호환성 확인이 필요합니다.",
    }


def matching_workspace_planning_input_reference(connection):
    planning_input_reference = getattr(connection, "planning_input_reference", None)
    if planning_input_reference is None:
        return None
    if getattr(planning_input_reference, "workspace_id", None) != getattr(
        connection, "workspace_id", None
    ):
        return None
    return planning_input_reference


def build_repository_identity(
    *,
    provider: RepositoryProvider,
    provider_instance_url: str | None,
    provider_project_path: str,
) -> RepositoryIdentity:
    normalized_project_path = _normalize_provider_project_path(provider_project_path)
    if provider is RepositoryProvider.GITHUB_CLOUD:
        normalized_project_path = normalized_project_path.lower()
        return RepositoryIdentity(
            provider=provider,
            provider_instance_url=None,
            provider_project_path=normalized_project_path,
            canonical_key=f"{provider.value}:{normalized_project_path}",
        )
    if provider is RepositoryProvider.GITLAB_SELF_MANAGED:
        normalized_instance_url = _normalize_provider_instance_url(
            provider_instance_url
        )
        if normalized_instance_url is None:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "GitLab Self-Managed identity requires provider_instance_url.",
            )
        return RepositoryIdentity(
            provider=provider,
            provider_instance_url=normalized_instance_url,
            provider_project_path=normalized_project_path,
            canonical_key=(
                f"{provider.value}:{normalized_instance_url}:"
                f"{normalized_project_path}"
            ),
        )
    raise RepositoryConnectionProblem(ProblemCode.UNSUPPORTED_PROVIDER)


def _normalize_provider_project_path(provider_project_path: str) -> str:
    normalized_path = provider_project_path.strip().strip("/").removesuffix(".git")
    if (
        not normalized_path
        or "/" not in normalized_path
        or "//" in normalized_path
        or any(
            character.isspace() or ord(character) < 32 for character in normalized_path
        )
        or any(segment in ("", ".", "..") for segment in normalized_path.split("/"))
    ):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "Repository identity requires a normalized provider_project_path.",
        )
    return normalized_path


def _normalize_provider_instance_url(provider_instance_url: str | None) -> str | None:
    if provider_instance_url is None:
        return None
    parsed_instance = urlparse(provider_instance_url.strip())
    if parsed_instance.scheme not in {"http", "https"}:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "Repository identity requires an http or https provider_instance_url.",
        )
    hostname = parsed_instance.hostname
    if hostname is None:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "Repository identity requires provider_instance_url host.",
        )
    try:
        port = parsed_instance.port
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "Repository identity requires a valid provider_instance_url port.",
        ) from error
    instance_url = f"{parsed_instance.scheme}://{hostname.lower().rstrip('.')}"
    if port is not None and not _is_default_url_port(
        scheme=parsed_instance.scheme,
        port=port,
    ):
        instance_url = f"{instance_url}:{port}"
    return instance_url


def _is_default_url_port(*, scheme: str, port: int) -> bool:
    return (scheme == "https" and port == 443) or (scheme == "http" and port == 80)


def parse_provider(raw_value: str) -> RepositoryProvider:
    try:
        return RepositoryProvider(raw_value)
    except ValueError as error:
        raise RepositoryConnectionProblem(ProblemCode.UNSUPPORTED_PROVIDER) from error


def parse_transport(raw_value: str) -> RepositoryTransport:
    try:
        return RepositoryTransport(raw_value)
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "transport는 ssh, https 또는 http여야 합니다.",
        ) from error


def parse_default_ref_type(raw_value: str) -> DefaultRefType:
    try:
        return DefaultRefType(raw_value)
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "defaultRefType은 branch 또는 tag여야 합니다.",
        ) from error


def parse_credential_type(raw_value: str) -> CredentialType:
    try:
        return CredentialType(raw_value)
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "credential.type은 ssh_private_key 또는 https_pat여야 합니다.",
        ) from error


def require_active_operation_credential(
    credential_revision: OperationCredentialRevision | None,
) -> OperationCredential:
    if credential_revision is None:
        raise _missing_operation_credential_problem()

    if credential_revision.status is not CredentialRevisionStatus.ACTIVE:
        raise _missing_operation_credential_problem()
    if not credential_revision.read_only_validated:
        raise _missing_operation_credential_problem()

    if not credential_revision.encrypted_secret:
        raise _missing_operation_credential_problem()

    return OperationCredential(
        credential_type=credential_revision.credential_type,
        encrypted_secret=credential_revision.encrypted_secret,
    )


def _missing_operation_credential_problem() -> RepositoryConnectionProblem:
    return RepositoryConnectionProblem(
        ProblemCode.CONNECTION_AUTH_FAILED,
        "활성 워크스페이스 읽기 전용 자격 증명을 찾을 수 없습니다.",
    )


def hash_secret_for_storage(secret: str) -> str:
    # fingerprint 표시값은 원문 대신 해시 기반 표현으로 고정한다.
    return sha256(secret.encode("utf-8")).hexdigest()


def encrypt_secret_for_storage(secret: str, *, settings) -> str:
    return _build_fernet(settings).encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret_from_storage(encrypted_secret: str, *, settings) -> str:
    try:
        return (
            _build_fernet(settings)
            .decrypt(encrypted_secret.encode("utf-8"))
            .decode("utf-8")
        )
    except InvalidToken as error:
        raise RepositoryConnectionProblem(
            ProblemCode.CONNECTION_AUTH_FAILED,
            "저장된 자격 증명을 복호화할 수 없습니다.",
        ) from error


def derive_fingerprint(*, secret: str, provided_fingerprint: str | None) -> str:
    if provided_fingerprint:
        # 클라이언트가 보낸 fingerprint를 그대로 저장하지 않고 서버 기준 표현으로 고정한다.
        return f"provided:{hash_secret_for_storage(provided_fingerprint)[:12]}"
    return f"sha256:{hash_secret_for_storage(secret)[:12]}"


def ensure_gitlab_self_managed_host_allowed(
    *,
    provider: RepositoryProvider,
    provider_instance_url: str | None,
    settings,
    transport: RepositoryTransport | None = None,
    remote_url: str | None = None,
    remote_port: int | None = None,
) -> None:
    if provider is not RepositoryProvider.GITLAB_SELF_MANAGED:
        return
    if provider_instance_url is None:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
        )
    parsed_instance = urlparse(provider_instance_url)
    uses_http_remote = (
        parsed_instance.scheme == "http"
        or transport is RepositoryTransport.HTTP
        or (remote_url is not None and remote_url.startswith("http://"))
    )
    uses_http_family_remote = transport in (
        RepositoryTransport.HTTP,
        RepositoryTransport.HTTPS,
    ) or (remote_url is not None and remote_url.startswith(("http://", "https://")))
    if uses_http_remote and not getattr(settings, "allow_insecure_gitlab_http", False):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "GitLab Self-Managed HTTP 연결은 TCI_ALLOW_INSECURE_GITLAB_HTTP=true일 때만 허용됩니다.",
        )
    hostname = (parsed_instance.hostname or "").lower().rstrip(".")
    effective_port = (
        remote_port
        if remote_port is not None
        else (
            _extract_remote_port(remote_url)
            if remote_url is not None
            else parsed_instance.port
        )
    )
    if effective_port is not None and uses_http_family_remote:
        effective_scheme = (
            "http"
            if (
                parsed_instance.scheme == "http"
                or transport is RepositoryTransport.HTTP
                or (remote_url is not None and remote_url.startswith("http://"))
            )
            else "https"
        )
        if _is_default_url_port(scheme=effective_scheme, port=effective_port):
            effective_port = None
    allowed_origin = (
        hostname if effective_port is None else f"{hostname}:{effective_port}"
    )
    allowed_hosts = tuple(
        host.lower().rstrip(".")
        for host in getattr(settings, "gitlab_self_managed_allowed_hosts", ())
    )
    if allowed_origin not in allowed_hosts:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "GitLab Self-Managed host는 허용 목록에 등록되어야 합니다.",
        )


def _extract_remote_port(remote_url: str | None) -> int | None:
    if remote_url is None:
        return None
    if (
        remote_url.startswith("ssh://")
        or remote_url.startswith("https://")
        or remote_url.startswith("http://")
    ):
        try:
            return urlparse(remote_url).port
        except ValueError:
            return None
    return None


@contextmanager
def bind_git_credential(
    *,
    remote_url: str,
    transport: RepositoryTransport,
    credential_type: CredentialType,
    credential_secret: str,
):
    if transport in (RepositoryTransport.HTTPS, RepositoryTransport.HTTP):
        if credential_type is not CredentialType.HTTPS_PAT:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "http 또는 https 연결에는 https_pat 자격 증명이 필요합니다.",
            )
        with _https_askpass_environment(credential_secret=credential_secret) as env:
            with git_command_environment(env):
                yield remote_url
        return

    if credential_type is not CredentialType.SSH_PRIVATE_KEY:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "ssh 연결에는 ssh_private_key 자격 증명이 필요합니다.",
        )

    with _SSH_CREDENTIAL_BIND_LOCK:
        agent_env = _start_ssh_agent()
        try:
            _add_ssh_private_key_to_agent(
                credential_secret=credential_secret,
                agent_env=agent_env,
            )
            ssh_command = (
                "ssh -F /dev/null -oIdentitiesOnly=yes "
                f"-oIdentityAgent={shlex.quote(agent_env['SSH_AUTH_SOCK'])} "
                "-oIdentityFile=none"
            )
            with git_command_environment({"GIT_SSH_COMMAND": ssh_command}):
                yield remote_url
        finally:
            _stop_ssh_agent(agent_env)


@contextmanager
def _https_askpass_environment(*, credential_secret: str):
    with tempfile.TemporaryDirectory(prefix="tci-git-askpass-") as temp_dir:
        temp_path = Path(temp_dir)
        socket_path = temp_path / "askpass.sock"
        script_path = temp_path / "askpass.py"
        stop_event = Event()
        ready_event = Event()
        startup_errors: list[BaseException] = []
        auth_token = secrets.token_urlsafe(32)
        server_thread = Thread(
            target=_serve_https_askpass,
            kwargs={
                "socket_path": socket_path,
                "credential_secret": credential_secret,
                "stop_event": stop_event,
                "ready_event": ready_event,
                "startup_errors": startup_errors,
                "auth_token": auth_token,
            },
            daemon=True,
        )
        script_path.write_text(_ASKPASS_SCRIPT, encoding="utf-8")
        script_path.chmod(0o700)
        server_thread.start()
        try:
            if not ready_event.wait(timeout=_ASKPASS_READY_TIMEOUT_SECONDS):
                raise RepositoryConnectionProblem(
                    ProblemCode.CONNECTION_AUTH_FAILED,
                    "Git askpass helper를 시작할 수 없습니다.",
                )
            if startup_errors:
                raise RepositoryConnectionProblem(
                    ProblemCode.CONNECTION_AUTH_FAILED,
                    "Git askpass helper를 시작할 수 없습니다.",
                ) from startup_errors[0]
            yield {
                "GIT_ASKPASS": str(script_path),
                "TCI_GIT_ASKPASS_SOCKET": str(socket_path),
                "TCI_GIT_ASKPASS_TOKEN": auth_token,
            }
        finally:
            stop_event.set()
            _poke_askpass_socket(socket_path)
            server_thread.join(timeout=1)


_ASKPASS_SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os
    import socket
    import sys

    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    request = "username" if "username" in prompt.lower() else "password"
    with socket.socket(socket.AF_UNIX) as client:
        client.connect(os.environ["TCI_GIT_ASKPASS_SOCKET"])
        client.sendall(
            os.environ["TCI_GIT_ASKPASS_TOKEN"].encode("utf-8")
            + b"\\0"
            + request.encode("utf-8")
        )
        sys.stdout.write(client.recv(65536).decode("utf-8"))
    """
)


def _serve_https_askpass(
    *,
    socket_path: Path,
    credential_secret: str,
    stop_event: Event,
    ready_event: Event,
    startup_errors: list[BaseException],
    auth_token: str,
) -> None:
    try:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(socket_path))
            server.listen()
            server.settimeout(0.2)
            ready_event.set()
            while not stop_event.is_set():
                try:
                    connection, _address = server.accept()
                except TimeoutError:
                    continue
                with connection:
                    raw_request = connection.recv(512).decode("utf-8")
                    request_auth_token, separator, request = raw_request.partition("\0")
                    if separator != "\0" or request_auth_token != auth_token:
                        continue
                    response = (
                        "x-access-token\n"
                        if request == "username"
                        else f"{credential_secret}\n"
                    )
                    try:
                        connection.sendall(response.encode("utf-8"))
                    except OSError:
                        continue
    except OSError as error:
        if not ready_event.is_set():
            startup_errors.append(error)
            ready_event.set()


def _poke_askpass_socket(socket_path: Path) -> None:
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.1)
            client.connect(str(socket_path))
            client.sendall(b"stop")
    except OSError:
        return


def _start_ssh_agent() -> dict[str, str]:
    completed = subprocess.run(
        ("ssh-agent", "-s"),
        capture_output=True,
        check=False,
        text=True,
        env=_minimal_subprocess_env(),
    )
    if completed.returncode != 0:
        raise RepositoryConnectionProblem(
            ProblemCode.CONNECTION_AUTH_FAILED,
            "SSH agent를 시작할 수 없습니다.",
        )
    agent_env = _parse_ssh_agent_output(completed.stdout)
    if "SSH_AUTH_SOCK" not in agent_env or "SSH_AGENT_PID" not in agent_env:
        raise RepositoryConnectionProblem(
            ProblemCode.CONNECTION_AUTH_FAILED,
            "SSH agent 환경을 확인할 수 없습니다.",
        )
    return agent_env


def _parse_ssh_agent_output(output: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ("SSH_AUTH_SOCK", "SSH_AGENT_PID"):
        match = re.search(rf"{key}=([^;]+);", output)
        if match is not None:
            env[key] = match.group(1)
    return env


def _add_ssh_private_key_to_agent(
    *, credential_secret: str, agent_env: dict[str, str]
) -> None:
    completed = subprocess.run(
        ("ssh-add", "-"),
        input=(
            credential_secret
            if credential_secret.endswith("\n")
            else f"{credential_secret}\n"
        ),
        capture_output=True,
        check=False,
        text=True,
        env={**_minimal_subprocess_env(), **agent_env},
    )
    if completed.returncode != 0:
        raise RepositoryConnectionProblem(
            ProblemCode.CONNECTION_AUTH_FAILED,
            "SSH private key를 agent에 등록할 수 없습니다.",
        )


def _stop_ssh_agent(agent_env: dict[str, str]) -> None:
    try:
        completed = subprocess.run(
            ("ssh-agent", "-k"),
            capture_output=True,
            check=False,
            text=True,
            env={**_minimal_subprocess_env(), **agent_env},
        )
    except OSError:
        _LOGGER.warning("ssh-agent cleanup command failed", exc_info=True)
        return
    if completed.returncode != 0:
        _LOGGER.warning(
            "ssh-agent cleanup returned non-zero status",
            extra={"returncode": completed.returncode},
        )


def _minimal_subprocess_env() -> dict[str, str]:
    allowed_keys = (
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "TMPDIR",
        "XDG_CONFIG_HOME",
    )
    return {
        **{key: value for key, value in os.environ.items() if key in allowed_keys},
        "GIT_TERMINAL_PROMPT": "0",
    }


def _build_fernet(settings) -> Fernet:
    key = getattr(settings, "credential_encryption_key", None)
    if not key:
        raise RepositoryConnectionProblem(
            ProblemCode.CONNECTION_AUTH_FAILED,
            "저장소 자격 증명을 사용할 수 없습니다.",
        )
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.CONNECTION_AUTH_FAILED,
            "저장소 자격 증명을 사용할 수 없습니다.",
        ) from error
