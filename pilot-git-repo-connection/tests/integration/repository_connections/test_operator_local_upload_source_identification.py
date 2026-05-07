from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import cast

from fastapi import FastAPI

from tests.support.local_upload_testkit import build_project_zip
from tests.support.repository_connection_testkit import (
    create_connection_payload,
    create_test_client,
    now_utc,
    seed_planning_input_reference,
)
from tci.domain.services.list_repository_candidates import (
    RepositoryCandidateProjection,
)
from tci.infrastructure.persistence.models import (
    LocalUpload,
    LocalUploadStatus,
    RepositoryProvider,
    Workspace,
    WorkspaceStatus,
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


def test_operator_connections_page_identifies_repository_and_local_upload_sources(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(_store, workspace_id=workspace_id)
    _create_connection(client, provider="github_cloud")
    _create_connection(
        client,
        provider="gitlab_self_managed",
        remote_url="https://gitlab.example.com/group/sample-repo.git",
    )
    upload_response = client.post(
        "/api/local-uploads",
        files={"file": ("local-project.zip", build_project_zip(), "application/zip")},
    )
    assert upload_response.status_code == 201

    response = client.get(f"/connections?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "저장소 연결 출처" in response.text
    assert "제공자: github_cloud" in response.text
    assert "제공자: gitlab_self_managed" in response.text
    assert "Local Upload 출처" in response.text
    assert "local-project.zip" in response.text
    assert str(upload_response.json()["latestSnapshotId"]) in response.text
    assert "Local Upload는 저장소 연결이 아닙니다." in response.text


def test_operator_connection_detail_keeps_local_upload_source_separate(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    seed_planning_input_reference(store, workspace_id=workspace_id)
    connection_response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(),
    )
    upload_response = client.post(
        "/api/local-uploads",
        files={"file": ("local-project.zip", build_project_zip(), "application/zip")},
    )
    assert connection_response.status_code == 201
    assert upload_response.status_code == 201

    response = client.get(
        f"/connections/{connection_response.json()['id']}?workspaceId={workspace_id}"
    )

    assert response.status_code == 200
    assert "저장소 연결 상세" in response.text
    assert "Local Upload 출처" in response.text
    assert "local-project.zip" in response.text
    assert str(upload_response.json()["latestSnapshotId"]) in response.text
    assert "Local Upload는 저장소 연결이 아닙니다." in response.text


def test_operator_connections_page_hides_local_upload_rows_for_deleted_workspace(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    app = cast(FastAPI, client.app)
    object.__setattr__(
        app.state.dependencies,
        "repository_candidate_source",
        StaticCandidateSource(
            (
                RepositoryCandidateProjection(
                    id="github:acme/private-repo",
                    workspace_id=workspace_id,
                    provider=RepositoryProvider.GITHUB_CLOUD,
                    provider_scope="acme",
                    remote_url="https://github.com/acme/private-repo.git",
                    repository_owner="acme",
                    repository_name="private-repo",
                    provider_project_path="acme/private-repo",
                    access_status="available",
                ),
            )
        ),
    )
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.DELETED,
        created_at=now_utc(),
        updated_at=now_utc(),
        deleted_at=now_utc(),
        deleted_by="operator",
    )
    store.local_uploads[upload_id] = LocalUpload(
        id=upload_id,
        workspace_id=workspace_id,
        status=LocalUploadStatus.SUCCEEDED,
        original_filename_display="retained-local-project.zip",
        upload_sha256="a" * 64,
        compressed_size_bytes=100,
        uncompressed_size_bytes=100,
        file_count=1,
        directory_count=1,
        latest_snapshot_id=uuid.uuid4(),
        created_by="operator",
        created_at=now_utc(),
        completed_at=now_utc(),
    )

    response = client.get(f"/connections?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "등록된 저장소 연결이 없습니다." in response.text
    assert "등록된 Local Upload가 없습니다." in response.text
    assert "retained-local-project.zip" not in response.text
    assert "private-repo" not in response.text
    assert "선택 가능" not in response.text
    assert str(upload_id) not in response.text


def test_operator_connection_post_does_not_resolve_candidates_for_deleted_workspace(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    app = cast(FastAPI, client.app)
    object.__setattr__(
        app.state.dependencies,
        "repository_candidate_source",
        StaticCandidateSource(
            (
                RepositoryCandidateProjection(
                    id="github:acme/private-repo",
                    workspace_id=workspace_id,
                    provider=RepositoryProvider.GITHUB_CLOUD,
                    provider_scope="acme",
                    remote_url="https://github.com/acme/private-repo.git",
                    repository_owner="acme",
                    repository_name="private-repo",
                    provider_project_path="acme/private-repo",
                    access_status="available",
                ),
            )
        ),
    )
    store.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.DELETED,
        created_at=now_utc(),
        updated_at=now_utc(),
        deleted_at=now_utc(),
        deleted_by="operator",
    )

    response = client.post(
        f"/connections?workspaceId={workspace_id}",
        headers={"Origin": str(client.base_url).rstrip("/")},
        data={
            "candidateId": "github:acme/private-repo",
            "provider": "github_cloud",
            "remoteUrl": "",
            "transport": "https",
            "defaultRefType": "branch",
            "defaultRefName": "main",
            "credentialType": "https_pat",
            "credentialSecret": "readonly-token-value",
            "credentialFingerprint": "pat-01",
        },
    )

    assert response.status_code == 409
    assert "활성 워크스페이스에서만 저장소 연결을 생성할 수 있습니다." in response.text
    assert "private-repo" not in response.text
    assert "https://github.com/acme/private-repo.git" not in response.text
    assert "선택 가능" not in response.text
    assert store.connections == {}


def test_operator_connections_page_does_not_render_candidates_for_missing_workspace(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, _store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    app = cast(FastAPI, client.app)
    object.__setattr__(
        app.state.dependencies,
        "repository_candidate_source",
        StaticCandidateSource(
            (
                RepositoryCandidateProjection(
                    id="github:acme/private-repo",
                    workspace_id=workspace_id,
                    provider=RepositoryProvider.GITHUB_CLOUD,
                    provider_scope="acme",
                    remote_url="https://github.com/acme/private-repo.git",
                    repository_owner="acme",
                    repository_name="private-repo",
                    provider_project_path="acme/private-repo",
                    access_status="available",
                ),
            )
        ),
    )

    response = client.get(f"/connections?workspaceId={workspace_id}")

    assert response.status_code == 200
    assert "등록된 저장소 연결이 없습니다." in response.text
    assert "private-repo" not in response.text
    assert "https://github.com/acme/private-repo.git" not in response.text
    assert "선택 가능" not in response.text


def test_operator_connection_post_does_not_create_from_candidate_for_missing_workspace(
    tmp_path,
) -> None:
    workspace_id = uuid.uuid4()
    client, store = create_test_client(tmp_path=tmp_path, workspace_id=workspace_id)
    app = cast(FastAPI, client.app)
    object.__setattr__(
        app.state.dependencies,
        "repository_candidate_source",
        StaticCandidateSource(
            (
                RepositoryCandidateProjection(
                    id="github:acme/private-repo",
                    workspace_id=workspace_id,
                    provider=RepositoryProvider.GITHUB_CLOUD,
                    provider_scope="acme",
                    remote_url="https://github.com/acme/private-repo.git",
                    repository_owner="acme",
                    repository_name="private-repo",
                    provider_project_path="acme/private-repo",
                    access_status="available",
                ),
            )
        ),
    )

    response = client.post(
        f"/connections?workspaceId={workspace_id}",
        headers={"Origin": str(client.base_url).rstrip("/")},
        data={
            "candidateId": "github:acme/private-repo",
            "provider": "github_cloud",
            "remoteUrl": "",
            "transport": "https",
            "defaultRefType": "branch",
            "defaultRefName": "main",
            "credentialType": "https_pat",
            "credentialSecret": "readonly-token-value",
            "credentialFingerprint": "pat-01",
        },
    )

    assert response.status_code == 409
    assert "활성 워크스페이스에서만 저장소 연결을 생성할 수 있습니다." in response.text
    assert "private-repo" not in response.text
    assert "https://github.com/acme/private-repo.git" not in response.text
    assert store.connections == {}
    assert store.workspaces == {}


def _create_connection(
    client,
    *,
    provider: str,
    remote_url: str = "https://github.com/acme/sample-repo.git",
) -> None:
    response = client.post(
        "/api/repository-connections",
        json=create_connection_payload(provider=provider, remote_url=remote_url),
    )
    assert response.status_code == 201
