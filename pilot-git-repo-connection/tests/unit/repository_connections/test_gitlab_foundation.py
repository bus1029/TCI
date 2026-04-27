from __future__ import annotations

from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import SimpleNamespace
from types import ModuleType
from typing import Any, cast
from unittest.mock import MagicMock
import uuid

# mypy: disable-error-code=import-untyped
from sqlalchemy import CheckConstraint, UniqueConstraint

from tci.infrastructure.persistence.models import (
    Base,
    DefaultRefType,
    DomainEventType,
    EventProcessingStatus,
    EventTargetKind,
    ProcessingDecision,
    ProviderEventIdempotencySource,
    ProviderEventType,
    RepositoryConnectionStatus,
    RepositoryProvider,
    RepositoryTransport,
    SignatureStatus,
    SyncTriggerType,
    WebhookAuthMode,
)
from tci.infrastructure.persistence.repository_connection_repository import (
    RepositoryConnectionDraft,
    RepositoryConnectionRepository,
)
from tci.infrastructure.persistence.repository_event_repository import (
    RepositoryEventDraft,
    RepositoryEventRepository,
)
from tests.support.repository_connection_testkit import (
    FakeRepositoryConnectionRepository,
    InMemoryRepositoryStore,
    TestWebhookSecretRevision as WebhookSecretRevisionFixture,
)


def _load_revision_module(filename: str, module_name: str):
    revision_path = (
        Path(__file__).resolve().parents[3] / "alembic" / "versions" / filename
    )
    spec = spec_from_file_location(module_name, revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{filename} Alembic revision 모듈을 불러올 수 없습니다.")

    module = module_from_spec(spec)
    alembic_stub = ModuleType("alembic")
    setattr(alembic_stub, "op", object())
    previous_alembic = sys.modules.get("alembic")
    sys.modules["alembic"] = alembic_stub

    try:
        spec.loader.exec_module(module)
    finally:
        if previous_alembic is None:
            sys.modules.pop("alembic", None)
        else:
            sys.modules["alembic"] = previous_alembic

    return module


def _enum_values(column: Any) -> list[str]:
    return list(cast(Any, column.type).enums)


def _check_constraints(table_name: str) -> dict[str, str]:
    table = Base.metadata.tables[table_name]
    return {
        cast(str, constraint.name): str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def _check_sql(table_name: str, constraint_suffix: str) -> str:
    constraints = _check_constraints(table_name)
    for name, sqltext in constraints.items():
        if name.endswith(constraint_suffix):
            return sqltext
    raise AssertionError(f"{constraint_suffix} check constraint가 metadata에 없습니다.")


def test_gitlab_foundation_repository_connection_metadata_is_provider_aware() -> None:
    connection_table = Base.metadata.tables["repository_connections"]

    assert [member.value for member in RepositoryProvider] == [
        "github_cloud",
        "gitlab_self_managed",
    ]
    assert {
        "provider_instance_url",
        "provider_project_path",
        "webhook_auth_mode",
        "provider_reachability_status",
        "last_reachability_failure_code",
    } <= set(connection_table.c.keys())


def test_gitlab_foundation_connection_constraints_enforce_gitlab_instance_and_host_match() -> (
    None
):
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "008_gitlab_insecure_http_transport.py"
    )
    revision_text = revision_path.read_text(encoding="utf-8")
    instance_url_sql = _check_sql(
        "repository_connections", "ck_repo_conn_gitlab_instance_url_https"
    )
    instance_host_sql = _check_sql(
        "repository_connections", "ck_repo_conn_gitlab_instance_host_match"
    )
    instance_port_sql = _check_sql(
        "repository_connections", "ck_repo_conn_gitlab_https_port_match"
    )
    scheme_match_sql = _check_sql(
        "repository_connections", "ck_repo_conn_gitlab_http_scheme_match"
    )
    remote_url_userinfo_sql = _check_sql(
        "repository_connections", "ck_repo_conn_remote_url_no_userinfo"
    )
    transport_scheme_sql = _check_sql(
        "repository_connections", "ck_repo_conn_transport_remote_url_scheme_match"
    )

    assert "provider_instance_url ~ '^https?://" in instance_url_sql
    assert "(?::[0-9]+)?/?$" in instance_url_sql
    assert "!~ '^https?://[^/:/]*-(?::[0-9]+)?/?$'" in instance_url_sql
    assert "lower(regexp_replace(provider_instance_url, '^https?://" in instance_host_sql
    assert "WHEN remote_url LIKE 'http://%'" in instance_host_sql
    assert "regexp_replace(remote_url, '^git@([^:]+):.*$', '\\1')" in instance_host_sql
    assert "regexp_replace(remote_url, '^ssh://" in instance_host_sql
    assert "coalesce(nullif" in instance_port_sql
    assert "^https://[^/:?#]+(?::([0-9]+))?/.*$" in instance_port_sql
    assert "^http://[^/:?#]+(?::([0-9]+))?/.*$" in instance_port_sql
    assert "provider_instance_url LIKE 'https://%'" in scheme_match_sql
    assert "provider_instance_url LIKE 'http://%'" in scheme_match_sql
    assert "http://%@%/%" in remote_url_userinfo_sql
    assert "transport = 'http'" in transport_scheme_sql
    assert "transport = 'https'" in transport_scheme_sql
    assert "transport = 'ssh'" in transport_scheme_sql
    assert "ssh://%:%@%/%" in remote_url_userinfo_sql
    assert "remote_url NOT LIKE '%?%'" in remote_url_userinfo_sql
    assert "remote_url NOT LIKE '%#%'" in remote_url_userinfo_sql
    remote_url_host_sql = _check_sql(
        "repository_connections", "ck_repo_conn_remote_url_host"
    )
    assert "github\\.com\\.?" in remote_url_host_sql
    assert "!~* '^https://github\\.com\\.?" in remote_url_host_sql
    assert "!~* '^http://github\\.com\\.?" in remote_url_host_sql
    assert "!~* '^ssh://(?:[^@/]+@)?github\\.com\\.?" in remote_url_host_sql
    assert "!~ '^git@[-[:space:][:cntrl:]]'" in remote_url_host_sql
    assert "remote_url LIKE 'http://%/%'" in remote_url_host_sql
    assert "remote_url LIKE 'ssh://git@%/%'" in remote_url_host_sql
    assert "!~ '^ssh://git@[-[:space:][:cntrl:]]'" in remote_url_host_sql
    assert "!~ '^git@[^:]*\\.:'" in remote_url_host_sql
    assert "!~ '^https://[^/?#]*\\." in remote_url_host_sql
    assert "!~ '^http://[^/?#]*\\." in remote_url_host_sql
    assert "!~ '^ssh://git@[^/?#]*\\." in remote_url_host_sql
    assert "!~ '^https://\\['" in remote_url_host_sql
    assert "!~ '^http://\\['" in remote_url_host_sql
    assert "!~ '^ssh://git@\\['" in remote_url_host_sql
    provider_project_path_sql = _check_sql(
        "repository_connections", "ck_repo_conn_provider_project_path"
    )
    project_path_match_sql = _check_sql(
        "repository_connections", "ck_repo_conn_gitlab_project_path_match"
    )
    assert "provider_project_path IS NOT NULL" in provider_project_path_sql
    assert "provider_project_path NOT LIKE '%?%'" in provider_project_path_sql
    assert "provider_project_path NOT LIKE '%#%'" in provider_project_path_sql
    assert (
        "provider_project_path !~ '[[:space:][:cntrl:]]'" in provider_project_path_sql
    )
    assert "provider_project_path !~ '(^|/)\\.\\.?(/|$)'" in provider_project_path_sql
    assert "provider_project_path IS NOT NULL" in project_path_match_sql
    assert "WHEN remote_url LIKE 'http://%'" in project_path_match_sql
    assert "ck_repo_conn_gitlab_http_scheme_match" in revision_text
    assert "ck_repo_conn_transport_remote_url_scheme_match" in revision_text
    assert "DROP CONSTRAINT IF EXISTS" in revision_text
    assert "truncate_and_render_constraint_name" in revision_text
    assert "ck_repo_conn_gitlab_instance_url_https" in revision_text
    assert "ck_repo_conn_gitlab_instance_host_match" in revision_text
    assert "ck_repo_conn_gitlab_https_port_match" in revision_text


def test_gitlab_foundation_merge_request_enums_and_delivery_source_are_registered() -> (
    None
):
    event_table = Base.metadata.tables["repository_events"]
    sync_run_table = Base.metadata.tables["repository_sync_runs"]

    assert [member.value for member in ProviderEventType] == [
        "push",
        "pull_request",
        "merge_request",
        "ping",
        "unknown",
    ]
    assert [member.value for member in DomainEventType] == [
        "commit_recorded",
        "push_received",
        "pr_received",
        "mr_received",
        "signature_rejected",
        "secret_missing",
        "secret_mismatch",
    ]
    assert [member.value for member in EventTargetKind] == [
        "default_ref",
        "pull_request_source",
        "merge_request_source",
        "none",
    ]
    assert [member.value for member in SyncTriggerType] == [
        "manual_initial",
        "manual_refresh",
        "webhook_push",
        "webhook_pull_request",
        "webhook_merge_request",
    ]
    assert "provider_event_idempotency_source" in event_table.c
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in event_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and getattr(constraint, "name", None)
        == "uq_repository_events_connection_delivery"
    }
    assert unique_constraints == {
        (
            "connection_id",
            "provider_delivery_id",
            "provider_event_idempotency_source",
        )
    }
    assert _enum_values(event_table.c["provider_event_type"]) == [
        "push",
        "pull_request",
        "merge_request",
        "ping",
        "unknown",
    ]
    assert _enum_values(sync_run_table.c["trigger_type"]) == [
        "manual_initial",
        "manual_refresh",
        "webhook_push",
        "webhook_pull_request",
        "webhook_merge_request",
    ]


def test_gitlab_foundation_repository_event_secret_audit_columns_move_together() -> (
    None
):
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "004_gitlab_self_managed_provider_support.py"
    )
    revision_text = revision_path.read_text(encoding="utf-8")
    verified_secret_sql = _check_sql(
        "repository_events", "ck_repo_event_verified_secret_pair"
    )

    assert "verified_secret_revision_id IS NULL" in verified_secret_sql
    assert "verified_secret_revision_status IS NULL" in verified_secret_sql
    assert "ck_repo_event_verified_secret_pair" in revision_text
    assert "Cannot add ck_repo_event_verified_secret_pair" in revision_text


def test_gitlab_foundation_active_webhook_secret_fk_has_supporting_index() -> None:
    connection_table = Base.metadata.tables["repository_connections"]
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "004_gitlab_self_managed_provider_support.py"
    )
    revision_text = revision_path.read_text(encoding="utf-8")

    index_names = {index.name for index in connection_table.indexes}

    assert "ix_repo_conn_active_webhook_secret_revision_id" in index_names
    assert "ix_repo_conn_active_webhook_secret_revision_id" in revision_text
    assert "Cannot add fk_repo_conn_active_webhook_secret_owner" in revision_text


def test_gitlab_foundation_additive_migration_exists_and_targets_revision_003() -> None:
    revision_004 = _load_revision_module(
        "004_gitlab_self_managed_provider_support.py",
        "gitlab_self_managed_provider_support",
    )

    assert revision_004.down_revision == "003_event_secret_revision"
    assert revision_004.revision == "004_gitlab_provider_support"


def test_gitlab_foundation_downgrade_recreates_pre_004_enums_with_preflight() -> None:
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "004_gitlab_self_managed_provider_support.py"
    )
    revision_text = revision_path.read_text(encoding="utf-8")

    assert "def downgrade()" in revision_text
    assert "Cannot downgrade 004 while GitLab provider data exists." in revision_text
    assert "_recreate_enum_without_values(" in revision_text
    assert 'type_name="repository_provider"' in revision_text
    assert "DROP TYPE provider_event_idempotency_source" in revision_text


def test_gitlab_foundation_repository_requires_gitlab_metadata_for_nested_project_paths() -> (
    None
):
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://gitlab.example.com/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com",
        provider_project_path="group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    connection = repository.create(draft)

    assert connection.provider_project_path == "group/subgroup/repo"
    assert connection.provider_instance_url == "https://gitlab.example.com"
    assert connection.webhook_auth_mode is WebhookAuthMode.SHARED_TOKEN


def test_gitlab_foundation_repository_rejects_missing_gitlab_project_path() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://gitlab.example.com/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com",
        provider_project_path=None,
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    try:
        repository.create(draft)
    except ValueError as error:
        assert "provider_project_path" in str(error)
    else:
        raise AssertionError("GitLab connection should require provider_project_path")


def test_gitlab_foundation_repository_rejects_blank_gitlab_instance_url() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://gitlab.example.com/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="   ",
        provider_project_path="group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    try:
        repository.create(draft)
    except ValueError as error:
        assert "provider_instance_url" in str(error)
    else:
        raise AssertionError(
            "GitLab connection should require a non-blank provider_instance_url"
        )


def test_gitlab_foundation_repository_rejects_github_provider_instance_url() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITHUB_CLOUD,
                remote_url="https://github.com/org/repo.git",
                transport=RepositoryTransport.HTTPS,
                repository_owner="org",
                repository_name="repo",
                provider_instance_url="https://gitlab.example.com",
                provider_project_path="other/path",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "GitHub connection does not accept provider_instance_url" in str(error)
    else:
        raise AssertionError("GitHub connection should reject provider_instance_url")


def test_gitlab_foundation_repository_rejects_remote_url_query_or_fragment() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="https://gitlab.example.com/group/subgroup/repo.git?via=ui",
                transport=RepositoryTransport.HTTPS,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="https://gitlab.example.com",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "must not include query or fragment" in str(error)
    else:
        raise AssertionError(
            "GitLab connection should reject remote_url query/fragment"
        )


def test_gitlab_foundation_repository_rejects_http_userinfo() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="http://x-access-token:secret@gitlab.example.com/group/subgroup/repo.git",
                transport=RepositoryTransport.HTTP,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="http://gitlab.example.com",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "must not include credential-bearing userinfo" in str(error)
    else:
        raise AssertionError("GitLab HTTP connection should reject userinfo")


def test_gitlab_foundation_repository_rejects_http_remote_with_https_instance() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="http://gitlab.example.com/group/subgroup/repo.git",
                transport=RepositoryTransport.HTTP,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="https://gitlab.example.com:80",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "scheme must match" in str(error)
    else:
        raise AssertionError(
            "GitLab HTTP remote should reject HTTPS provider_instance_url"
        )


def test_gitlab_foundation_repository_rejects_http_remote_with_https_transport() -> (
    None
):
    repository = RepositoryConnectionRepository(session=MagicMock())

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="http://gitlab.example.com/group/subgroup/repo.git",
                transport=RepositoryTransport.HTTPS,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="http://gitlab.example.com",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "transport must match" in str(error)
    else:
        raise AssertionError("GitLab HTTP remote should reject HTTPS transport")


def test_gitlab_foundation_repository_rejects_https_remote_with_http_instance() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="https://gitlab.example.com:80/group/subgroup/repo.git",
                transport=RepositoryTransport.HTTPS,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="http://gitlab.example.com",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "scheme must match" in str(error)
    else:
        raise AssertionError(
            "GitLab HTTPS remote should reject HTTP provider_instance_url"
        )


def test_gitlab_foundation_repository_treats_gitlab_path_prefix_as_project_namespace_for_ssh_remote() -> (
    None
):
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="git@GitLab.EXAMPLE.com:gitlab/group/subgroup/repo.git",
        transport=RepositoryTransport.SSH,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com",
        provider_project_path="gitlab/group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    connection = repository.create(draft)

    assert connection.provider_instance_url == "https://gitlab.example.com"
    assert connection.provider_project_path == "gitlab/group/subgroup/repo"


def test_gitlab_foundation_repository_treats_gitlab_path_prefix_as_project_namespace_for_https_remote() -> (
    None
):
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://GitLab.EXAMPLE.com/gitlab/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://GitLab.EXAMPLE.com/",
        provider_project_path="gitlab/group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    connection = repository.create(draft)

    assert connection.provider_instance_url == "https://gitlab.example.com"
    assert connection.provider_project_path == "gitlab/group/subgroup/repo"


def test_gitlab_foundation_repository_accepts_nondefault_https_instance_port() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://gitlab.example.com:8443/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com:8443",
        provider_project_path="group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    connection = repository.create(draft)

    assert connection.provider_instance_url == "https://gitlab.example.com:8443"


def test_gitlab_foundation_repository_rejects_https_port_mismatch() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://gitlab.example.com/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com:8443",
        provider_project_path="group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    try:
        repository.create(draft)
    except ValueError as error:
        assert "HTTP(S) remote_url port must match" in str(error)
    else:
        raise AssertionError(
            "GitLab connection should reject HTTPS port mismatch against default 443"
        )


def test_gitlab_foundation_repository_rejects_instance_url_with_query_or_fragment() -> (
    None
):
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://gitlab.example.com/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com?via=ui",
        provider_project_path="group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    try:
        repository.create(draft)
    except ValueError as error:
        assert "without query or fragment" in str(error)
    else:
        raise AssertionError(
            "GitLab connection should reject provider_instance_url with query or fragment"
        )


def test_gitlab_foundation_repository_rejects_project_path_mismatch() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="git@gitlab.example.com:group/subgroup/repo.git",
        transport=RepositoryTransport.SSH,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com",
        provider_project_path="group/other/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    try:
        repository.create(draft)
    except ValueError as error:
        assert "provider_project_path must match remote_url path" in str(error)
    else:
        raise AssertionError(
            "GitLab connection should reject mismatched provider_project_path"
        )


def test_gitlab_foundation_repository_accepts_localhost_and_private_ip_remotes() -> (
    None
):
    repository = RepositoryConnectionRepository(session=MagicMock())

    for remote_url, transport, instance_url in (
        (
            "https://localhost/group/subgroup/repo.git",
            RepositoryTransport.HTTPS,
            "https://localhost",
        ),
        (
            "ssh://git@192.168.10.20:2222/group/subgroup/repo.git",
            RepositoryTransport.SSH,
            "https://192.168.10.20",
        ),
    ):
        draft = RepositoryConnectionDraft(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            planning_input_reference_id=uuid.uuid4(),
            provider=RepositoryProvider.GITLAB_SELF_MANAGED,
            remote_url=remote_url,
            transport=transport,
            repository_owner="group/subgroup",
            repository_name="repo",
            provider_instance_url=instance_url,
            provider_project_path="group/subgroup/repo",
            default_ref_type=DefaultRefType.BRANCH,
            default_ref_name="main",
            status=RepositoryConnectionStatus.ACTIVE,
            mirror_path=".runtime/git-mirrors/example.git",
            last_verified_at=None,
        )

        connection = repository.create(draft)

        assert connection.provider_instance_url == instance_url
        assert connection.provider_project_path == "group/subgroup/repo"


def test_gitlab_foundation_repository_rejects_trailing_dot_hosts() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    for remote_url, transport, instance_url in (
        (
            "https://gitlab.example.com./group/subgroup/repo.git",
            RepositoryTransport.HTTPS,
            "https://gitlab.example.com.",
        ),
        (
            "git@gitlab.example.com.:group/subgroup/repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com.",
        ),
        (
            "ssh://git@gitlab.example.com./group/subgroup/repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com.",
        ),
    ):
        draft = RepositoryConnectionDraft(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            planning_input_reference_id=uuid.uuid4(),
            provider=RepositoryProvider.GITLAB_SELF_MANAGED,
            remote_url=remote_url,
            transport=transport,
            repository_owner="group/subgroup",
            repository_name="repo",
            provider_instance_url=instance_url,
            provider_project_path="group/subgroup/repo",
            default_ref_type=DefaultRefType.BRANCH,
            default_ref_name="main",
            status=RepositoryConnectionStatus.ACTIVE,
            mirror_path=".runtime/git-mirrors/example.git",
            last_verified_at=None,
        )

        try:
            repository.create(draft)
        except ValueError as error:
            assert "supported host" in str(error)
        else:
            raise AssertionError("GitLab connection should reject trailing-dot hosts")


def test_gitlab_foundation_repository_rejects_invalid_project_paths() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    for project_path in (
        "group name/subgroup/repo",
        "group/\x01/repo",
        "group/./repo",
        "group/../repo",
    ):
        draft = RepositoryConnectionDraft(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            planning_input_reference_id=uuid.uuid4(),
            provider=RepositoryProvider.GITLAB_SELF_MANAGED,
            remote_url="https://gitlab.example.com/group/subgroup/repo.git",
            transport=RepositoryTransport.HTTPS,
            repository_owner="group/subgroup",
            repository_name="repo",
            provider_instance_url="https://gitlab.example.com",
            provider_project_path=project_path,
            default_ref_type=DefaultRefType.BRANCH,
            default_ref_name="main",
            status=RepositoryConnectionStatus.ACTIVE,
            mirror_path=".runtime/git-mirrors/example.git",
            last_verified_at=None,
        )

        try:
            repository.create(draft)
        except ValueError as error:
            assert "normalized provider_project_path" in str(error)
        else:
            raise AssertionError(
                "GitLab connection should reject invalid project paths"
            )


def test_gitlab_foundation_repository_rejects_unsafe_ssh_hosts() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    for remote_url, instance_url in (
        (
            "ssh://deploy@gitlab.example.com/group/subgroup/repo.git",
            "https://gitlab.example.com",
        ),
        (
            "git@gitlab.example.com:group/subgroup/repo.git?x=1",
            "https://gitlab.example.com",
        ),
        (
            "git@gitlab.example.com:group/subgroup/repo.git#frag",
            "https://gitlab.example.com",
        ),
        (
            "ssh://git@gitlab.example.com:/group/subgroup/repo.git",
            "https://gitlab.example.com",
        ),
        ("git@-oProxyCommand=sh:group/subgroup/repo.git", "https://-oproxycommand=sh"),
        ("git@host withspace:group/subgroup/repo.git", "https://host withspace"),
        ("ssh://git@-evil/group/subgroup/repo.git", "https://-evil"),
        ("ssh://git@[::1]/group/subgroup/repo.git", "https://[::1]"),
    ):
        draft = RepositoryConnectionDraft(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            planning_input_reference_id=uuid.uuid4(),
            provider=RepositoryProvider.GITLAB_SELF_MANAGED,
            remote_url=remote_url,
            transport=RepositoryTransport.SSH,
            repository_owner="group/subgroup",
            repository_name="repo",
            provider_instance_url=instance_url,
            provider_project_path="group/subgroup/repo",
            default_ref_type=DefaultRefType.BRANCH,
            default_ref_name="main",
            status=RepositoryConnectionStatus.ACTIVE,
            mirror_path=".runtime/git-mirrors/example.git",
            last_verified_at=None,
        )

        try:
            repository.create(draft)
        except ValueError as error:
            assert (
                "supported" in str(error)
                or "query or fragment" in str(error)
                or "whitespace or control" in str(error)
            )
        else:
            raise AssertionError("GitLab connection should reject unsafe SSH hosts")


def test_gitlab_foundation_repository_event_repository_tracks_idempotency_source() -> (
    None
):
    session = MagicMock()
    repository = RepositoryEventRepository(session=session)
    draft = RepositoryEventDraft(
        id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        provider_delivery_id="delivery-1",
        provider_event_type=ProviderEventType.MERGE_REQUEST,
        provider_action="update",
        domain_event_type=DomainEventType.MR_RECEIVED,
        target_kind=EventTargetKind.MERGE_REQUEST_SOURCE,
        target_key="mr:42",
        target_ref_name="feature/demo",
        target_head_sha="a" * 40,
        occurred_at=datetime.now(tz=UTC),
        received_at=datetime.now(tz=UTC),
        processed_at=None,
        signature_status=SignatureStatus.VERIFIED,
        verified_secret_revision_status=None,
        verified_secret_revision_id=None,
        rejection_reason=None,
        processing_decision=ProcessingDecision.QUEUED,
        processing_status=EventProcessingStatus.RECEIVED,
        payload_hash="b" * 64,
        provider_event_idempotency_source=ProviderEventIdempotencySource.UUID_HEADER,
    )

    event = repository.create(draft)
    repository.get_by_delivery_id(
        connection_id=draft.connection_id,
        provider_delivery_id=draft.provider_delivery_id,
        provider_event_idempotency_source=ProviderEventIdempotencySource.UUID_HEADER,
    )

    assert (
        event.provider_event_idempotency_source
        is ProviderEventIdempotencySource.UUID_HEADER
    )
    statement = session.scalar.call_args[0][0]
    assert "provider_event_idempotency_source" in str(statement)


def test_gitlab_foundation_repository_rejects_inconsistent_instance_host() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())
    draft = RepositoryConnectionDraft(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        planning_input_reference_id=uuid.uuid4(),
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://github.com/group/subgroup/repo.git",
        transport=RepositoryTransport.HTTPS,
        repository_owner="group",
        repository_name="repo",
        provider_instance_url="https://gitlab.example.com",
        provider_project_path="group/subgroup/repo",
        default_ref_type=DefaultRefType.BRANCH,
        default_ref_name="main",
        status=RepositoryConnectionStatus.ACTIVE,
        mirror_path=".runtime/git-mirrors/example.git",
        last_verified_at=None,
    )

    try:
        repository.create(draft)
    except ValueError as error:
        assert "GitHub remotes cannot be stored as GitLab providers" in str(error)
    else:
        raise AssertionError(
            "GitLab connection should reject inconsistent provider host"
        )


def test_gitlab_foundation_repository_rejects_github_host_variants() -> None:
    repository = RepositoryConnectionRepository(session=MagicMock())

    for remote_url, transport in (
        ("https://github.com:443/group/subgroup/repo.git", RepositoryTransport.HTTPS),
        ("ssh://git@github.com:22/group/subgroup/repo.git", RepositoryTransport.SSH),
    ):
        draft = RepositoryConnectionDraft(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            planning_input_reference_id=uuid.uuid4(),
            provider=RepositoryProvider.GITLAB_SELF_MANAGED,
            remote_url=remote_url,
            transport=transport,
            repository_owner="group",
            repository_name="repo",
            provider_instance_url="https://github.com",
            provider_project_path="group/subgroup/repo",
            default_ref_type=DefaultRefType.BRANCH,
            default_ref_name="main",
            status=RepositoryConnectionStatus.ACTIVE,
            mirror_path=".runtime/git-mirrors/example.git",
            last_verified_at=None,
        )

        try:
            repository.create(draft)
        except ValueError as error:
            assert "GitHub remotes cannot be stored as GitLab providers" in str(error)
        else:
            raise AssertionError("GitLab provider should reject GitHub-hosted remotes")


def test_gitlab_foundation_repository_rejects_cross_connection_webhook_secret_revision() -> (
    None
):
    session = MagicMock()
    repository = RepositoryConnectionRepository(session=session)
    repository._require = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            active_webhook_secret_revision_id=None,
            webhook_health_state=None,
            last_webhook_rejection_reason="old",
            last_webhook_rejected_at=datetime.now(tz=UTC),
        )
    )
    session.scalar.return_value = None

    try:
        repository.set_active_webhook_secret_revision(
            workspace_id=uuid.uuid4(),
            connection_id=uuid.uuid4(),
            webhook_secret_revision_id=uuid.uuid4(),
        )
    except LookupError as error:
        assert "webhook secret revision" in str(error)
    else:
        raise AssertionError(
            "cross-connection webhook secret revision should be rejected"
        )


def test_gitlab_foundation_fake_repository_rejects_cross_connection_webhook_secret_revision() -> (
    None
):
    store = InMemoryRepositoryStore()
    repository = FakeRepositoryConnectionRepository(store)
    workspace_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    foreign_connection_id = uuid.uuid4()
    repository.create(
        RepositoryConnectionDraft(
            id=connection_id,
            workspace_id=workspace_id,
            planning_input_reference_id=uuid.uuid4(),
            provider=RepositoryProvider.GITLAB_SELF_MANAGED,
            remote_url="https://gitlab.example.com/group/subgroup/repo.git",
            transport=RepositoryTransport.HTTPS,
            repository_owner="group",
            repository_name="repo",
            provider_instance_url="https://gitlab.example.com",
            provider_project_path="group/subgroup/repo",
            default_ref_type=DefaultRefType.BRANCH,
            default_ref_name="main",
            status=RepositoryConnectionStatus.ACTIVE,
            mirror_path=".runtime/git-mirrors/example.git",
            last_verified_at=None,
        )
    )
    foreign_secret_id = uuid.uuid4()
    store.webhook_secret_revisions[foreign_secret_id] = WebhookSecretRevisionFixture(
        id=foreign_secret_id,
        connection_id=foreign_connection_id,
        secret="secret",
        status="active",
        created_at=datetime.now(tz=UTC),
    )

    try:
        repository.set_active_webhook_secret_revision(
            workspace_id=workspace_id,
            connection_id=connection_id,
            webhook_secret_revision_id=foreign_secret_id,
        )
    except LookupError as error:
        assert "webhook secret revision" in str(error)
    else:
        raise AssertionError(
            "fake repository should reject cross-connection webhook secret revision"
        )


def test_gitlab_foundation_fake_repository_rejects_credential_bearing_remote_url() -> (
    None
):
    store = InMemoryRepositoryStore()
    repository = FakeRepositoryConnectionRepository(store)

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="ssh://git:secret@gitlab.example.com/group/subgroup/repo.git",
                transport=RepositoryTransport.SSH,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="https://gitlab.example.com",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "must not include credential-bearing userinfo" in str(error)
    else:
        raise AssertionError(
            "fake repository should reject credential-bearing remote_url"
        )


def test_gitlab_foundation_fake_repository_rejects_http_userinfo() -> None:
    store = InMemoryRepositoryStore()
    repository = FakeRepositoryConnectionRepository(store)

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="http://x-access-token:secret@gitlab.example.com/group/subgroup/repo.git",
                transport=RepositoryTransport.HTTP,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="http://gitlab.example.com",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "must not include credential-bearing userinfo" in str(error)
    else:
        raise AssertionError("fake repository should reject HTTP userinfo")


def test_gitlab_foundation_fake_repository_rejects_remote_url_query_or_fragment() -> (
    None
):
    store = InMemoryRepositoryStore()
    repository = FakeRepositoryConnectionRepository(store)

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITLAB_SELF_MANAGED,
                remote_url="https://gitlab.example.com/group/subgroup/repo.git#frag",
                transport=RepositoryTransport.HTTPS,
                repository_owner="group",
                repository_name="repo",
                provider_instance_url="https://gitlab.example.com",
                provider_project_path="group/subgroup/repo",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "must not include query or fragment" in str(error)
    else:
        raise AssertionError("fake repository should reject remote_url query/fragment")


def test_gitlab_foundation_fake_repository_rejects_github_provider_instance_url() -> (
    None
):
    store = InMemoryRepositoryStore()
    repository = FakeRepositoryConnectionRepository(store)

    try:
        repository.create(
            RepositoryConnectionDraft(
                id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                planning_input_reference_id=uuid.uuid4(),
                provider=RepositoryProvider.GITHUB_CLOUD,
                remote_url="https://github.com/org/repo.git",
                transport=RepositoryTransport.HTTPS,
                repository_owner="org",
                repository_name="repo",
                provider_instance_url="https://gitlab.example.com",
                provider_project_path="other/path",
                default_ref_type=DefaultRefType.BRANCH,
                default_ref_name="main",
                status=RepositoryConnectionStatus.ACTIVE,
                mirror_path=".runtime/git-mirrors/example.git",
                last_verified_at=None,
            )
        )
    except ValueError as error:
        assert "GitHub connection does not accept provider_instance_url" in str(error)
    else:
        raise AssertionError(
            "fake repository should reject GitHub provider_instance_url"
        )
