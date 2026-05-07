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
| SC-008 | Partial automated coverage | Foundation now blocks several deleting/deleted workspace mutation races for existing repository flows, but full workspace deletion implementation and integration coverage are still pending |
| SC-009 | Pending | Requires content purge implementation |
| SC-010 | Pending | Requires repeated Local Upload snapshot implementation |

## Carryover Notes

- Phase 2 foundation T001-T017 is implemented and checked in the working tree.
- Local Upload API, ZIP extractor, Local Upload snapshot creation service, workspace deletion service, archive purge, and operator UI are not implemented yet.
- Deleted/deleting workspace guard work in existing GitHub/GitLab flows was tightened during review because Phase 2 introduced shared workspace lifecycle state. This is not a substitute for the full US2 deletion flow.
- No credentials, raw ZIP contents, private file paths, secret-bearing URLs, screenshots, or raw sensitive logs were recorded in this evidence.
