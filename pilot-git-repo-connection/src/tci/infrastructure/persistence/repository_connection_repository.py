from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
from ipaddress import ip_address
import re
import time
import uuid
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from tci.infrastructure.persistence.models import (
    CollectionScopeRuleVersion,
    DefaultRefType,
    RepositoryEvent,
    RepositoryEventCursor,
    RepositoryConnection,
    RepositoryConnectionStatus,
    RepositoryProvider,
    RepositoryTransport,
    RepositorySyncRun,
    ScopeRuleWarningState,
    Workspace,
    WorkspaceStatus,
    WebhookAuthMode,
    WebhookHealthState,
    WebhookRejectionReason,
    WebhookSecretRevision,
)


_HOSTNAME_PATTERN = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$"
)
_SIDE_EFFECT_LOCK_TIMEOUT_SECONDS = 30.0
_SIDE_EFFECT_LOCK_RETRY_SECONDS = 0.1


def _has_whitespace_or_control(value: str) -> bool:
    return any(character.isspace() or ord(character) < 32 for character in value)


@dataclass(frozen=True, slots=True)
class RepositoryConnectionDraft:
    id: uuid.UUID
    workspace_id: uuid.UUID
    planning_input_reference_id: uuid.UUID | None
    provider: RepositoryProvider
    remote_url: str
    transport: RepositoryTransport
    repository_owner: str
    repository_name: str
    default_ref_type: DefaultRefType
    default_ref_name: str
    status: RepositoryConnectionStatus
    mirror_path: str
    last_verified_at: datetime | None
    provider_instance_url: str | None = None
    provider_project_path: str | None = None


class RepositoryConnectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, draft: RepositoryConnectionDraft) -> RepositoryConnection:
        self._validate_remote_url_credentials(remote_url=draft.remote_url)
        provider_instance_url = (
            None
            if draft.provider_instance_url is None
            else draft.provider_instance_url.strip()
        )
        provider_project_path = (
            None
            if draft.provider_project_path is None
            else draft.provider_project_path.strip()
        )
        if draft.provider is RepositoryProvider.GITLAB_SELF_MANAGED:
            if not provider_instance_url:
                raise ValueError("GitLab connection requires provider_instance_url.")
            if not provider_project_path:
                raise ValueError("GitLab connection requires provider_project_path.")
            self._validate_transport_matches_remote_url(
                transport=draft.transport, remote_url=draft.remote_url
            )
            self._validate_gitlab_project_path(
                provider_project_path=provider_project_path
            )
            provider_instance_url = self._normalize_gitlab_instance_url(
                provider_instance_url
            )
            canonical_project_path = self._canonical_gitlab_project_path(
                provider_instance_url=provider_instance_url, remote_url=draft.remote_url
            )
            if provider_project_path != canonical_project_path:
                raise ValueError(
                    "GitLab connection provider_project_path must match remote_url path."
                )
            self._validate_gitlab_instance_alignment(
                provider_instance_url=provider_instance_url,
                remote_url=draft.remote_url,
            )
        elif provider_instance_url is not None:
            raise ValueError("GitHub connection does not accept provider_instance_url.")
        if draft.provider is RepositoryProvider.GITHUB_CLOUD:
            provider_project_path = f"{draft.repository_owner}/{draft.repository_name}"
        elif provider_project_path is None:
            provider_project_path = f"{draft.repository_owner}/{draft.repository_name}"
        webhook_auth_mode = (
            WebhookAuthMode.SHARED_TOKEN
            if draft.provider is RepositoryProvider.GITLAB_SELF_MANAGED
            else WebhookAuthMode.HMAC_SHA256
        )
        self._raise_if_duplicate_connection_exists(
            workspace_id=draft.workspace_id,
            provider=draft.provider,
            provider_instance_url=provider_instance_url,
            provider_project_path=provider_project_path,
        )
        self.ensure_active_workspace(workspace_id=draft.workspace_id)

        connection = RepositoryConnection(
            id=draft.id,
            workspace_id=draft.workspace_id,
            planning_input_reference_id=draft.planning_input_reference_id,
            provider=draft.provider,
            remote_url=draft.remote_url,
            provider_instance_url=provider_instance_url,
            transport=draft.transport,
            repository_owner=draft.repository_owner,
            repository_name=draft.repository_name,
            provider_project_path=provider_project_path,
            default_ref_type=draft.default_ref_type,
            default_ref_name=draft.default_ref_name,
            status=draft.status,
            mirror_path=draft.mirror_path,
            webhook_auth_mode=webhook_auth_mode,
            last_verified_at=draft.last_verified_at,
        )
        self._session.add(connection)
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def ensure_active_workspace(self, *, workspace_id: uuid.UUID) -> None:
        try:
            with self._session.begin_nested():
                self._session.add(Workspace(id=workspace_id))
                self._session.flush()
        except IntegrityError:
            pass
        workspace = self._session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        if not isinstance(workspace, Workspace):
            return
        if workspace.status is not WorkspaceStatus.ACTIVE:
            raise ValueError("Repository connection requires an active workspace.")

    def _raise_if_duplicate_connection_exists(
        self,
        *,
        workspace_id: uuid.UUID,
        provider: RepositoryProvider,
        provider_instance_url: str | None,
        provider_project_path: str,
    ) -> None:
        statement = select(RepositoryConnection.id).where(
            RepositoryConnection.workspace_id == workspace_id,
            RepositoryConnection.provider == provider,
            RepositoryConnection.provider_project_path == provider_project_path,
        )
        if provider is RepositoryProvider.GITLAB_SELF_MANAGED:
            statement = statement.where(
                RepositoryConnection.provider_instance_url == provider_instance_url
            )
        if isinstance(self._session.scalar(statement), uuid.UUID):
            raise ValueError("Repository connection already exists for this workspace.")

    def ensure_repository_identity_available(
        self,
        *,
        workspace_id: uuid.UUID,
        provider: RepositoryProvider,
        provider_instance_url: str | None,
        provider_project_path: str,
    ) -> None:
        self._raise_if_duplicate_connection_exists(
            workspace_id=workspace_id,
            provider=provider,
            provider_instance_url=provider_instance_url,
            provider_project_path=provider_project_path,
        )

    @contextmanager
    def repository_identity_creation_lock(
        self,
        *,
        workspace_id: uuid.UUID,
        provider: RepositoryProvider,
        provider_instance_url: str | None,
        provider_project_path: str,
    ):
        bind = self._session.get_bind()
        if bind.dialect.name != "postgresql":
            yield
            return
        lock_key = _repository_identity_lock_key(
            workspace_id=workspace_id,
            provider=provider,
            provider_instance_url=provider_instance_url,
            provider_project_path=provider_project_path,
        )
        self._session.execute(
            sa.text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )
        yield

    @contextmanager
    def repository_identity_side_effect_lock(
        self,
        *,
        workspace_id: uuid.UUID,
        provider: RepositoryProvider,
        provider_instance_url: str | None,
        provider_project_path: str,
    ):
        bind = self._session.get_bind()
        if bind.dialect.name != "postgresql":
            yield
            return
        lock_key = _repository_identity_lock_key(
            workspace_id=workspace_id,
            provider=provider,
            provider_instance_url=provider_instance_url,
            provider_project_path=provider_project_path,
        )
        # Session-level advisory locks must keep the PostgreSQL backend checked out
        # while Git side effects run. Use try-lock polling so same-identity creates
        # fail boundedly instead of blocking a pooled connection forever.
        deadline = time.monotonic() + _SIDE_EFFECT_LOCK_TIMEOUT_SECONDS
        while True:
            if isinstance(bind, Engine):
                with bind.connect() as connection:
                    acquired = connection.scalar(
                        sa.text("SELECT pg_try_advisory_lock(:lock_key)"),
                        {"lock_key": lock_key},
                    )
                    connection.commit()
                    if acquired:
                        try:
                            yield
                        finally:
                            connection.execute(
                                sa.text("SELECT pg_advisory_unlock(:lock_key)"),
                                {"lock_key": lock_key},
                            )
                            connection.commit()
                        return
            else:
                acquired = bind.scalar(
                    sa.text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": lock_key},
                )
                if acquired:
                    try:
                        yield
                    finally:
                        bind.execute(
                            sa.text("SELECT pg_advisory_unlock(:lock_key)"),
                            {"lock_key": lock_key},
                        )
                    return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Repository connection identity lock is busy. Retry later."
                )
            time.sleep(_SIDE_EFFECT_LOCK_RETRY_SECONDS)

    @staticmethod
    def _validate_transport_matches_remote_url(
        *, transport: RepositoryTransport, remote_url: str
    ) -> None:
        if transport is RepositoryTransport.HTTP and not remote_url.startswith(
            "http://"
        ):
            raise ValueError("Repository transport must match remote_url scheme.")
        if transport is RepositoryTransport.HTTPS and not remote_url.startswith(
            "https://"
        ):
            raise ValueError("Repository transport must match remote_url scheme.")
        if transport is RepositoryTransport.SSH and not remote_url.startswith(
            ("git@", "ssh://")
        ):
            raise ValueError("Repository transport must match remote_url scheme.")

    @staticmethod
    def _validate_remote_url_credentials(*, remote_url: str) -> None:
        if _has_whitespace_or_control(remote_url):
            raise ValueError(
                "Repository remote_url must not include whitespace or control characters."
            )
        if remote_url.startswith("git@") and ("?" in remote_url or "#" in remote_url):
            raise ValueError(
                "Repository remote_url must not include query or fragment."
            )
        if remote_url.startswith(("http://", "https://", "ssh://")):
            parsed_remote = urlparse(remote_url)
            if parsed_remote.params or parsed_remote.query or parsed_remote.fragment:
                raise ValueError(
                    "Repository remote_url must not include query or fragment."
                )
            if parsed_remote.password is not None:
                raise ValueError(
                    "Repository remote_url must not include credential-bearing userinfo."
                )
            if (
                remote_url.startswith(("http://", "https://"))
                and parsed_remote.username is not None
            ):
                raise ValueError(
                    "Repository remote_url must not include credential-bearing userinfo."
                )

    @staticmethod
    def _normalize_gitlab_instance_url(provider_instance_url: str) -> str:
        parsed_instance = urlparse(provider_instance_url)
        has_supported_base_url = (
            bool(parsed_instance.hostname)
            and not parsed_instance.params
            and not parsed_instance.query
            and not parsed_instance.fragment
            and parsed_instance.username is None
            and parsed_instance.password is None
        )
        if (
            parsed_instance.scheme not in ("http", "https")
            or not parsed_instance.netloc
            or not has_supported_base_url
            or parsed_instance.path not in ("", "/")
        ):
            raise ValueError(
                "GitLab connection requires an http or https provider_instance_url without query or fragment."
            )
        normalized_host = (parsed_instance.hostname or "").lower()
        RepositoryConnectionRepository._validate_gitlab_host(hostname=normalized_host)
        parsed_port = RepositoryConnectionRepository._parse_url_port(
            parsed_url=parsed_instance
        )
        normalized_port = (
            f":{parsed_port}"
            if parsed_port is not None
            and not (
                (parsed_instance.scheme == "https" and parsed_port == 443)
                or (parsed_instance.scheme == "http" and parsed_port == 80)
            )
            else ""
        )
        return f"{parsed_instance.scheme}://{normalized_host}{normalized_port}"

    @staticmethod
    def _canonical_gitlab_project_path(
        *, provider_instance_url: str, remote_url: str
    ) -> str:
        if remote_url.startswith(("http://", "https://", "ssh://")):
            parsed_remote = urlparse(remote_url)
            project_path = parsed_remote.path.lstrip("/")
        elif remote_url.startswith("git@"):
            _, separator, project_path = remote_url.partition(":")
            if not separator:
                project_path = ""
        else:
            project_path = ""

        canonical_path = project_path.removesuffix(".git")
        if (
            not canonical_path
            or canonical_path.startswith("/")
            or canonical_path.endswith("/")
            or "//" in canonical_path
            or "/" not in canonical_path
        ):
            raise ValueError("GitLab connection requires a supported remote_url.")
        return canonical_path

    @staticmethod
    def _extract_gitlab_remote_location(
        *, remote_url: str
    ) -> tuple[str, int | None, str] | None:
        if remote_url.startswith(("http://", "https://")):
            parsed_remote = urlparse(remote_url)
            if parsed_remote.hostname is None:
                return None
            return (
                parsed_remote.hostname,
                RepositoryConnectionRepository._parse_url_port(
                    parsed_url=parsed_remote
                ),
                parsed_remote.scheme,
            )
        if remote_url.startswith("ssh://"):
            parsed_remote = urlparse(remote_url)
            if parsed_remote.hostname is None or parsed_remote.username != "git":
                return None
            return (
                parsed_remote.hostname,
                RepositoryConnectionRepository._parse_url_port(
                    parsed_url=parsed_remote
                ),
                "ssh_url",
            )
        if remote_url.startswith("git@"):
            remote_host = remote_url.partition("@")[2].partition(":")[0]
            if not remote_host:
                return None
            return remote_host.lower(), None, "scp"
        return None

    @classmethod
    def _validate_gitlab_instance_alignment(
        cls,
        *,
        provider_instance_url: str,
        remote_url: str,
    ) -> None:
        parsed_instance = urlparse(provider_instance_url)
        remote_location = cls._extract_gitlab_remote_location(remote_url=remote_url)
        if remote_location is None or parsed_instance.hostname is None:
            raise ValueError("GitLab connection requires a supported remote_url.")
        remote_host, remote_port, remote_scheme = remote_location
        cls._validate_gitlab_host(hostname=remote_host)
        remote_host = remote_host.lower()
        if remote_host.rstrip(".") == "github.com":
            raise ValueError("GitHub remotes cannot be stored as GitLab providers.")
        if parsed_instance.hostname != remote_host:
            raise ValueError(
                "GitLab connection remote_url must match provider_instance_url host."
            )
        if remote_scheme in ("http", "https"):
            if parsed_instance.scheme != remote_scheme:
                raise ValueError(
                    "GitLab HTTP(S) remote_url scheme must match provider_instance_url scheme."
                )
            default_port = 80 if remote_scheme == "http" else 443
            instance_port = parsed_instance.port or default_port
            expected_remote_port = remote_port or default_port
            if instance_port != expected_remote_port:
                raise ValueError(
                    "GitLab HTTP(S) remote_url port must match provider_instance_url port."
                )

    @staticmethod
    def _validate_gitlab_host(*, hostname: str) -> None:
        if (
            not hostname
            or hostname.startswith("-")
            or _has_whitespace_or_control(hostname)
        ):
            raise ValueError("GitLab connection requires a supported host.")
        try:
            parsed_ip = ip_address(hostname)
        except ValueError:
            if not _HOSTNAME_PATTERN.fullmatch(hostname):
                raise ValueError(
                    "GitLab connection requires a supported host."
                ) from None
        else:
            if parsed_ip.version != 4:
                raise ValueError("GitLab connection requires a supported host.")

    @staticmethod
    def _validate_gitlab_project_path(*, provider_project_path: str) -> None:
        segments = provider_project_path.split("/")
        if (
            len(segments) < 2
            or provider_project_path.startswith("/")
            or provider_project_path.endswith("/")
            or "//" in provider_project_path
            or any(segment in (".", "..") for segment in segments)
            or _has_whitespace_or_control(provider_project_path)
        ):
            raise ValueError(
                "GitLab connection requires a normalized provider_project_path."
            )

    @staticmethod
    def _parse_url_port(*, parsed_url) -> int | None:
        if parsed_url.netloc.rsplit("@", 1)[-1].endswith(":"):
            raise ValueError("GitLab connection requires a supported port.")
        try:
            return parsed_url.port
        except ValueError as error:
            raise ValueError("GitLab connection requires a supported port.") from error

    def get(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection | None:
        statement = (
            select(RepositoryConnection)
            .options(
                joinedload(RepositoryConnection.planning_input_reference),
                joinedload(RepositoryConnection.active_scope_rule_version),
            )
            .where(
                RepositoryConnection.id == connection_id,
                RepositoryConnection.workspace_id == workspace_id,
            )
        )
        return self._session.scalar(statement)

    def get_for_update(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection | None:
        statement = (
            select(RepositoryConnection)
            .where(
                RepositoryConnection.id == connection_id,
                RepositoryConnection.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        return self._session.scalar(statement)

    def get_any(self, *, connection_id: uuid.UUID) -> RepositoryConnection | None:
        statement = (
            select(RepositoryConnection)
            .options(
                joinedload(RepositoryConnection.planning_input_reference),
                joinedload(RepositoryConnection.active_scope_rule_version),
                joinedload(RepositoryConnection.active_webhook_secret_revision),
                joinedload(RepositoryConnection.last_processed_event),
            )
            .where(RepositoryConnection.id == connection_id)
        )
        return self._session.scalar(statement)

    def list_for_workspace(
        self, *, workspace_id: uuid.UUID
    ) -> list[RepositoryConnection]:
        statement = (
            select(RepositoryConnection)
            .options(
                joinedload(RepositoryConnection.planning_input_reference),
                joinedload(RepositoryConnection.active_scope_rule_version),
            )
            .where(RepositoryConnection.workspace_id == workspace_id)
            .order_by(
                RepositoryConnection.created_at.desc(), RepositoryConnection.id.desc()
            )
        )
        return list(self._session.scalars(statement).unique())

    def delete_for_workspace(self, *, workspace_id: uuid.UUID) -> int:
        connections = self.list_for_workspace(workspace_id=workspace_id)
        connection_ids = [connection.id for connection in connections]
        if not connection_ids:
            return 0
        self._clear_delete_blocking_references(connection_ids=connection_ids)
        for connection in connections:
            self._session.delete(connection)
        self._session.flush()
        return len(connections)

    def _clear_delete_blocking_references(
        self, *, connection_ids: list[uuid.UUID]
    ) -> None:
        self._session.execute(
            sa.update(RepositoryConnection)
            .where(RepositoryConnection.id.in_(connection_ids))
            .values(
                active_scope_rule_version_id=None,
                active_credential_revision_id=None,
                active_webhook_secret_revision_id=None,
                last_processed_event_id=None,
            )
        )
        self._session.execute(
            sa.delete(RepositoryEventCursor).where(
                RepositoryEventCursor.connection_id.in_(connection_ids)
            )
        )
        self._session.execute(
            sa.update(RepositorySyncRun)
            .where(RepositorySyncRun.connection_id.in_(connection_ids))
            .values(trigger_event_id=None)
        )
        self._session.execute(
            sa.update(RepositoryEvent)
            .where(RepositoryEvent.connection_id.in_(connection_ids))
            .values(
                sync_run_id=None,
                snapshot_id=None,
                verified_secret_revision_id=None,
                verified_secret_revision_status=None,
            )
        )
        self._session.flush()

    def set_active_credential_revision(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        credential_revision_id: uuid.UUID,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.active_credential_revision_id = credential_revision_id
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def set_active_webhook_secret_revision(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        webhook_secret_revision_id: uuid.UUID,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        owned_revision = self._session.scalar(
            select(WebhookSecretRevision.id).where(
                WebhookSecretRevision.id == webhook_secret_revision_id,
                WebhookSecretRevision.connection_id == connection_id,
            )
        )
        if owned_revision is None:
            raise LookupError("같은 연결에 속한 webhook secret revision이 아닙니다.")
        connection.active_webhook_secret_revision_id = webhook_secret_revision_id
        connection.webhook_health_state = WebhookHealthState.HEALTHY
        connection.last_webhook_rejection_reason = None
        connection.last_webhook_rejected_at = None
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def update_default_ref(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        default_ref_type: DefaultRefType,
        default_ref_name: str,
        status: RepositoryConnectionStatus,
        last_verified_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.default_ref_type = default_ref_type
        connection.default_ref_name = default_ref_name
        connection.status = status
        connection.last_verified_at = last_verified_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def update_verification(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        status: RepositoryConnectionStatus,
        last_verified_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.status = status
        connection.last_verified_at = last_verified_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def update_status(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        status: RepositoryConnectionStatus,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.status = status
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def ensure_default_scope_rule_version(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> CollectionScopeRuleVersion:
        self._lock_active_workspace(workspace_id=workspace_id)
        connection = self.get_for_update(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        if connection.active_scope_rule_version_id is not None:
            scope_rule = self._session.get(
                CollectionScopeRuleVersion,
                connection.active_scope_rule_version_id,
            )
            if scope_rule is None:
                raise LookupError("활성 범위 규칙을 찾을 수 없습니다.")
            return scope_rule

        scope_rule = CollectionScopeRuleVersion(
            connection_id=connection.id,
            planning_input_reference_id=connection.planning_input_reference_id,
            include_paths=[],
            exclude_paths=[],
            allowed_file_types=[],
            blocked_file_types=[],
            max_file_size_bytes=5 * 1024 * 1024,
            exclude_binary=True,
            is_auto_default=True,
            warning_state=ScopeRuleWarningState.OK,
            created_by=created_by,
        )
        self._session.add(scope_rule)
        self._session.flush()
        connection.active_scope_rule_version_id = scope_rule.id
        connection.active_scope_rule_version = scope_rule
        self._session.flush()
        self._session.refresh(scope_rule)
        self._session.refresh(connection)
        return scope_rule

    def _lock_active_workspace(self, *, workspace_id: uuid.UUID) -> None:
        workspace = self._session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        if workspace is None or workspace.status is not WorkspaceStatus.ACTIVE:
            raise ValueError("저장소 연결 작업에는 활성 워크스페이스가 필요합니다.")

    def record_sync_failure(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        failed_at: datetime,
        status: RepositoryConnectionStatus | None = None,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.last_failed_sync_at = failed_at
        if status is not None:
            connection.status = status
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def record_snapshot_success(
        self,
        *,
        workspace_id: uuid.UUID,
        connection_id: uuid.UUID,
        succeeded_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        connection.last_successful_snapshot_at = succeeded_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def record_webhook_rejection(
        self,
        *,
        connection_id: uuid.UUID,
        health_state: WebhookHealthState,
        rejection_reason: WebhookRejectionReason,
        rejected_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require_any(connection_id=connection_id)
        connection.webhook_health_state = health_state
        connection.last_webhook_rejection_reason = rejection_reason
        connection.last_webhook_rejected_at = rejected_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def record_processed_event(
        self,
        *,
        connection_id: uuid.UUID,
        event_id: uuid.UUID,
        processed_at: datetime,
        health_state: WebhookHealthState,
    ) -> RepositoryConnection:
        connection = self._require_any(connection_id=connection_id)
        connection.last_processed_event_id = event_id
        connection.last_processed_event_at = processed_at
        connection.webhook_health_state = health_state
        if health_state is WebhookHealthState.HEALTHY:
            connection.last_webhook_rejection_reason = None
            connection.last_webhook_rejected_at = None
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def record_processed_event_preserving_webhook_health(
        self,
        *,
        connection_id: uuid.UUID,
        event_id: uuid.UUID,
        processed_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require_any(connection_id=connection_id)
        connection.last_processed_event_id = event_id
        connection.last_processed_event_at = processed_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def record_webhook_delivery_failure(
        self,
        *,
        connection_id: uuid.UUID,
        event_id: uuid.UUID,
        failed_at: datetime,
    ) -> RepositoryConnection:
        connection = self._require_any(connection_id=connection_id)
        connection.last_processed_event_id = event_id
        connection.last_processed_event_at = failed_at
        self._session.flush()
        self._session.refresh(connection)
        return connection

    def _require(
        self, *, workspace_id: uuid.UUID, connection_id: uuid.UUID
    ) -> RepositoryConnection:
        connection = self.get(workspace_id=workspace_id, connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection

    def _require_any(self, *, connection_id: uuid.UUID) -> RepositoryConnection:
        connection = self.get_any(connection_id=connection_id)
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        return connection


def _repository_identity_lock_key(
    *,
    workspace_id: uuid.UUID,
    provider: RepositoryProvider,
    provider_instance_url: str | None,
    provider_project_path: str,
) -> int:
    raw_key = "\0".join(
        (
            str(workspace_id),
            provider.value,
            "" if provider_instance_url is None else provider_instance_url,
            provider_project_path,
        )
    )
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)
