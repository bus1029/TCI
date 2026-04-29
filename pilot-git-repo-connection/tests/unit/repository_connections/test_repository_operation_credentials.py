from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from tci.domain.services.create_repository_connection import (
    CreateRepositoryConnectionCommand,
)


def test_create_command_has_no_planning_reference_operation_input() -> None:
    command_fields = {field.name for field in fields(CreateRepositoryConnectionCommand)}

    assert "planning_input_reference_id" not in command_fields
    assert "credential_secret" in command_fields


def test_repository_operation_modules_do_not_accept_personal_candidate_grants() -> None:
    service_root = (
        Path(__file__).resolve().parents[3] / "src" / "tci" / "domain" / "services"
    )
    operation_modules = (
        "create_repository_connection.py",
        "verify_repository_connection.py",
        "build_code_snapshot.py",
        "process_github_event.py",
        "process_gitlab_event.py",
        "get_repository_connection_detail.py",
    )

    for module_name in operation_modules:
        source = (service_root / module_name).read_text(encoding="utf-8")
        assert "personal" not in source
        assert "candidate_grant" not in source
        assert "provider_grant" not in source


def test_verify_and_collect_paths_load_active_workspace_credential() -> None:
    service_root = (
        Path(__file__).resolve().parents[3] / "src" / "tci" / "domain" / "services"
    )

    verify_source = (service_root / "verify_repository_connection.py").read_text(
        encoding="utf-8"
    )
    collect_source = (service_root / "build_code_snapshot.py").read_text(
        encoding="utf-8"
    )

    assert "credential_repository.get_active_for_connection" in verify_source
    assert "credential_repository.get_active_for_connection" in collect_source
    assert "decrypt_secret_from_storage" in verify_source
    assert "decrypt_secret_from_storage" in collect_source
