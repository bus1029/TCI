from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tci.infrastructure.git.git_ref_resolver import GitCommandResult
from tci.settings import load_settings


def test_create_app_bootstraps_runtime_directories_from_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))

    from tci.app import create_app

    settings = load_settings()
    app = create_app(settings=settings)

    with TestClient(app):
        assert settings.runtime_root.is_dir()
        assert settings.git_mirror_root.is_dir()
        assert settings.code_snapshot_root.is_dir()


def test_create_app_exposes_shared_dependencies_on_app_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))

    from tci.app import AppDependencies, create_app

    settings = load_settings()
    app = create_app(settings=settings)

    assert app.state.settings == settings
    assert isinstance(app.state.dependencies, AppDependencies)
    assert app.state.dependencies.settings == settings


def test_build_app_dependencies_uses_gitlab_aware_readonly_validator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))

    import tci.app as app_module
    from tci.infrastructure.git.gitlab_readonly_validator import GitLabReadonlyValidator

    monkeypatch.setattr(
        app_module,
        "_subprocess_git_runner",
        lambda command: GitCommandResult(
            returncode=1,
            stdout="",
            stderr="remote: 403 forbidden by repository policy",
        ),
    )
    settings = load_settings()
    dependencies = app_module.build_app_dependencies(settings)

    assert isinstance(dependencies.git_readonly_validator, GitLabReadonlyValidator)

    result = dependencies.git_readonly_validator.probe(
        remote_url="https://gitlab.example.com/group/repo.git"
    )
    assert result.is_read_only is False
    assert result.problem_code is None
