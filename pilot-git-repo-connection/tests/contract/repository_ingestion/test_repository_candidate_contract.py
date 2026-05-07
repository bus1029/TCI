from __future__ import annotations

from dataclasses import dataclass
from typing import cast
import uuid

from fastapi import FastAPI

from tci.domain.services.list_repository_candidates import RepositoryCandidateProjection
from tci.infrastructure.persistence.models import RepositoryProvider
from tests.support.repository_connection_testkit import (
    create_test_client,
    seed_active_workspace,
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


def test_list_repository_candidates_returns_manual_url_empty_state(tmp_path) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_active_workspace(store, workspace_id=workspace_id)

    response = client.get("/api/repository-candidates?provider=github_cloud")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "manualUrlAllowed": True,
        "emptyReason": "provider_not_configured",
        "guidance": "설정된 provider 후보가 없어 수동 URL 입력을 사용할 수 있습니다.",
    }


def test_list_repository_candidates_returns_configured_provider_scope(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_active_workspace(_store, workspace_id=workspace_id)
    app = cast(FastAPI, client.app)
    object.__setattr__(
        app.state.dependencies,
        "repository_candidate_source",
        StaticCandidateSource(
            (
                RepositoryCandidateProjection(
                    id="github:acme/sample-repo",
                    workspace_id=workspace_id,
                    provider=RepositoryProvider.GITHUB_CLOUD,
                    provider_scope="acme",
                    remote_url="https://github.com/acme/sample-repo.git",
                    repository_owner="acme",
                    repository_name="sample-repo",
                    provider_project_path="acme/sample-repo",
                    access_status="available",
                ),
            )
        ),
    )

    response = client.get("/api/repository-candidates?provider=github_cloud")

    assert response.status_code == 200
    assert response.json() == {
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
                "alreadyConnected": False,
                "existingConnectionId": None,
                "selectable": True,
                "accessStatus": "available",
            }
        ],
        "manualUrlAllowed": True,
        "emptyReason": "none",
        "guidance": "후보를 선택하거나 수동 URL 입력을 사용할 수 있습니다.",
    }
