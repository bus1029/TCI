from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
import re
from urllib.parse import ParseResult, urlparse

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
)
from tci.infrastructure.persistence.models import (
    RepositoryProvider,
    RepositoryTransport,
)


@dataclass(frozen=True, slots=True)
class ParsedRepositoryRemote:
    owner: str
    name: str
    provider_instance_url: str | None
    provider_project_path: str
    provider_remote_port: int | None = None


_GITHUB_HTTPS_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?$"
)
_GITHUB_SSH_PATTERN = re.compile(
    r"^git@github\.com:(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?$"
)
_GITLAB_SSH_PATTERN = re.compile(
    r"^git@(?P<host>[^:/?#]+):(?P<project_path>[^?#]+?)(?:\.git)?$"
)
_HOSTNAME_PATTERN = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$"
)
_INVALID_HOST_MESSAGE = "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다."


def parse_repository_remote(
    *,
    provider: RepositoryProvider,
    remote_url: str,
    transport: RepositoryTransport,
) -> ParsedRepositoryRemote:
    if provider is RepositoryProvider.GITHUB_CLOUD:
        return _parse_github_remote(remote_url=remote_url, transport=transport)
    if provider is RepositoryProvider.GITLAB_SELF_MANAGED:
        return _parse_gitlab_remote(remote_url=remote_url, transport=transport)
    raise RepositoryConnectionProblem(ProblemCode.UNSUPPORTED_PROVIDER)


def _parse_github_remote(
    *, remote_url: str, transport: RepositoryTransport
) -> ParsedRepositoryRemote:
    if transport is RepositoryTransport.HTTP:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "remoteUrl은 GitHub Cloud 저장소 주소여야 합니다.",
        )
    pattern = (
        _GITHUB_HTTPS_PATTERN
        if transport is RepositoryTransport.HTTPS
        else _GITHUB_SSH_PATTERN
    )
    match = pattern.match(remote_url)
    if match is None:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "remoteUrl은 GitHub Cloud 저장소 주소여야 합니다.",
        )
    owner = match.group("owner")
    name = match.group("name")
    return ParsedRepositoryRemote(
        owner=owner,
        name=name,
        provider_instance_url=None,
        provider_project_path=f"{owner}/{name}",
    )


def _parse_gitlab_remote(
    *, remote_url: str, transport: RepositoryTransport
) -> ParsedRepositoryRemote:
    if _has_whitespace_or_control(remote_url):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            _INVALID_HOST_MESSAGE,
        )
    if transport in (RepositoryTransport.HTTPS, RepositoryTransport.HTTP):
        parsed_remote = _parse_url(remote_url)
        expected_scheme = "http" if transport is RepositoryTransport.HTTP else "https"
        if (
            parsed_remote.scheme != expected_scheme
            or _parse_url_hostname(parsed_remote) is None
            or parsed_remote.username is not None
            or parsed_remote.password is not None
            or parsed_remote.params
            or parsed_remote.query
            or parsed_remote.fragment
        ):
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                _INVALID_HOST_MESSAGE,
            )
        hostname = _parse_url_hostname(parsed_remote)
        if hostname is None:
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                _INVALID_HOST_MESSAGE,
            )
        hostname = _normalize_host(hostname)
        if not _is_valid_gitlab_host(hostname) or _is_github_host(hostname):
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                _INVALID_HOST_MESSAGE,
            )
        instance_url = f"{expected_scheme}://{hostname}"
        parsed_port = _parse_url_port(parsed_remote)
        if parsed_port is not None:
            instance_url = f"{instance_url}:{parsed_port}"
        return _build_gitlab_remote(
            instance_url=instance_url,
            project_path=_normalize_project_path(parsed_remote.path),
            remote_port=parsed_port,
        )

    ssh_match = _GITLAB_SSH_PATTERN.match(remote_url)
    if ssh_match is not None:
        hostname = _normalize_host(ssh_match.group("host"))
        if not _is_valid_gitlab_host(hostname) or _is_github_host(hostname):
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                _INVALID_HOST_MESSAGE,
            )
        instance_url = f"https://{hostname}"
        return _build_gitlab_remote(
            instance_url=instance_url,
            project_path=_normalize_project_path(ssh_match.group("project_path")),
        )

    parsed_remote = _parse_url(remote_url)
    parsed_hostname = _parse_url_hostname(parsed_remote)
    if parsed_remote.scheme == "ssh" and parsed_hostname is not None:
        if (
            parsed_remote.username != "git"
            or parsed_remote.password is not None
            or parsed_remote.params
            or parsed_remote.query
            or parsed_remote.fragment
        ):
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                _INVALID_HOST_MESSAGE,
            )
        hostname = _normalize_host(parsed_hostname)
        if not _is_valid_gitlab_host(hostname) or _is_github_host(hostname):
            raise RepositoryConnectionProblem(
                ProblemCode.INVALID_INPUT,
                _INVALID_HOST_MESSAGE,
            )
        parsed_port = _parse_url_port(parsed_remote)
        instance_url = f"https://{hostname}"
        return _build_gitlab_remote(
            instance_url=instance_url,
            project_path=_normalize_project_path(parsed_remote.path),
            remote_port=parsed_port,
        )

    raise RepositoryConnectionProblem(
        ProblemCode.INVALID_INPUT,
        _INVALID_HOST_MESSAGE,
    )


def _build_gitlab_remote(
    *, instance_url: str, project_path: str, remote_port: int | None = None
) -> ParsedRepositoryRemote:
    namespace, _, name = project_path.rpartition("/")
    return ParsedRepositoryRemote(
        owner=namespace,
        name=name,
        provider_instance_url=instance_url,
        provider_project_path=project_path,
        provider_remote_port=remote_port,
    )


def _normalize_project_path(raw_path: str) -> str:
    project_path = raw_path.lstrip("/").removesuffix(".git")
    segments = project_path.split("/")
    if (
        len(segments) < 2
        or any(not segment for segment in segments)
        or any(segment in (".", "..") for segment in segments)
        or any(character.isspace() or ord(character) < 32 for character in project_path)
        or project_path.endswith("/")
    ):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            _INVALID_HOST_MESSAGE,
        )
    return project_path


def _is_valid_gitlab_host(hostname: str) -> bool:
    if not hostname or hostname.startswith("-") or _has_whitespace_or_control(hostname):
        return False
    try:
        parsed_ip = ip_address(hostname)
    except ValueError:
        return bool(_HOSTNAME_PATTERN.fullmatch(hostname))
    if parsed_ip.version != 4:
        return False
    return True


def _normalize_host(hostname: str) -> str:
    return hostname.lower()


def _is_github_host(hostname: str) -> bool:
    return _normalize_host(hostname).rstrip(".") == "github.com"


def _parse_url_port(parsed_url: ParseResult) -> int | None:
    if parsed_url.netloc.rsplit("@", 1)[-1].endswith(":"):
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            _INVALID_HOST_MESSAGE,
        )
    try:
        return parsed_url.port
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            _INVALID_HOST_MESSAGE,
        ) from error


def _parse_url(remote_url: str) -> ParseResult:
    try:
        return urlparse(remote_url)
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            _INVALID_HOST_MESSAGE,
        ) from error


def _parse_url_hostname(parsed_url: ParseResult) -> str | None:
    try:
        return parsed_url.hostname
    except ValueError as error:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            _INVALID_HOST_MESSAGE,
        ) from error


def _has_whitespace_or_control(value: str) -> bool:
    return any(character.isspace() or ord(character) < 32 for character in value)
