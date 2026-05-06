# Delivery Evidence: ZIP 업로드 스냅샷과 워크스페이스 삭제

## Evidence Rules

- 민감 정보 기록 금지: credentials, tokens, raw ZIP contents, private file paths, raw remote URLs with secrets, cookies, screenshots containing private code, raw logs with sensitive values
- 허용 정보: redacted workspace IDs, source labels, counts, timestamps, pass/fail outcomes, command names
- 실제 운영자 리허설이 필요한 항목은 자동 테스트만으로 완료 처리하지 않음

## Current Implementation Evidence

| Date | Scope | Evidence | Result |
|------|-------|----------|--------|
| 2026-05-06 | T001-T006, T009-T010 | `rtk proxy pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py` before implementation | RED: missing `CodeSnapshotSourceKind` import, expected missing model contract |
| 2026-05-06 | T001-T006, T009-T010 | `rtk pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/repository_connections/test_settings.py` | 40 passed |
| 2026-05-06 | T001-T006, T009-T010 | `rtk pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/repository_connections/test_settings.py tests/unit/repository_connections/test_phase2_foundation.py tests/unit/repository_connections/test_snapshot_storage.py` | 79 passed |
| 2026-05-06 | Unit regression | `rtk pytest -q tests/unit` | 330 passed |
| 2026-05-06 | Contract regression | `rtk pytest -q tests/contract/repository_ingestion` | 152 passed |
| 2026-05-06 | Focused typing | `rtk mypy src/tci/settings.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/persistence/code_snapshot_repository.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/persistence/planning_input_reference_repository.py tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/support/local_upload_testkit.py` | No issues found |
| 2026-05-06 | Formatting and lint | `rtk black --check src tests alembic/versions/010_local_upload_workspace_delete.py`, `rtk ruff check src tests alembic/versions/010_local_upload_workspace_delete.py`, `rtk git diff --check` | Passed |
| 2026-05-06 | Migration syntax | `rtk python -m py_compile alembic/versions/010_local_upload_workspace_delete.py` | Passed |
| 2026-05-06 | Migration head | `rtk alembic heads` | `010_local_upload_workspace_del (head)` |
| 2026-05-06 | Review loop | `reviewer`, `python-reviewer`, `database-reviewer`, `security-reviewer` final pass | No remaining findings |

## Success Criteria Status

| Success Criterion | Status | Notes |
|-------------------|--------|-------|
| SC-001 | Pending | Requires three real operator upload rehearsals |
| SC-002 | Pending | Requires Local Upload extraction and snapshot detail implementation |
| SC-003 | Pending | Requires ZIP failure path implementation |
| SC-004 | Pending | Requires GitHub/GitLab baseline regression after Local Upload implementation |
| SC-005 | Pending | Requires mixed-source UI and operator identification exercise |
| SC-006 | Pending | Requires workspace deletion implementation |
| SC-007 | Pending | Requires delete authorization implementation |
| SC-008 | Pending | Requires deleted-workspace guard implementation |
| SC-009 | Pending | Requires content purge implementation |
| SC-010 | Pending | Requires repeated Local Upload snapshot implementation |

## Carryover Notes

- T007, T008, T011-T017 remain open for the next foundational cycle
- `CodeSnapshotRepository` and `repository_connection_testkit.py` were adjusted only to preserve existing repository-backed snapshot behavior after adding required `workspace_id` and `source_kind`
- No Local Upload API, ZIP extractor, workspace deletion service, or operator UI behavior is claimed complete in this evidence
