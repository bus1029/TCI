# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

from pathlib import Path

import pytest

from tci.settings import get_settings, load_settings


def _expected_project_root() -> Path:
    current_dir = Path.cwd().resolve()
    for candidate in (current_dir, *current_dir.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate

    module_dir = Path(__file__).resolve().parent
    for candidate in (module_dir, *module_dir.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate

    return current_dir


def test_package_scaffold_modules_are_importable() -> None:
    import tci  # noqa: F401
    import tci.api  # noqa: F401
    import tci.web  # noqa: F401


def test_load_settings_uses_project_runtime_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TCI_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("TCI_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("TCI_GIT_MIRROR_ROOT", raising=False)
    monkeypatch.delenv("TCI_CODE_SNAPSHOT_ROOT", raising=False)
    monkeypatch.delenv("TCI_TEMPLATE_ROOT", raising=False)
    monkeypatch.delenv("TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("TCI_GITLAB_WEBHOOK_TRUSTED_PROXY_HOSTS", raising=False)

    settings = load_settings()
    expected_root = _expected_project_root()

    assert settings.project_root.samefile(expected_root)
    assert settings.runtime_root == expected_root / ".runtime"
    assert settings.git_mirror_root == expected_root / ".runtime" / "git-mirrors"
    assert settings.code_snapshot_root == expected_root / ".runtime" / "code-snapshots"
    assert settings.template_root == expected_root / "src" / "tci" / "web" / "templates"
    assert settings.gitlab_self_managed_allowed_hosts == ()
    assert settings.gitlab_webhook_trusted_proxy_hosts == ()


def test_load_settings_parses_gitlab_self_managed_allowed_hosts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS",
        "GitLab.Example.Com., GitLab.Example.Com.:8443, localhost, 192.168.10.20",
    )

    settings = load_settings()

    assert settings.gitlab_self_managed_allowed_hosts == (
        "gitlab.example.com",
        "gitlab.example.com:8443",
        "localhost",
        "192.168.10.20",
    )


def test_load_settings_parses_gitlab_webhook_trusted_proxy_hosts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "TCI_GITLAB_WEBHOOK_TRUSTED_PROXY_HOSTS",
        "Proxy.Example.Com.:443, 10.0.0.10, 2001:db8::1, [2001:db8::2]:8443",
    )

    settings = load_settings()

    assert settings.gitlab_webhook_trusted_proxy_hosts == (
        "proxy.example.com",
        "10.0.0.10",
        "2001:db8::1",
        "2001:db8::2",
    )


def test_load_settings_allows_runtime_path_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_RUNTIME_ROOT", ".custom-runtime")
    monkeypatch.setenv("TCI_GIT_MIRROR_ROOT", ".custom-runtime/mirrors")
    monkeypatch.setenv("TCI_CODE_SNAPSHOT_ROOT", ".custom-runtime/snapshots")
    monkeypatch.setenv("TCI_TEMPLATE_ROOT", "src/tci/web/templates")

    settings = load_settings()

    assert settings.project_root.samefile(tmp_path)
    assert settings.runtime_root == tmp_path / ".custom-runtime"
    assert settings.git_mirror_root == tmp_path / ".custom-runtime" / "mirrors"
    assert settings.code_snapshot_root == tmp_path / ".custom-runtime" / "snapshots"
    assert settings.template_root == tmp_path / "src" / "tci" / "web" / "templates"


def test_load_settings_allows_absolute_path_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    mirror_root = tmp_path / "mirrors"
    snapshot_root = tmp_path / "snapshots"
    template_root = tmp_path / "templates"
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("TCI_GIT_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("TCI_CODE_SNAPSHOT_ROOT", str(snapshot_root))
    monkeypatch.setenv("TCI_TEMPLATE_ROOT", str(template_root))

    settings = load_settings()

    assert settings.runtime_root == runtime_root
    assert settings.git_mirror_root == mirror_root
    assert settings.code_snapshot_root == snapshot_root
    assert settings.template_root == template_root


@pytest.mark.parametrize(
    ("env_key", "child_name"),
    (
        ("TCI_RUNTIME_ROOT", "runtime"),
        ("TCI_GIT_MIRROR_ROOT", "mirrors"),
        ("TCI_CODE_SNAPSHOT_ROOT", "snapshots"),
    ),
)
def test_load_settings_rejects_runtime_paths_outside_project_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env_key: str,
    child_name: str,
) -> None:
    outside_root = tmp_path.parent / "outside-runtime"
    outside_root.mkdir(exist_ok=True)
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv(env_key, str(outside_root / child_name))

    with pytest.raises(RuntimeError, match="프로젝트 루트 아래"):
        load_settings()


def test_runtime_directories_are_listed_for_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TCI_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("TCI_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("TCI_GIT_MIRROR_ROOT", raising=False)
    monkeypatch.delenv("TCI_CODE_SNAPSHOT_ROOT", raising=False)

    settings = load_settings()
    expected_root = _expected_project_root()

    assert settings.runtime_directories() == (
        expected_root / ".runtime",
        expected_root / ".runtime" / "git-mirrors",
        expected_root / ".runtime" / "code-snapshots",
    )


def test_get_settings_uses_overridden_project_root_after_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.project_root.samefile(tmp_path)
    assert settings.runtime_root == tmp_path / ".runtime"

    get_settings.cache_clear()


def test_load_settings_discovers_project_root_from_nested_working_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested_directory = Path(__file__).resolve().parent
    monkeypatch.delenv("TCI_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(nested_directory)

    settings = load_settings()

    assert settings.project_root.samefile(Path(__file__).resolve().parents[3])


def test_get_settings_keeps_cached_value_until_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(first_root))
    get_settings.cache_clear()

    cached_settings = get_settings()

    monkeypatch.setenv("TCI_PROJECT_ROOT", str(second_root))
    unchanged_settings = get_settings()

    assert cached_settings.project_root.samefile(first_root)
    assert unchanged_settings.project_root.samefile(first_root)

    get_settings.cache_clear()
    refreshed_settings = get_settings()

    assert refreshed_settings.project_root.samefile(second_root)

    get_settings.cache_clear()


def test_load_settings_uses_module_checkout_when_working_directory_is_outside_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("TCI_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = load_settings()

    assert settings.project_root.samefile(Path(__file__).resolve().parents[3])


def test_load_settings_prefers_module_checkout_over_foreign_pyproject(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    foreign_project_root = tmp_path / "foreign-project"
    foreign_project_root.mkdir()
    (foreign_project_root / "pyproject.toml").write_text(
        "[project]\nname='foreign'\n", encoding="utf-8"
    )
    monkeypatch.delenv("TCI_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(foreign_project_root)

    settings = load_settings()

    assert settings.project_root.samefile(Path(__file__).resolve().parents[3])


def test_load_settings_rejects_non_directory_project_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    invalid_root = tmp_path / "project-root.txt"
    invalid_root.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(invalid_root))

    with pytest.raises(RuntimeError, match="TCI_PROJECT_ROOT"):
        load_settings()


def test_load_settings_rejects_invalid_credential_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_CREDENTIAL_ENCRYPTION_KEY", "invalid-key")

    with pytest.raises(RuntimeError, match="TCI_CREDENTIAL_ENCRYPTION_KEY"):
        load_settings()


def test_load_settings_rejects_short_operator_api_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_OPERATOR_API_TOKEN", "short")

    with pytest.raises(RuntimeError, match="TCI_OPERATOR_API_TOKEN"):
        load_settings()


def test_load_settings_rejects_operator_api_token_with_outer_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_OPERATOR_API_TOKEN", " test-operator-token ")

    with pytest.raises(RuntimeError, match="TCI_OPERATOR_API_TOKEN"):
        load_settings()


def test_load_settings_rejects_low_entropy_production_operator_api_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_ENV", "production")
    monkeypatch.setenv("TCI_OPERATOR_API_TOKEN", "test-operator-token")

    with pytest.raises(RuntimeError, match="TCI_OPERATOR_API_TOKEN"):
        load_settings()


def test_load_settings_accepts_high_entropy_production_operator_api_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TCI_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("TCI_ENV", "production")
    monkeypatch.setenv(
        "TCI_OPERATOR_API_TOKEN",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    )

    settings = load_settings()

    assert settings.operator_api_token is not None


def test_get_settings_prefers_module_checkout_over_foreign_pyproject_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    foreign_project_root = tmp_path / "foreign-project"
    foreign_project_root.mkdir()
    (foreign_project_root / "pyproject.toml").write_text(
        "[project]\nname='foreign'\n", encoding="utf-8"
    )
    monkeypatch.delenv("TCI_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(foreign_project_root)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.project_root.samefile(Path(__file__).resolve().parents[3])

    get_settings.cache_clear()
