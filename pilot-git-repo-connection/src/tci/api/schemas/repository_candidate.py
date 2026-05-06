from __future__ import annotations

from pydantic import Field

from tci.api.schemas._base import CamelModel


class RepositoryCandidateResponse(CamelModel):
    id: str
    provider: str
    provider_scope: str = Field(alias="providerScope")
    remote_url: str | None = Field(alias="remoteUrl")
    repository_owner: str = Field(alias="repositoryOwner")
    repository_name: str = Field(alias="repositoryName")
    provider_project_path: str = Field(alias="providerProjectPath")
    canonical_repository_key: str = Field(alias="canonicalRepositoryKey")
    already_connected: bool = Field(alias="alreadyConnected")
    existing_connection_id: str | None = Field(alias="existingConnectionId")
    selectable: bool
    access_status: str = Field(alias="accessStatus")


class RepositoryCandidateListResponse(CamelModel):
    items: list[RepositoryCandidateResponse]
    manual_url_allowed: bool = Field(alias="manualUrlAllowed")
    empty_reason: str = Field(alias="emptyReason")
    guidance: str
