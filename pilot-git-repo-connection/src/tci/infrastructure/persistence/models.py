from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum
from sqlalchemy import ForeignKey, ForeignKeyConstraint, Integer, MetaData, String, Text
from sqlalchemy import Index, Uuid, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class PlanningInputSourceType(StrEnum):
    USER_REQUEST = "user_request"
    PLANNING_BRIEF = "planning_brief"
    IMPORTED_NOTE = "imported_note"


class RepositoryProvider(StrEnum):
    GITHUB_CLOUD = "github_cloud"
    GITLAB_SELF_MANAGED = "gitlab_self_managed"


class RepositoryTransport(StrEnum):
    SSH = "ssh"
    HTTPS = "https"
    HTTP = "http"


class RefType(StrEnum):
    BRANCH = "branch"
    TAG = "tag"
    PULL_REQUEST_BRANCH = "pull_request_branch"


class DefaultRefType(StrEnum):
    BRANCH = "branch"
    TAG = "tag"


class RepositoryConnectionStatus(StrEnum):
    ACTIVE = "active"
    REAUTH_REQUIRED = "reauth_required"
    REF_MISSING = "ref_missing"


class CredentialType(StrEnum):
    SSH_PRIVATE_KEY = "ssh_private_key"
    HTTPS_PAT = "https_pat"


class CredentialRevisionStatus(StrEnum):
    ACTIVE = "active"
    PREVIOUS_GRACE = "previous_grace"
    REVOKED = "revoked"


class WebhookSecretRevisionStatus(StrEnum):
    ACTIVE = "active"
    PREVIOUS_GRACE = "previous_grace"
    REVOKED = "revoked"


class WebhookHealthState(StrEnum):
    HEALTHY = "healthy"
    MISSING_SECRET = "missing_secret"
    SECRET_MISMATCH_DETECTED = "secret_mismatch_detected"
    SIGNATURE_INVALID_RECENTLY = "signature_invalid_recently"


class WebhookRejectionReason(StrEnum):
    SECRET_MISSING = "secret_missing"
    SECRET_MISMATCH = "secret_mismatch"
    SIGNATURE_INVALID = "signature_invalid"


class WebhookAuthMode(StrEnum):
    HMAC_SHA256 = "hmac_sha256"
    SHARED_TOKEN = "shared_token"


class ProviderReachabilityStatus(StrEnum):
    REACHABLE = "reachable"
    UNREACHABLE_RECENTLY = "unreachable_recently"
    TLS_FAILED_RECENTLY = "tls_failed_recently"
    DNS_FAILED_RECENTLY = "dns_failed_recently"


class ScopeRuleWarningState(StrEnum):
    OK = "ok"
    EMPTY_RESULT_RISK = "empty_result_risk"
    PREVIEW_FAILED = "preview_failed"
    OVER_BROAD_INCLUDE = "over_broad_include"


class SyncRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class SyncTriggerType(StrEnum):
    MANUAL_INITIAL = "manual_initial"
    MANUAL_REFRESH = "manual_refresh"
    WEBHOOK_PUSH = "webhook_push"
    WEBHOOK_PULL_REQUEST = "webhook_pull_request"
    WEBHOOK_MERGE_REQUEST = "webhook_merge_request"


class SyncFailureCode(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    REF_NOT_FOUND = "REF_NOT_FOUND"
    NO_INCLUDED_FILES = "NO_INCLUDED_FILES"
    MIRROR_SYNC_FAILED = "MIRROR_SYNC_FAILED"
    SNAPSHOT_WRITE_FAILED = "SNAPSHOT_WRITE_FAILED"
    QUEUE_DISPATCH_FAILED = "QUEUE_DISPATCH_FAILED"


class ProviderEventType(StrEnum):
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    MERGE_REQUEST = "merge_request"
    PING = "ping"
    UNKNOWN = "unknown"


class DomainEventType(StrEnum):
    COMMIT_RECORDED = "commit_recorded"
    PUSH_RECEIVED = "push_received"
    PR_RECEIVED = "pr_received"
    MR_RECEIVED = "mr_received"
    SIGNATURE_REJECTED = "signature_rejected"
    SECRET_MISSING = "secret_missing"
    SECRET_MISMATCH = "secret_mismatch"


class EventTargetKind(StrEnum):
    DEFAULT_REF = "default_ref"
    PULL_REQUEST_SOURCE = "pull_request_source"
    MERGE_REQUEST_SOURCE = "merge_request_source"
    NONE = "none"


class ProviderEventIdempotencySource(StrEnum):
    DELIVERY_HEADER = "delivery_header"
    UUID_HEADER = "uuid_header"
    DERIVED_HASH = "derived_hash"


class SignatureStatus(StrEnum):
    VERIFIED = "verified"
    SECRET_MISSING = "secret_missing"
    SECRET_MISMATCH = "secret_mismatch"
    SIGNATURE_INVALID = "signature_invalid"


class ProcessingDecision(StrEnum):
    RECORD_ONLY = "record_only"
    QUEUED = "queued"
    DUPLICATE_DELIVERY = "duplicate_delivery"
    DUPLICATE_HEAD = "duplicate_head"
    STALE_HEAD = "stale_head"
    REJECTED = "rejected"


class EventProcessingStatus(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    QUEUED = "queued"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class SnapshotInclusionReason(StrEnum):
    DEFAULT_POLICY = "default_policy"
    USER_INCLUDE = "user_include"
    PR_SOURCE_SNAPSHOT = "pr_source_snapshot"


def sql_enum(enum_type: type[StrEnum], *, name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class PlanningInputReference(Base):
    __tablename__ = "planning_input_references"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_plan_input_workspace_id_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    source_type: Mapped[PlanningInputSourceType] = mapped_column(
        sql_enum(PlanningInputSourceType, name="planning_input_source_type"),
        nullable=False,
    )
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    approved_spec_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    approved_plan_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    repository_connections: Mapped[list[RepositoryConnection]] = relationship(
        back_populates="planning_input_reference",
        foreign_keys="RepositoryConnection.planning_input_reference_id",
    )
    scope_rule_versions: Mapped[list[CollectionScopeRuleVersion]] = relationship(
        back_populates="planning_input_reference"
    )


class RepositoryConnection(Base):
    __tablename__ = "repository_connections"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "planning_input_reference_id",
            name="uq_repo_conn_id_plan_input_id",
        ),
        CheckConstraint(
            "((provider = 'github_cloud' AND "
            "(remote_url LIKE 'git@github.com:%' OR remote_url LIKE 'https://github.com/%')) "
            "OR (provider = 'gitlab_self_managed' AND "
            "((remote_url LIKE 'git@%:%' AND remote_url !~* '^git@github\\.com\\.?:' "
            "AND remote_url !~ '^git@[-[:space:][:cntrl:]]' "
            "AND remote_url !~ '^git@[^:]*\\.\\.' "
            "AND remote_url !~ '^git@[^:]*\\.-' "
            "AND remote_url !~ '^git@[^:]*\\.:' "
            "AND remote_url !~ '^git@[^:]*-[.:]' "
            "AND remote_url !~ '^git@[^:]*[[:space:][:cntrl:]][^:]*:') "
            "OR (remote_url LIKE 'https://%/%' "
            "AND remote_url !~* '^https://github\\.com\\.?(?::[0-9]+)?/' "
            "AND remote_url !~ '^https://[-[:space:][:cntrl:]]' "
            "AND remote_url !~ '^https://[^/]*\\.\\.' "
            "AND remote_url !~ '^https://[^/]*\\.-' "
            "AND remote_url !~ '^https://[^/?#]*\\.(?::[0-9]+)?/' "
            "AND remote_url !~ '^https://[^/]*-[.:/]' "
            "AND remote_url !~ '^https://[^/]*[[:space:][:cntrl:]][^/]*/' "
            "AND remote_url !~ '^https://\\[') "
            "OR (remote_url LIKE 'http://%/%' "
            "AND remote_url !~* '^http://github\\.com\\.?(?::[0-9]+)?/' "
            "AND remote_url !~ '^http://[-[:space:][:cntrl:]]' "
            "AND remote_url !~ '^http://[^/]*\\.\\.' "
            "AND remote_url !~ '^http://[^/]*\\.-' "
            "AND remote_url !~ '^http://[^/?#]*\\.(?::[0-9]+)?/' "
            "AND remote_url !~ '^http://[^/]*-[.:/]' "
            "AND remote_url !~ '^http://[^/]*[[:space:][:cntrl:]][^/]*/' "
            "AND remote_url !~ '^http://\\[') "
            "OR (remote_url LIKE 'ssh://git@%/%' "
            "AND remote_url !~* '^ssh://(?:[^@/]+@)?github\\.com\\.?(?::[0-9]+)?/' "
            "AND remote_url !~ '^ssh://git@[-[:space:][:cntrl:]]' "
            "AND remote_url !~ '^ssh://git@[^/]*\\.\\.' "
            "AND remote_url !~ '^ssh://git@[^/]*\\.-' "
            "AND remote_url !~ '^ssh://git@[^/?#]*\\.(?::[0-9]+)?/' "
            "AND remote_url !~ '^ssh://git@[^/]*-[.:/]' "
            "AND remote_url !~ '^ssh://git@[^/]*[[:space:][:cntrl:]][^/]*/' "
            "AND remote_url !~ '^ssh://git@\\['))))",
            name="ck_repo_conn_remote_url_host",
        ),
        CheckConstraint(
            "remote_url NOT LIKE 'https://%@%/%' "
            "AND remote_url NOT LIKE 'http://%@%/%' "
            "AND remote_url NOT LIKE 'ssh://%:%@%/%' "
            "AND remote_url NOT LIKE '%?%' "
            "AND remote_url NOT LIKE '%#%'",
            name="ck_repo_conn_remote_url_no_userinfo",
        ),
        CheckConstraint(
            "("
            "(transport = 'http' AND remote_url LIKE 'http://%/%') "
            "OR (transport = 'https' AND remote_url LIKE 'https://%/%') "
            "OR (transport = 'ssh' AND (remote_url LIKE 'git@%:%' OR remote_url LIKE 'ssh://%/%'))"
            ")",
            name="ck_repo_conn_transport_remote_url_scheme_match",
        ),
        CheckConstraint(
            "("
            "(provider = 'github_cloud' AND provider_instance_url IS NULL "
            "AND webhook_auth_mode = 'hmac_sha256') "
            "OR "
            "(provider = 'gitlab_self_managed' AND provider_instance_url IS NOT NULL "
            "AND btrim(provider_instance_url) <> '' "
            "AND webhook_auth_mode = 'shared_token')"
            ")",
            name="ck_repo_conn_provider_metadata",
        ),
        CheckConstraint(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(provider_instance_url ~ '^https?://[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]+)?/?$' "
            "AND provider_instance_url !~ '^https?://[^/]*\\.\\.' "
            "AND provider_instance_url !~ '^https?://[^/]*\\.-' "
            "AND provider_instance_url !~ '^https?://[^/]*\\.(?::[0-9]+)?/?$' "
            "AND provider_instance_url !~ '^https?://[^/:/]*-(?::[0-9]+)?/?$' "
            "AND provider_instance_url !~ '^https?://[^/]*[[:space:][:cntrl:]][^/]*' "
            "AND provider_instance_url !~ '^https?://[^/]*-[.:/]')"
            ")",
            name="ck_repo_conn_gitlab_instance_url_https",
        ),
        CheckConstraint(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(lower(regexp_replace(provider_instance_url, '^https?://([^/:?#]+)(?::[0-9]+)?(?:/.*)?$', '\\1')) = CASE "
            "WHEN remote_url LIKE 'https://%' "
            "THEN lower(regexp_replace(remote_url, '^https://([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
            "WHEN remote_url LIKE 'http://%' "
            "THEN lower(regexp_replace(remote_url, '^http://([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
            "WHEN remote_url LIKE 'git@%:%' "
            "THEN lower(regexp_replace(remote_url, '^git@([^:]+):.*$', '\\1')) "
            "WHEN remote_url LIKE 'ssh://%/%' "
            "THEN lower(regexp_replace(remote_url, '^ssh://(?:[^@/]+@)?([^/:?#]+)(?::[0-9]+)?/.*$', '\\1')) "
            "ELSE '' "
            "END)"
            ")",
            name="ck_repo_conn_gitlab_instance_host_match",
        ),
        CheckConstraint(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(remote_url NOT LIKE 'https://%/%' AND remote_url NOT LIKE 'http://%/%') "
            "OR "
            "(CASE WHEN provider_instance_url LIKE 'http://%' "
            "THEN coalesce(nullif(regexp_replace(provider_instance_url, '^http://[^/:?#]+(?::([0-9]+))?(?:/.*)?$', '\\1'), ''), '80') "
            "ELSE coalesce(nullif(regexp_replace(provider_instance_url, '^https://[^/:?#]+(?::([0-9]+))?(?:/.*)?$', '\\1'), ''), '443') END = "
            "CASE WHEN remote_url LIKE 'http://%' "
            "THEN coalesce(nullif(regexp_replace(remote_url, '^http://[^/:?#]+(?::([0-9]+))?/.*$', '\\1'), ''), '80') "
            "ELSE coalesce(nullif(regexp_replace(remote_url, '^https://[^/:?#]+(?::([0-9]+))?/.*$', '\\1'), ''), '443') END)"
            ")",
            name="ck_repo_conn_gitlab_https_port_match",
        ),
        CheckConstraint(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(remote_url NOT LIKE 'https://%/%' AND remote_url NOT LIKE 'http://%/%') "
            "OR "
            "((provider_instance_url LIKE 'https://%' AND remote_url LIKE 'https://%/%') "
            "OR (provider_instance_url LIKE 'http://%' AND remote_url LIKE 'http://%/%'))"
            ")",
            name="ck_repo_conn_gitlab_http_scheme_match",
        ),
        CheckConstraint(
            "((provider <> 'gitlab_self_managed') "
            "OR (provider_project_path IS NOT NULL "
            "AND provider_project_path LIKE '%/%' "
            "AND provider_project_path NOT LIKE '/%' "
            "AND provider_project_path NOT LIKE '%/' "
            "AND provider_project_path NOT LIKE '%//%' "
            "AND provider_project_path NOT LIKE '%?%' "
            "AND provider_project_path NOT LIKE '%#%' "
            "AND provider_project_path !~ '[[:space:][:cntrl:]]' "
            "AND provider_project_path !~ '(^|/)\\.\\.?(/|$)'))",
            name="ck_repo_conn_provider_project_path",
        ),
        CheckConstraint(
            "("
            "(provider <> 'gitlab_self_managed') "
            "OR "
            "(provider_project_path IS NOT NULL AND provider_project_path = CASE "
            "WHEN remote_url LIKE 'https://%' "
            "THEN regexp_replace(regexp_replace(remote_url, '^https://[^/]+/', ''), '\\.git$', '') "
            "WHEN remote_url LIKE 'http://%' "
            "THEN regexp_replace(regexp_replace(remote_url, '^http://[^/]+/', ''), '\\.git$', '') "
            "WHEN remote_url LIKE 'git@%:%' "
            "THEN regexp_replace(regexp_replace(remote_url, '^git@[^:]+:', ''), '\\.git$', '') "
            "WHEN remote_url LIKE 'ssh://%/%' "
            "THEN regexp_replace(regexp_replace(remote_url, '^ssh://(?:[^@/]+@)?[^/]+/', ''), '\\.git$', '') "
            "ELSE '' "
            "END)"
            ")",
            name="ck_repo_conn_gitlab_project_path_match",
        ),
        CheckConstraint(
            "provider <> 'github_cloud' "
            "OR (provider_project_path IS NOT NULL "
            "AND provider_project_path = repository_owner || '/' || repository_name)",
            name="ck_repo_conn_github_project_path_present",
        ),
        CheckConstraint(
            "mirror_path NOT LIKE '/%' AND mirror_path NOT LIKE '%..%'",
            name="ck_repo_conn_mirror_path_safe",
        ),
        ForeignKeyConstraint(
            ["id", "active_scope_rule_version_id"],
            [
                "collection_scope_rule_versions.connection_id",
                "collection_scope_rule_versions.id",
            ],
            name="fk_repo_conn_active_scope_owner",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["id", "active_credential_revision_id"],
            [
                "repository_credential_revisions.connection_id",
                "repository_credential_revisions.id",
            ],
            name="fk_repo_conn_active_cred_owner",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["id", "active_webhook_secret_revision_id"],
            ["webhook_secret_revisions.connection_id", "webhook_secret_revisions.id"],
            name="fk_repo_conn_active_webhook_secret_owner",
            use_alter=True,
        ),
        Index(
            "ix_repo_conn_active_webhook_secret_revision_id",
            "active_webhook_secret_revision_id",
        ),
        Index(
            "ix_repo_conn_active_scope_rule_version_id",
            "active_scope_rule_version_id",
        ),
        Index(
            "ix_repo_conn_active_credential_revision_id",
            "active_credential_revision_id",
        ),
        Index(
            "ix_repo_conn_last_processed_event_id",
            "last_processed_event_id",
        ),
        Index("ix_repo_conn_plan_input_ref_id", "planning_input_reference_id"),
        Index(
            "uq_repo_conn_workspace_github_repo",
            "workspace_id",
            "provider",
            "provider_project_path",
            unique=True,
            postgresql_where=text("provider = 'github_cloud'"),
        ),
        Index(
            "uq_repo_conn_workspace_gitlab_repo",
            "workspace_id",
            "provider",
            "provider_instance_url",
            "provider_project_path",
            unique=True,
            postgresql_where=text("provider = 'gitlab_self_managed'"),
        ),
        ForeignKeyConstraint(
            ["workspace_id", "planning_input_reference_id"],
            ["planning_input_references.workspace_id", "planning_input_references.id"],
            name="fk_repo_conn_plan_input_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    planning_input_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("planning_input_references.id", name="fk_repo_conn_plan_input_id"),
        nullable=True,
    )
    provider: Mapped[RepositoryProvider] = mapped_column(
        sql_enum(RepositoryProvider, name="repository_provider"),
        nullable=False,
    )
    remote_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    provider_instance_url: Mapped[str | None] = mapped_column(String(1024))
    transport: Mapped[RepositoryTransport] = mapped_column(
        sql_enum(RepositoryTransport, name="repository_transport"),
        nullable=False,
    )
    repository_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repository_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_project_path: Mapped[str | None] = mapped_column(String(512))
    default_ref_type: Mapped[DefaultRefType] = mapped_column(
        sql_enum(DefaultRefType, name="default_ref_type"),
        nullable=False,
    )
    default_ref_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RepositoryConnectionStatus] = mapped_column(
        sql_enum(RepositoryConnectionStatus, name="repository_connection_status"),
        nullable=False,
        default=RepositoryConnectionStatus.ACTIVE,
    )
    mirror_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    active_scope_rule_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey(
            "collection_scope_rule_versions.id",
            use_alter=True,
            name="fk_repo_conn_active_scope_id",
        ),
        nullable=True,
    )
    active_credential_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey(
            "repository_credential_revisions.id",
            use_alter=True,
            name="fk_repo_conn_active_cred_id",
        ),
        nullable=True,
    )
    active_webhook_secret_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey(
            "webhook_secret_revisions.id",
            use_alter=True,
            name="fk_repo_conn_active_webhook_secret_id",
        ),
        nullable=True,
    )
    webhook_auth_mode: Mapped[WebhookAuthMode] = mapped_column(
        sql_enum(WebhookAuthMode, name="webhook_auth_mode"),
        nullable=False,
        default=WebhookAuthMode.HMAC_SHA256,
        server_default=text("'hmac_sha256'"),
    )
    webhook_health_state: Mapped[WebhookHealthState] = mapped_column(
        sql_enum(WebhookHealthState, name="webhook_health_state"),
        nullable=False,
        default=WebhookHealthState.HEALTHY,
        server_default=text("'healthy'"),
    )
    provider_reachability_status: Mapped[ProviderReachabilityStatus] = mapped_column(
        sql_enum(ProviderReachabilityStatus, name="provider_reachability_status"),
        nullable=False,
        default=ProviderReachabilityStatus.REACHABLE,
        server_default=text("'reachable'"),
    )
    last_reachability_failure_code: Mapped[str | None] = mapped_column(String(64))
    last_webhook_rejection_reason: Mapped[WebhookRejectionReason | None] = (
        mapped_column(sql_enum(WebhookRejectionReason, name="webhook_rejection_reason"))
    )
    last_webhook_rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_failed_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_processed_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey(
            "repository_events.id",
            use_alter=True,
            name="fk_repo_conn_last_processed_event_id",
        ),
    )
    last_processed_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    planning_input_reference: Mapped[PlanningInputReference | None] = relationship(
        back_populates="repository_connections",
        foreign_keys=[planning_input_reference_id],
    )
    credential_revisions: Mapped[list[RepositoryCredentialRevision]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
        foreign_keys="RepositoryCredentialRevision.connection_id",
    )
    active_credential_revision: Mapped[RepositoryCredentialRevision | None] = (
        relationship(
            foreign_keys=[active_credential_revision_id],
            post_update=True,
        )
    )
    webhook_secret_revisions: Mapped[list[WebhookSecretRevision]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
        foreign_keys="WebhookSecretRevision.connection_id",
    )
    active_webhook_secret_revision: Mapped[WebhookSecretRevision | None] = relationship(
        foreign_keys=[active_webhook_secret_revision_id],
        post_update=True,
    )
    scope_rule_versions: Mapped[list[CollectionScopeRuleVersion]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
        foreign_keys="CollectionScopeRuleVersion.connection_id",
    )
    active_scope_rule_version: Mapped[CollectionScopeRuleVersion | None] = relationship(
        foreign_keys=[active_scope_rule_version_id],
        post_update=True,
    )
    sync_runs: Mapped[list[RepositorySyncRun]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    repository_events: Mapped[list[RepositoryEvent]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
        foreign_keys="RepositoryEvent.connection_id",
    )
    event_cursors: Mapped[list[RepositoryEventCursor]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
        foreign_keys="RepositoryEventCursor.connection_id",
    )
    code_snapshots: Mapped[list[CodeSnapshot]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    last_processed_event: Mapped[RepositoryEvent | None] = relationship(
        foreign_keys=[last_processed_event_id],
        post_update=True,
    )


class RepositoryCredentialRevision(Base):
    __tablename__ = "repository_credential_revisions"
    __table_args__ = (
        UniqueConstraint("connection_id", "id", name="uq_cred_rev_conn_id_id"),
        CheckConstraint(
            "status != 'active' OR read_only_validated",
            name="ck_cred_rev_active_requires_ro",
        ),
        CheckConstraint(
            "status != 'previous_grace' OR grace_until IS NOT NULL",
            name="ck_cred_rev_grace_until_required",
        ),
        Index(
            "ix_cred_rev_one_active",
            "connection_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_cred_rev_connection_id", "connection_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_connections.id", name="fk_cred_rev_conn_id"),
        nullable=False,
    )
    credential_type: Mapped[CredentialType] = mapped_column(
        sql_enum(CredentialType, name="credential_type"),
        nullable=False,
    )
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    display_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    read_only_validated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    status: Mapped[CredentialRevisionStatus] = mapped_column(
        sql_enum(CredentialRevisionStatus, name="credential_revision_status"),
        nullable=False,
        default=CredentialRevisionStatus.ACTIVE,
    )
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    connection: Mapped[RepositoryConnection] = relationship(
        back_populates="credential_revisions",
        foreign_keys=[connection_id],
    )


class WebhookSecretRevision(Base):
    __tablename__ = "webhook_secret_revisions"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "id", name="uq_webhook_secret_rev_conn_id_id"
        ),
        CheckConstraint(
            "status != 'previous_grace' OR grace_until IS NOT NULL",
            name="ck_webhook_secret_rev_grace_until_required",
        ),
        Index(
            "ix_webhook_secret_rev_one_active",
            "connection_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_webhook_secret_rev_connection_id", "connection_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_connections.id", name="fk_webhook_secret_rev_conn_id"),
        nullable=False,
    )
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WebhookSecretRevisionStatus] = mapped_column(
        sql_enum(WebhookSecretRevisionStatus, name="webhook_secret_revision_status"),
        nullable=False,
        default=WebhookSecretRevisionStatus.ACTIVE,
        server_default=text("'active'"),
    )
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    connection: Mapped[RepositoryConnection] = relationship(
        back_populates="webhook_secret_revisions",
        foreign_keys=[connection_id],
    )


class CollectionScopeRuleVersion(Base):
    __tablename__ = "collection_scope_rule_versions"
    __table_args__ = (
        UniqueConstraint("connection_id", "id", name="uq_scope_rule_conn_id_id"),
        Index("ix_scope_rule_plan_input_ref_id", "planning_input_reference_id"),
        ForeignKeyConstraint(
            ["connection_id", "planning_input_reference_id"],
            [
                "repository_connections.id",
                "repository_connections.planning_input_reference_id",
            ],
            name="fk_scope_rule_plan_input_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_connections.id", name="fk_scope_rule_conn_id"),
        nullable=False,
    )
    planning_input_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("planning_input_references.id", name="fk_scope_rule_plan_input_id"),
        nullable=True,
    )
    include_paths: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    exclude_paths: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    allowed_file_types: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    blocked_file_types: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    max_file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5 * 1024 * 1024,
        server_default=text("5242880"),
    )
    exclude_binary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_auto_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    warning_state: Mapped[ScopeRuleWarningState] = mapped_column(
        sql_enum(ScopeRuleWarningState, name="scope_rule_warning_state"),
        nullable=False,
        default=ScopeRuleWarningState.OK,
        server_default=text("'ok'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)

    connection: Mapped[RepositoryConnection] = relationship(
        back_populates="scope_rule_versions",
        foreign_keys=[connection_id],
    )
    planning_input_reference: Mapped[PlanningInputReference | None] = relationship(
        back_populates="scope_rule_versions"
    )
    snapshots: Mapped[list[CodeSnapshot]] = relationship(
        back_populates="scope_rule_version",
        foreign_keys="CodeSnapshot.scope_rule_version_id",
    )


class RepositoryEvent(Base):
    __tablename__ = "repository_events"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "provider_delivery_id",
            "provider_event_idempotency_source",
            name="uq_repository_events_connection_delivery",
        ),
        CheckConstraint(
            "((verified_secret_revision_id IS NULL) = "
            "(verified_secret_revision_status IS NULL))",
            name="ck_repo_event_verified_secret_pair",
        ),
        ForeignKeyConstraint(
            ["connection_id", "verified_secret_revision_id"],
            ["webhook_secret_revisions.connection_id", "webhook_secret_revisions.id"],
            name="fk_repository_event_verified_webhook_secret_revision_owner",
        ),
        Index(
            "ix_repository_event_verified_secret_revision_id",
            "verified_secret_revision_id",
        ),
        Index("ix_repository_event_sync_run_id", "sync_run_id"),
        Index("ix_repository_event_snapshot_id", "snapshot_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_connections.id", name="fk_repository_event_conn_id"),
        nullable=False,
    )
    provider_delivery_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_event_idempotency_source: Mapped[ProviderEventIdempotencySource] = (
        mapped_column(
            sql_enum(
                ProviderEventIdempotencySource,
                name="provider_event_idempotency_source",
            ),
            nullable=False,
            default=ProviderEventIdempotencySource.DELIVERY_HEADER,
            server_default=text("'delivery_header'"),
        )
    )
    provider_event_type: Mapped[ProviderEventType] = mapped_column(
        sql_enum(ProviderEventType, name="provider_event_type"),
        nullable=False,
    )
    provider_action: Mapped[str | None] = mapped_column(String(128))
    domain_event_type: Mapped[DomainEventType] = mapped_column(
        sql_enum(DomainEventType, name="domain_event_type"),
        nullable=False,
    )
    target_kind: Mapped[EventTargetKind] = mapped_column(
        sql_enum(EventTargetKind, name="event_target_kind"),
        nullable=False,
    )
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    target_ref_name: Mapped[str | None] = mapped_column(String(255))
    target_head_sha: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signature_status: Mapped[SignatureStatus] = mapped_column(
        sql_enum(SignatureStatus, name="signature_status"),
        nullable=False,
    )
    verified_secret_revision_status: Mapped[WebhookSecretRevisionStatus | None] = (
        mapped_column(
            sql_enum(
                WebhookSecretRevisionStatus,
                name="verified_webhook_secret_revision_status",
            )
        )
    )
    verified_secret_revision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    rejection_reason: Mapped[WebhookRejectionReason | None] = mapped_column(
        sql_enum(WebhookRejectionReason, name="repository_event_rejection_reason")
    )
    processing_decision: Mapped[ProcessingDecision] = mapped_column(
        sql_enum(ProcessingDecision, name="processing_decision"),
        nullable=False,
    )
    processing_status: Mapped[EventProcessingStatus] = mapped_column(
        sql_enum(EventProcessingStatus, name="event_processing_status"),
        nullable=False,
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_sync_runs.id", name="fk_repository_event_sync_run_id")
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("code_snapshots.id", name="fk_repository_event_snapshot_id")
    )

    connection: Mapped[RepositoryConnection] = relationship(
        back_populates="repository_events",
        foreign_keys=[connection_id],
    )


class RepositoryEventCursor(Base):
    __tablename__ = "repository_event_cursors"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "target_key",
            name="uq_repository_event_cursors_connection_target",
        ),
        Index("ix_repository_event_cursor_latest_event_id", "latest_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "repository_connections.id", name="fk_repository_event_cursor_conn_id"
        ),
        nullable=False,
    )
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    latest_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "repository_events.id", name="fk_repository_event_cursor_latest_event_id"
        ),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    connection: Mapped[RepositoryConnection] = relationship(
        back_populates="event_cursors",
        foreign_keys=[connection_id],
    )


class RepositorySyncRun(Base):
    __tablename__ = "repository_sync_runs"
    __table_args__ = (
        UniqueConstraint("connection_id", "id", name="uq_sync_run_conn_id_id"),
        Index("ix_sync_run_trigger_event_id", "trigger_event_id"),
        Index(
            "ix_sync_run_one_active_per_requested_ref",
            "connection_id",
            "requested_ref_type",
            "requested_ref_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
        Index(
            "ix_sync_run_one_blocked_per_requested_ref",
            "connection_id",
            "requested_ref_type",
            "requested_ref_key",
            unique=True,
            postgresql_where=text("status = 'blocked'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_connections.id", name="fk_sync_run_conn_id"),
        nullable=False,
    )
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_events.id", name="fk_sync_run_trigger_event_id")
    )
    trigger_type: Mapped[SyncTriggerType] = mapped_column(
        sql_enum(SyncTriggerType, name="sync_trigger_type"),
        nullable=False,
    )
    requested_ref_type: Mapped[RefType] = mapped_column(
        sql_enum(RefType, name="requested_ref_type"),
        nullable=False,
    )
    requested_ref_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_ref_key: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_commit_sha: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[SyncRunStatus] = mapped_column(
        sql_enum(SyncRunStatus, name="sync_run_status"),
        nullable=False,
        default=SyncRunStatus.PENDING,
        server_default=text("'pending'"),
    )
    failure_code: Mapped[SyncFailureCode | None] = mapped_column(
        sql_enum(SyncFailureCode, name="sync_failure_code")
    )
    failure_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    dispatch_enqueued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    connection: Mapped[RepositoryConnection] = relationship(back_populates="sync_runs")
    code_snapshot: Mapped[CodeSnapshot | None] = relationship(
        back_populates="sync_run",
        uselist=False,
        foreign_keys="CodeSnapshot.sync_run_id",
    )


class CodeSnapshot(Base):
    __tablename__ = "code_snapshots"
    __table_args__ = (
        UniqueConstraint("sync_run_id", name="uq_code_snapshot_sync_run_id"),
        CheckConstraint(
            "archive_path NOT LIKE '/%' AND archive_path NOT LIKE '%..%'",
            name="ck_code_snapshot_archive_path_safe",
        ),
        ForeignKeyConstraint(
            ["connection_id", "sync_run_id"],
            ["repository_sync_runs.connection_id", "repository_sync_runs.id"],
            name="fk_code_snapshot_sync_owner",
        ),
        ForeignKeyConstraint(
            ["connection_id", "scope_rule_version_id"],
            [
                "collection_scope_rule_versions.connection_id",
                "collection_scope_rule_versions.id",
            ],
            name="fk_code_snapshot_scope_owner",
        ),
        Index("ix_code_snapshot_connection_id", "connection_id"),
        Index("ix_code_snapshot_scope_rule_version_id", "scope_rule_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_connections.id", name="fk_code_snapshot_conn_id"),
        nullable=False,
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_sync_runs.id", name="fk_code_snapshot_sync_id"),
        nullable=False,
    )
    scope_rule_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "collection_scope_rule_versions.id", name="fk_code_snapshot_scope_id"
        ),
        nullable=False,
    )
    requested_ref_type: Mapped[RefType] = mapped_column(
        sql_enum(RefType, name="requested_ref_type"),
        nullable=False,
    )
    requested_ref_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    connection: Mapped[RepositoryConnection] = relationship(
        back_populates="code_snapshots"
    )
    sync_run: Mapped[RepositorySyncRun] = relationship(
        back_populates="code_snapshot",
        foreign_keys=[sync_run_id],
    )
    scope_rule_version: Mapped[CollectionScopeRuleVersion] = relationship(
        back_populates="snapshots",
        foreign_keys=[scope_rule_version_id],
    )
    files: Mapped[list[CodeSnapshotFile]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class CodeSnapshotFile(Base):
    __tablename__ = "code_snapshot_files"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "path"),
        CheckConstraint(
            "archive_blob_path NOT LIKE '/%' AND archive_blob_path NOT LIKE '%..%'",
            name="ck_snapshot_file_blob_path_safe",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_snapshots.id", name="fk_snapshot_file_snapshot_id"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    extension: Mapped[str | None] = mapped_column(String(32))
    language_hint: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_blob_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    included_by: Mapped[SnapshotInclusionReason] = mapped_column(
        sql_enum(SnapshotInclusionReason, name="snapshot_inclusion_reason"),
        nullable=False,
    )

    snapshot: Mapped[CodeSnapshot] = relationship(back_populates="files")
