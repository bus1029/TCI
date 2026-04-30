from __future__ import annotations

import uuid
from typing import Any, cast

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    decrypt_secret_from_storage,
)
from tci.infrastructure.git.git_readonly_validator import ReadonlyProbeResult
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
)
from tci.domain.services.list_repository_candidates import RepositoryCandidateProjection
from tci.infrastructure.persistence.models import RepositoryProvider


class _CandidateSourceWithPersonalGrant:
    personal_grant_secret = "personal-provider-token"

    def __init__(self, *, project_path: str = "acme/sample-repo") -> None:
        self.project_path = project_path
        self.call_count = 0

    def list_candidates(self, *, workspace_id: uuid.UUID, provider):
        self.call_count += 1
        repository_owner, _, repository_name = self.project_path.rpartition("/")
        return (
            RepositoryCandidateProjection(
                id="candidate-1",
                workspace_id=workspace_id,
                provider=RepositoryProvider.GITHUB_CLOUD,
                provider_scope="github:acme",
                remote_url=(
                    "https://personal-provider-token@github.com/acme/sample-repo.git"
                ),
                repository_owner=repository_owner,
                repository_name=repository_name,
                provider_project_path=self.project_path,
                access_status="available",
            ),
        )


def _dependencies(client) -> Any:
    return cast(Any, client.app).state.dependencies


def _settings(client) -> Any:
    return cast(Any, client.app).state.settings


def test_candidate_personal_grant_is_not_persisted_as_operation_credential(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    candidate_source = _CandidateSourceWithPersonalGrant()
    object.__setattr__(
        _dependencies(client),
        "repository_candidate_source",
        candidate_source,
    )
    payload = create_connection_payload(credential_secret="workspace-readonly-token")
    payload["candidateId"] = "candidate-1"

    response = client.post("/api/repository-connections", json=payload)

    assert response.status_code == 201
    assert candidate_source.call_count == 1
    assert len(store.credentials) == 1
    stored_credential = next(iter(store.credentials.values()))
    persisted_secret = decrypt_secret_from_storage(
        stored_credential.encrypted_secret,
        settings=_settings(client),
    )
    assert persisted_secret == "workspace-readonly-token"
    assert persisted_secret != "personal-provider-token"
    assert stored_credential.display_fingerprint != "personal-provider-token"


def test_invalid_shared_readonly_credential_with_candidate_has_no_side_effects(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    object.__setattr__(
        _dependencies(client),
        "repository_candidate_source",
        _CandidateSourceWithPersonalGrant(),
    )
    store.readonly_probe_result = ReadonlyProbeResult(
        is_read_only=False,
        problem_code=ProblemCode.READ_WRITE_CREDENTIAL_NOT_ALLOWED,
        detail="워크스페이스 공유 읽기 전용 자격 증명이 아닙니다.",
    )
    payload = create_connection_payload(credential_secret="workspace-secret")
    payload["candidateId"] = "candidate-1"

    response = client.post("/api/repository-connections", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "code": "READ_WRITE_CREDENTIAL_NOT_ALLOWED",
        "message": "워크스페이스 공유 읽기 전용 자격 증명이 아닙니다.",
    }
    assert store.connections == {}
    assert store.credentials == {}
    assert store.repository_events == {}
    assert store.sync_runs == {}
    assert "workspace-secret" not in response.text
    assert "personal-provider-token" not in response.text


def test_candidate_selected_create_rejects_identity_mismatch_without_side_effects(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    candidate_source = _CandidateSourceWithPersonalGrant(project_path="other/repo")
    object.__setattr__(
        _dependencies(client),
        "repository_candidate_source",
        candidate_source,
    )
    payload = create_connection_payload(credential_secret="workspace-secret")
    payload["candidateId"] = "candidate-1"

    response = client.post("/api/repository-connections", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "선택한 후보 저장소와 제출된 저장소 URL이 일치하지 않습니다.",
    }
    assert candidate_source.call_count == 1
    assert store.connections == {}
    assert store.credentials == {}
    assert store.sync_runs == {}


def test_candidate_selected_create_requires_configured_candidate_source(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    payload = create_connection_payload(credential_secret="workspace-secret")
    payload["candidateId"] = "candidate-1"

    response = client.post("/api/repository-connections", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_INPUT",
        "message": "선택한 후보 저장소를 확인할 수 없습니다.",
    }
    assert store.connections == {}
    assert store.credentials == {}
    assert store.sync_runs == {}
