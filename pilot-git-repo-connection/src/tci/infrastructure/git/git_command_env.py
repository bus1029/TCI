from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
import os


_GIT_ENV_OVERRIDES: ContextVar[dict[str, str]] = ContextVar(
    "git_env_overrides",
    default={},
)
_BASE_ENV_KEYS = frozenset(
    {
        "LANG",
        "LC_ALL",
        "PATH",
        "TMPDIR",
    }
)


@contextmanager
def git_command_environment(overrides: Mapping[str, str]) -> Iterator[None]:
    current_overrides = _GIT_ENV_OVERRIDES.get()
    token = _GIT_ENV_OVERRIDES.set({**current_overrides, **dict(overrides)})
    try:
        yield
    finally:
        _GIT_ENV_OVERRIDES.reset(token)


def current_git_command_environment() -> dict[str, str]:
    return dict(_GIT_ENV_OVERRIDES.get())


def build_git_env() -> dict[str, str]:
    overrides = current_git_command_environment()
    ssh_command = overrides.get("GIT_SSH_COMMAND")
    if ssh_command is None:
        ssh_command = "ssh"
    if "batchmode=yes" not in ssh_command.lower():
        ssh_command = f"{ssh_command} -oBatchMode=yes"
    base_env = {
        key: value for key, value in os.environ.items() if key in _BASE_ENV_KEYS
    }
    return {
        **base_env,
        **overrides,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": ssh_command,
    }
