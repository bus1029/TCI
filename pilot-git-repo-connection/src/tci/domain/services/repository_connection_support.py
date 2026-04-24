from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import shlex
import tempfile
from threading import Lock
from urllib.parse import quote, urlparse

from cryptography.fernet import Fernet, InvalidToken

from tci.api.problem_details import ProblemCode
from tci.infrastructure.persistence.models import (
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


_SSH_CREDENTIAL_BIND_LOCK = Lock()


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
            "transport는 ssh 또는 https여야 합니다.",
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
    if remote_url.startswith("ssh://") or remote_url.startswith("https://"):
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
    if transport is RepositoryTransport.HTTPS:
        if credential_type is not CredentialType.HTTPS_PAT:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                "https 연결에는 https_pat 자격 증명이 필요합니다.",
            )
        quoted_secret = quote(credential_secret, safe="")
        yield remote_url.replace("https://", f"https://x-access-token:{quoted_secret}@")
        return

    if credential_type is not CredentialType.SSH_PRIVATE_KEY:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "ssh 연결에는 ssh_private_key 자격 증명이 필요합니다.",
        )

    file_descriptor, raw_path = tempfile.mkstemp(prefix="tci-git-key-")
    os.close(file_descriptor)
    key_file = Path(raw_path)
    previous_ssh_command = os.environ.get("GIT_SSH_COMMAND")
    with _SSH_CREDENTIAL_BIND_LOCK:
        try:
            key_file.write_text(credential_secret, encoding="utf-8")
            key_file.chmod(0o600)
            os.environ["GIT_SSH_COMMAND"] = (
                f"ssh -i {shlex.quote(str(key_file))} -oIdentitiesOnly=yes"
            )
            yield remote_url
        finally:
            if previous_ssh_command is None:
                os.environ.pop("GIT_SSH_COMMAND", None)
            else:
                os.environ["GIT_SSH_COMMAND"] = previous_ssh_command
            key_file.unlink(missing_ok=True)


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
