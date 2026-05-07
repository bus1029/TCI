# Delivery Evidence: ZIP 업로드 스냅샷과 워크스페이스 삭제

## Evidence Rules

- 민감 정보 기록 금지: credentials, tokens, raw ZIP contents, private file paths, raw remote URLs with secrets, cookies, screenshots containing private code, raw logs with sensitive values
- 허용 정보: redacted workspace IDs, source labels, counts, timestamps, pass/fail outcomes, command names
- 실제 운영자 리허설이 필요한 항목은 자동 테스트만으로 완료 처리하지 않음

## Current Implementation Evidence

| Date | Scope | Evidence | Result |
|------|-------|----------|--------|
| 2026-05-06 | T001-T006, T009-T010 | `rtk proxy pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py` before implementation | RED: missing `CodeSnapshotSourceKind` import, expected missing model contract |
| 2026-05-06 | T007, T008 | `rtk proxy pytest -q tests/unit/local_uploads/test_source_aware_snapshot_repository.py tests/unit/local_uploads/test_workspace_lifecycle_guard.py` before implementation | RED: missing repository and workspace lifecycle guard contracts |
| 2026-05-06 | T011-T016 | Repository and guard unit tests for workspace lifecycle, Local Upload persistence, source-aware snapshots, fake repository parity, and deleted-workspace side-effect guards | GREEN after implementation |
| 2026-05-06 | T017 focused foundation | `rtk pytest -q pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_lifecycle_models.py pilot-git-repo-connection/tests/unit/local_uploads/test_source_aware_snapshot_repository.py pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_lifecycle_guard.py pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_local_upload_repositories.py pilot-git-repo-connection/tests/unit/repository_connections/test_snapshot_storage.py pilot-git-repo-connection/tests/unit/repository_connections/test_app.py pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py pilot-git-repo-connection/tests/unit/repository_connections/test_git_foundation.py pilot-git-repo-connection/tests/unit/repository_connections/test_phase2_foundation.py pilot-git-repo-connection/tests/unit/repository_connections/test_repository_sync_run_repository.py pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py` | 222 passed |
| 2026-05-06 | Focused typing | `rtk mypy pilot-git-repo-connection/src/tci/domain/services pilot-git-repo-connection/src/tci/infrastructure/persistence pilot-git-repo-connection/src/tci/api/problem_details.py pilot-git-repo-connection/src/tci/app.py pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_local_upload_repositories.py` | No issues found |
| 2026-05-06 | Formatting and lint | `rtk black --check pilot-git-repo-connection/src/tci pilot-git-repo-connection/tests`, `rtk ruff check pilot-git-repo-connection/src/tci pilot-git-repo-connection/tests`, `rtk git diff --check` | Passed |
| 2026-05-06 | Migration syntax | `rtk python -m py_compile pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py` | Passed |
| 2026-05-06 | Migration head | `rtk alembic heads` from `pilot-git-repo-connection/` | `010_local_upload_workspace_del (head)` |
| 2026-05-06 | Review loop | `reviewer`, `python-reviewer`, `database-reviewer`, `security-reviewer`, followed by targeted follow-up review after fixes | No remaining findings |
| 2026-05-07 | T018, T019 RED | `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py` from `pilot-git-repo-connection/` before implementation | RED: missing `local_zip_extractor` and `create_local_upload_snapshot`, expected missing implementation |
| 2026-05-07 | T018-T019, T023-T026 core Local Upload snapshot | `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py` from `pilot-git-repo-connection/` | 17 passed |
| 2026-05-07 | T018-T019, T023-T026 plus foundation/snapshot/settings regression | `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/unit/repository_connections/test_snapshot_storage.py tests/unit/repository_connections/test_settings.py` and `rtk pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/local_uploads/test_source_aware_snapshot_repository.py tests/unit/local_uploads/test_workspace_lifecycle_guard.py tests/unit/local_uploads/test_workspace_local_upload_repositories.py` from `pilot-git-repo-connection/` | 78 passed; 40 passed |
| 2026-05-07 | Focused typing, formatting, lint | `rtk mypy src/tci/domain/services src/tci/infrastructure/snapshots src/tci/infrastructure/persistence src/tci/app.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/unit/local_uploads/test_local_zip_extractor.py`, `rtk black --check src/tci tests`, `rtk ruff check src/tci tests`, `rtk git diff --check` from `pilot-git-repo-connection/` or repo root as appropriate | No issues found; passed |

## Success Criteria Status

| Success Criterion | Status | Notes |
|-------------------|--------|-------|
| SC-001 | Pending | Requires three real operator upload rehearsals |
| SC-002 | Partial automated coverage | Core ZIP extraction and Local Upload snapshot service preserve file structure in unit coverage; API snapshot detail and acceptance evidence are still pending |
| SC-003 | Partial automated coverage | Corrupt ZIP, unsafe path, encrypted entry, duplicate path, reserved manifest, empty ZIP, and limit failures leave no active snapshot in unit coverage; API failure problem details are still pending |
| SC-004 | Pending | Requires GitHub/GitLab baseline regression after Local Upload implementation |
| SC-005 | Pending | Requires mixed-source UI and operator identification exercise |
| SC-006 | Pending | Requires workspace deletion implementation |
| SC-007 | Pending | Requires delete authorization implementation |
| SC-008 | Partial automated coverage | Foundation now blocks several deleting/deleted workspace mutation races for existing repository flows, but full workspace deletion implementation and integration coverage are still pending |
| SC-009 | Pending | Requires content purge implementation |
| SC-010 | Partial automated coverage | Repeated Local Upload service unit coverage creates independent snapshots and selects the latest; API/operator acceptance evidence is still pending |

## Carryover Notes

- Phase 2 foundation T001-T017 is implemented and checked in the working tree.
- Core Local Upload snapshot unit slice T018, T019, and T023-T026 is implemented and checked in the working tree.
- Local Upload API, contract/integration flow, worker entry point, snapshot detail API serialization, workspace deletion service, workspace archive purge, and operator UI are not implemented yet.
- Deleted/deleting workspace guard work in existing GitHub/GitLab flows was tightened during review because Phase 2 introduced shared workspace lifecycle state. This is not a substitute for the full US2 deletion flow.
- No credentials, raw ZIP contents, private file paths, secret-bearing URLs, screenshots, or raw sensitive logs were recorded in this evidence.
