from __future__ import annotations

import pytest

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    parse_provider,
)
from tci.infrastructure.git.remote_parsers import parse_repository_remote
from tci.infrastructure.persistence.models import (
    RepositoryProvider,
    RepositoryTransport,
)


def test_parse_provider_accepts_gitlab_self_managed() -> None:
    assert (
        parse_provider("gitlab_self_managed") is RepositoryProvider.GITLAB_SELF_MANAGED
    )


@pytest.mark.parametrize(
    (
        "remote_url",
        "transport",
        "expected_instance_url",
        "expected_owner",
        "expected_name",
    ),
    [
        (
            "https://gitlab.example.com/group/subgroup/sample-repo.git",
            RepositoryTransport.HTTPS,
            "https://gitlab.example.com",
            "group/subgroup",
            "sample-repo",
        ),
        (
            "https://gitlab.example.com/gitlab/group/subgroup/sample-repo.git",
            RepositoryTransport.HTTPS,
            "https://gitlab.example.com",
            "gitlab/group/subgroup",
            "sample-repo",
        ),
        (
            "https://gitlab.example.com/gitlab/group/sample-repo.git",
            RepositoryTransport.HTTPS,
            "https://gitlab.example.com",
            "gitlab/group",
            "sample-repo",
        ),
        (
            "git@gitlab.example.com:group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com",
            "group/subgroup",
            "sample-repo",
        ),
        (
            "git@gitlab.example.com:gitlab/group/sample-repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com",
            "gitlab/group",
            "sample-repo",
        ),
        (
            "ssh://git@gitlab.example.com/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com",
            "group/subgroup",
            "sample-repo",
        ),
        (
            "ssh://git@gitlab.example.com/gitlab/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com",
            "gitlab/group/subgroup",
            "sample-repo",
        ),
        (
            "ssh://git@gitlab.example.com/gitlab/group/sample-repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com",
            "gitlab/group",
            "sample-repo",
        ),
        (
            "ssh://git@gitlab.example.com:2222/group/sample-repo.git",
            RepositoryTransport.SSH,
            "https://gitlab.example.com",
            "group",
            "sample-repo",
        ),
        (
            "https://localhost/group/sample-repo.git",
            RepositoryTransport.HTTPS,
            "https://localhost",
            "group",
            "sample-repo",
        ),
        (
            "git@127.0.0.1:group/sample-repo.git",
            RepositoryTransport.SSH,
            "https://127.0.0.1",
            "group",
            "sample-repo",
        ),
        (
            "ssh://git@192.168.10.20:2222/group/sample-repo.git",
            RepositoryTransport.SSH,
            "https://192.168.10.20",
            "group",
            "sample-repo",
        ),
        (
            "https://gitlab.example.com:8443/group/sample-repo.git",
            RepositoryTransport.HTTPS,
            "https://gitlab.example.com:8443",
            "group",
            "sample-repo",
        ),
        (
            "http://gitlab.example.com/group/sample-repo.git",
            RepositoryTransport.HTTP,
            "http://gitlab.example.com",
            "group",
            "sample-repo",
        ),
        (
            "http://192.168.10.20:8080/group/sample-repo.git",
            RepositoryTransport.HTTP,
            "http://192.168.10.20:8080",
            "group",
            "sample-repo",
        ),
    ],
)
def test_gitlab_remote_parser_extracts_instance_namespace_and_project(
    remote_url: str,
    transport: RepositoryTransport,
    expected_instance_url: str,
    expected_owner: str,
    expected_name: str,
) -> None:
    parsed_remote = parse_repository_remote(
        provider=RepositoryProvider.GITLAB_SELF_MANAGED,
        remote_url=remote_url,
        transport=transport,
    )

    assert parsed_remote.owner == expected_owner
    assert parsed_remote.name == expected_name
    assert parsed_remote.provider_instance_url == expected_instance_url
    assert parsed_remote.provider_project_path == f"{expected_owner}/{expected_name}"


@pytest.mark.parametrize(
    ("provider", "remote_url", "transport", "expected_message"),
    [
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://github.com/acme/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://github.com./acme/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "git@github.com.:acme/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://git@github.com./acme/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://gitlab.example.com/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://gitlab.example.com./group/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "git@gitlab.example.com.:group/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://git@gitlab.example.com./group/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://gitlab.example.com/group name/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://gitlab.example.com/group/../sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://gitlab.example.com/group/\t/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "git@gitlab.example.com:group/\x01/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://gitlab.example.com:notaport/group/subgroup/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://gitlab.example.com:/group/subgroup/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://deploy@gitlab.example.com/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://git@gitlab.example.com:notaport/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://git@gitlab.example.com:/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "git@-oProxyCommand=sh:group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "git@host withspace:group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://git@-evil/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://git@[::1]/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "https://[::1/group/subgroup/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "ssh://git@[::1/group/subgroup/sample-repo.git",
            RepositoryTransport.SSH,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITHUB_CLOUD,
            "https://gitlab.example.com/group/sample-repo.git",
            RepositoryTransport.HTTPS,
            "remoteUrl은 GitHub Cloud 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITHUB_CLOUD,
            "http://github.com/acme/sample-repo.git",
            RepositoryTransport.HTTP,
            "remoteUrl은 GitHub Cloud 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "http://x-access-token:secret@gitlab.example.com/group/sample-repo.git",
            RepositoryTransport.HTTP,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
        (
            RepositoryProvider.GITLAB_SELF_MANAGED,
            "http://gitlab.example.com/group/sample-repo.git?token=secret",
            RepositoryTransport.HTTP,
            "remoteUrl은 GitLab Self-Managed 저장소 주소여야 합니다.",
        ),
    ],
)
def test_gitlab_remote_parser_rejects_unsupported_or_ambiguous_addresses(
    provider: RepositoryProvider,
    remote_url: str,
    transport: RepositoryTransport,
    expected_message: str,
) -> None:
    with pytest.raises(RepositoryConnectionProblem) as error_info:
        parse_repository_remote(
            provider=provider,
            remote_url=remote_url,
            transport=transport,
        )

    assert error_info.value.problem_code is ProblemCode.INVALID_INPUT
    assert error_info.value.detail == expected_message
