from __future__ import annotations

from datetime import UTC, datetime
import uuid

from tci.infrastructure.persistence.models import (
    DefaultRefType,
    ProviderReachabilityStatus,
    RepositoryConnection,
    RepositoryConnectionStatus,
    RepositoryProvider,
    RepositoryTransport,
    WebhookAuthMode,
)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def build_workspace_repository_connection(
    *,
    workspace_id: uuid.UUID | None = None,
    connection_id: uuid.UUID | None = None,
    provider: RepositoryProvider = RepositoryProvider.GITHUB_CLOUD,
    remote_url: str = "https://github.com/acme/sample-repo.git",
    repository_owner: str = "acme",
    repository_name: str = "sample-repo",
    provider_instance_url: str | None = None,
    provider_project_path: str | None = None,
    planning_input_reference_id: uuid.UUID | None = None,
) -> RepositoryConnection:
    workspace_id = workspace_id or uuid.uuid4()
    connection_id = connection_id or uuid.uuid4()
    if provider is RepositoryProvider.GITLAB_SELF_MANAGED:
        provider_instance_url = provider_instance_url or "https://gitlab.example.com"
        provider_project_path = (
            provider_project_path or f"{repository_owner}/{repository_name}"
        )
        webhook_auth_mode = WebhookAuthMode.SHARED_TOKEN
        transport = RepositoryTransport.HTTPS
    else:
        webhook_auth_mode = WebhookAuthMode.HMAC_SHA256
        transport = RepositoryTransport.HTTPS

    return RepositoryConnection(
        id=connection_id,
        workspace_id=workspace_id,
        planning_input_reference_id=planning_input_reference_id,
        provider=provider,
        remote_url=remote_url,
        provider_instance_url=provider_instance_url,
        transport=transport,
        repository_owner=repository_owner,
        repository_name=repository_name,
        provider_project_path=provider_project_path
        or f"{repository_owner}/{repository_name}",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=f".runtime/git-mirrors/{connection_id}.git",
        webhook_auth_mode=webhook_auth_mode,
        provider_reachability_status=ProviderReachabilityStatus.REACHABLE,
        last_reachability_failure_code=None,
        last_verified_at=now_utc(),
        last_successful_snapshot_at=None,
        last_failed_sync_at=None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
