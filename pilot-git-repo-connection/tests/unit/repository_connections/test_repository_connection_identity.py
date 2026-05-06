from __future__ import annotations

from tci.domain.services.repository_connection_support import (
    build_repository_identity,
)
from tci.infrastructure.git.remote_parsers import parse_repository_remote
from tci.infrastructure.persistence.models import (
    RepositoryProvider,
    RepositoryTransport,
)


def test_github_manual_url_and_candidate_share_canonical_identity() -> None:
    parsed_remote = parse_repository_remote(
        provider=RepositoryProvider.GITHUB_CLOUD,
        remote_url="https://github.com/acme/sample-repo.git",
        transport=RepositoryTransport.HTTPS,
    )

    manual_identity = build_repository_identity(
        provider=RepositoryProvider.GITHUB_CLOUD,
        provider_instance_url=parsed_remote.provider_instance_url,
        provider_project_path=parsed_remote.provider_project_path,
    )
    candidate_identity = build_repository_identity(
        provider=RepositoryProvider.GITHUB_CLOUD,
        provider_instance_url=None,
        provider_project_path="acme/sample-repo",
    )

    assert manual_identity == candidate_identity
    assert manual_identity.canonical_key == "github_cloud:acme/sample-repo"


def test_github_identity_normalizes_repository_path_case() -> None:
    mixed_case_identity = build_repository_identity(
        provider=RepositoryProvider.GITHUB_CLOUD,
        provider_instance_url=None,
        provider_project_path="Acme/Sample-Repo",
    )
    lower_case_identity = build_repository_identity(
        provider=RepositoryProvider.GITHUB_CLOUD,
        provider_instance_url=None,
        provider_project_path="acme/sample-repo",
    )

    assert mixed_case_identity == lower_case_identity
    assert mixed_case_identity.provider_project_path == "acme/sample-repo"
    assert mixed_case_identity.canonical_key == "github_cloud:acme/sample-repo"


def test_gitlab_manual_url_and_candidate_normalize_instance_identity() -> None:
    parsed_remote = parse_repository_remote(
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url="https://gitlab.example.com:8443/group/subgroup/sample-repo.git",
        transport=RepositoryTransport.HTTPS,
    )

    manual_identity = build_repository_identity(
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        provider_instance_url=parsed_remote.provider_instance_url,
        provider_project_path=parsed_remote.provider_project_path,
    )
    candidate_identity = build_repository_identity(
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        provider_instance_url="https://GITLAB.EXAMPLE.COM:8443/",
        provider_project_path="group/subgroup/sample-repo",
    )

    assert manual_identity == candidate_identity
    assert (
        manual_identity.canonical_key
        == "gitlab_self_managed:https://gitlab.example.com:8443:group/subgroup/sample-repo"
    )


def test_gitlab_identity_normalizes_default_https_port() -> None:
    default_port_identity = build_repository_identity(
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        provider_instance_url="https://gitlab.example.com:443",
        provider_project_path="group/sample-repo",
    )
    implicit_port_identity = build_repository_identity(
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        provider_instance_url="https://gitlab.example.com",
        provider_project_path="group/sample-repo",
    )

    assert default_port_identity == implicit_port_identity
    assert default_port_identity.provider_instance_url == "https://gitlab.example.com"
    assert (
        default_port_identity.canonical_key
        == "gitlab_self_managed:https://gitlab.example.com:group/sample-repo"
    )
