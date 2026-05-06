from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast
import uuid

from tci.domain.services.list_repository_candidates import (
    RepositoryCandidateDependencies,
    RepositoryCandidateProjection,
    list_repository_candidates,
)
from tci.infrastructure.persistence.models import RepositoryProvider
from tests.support.repository_connection_testkit import (
    FakeRepositoryConnectionRepository,
    InMemoryRepositoryStore,
)
from tests.support.repository_first_connection_testkit import (
    build_workspace_repository_connection,
)


@dataclass(frozen=True, slots=True)
class StaticCandidateSource:
    candidates: tuple[RepositoryCandidateProjection, ...]

    def list_candidates(
        self, *, workspace_id: uuid.UUID, provider: RepositoryProvider | None
    ) -> tuple[RepositoryCandidateProjection, ...]:
        del workspace_id
        if provider is None:
            return self.candidates
        return tuple(
            candidate for candidate in self.candidates if candidate.provider is provider
        )


def test_candidate_service_marks_existing_repository_as_not_selectable() -> None:
    workspace_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    store = InMemoryRepositoryStore()
    existing = build_workspace_repository_connection(
        connection_id=connection_id,
        workspace_id=workspace_id,
    )
    store.connections[connection_id] = existing
    candidate = RepositoryCandidateProjection(
        id="github:acme/sample-repo",
        workspace_id=workspace_id,
        provider=RepositoryProvider.GITHUB_CLOUD,
        provider_scope="acme",
        remote_url="https://github.com/acme/sample-repo.git",
        repository_owner="acme",
        repository_name="sample-repo",
        provider_project_path="acme/sample-repo",
        access_status="available",
    )
    dependencies = cast(
        RepositoryCandidateDependencies,
        SimpleNamespace(
            repository_candidate_source=StaticCandidateSource((candidate,)),
            repository_connection_repository_factory=lambda session: (
                FakeRepositoryConnectionRepository(store)
            ),
            session_factory=lambda: _NullSession(),
        ),
    )

    result = list_repository_candidates(
        workspace_id=workspace_id,
        provider=RepositoryProvider.GITHUB_CLOUD,
        dependencies=dependencies,
    )

    assert result == {
        "items": [
            {
                "id": "github:acme/sample-repo",
                "provider": "github_cloud",
                "providerScope": "acme",
                "remoteUrl": "https://github.com/acme/sample-repo.git",
                "repositoryOwner": "acme",
                "repositoryName": "sample-repo",
                "providerProjectPath": "acme/sample-repo",
                "canonicalRepositoryKey": "github_cloud:acme/sample-repo",
                "alreadyConnected": True,
                "existingConnectionId": str(connection_id),
                "selectable": False,
                "accessStatus": "available",
            }
        ],
        "manualUrlAllowed": True,
        "emptyReason": "none",
        "guidance": "후보를 선택하거나 수동 URL 입력을 사용할 수 있습니다.",
    }


def test_candidate_service_filters_candidates_from_other_workspaces() -> None:
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    store = InMemoryRepositoryStore()
    candidate = RepositoryCandidateProjection(
        id="github:acme/sample-repo",
        workspace_id=other_workspace_id,
        provider=RepositoryProvider.GITHUB_CLOUD,
        provider_scope="acme",
        remote_url="https://github.com/acme/sample-repo.git",
        repository_owner="acme",
        repository_name="sample-repo",
        provider_project_path="acme/sample-repo",
        access_status="available",
    )
    dependencies = cast(
        RepositoryCandidateDependencies,
        SimpleNamespace(
            repository_candidate_source=StaticCandidateSource((candidate,)),
            repository_connection_repository_factory=lambda session: (
                FakeRepositoryConnectionRepository(store)
            ),
            session_factory=lambda: _NullSession(),
        ),
    )

    result = list_repository_candidates(
        workspace_id=workspace_id,
        provider=RepositoryProvider.GITHUB_CLOUD,
        dependencies=dependencies,
    )

    assert result["items"] == []
    assert result["emptyReason"] == "no_accessible_repositories"


def test_candidate_service_removes_secret_bearing_remote_urls() -> None:
    workspace_id = uuid.uuid4()
    store = InMemoryRepositoryStore()
    candidate = RepositoryCandidateProjection(
        id="github:acme/sample-repo",
        workspace_id=workspace_id,
        provider=RepositoryProvider.GITHUB_CLOUD,
        provider_scope="acme",
        remote_url="https://token@github.com/acme/sample-repo.git?access_token=secret",
        repository_owner="acme",
        repository_name="sample-repo",
        provider_project_path="acme/sample-repo",
        access_status="available",
    )
    dependencies = cast(
        RepositoryCandidateDependencies,
        SimpleNamespace(
            repository_candidate_source=StaticCandidateSource((candidate,)),
            repository_connection_repository_factory=lambda session: (
                FakeRepositoryConnectionRepository(store)
            ),
            session_factory=lambda: _NullSession(),
        ),
    )

    result = list_repository_candidates(
        workspace_id=workspace_id,
        provider=RepositoryProvider.GITHUB_CLOUD,
        dependencies=dependencies,
    )

    items = cast(list[dict[str, object]], result["items"])
    item = items[0]
    assert item["remoteUrl"] is None
    assert "token" not in str(result)
    assert "secret" not in str(result)


def test_candidate_service_removes_malformed_or_unsafe_remote_urls() -> None:
    workspace_id = uuid.uuid4()
    store = InMemoryRepositoryStore()
    candidates = tuple(
        RepositoryCandidateProjection(
            id=f"github:acme/sample-repo-{index}",
            workspace_id=workspace_id,
            provider=RepositoryProvider.GITHUB_CLOUD,
            provider_scope="acme",
            remote_url=remote_url,
            repository_owner="acme",
            repository_name=f"sample-repo-{index}",
            provider_project_path=f"acme/sample-repo-{index}",
            access_status="available",
        )
        for index, remote_url in enumerate(
            (
                "http://example.com:bad/path",
                "http://exa mple.com/path",
                "https://example.com/bad path.git",
                "javascript://example.com/%0aalert(1)",
                "https://github.com/acme/sample-repo.git#token",
            ),
            start=1,
        )
    )
    dependencies = cast(
        RepositoryCandidateDependencies,
        SimpleNamespace(
            repository_candidate_source=StaticCandidateSource(candidates),
            repository_connection_repository_factory=lambda session: (
                FakeRepositoryConnectionRepository(store)
            ),
            session_factory=lambda: _NullSession(),
        ),
    )

    result = list_repository_candidates(
        workspace_id=workspace_id,
        provider=RepositoryProvider.GITHUB_CLOUD,
        dependencies=dependencies,
    )

    items = cast(list[dict[str, object]], result["items"])
    assert [item["remoteUrl"] for item in items] == [None, None, None, None, None]


class _NullSession:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None
