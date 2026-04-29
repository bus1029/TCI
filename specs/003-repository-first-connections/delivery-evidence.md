# Delivery Evidence: 워크스페이스 기반 저장소 연결 시작점 전환

## Coverage Map

| ID | Evidence Status | Notes |
|----|-----------------|-------|
| FR-001 | Pending | Workspace-start repository connection flow. |
| FR-002 | Pending | New connections do not require or store planning/spec/plan trace. |
| FR-002a | Pending | Obsolete planning/spec/plan create fields are rejected. |
| FR-003 | Pending | GitHub and GitLab are available in workspace-first flow. |
| FR-003a | Pending | Candidate list and manual URL paths are supported. |
| FR-003b | Pending | Operation paths use workspace shared read-only credentials only. |
| FR-003c | Pending | Candidates are limited to configured provider account/instance scope. |
| FR-003d | Pending | Manual URL fallback remains available without candidates. |
| FR-004 | Pending | Connections show workspace context in list/detail. |
| FR-005 | Pending | Existing planning-based GitHub/GitLab history is preserved. |
| FR-006 | Pending | Planning trace is optional legacy provenance only. |
| FR-007 | Pending | Connection origin is visible to operators. |
| FR-008 | Pending | Existing GitHub Cloud provider behavior regresses cleanly. |
| FR-009 | Pending | Existing GitLab Self-Managed provider behavior regresses cleanly. |
| FR-010 | Pending | Same workspace/provider/repository duplicate connections are blocked. |
| FR-011 | Pending | Mixed GitHub/GitLab status, event, snapshot, and history stay separated. |
| FR-012 | Pending | Unauthorized repository access blocks connection creation. |
| FR-012a | Pending | Personal provider grant alone cannot create active connections. |
| FR-012b | Pending | Missing/expired/revoked/invalid shared credential returns remediation. |
| FR-013 | Pending | Empty candidate state is not treated as an error. |
| FR-014 | Pending | Existing planning-based rows remain visible. |
| FR-014a | Pending | Existing `workspace_id` remains canonical for legacy rows. |
| FR-014b | Pending | Unclear legacy workspace assignment is visible as compatibility state. |
| FR-015 | Pending | New and legacy connections keep equivalent provider operations. |
| FR-016 | Pending | Planning-free connection verification, collection, snapshot, detail, status work. |
| SC-001 | Pending | Six operator timing attempts, 5 of 6 within 10 minutes. |
| SC-002 | Pending | Planning-free create/detail acceptance coverage. |
| SC-003 | Pending | Existing GitHub/GitLab baseline scenarios pass. |
| SC-004 | Pending | Mixed-provider identification rehearsal, 57 of 60 correct. |
| SC-005 | Pending | Duplicate connection attempts are blocked or routed to existing connection. |
| SC-006 | Pending | Existing planning/spec/plan history remains accessible. |
| SC-007 | Pending | Invalid shared credential attempts do not create connections. |

## Foundation Evidence

- 2026-04-29 RED: `rtk proxy pytest tests/unit/repository_connections/test_repository_connection_origin.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py tests/unit/repository_connections/test_repository_operation_credentials.py tests/integration/repository_connections/test_repository_first_migration.py -q`
  - Result: failed during collection because `serialize_connection_origin` did not exist, confirming missing origin support.
- 2026-04-29 GREEN: `rtk pytest tests/unit/repository_connections/test_repository_connection_origin.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py tests/unit/repository_connections/test_repository_operation_credentials.py tests/integration/repository_connections/test_repository_first_migration.py`
  - Result: 9 passed.
- 2026-04-29 Regression: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - Result after updating expected repository-first traceability shape: 67 passed.
- 2026-04-29 Provider compatibility regression: `rtk pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/contract/repository_ingestion/test_gitlab_webhook_contract.py tests/contract/repository_ingestion/test_github_webhook_contract.py`
  - Result: 78 passed.
- 2026-04-29 Unit regression: `rtk pytest tests/unit/repository_connections`
  - Result: 302 passed.
- 2026-04-29 Integration regression: `rtk pytest tests/integration/repository_connections`
  - Result: 96 passed.
- 2026-04-29 Contract regression: `rtk pytest tests/contract/repository_ingestion`
  - Result: 143 passed.
- 2026-04-29 Combined repository ingestion regression: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion`
  - Result after duplicate precheck fix: 541 passed.
- 2026-04-29 Review remediation focused checks: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_duplicate_before_git_access tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_rejects_obsolete_planning_fields tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_create_connection_validation_error_does_not_echo_secret tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_create_connection_rejects_planning_input_from_other_workspace tests/unit/repository_connections/test_snapshot_storage.py::test_snapshot_manifest_writer_serializes_null_planning_reference tests/integration/repository_connections/test_repository_first_migration.py`
  - Result: 8 passed.
- 2026-04-29 Alembic graph check: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-29 Changed-file lint: `rtk ruff check src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_repository_first_migration.py tests/unit/repository_connections/test_snapshot_storage.py tests/support/repository_connection_testkit.py tests/support/repository_first_connection_testkit.py`
  - Result: no issues found.
- 2026-04-29 Changed-file typing: `rtk mypy src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`
  - Result: no issues found.
- 2026-04-29 Combined repository ingestion regression after review fixes: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion`
  - Result: 546 passed.
- 2026-04-29 Review remediation focused checks after migration/helper/manifest fixes: `rtk pytest tests/unit/repository_connections/test_repository_operation_credentials.py tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_duplicate_before_git_access tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_create_connection_validation_error_does_not_echo_secret tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_rejects_obsolete_planning_fields`
  - Result: 6 passed.
- 2026-04-29 Final combined repository ingestion regression for Foundation: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion`
  - Result: 548 passed.
- 2026-04-29 Final changed-file lint: `rtk ruff check src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_repository_first_migration.py tests/unit/repository_connections/test_snapshot_storage.py tests/unit/repository_connections/test_repository_operation_credentials.py tests/support/repository_connection_testkit.py tests/support/repository_first_connection_testkit.py`
  - Result: no issues found.
- 2026-04-29 Final changed-file typing: `rtk mypy src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`
  - Result: no issues found.
- 2026-04-29 Second review remediation focused checks: `rtk pytest tests/integration/repository_connections/test_repository_first_migration.py tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_page_does_not_render_obsolete_planning_input tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_redirects_to_detail_page tests/contract/repository_ingestion/test_repository_connection_contract.py::test_repository_management_routes_accept_bearer_operator_token tests/contract/repository_ingestion/test_repository_connection_contract.py::test_get_connection_detail_returns_null_last_processed_event_and_traceability -q`
  - Result: 7 passed.
- 2026-04-29 Full lint after reviewer loop: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-29 Focused typing after reviewer loop: `rtk mypy src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`
  - Result: no issues found.
- 2026-04-29 Alembic graph check after reviewer loop: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-29 Final combined repository ingestion regression after second review loop: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 549 passed.
- 2026-04-29 Reviewer loop DB/security/Python remediation focused checks: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_serializes_duplicate_identity_before_git_access tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_duplicate_before_git_access tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py -q`
  - Result: 6 passed.
- 2026-04-29 Reviewer loop new-test typing: `rtk mypy tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py`
  - Result: no issues found.
- 2026-04-29 Reviewer loop full lint: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-29 Reviewer loop focused production/new-test typing: `rtk mypy src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py`
  - Result: no issues found.
- 2026-04-29 Reviewer loop Alembic graph check: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-29 Final combined repository ingestion regression after reviewer loop remediation: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 550 passed.
- 2026-04-29 Formatter remediation check: `rtk black --check <touched Python files>`
  - Result: 47 files would be left unchanged.
- 2026-04-29 Formatter remediation lint: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-29 Formatter remediation focused typing: `rtk mypy src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py tests/support/repository_connection_testkit.py`
  - Result: no issues found.
- 2026-04-29 Formatter remediation Alembic graph check: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-29 Formatter remediation combined repository ingestion regression: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 550 passed.
- 2026-04-29 Project-wide formatting remediation: `rtk black .`
  - Result: 35 files reformatted, 117 files left unchanged.
- 2026-04-29 Project-wide formatting check: `rtk black --check .`
  - Result: 152 files would be left unchanged.
- 2026-04-29 Project-wide lint after formatting: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-29 Project-wide formatting focused typing: `rtk mypy src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py tests/support/repository_connection_testkit.py`
  - Result: no issues found.
- 2026-04-29 Project-wide formatting Alembic graph check: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-29 Project-wide formatting combined repository ingestion regression: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 550 passed.

## User Story 1 Evidence

No commands recorded yet.

## User Story 2 Evidence

No commands recorded yet.

## User Story 3 Evidence

No commands recorded yet.

## Final Evidence

No commands recorded yet.
