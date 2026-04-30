from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol
import uuid
from urllib.parse import urlsplit, urlunsplit

from tci.infrastructure.persistence.models import RepositoryProvider


@dataclass(frozen=True, slots=True)
class RepositoryCandidateProjection:
    id: str
    workspace_id: uuid.UUID
    provider: RepositoryProvider
    provider_scope: str
    remote_url: str | None
    repository_owner: str
    repository_name: str
    provider_project_path: str
    access_status: str
    provider_instance_url: str | None = None


class RepositoryCandidateSource(Protocol):
    def list_candidates(
        self, *, workspace_id: uuid.UUID, provider: RepositoryProvider | None
    ) -> tuple[RepositoryCandidateProjection, ...]:
        pass


class RepositoryCandidateConnection(Protocol):
    id: uuid.UUID
    provider: RepositoryProvider
    provider_project_path: str | None
    provider_instance_url: str | None


class RepositoryCandidateConnectionRepository(Protocol):
    def list_for_workspace(
        self, *, workspace_id: uuid.UUID
    ) -> Sequence[RepositoryCandidateConnection]:
        pass


class RepositoryCandidateDependencies(Protocol):
    repository_candidate_source: RepositoryCandidateSource | None
    session_factory: Callable[[], AbstractContextManager[object]] | None
    repository_connection_repository_factory: Callable[
        [object], RepositoryCandidateConnectionRepository
    ]


def list_repository_candidates(
    *,
    workspace_id: uuid.UUID,
    provider: RepositoryProvider | None,
    dependencies: RepositoryCandidateDependencies,
) -> dict[str, object]:
    candidate_source = dependencies.repository_candidate_source
    if candidate_source is None:
        return _empty_response(empty_reason="provider_not_configured")

    candidates = candidate_source.list_candidates(
        workspace_id=workspace_id,
        provider=provider,
    )
    scoped_candidates = tuple(
        candidate for candidate in candidates if candidate.workspace_id == workspace_id
    )
    if not scoped_candidates:
        return _empty_response(empty_reason="no_accessible_repositories")

    if dependencies.session_factory is None:
        raise RuntimeError(
            "저장소 후보 목록을 조회하려면 데이터베이스 세션이 필요합니다."
        )

    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        existing_connections = connection_repository.list_for_workspace(
            workspace_id=workspace_id
        )

    return {
        "items": [
            _serialize_candidate(
                candidate,
                existing_connection=_find_existing_connection(
                    candidate=candidate,
                    existing_connections=existing_connections,
                ),
            )
            for candidate in scoped_candidates
        ],
        "manualUrlAllowed": True,
        "emptyReason": "none",
        "guidance": "후보를 선택하거나 수동 URL 입력을 사용할 수 있습니다.",
    }


def _empty_response(*, empty_reason: str) -> dict[str, object]:
    return {
        "items": [],
        "manualUrlAllowed": True,
        "emptyReason": empty_reason,
        "guidance": "설정된 provider 후보가 없어 수동 URL 입력을 사용할 수 있습니다.",
    }


def _serialize_candidate(
    candidate: RepositoryCandidateProjection,
    *,
    existing_connection: RepositoryCandidateConnection | None,
) -> dict[str, object]:
    already_connected = existing_connection is not None
    return {
        "id": candidate.id,
        "provider": candidate.provider.value,
        "providerScope": candidate.provider_scope,
        "remoteUrl": _safe_remote_url(candidate.remote_url),
        "repositoryOwner": candidate.repository_owner,
        "repositoryName": candidate.repository_name,
        "providerProjectPath": candidate.provider_project_path,
        "canonicalRepositoryKey": _canonical_repository_key(candidate),
        "alreadyConnected": already_connected,
        "existingConnectionId": (
            None if existing_connection is None else str(existing_connection.id)
        ),
        "selectable": not already_connected and candidate.access_status == "available",
        "accessStatus": candidate.access_status,
    }


def _find_existing_connection(
    *,
    candidate: RepositoryCandidateProjection,
    existing_connections: Sequence[RepositoryCandidateConnection],
) -> RepositoryCandidateConnection | None:
    for connection in existing_connections:
        if connection.provider is not candidate.provider:
            continue
        if connection.provider_project_path != candidate.provider_project_path:
            continue
        if (
            candidate.provider is RepositoryProvider.GITLAB_SELF_MANAGED
            and connection.provider_instance_url != candidate.provider_instance_url
        ):
            continue
        return connection
    return None


def _canonical_repository_key(candidate: RepositoryCandidateProjection) -> str:
    if candidate.provider is RepositoryProvider.GITLAB_SELF_MANAGED:
        instance = candidate.provider_instance_url or candidate.provider_scope
        return (
            f"{candidate.provider.value}:{instance}:{candidate.provider_project_path}"
        )
    return f"{candidate.provider.value}:{candidate.provider_project_path}"


def _safe_remote_url(remote_url: str | None) -> str | None:
    if remote_url is None:
        return None
    try:
        parsed = urlsplit(remote_url)
        parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.hostname is None:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    if _contains_unsafe_url_text(parsed.netloc) or _contains_unsafe_url_text(
        parsed.path
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _contains_unsafe_url_text(value: str) -> bool:
    if any(character.isspace() or ord(character) < 32 for character in value):
        return True
    lowered = value.lower()
    return "%0a" in lowered or "%0d" in lowered
