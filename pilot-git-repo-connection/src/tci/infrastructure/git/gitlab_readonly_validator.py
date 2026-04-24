from __future__ import annotations

from tci.infrastructure.git.git_readonly_validator import GitReadonlyValidator


class GitLabReadonlyValidator(GitReadonlyValidator):
    auth_failure_tokens = GitReadonlyValidator.auth_failure_tokens + (
        "http basic: access denied",
    )
    read_only_tokens = GitReadonlyValidator.read_only_tokens + (
        "you are not allowed to push code to this project",
        "gitlab: you are not allowed to push code to this project",
    )
