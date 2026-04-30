# Delivery Evidence: 워크스페이스 기반 저장소 연결 시작점 전환

## Coverage Map

| ID | Evidence Status | Notes |
|----|-----------------|-------|
| FR-001 | Partial | Manual URL workspace-start repository connection flow is covered; candidate decision support remains US3. |
| FR-002 | Verified | New connections do not require or store planning/spec/plan trace in create/detail/snapshot coverage. |
| FR-002a | Verified | Obsolete planning/spec/plan create fields are rejected and create no connection. |
| FR-003 | Verified | GitHub and GitLab are available in workspace-first manual URL flow. |
| FR-003a | Partial | Manual URL path is covered; candidate list path remains US3. |
| FR-003b | Pending | Operation paths use workspace shared read-only credentials only. |
| FR-003c | Partial | Candidate endpoint returns configured provider-scope projections; real provider account/instance integration remains open. |
| FR-003d | Partial | Candidate endpoint returns manual URL fallback empty state when provider candidates are not configured. |
| FR-004 | Partial | Operator list/detail now show workspace-origin context; full mixed-provider management remains US3. |
| FR-005 | Partial | Legacy planning trace is preserved in API/operator detail coverage; full provider history regression remains open. |
| FR-006 | Verified | Planning trace is optional legacy provenance only. |
| FR-007 | Verified | Connection origin is visible in API and operator list/detail. |
| FR-008 | Partial | Existing GitHub Cloud focused regression passed; full final regression remains open. |
| FR-009 | Partial | Existing GitLab Self-Managed focused regression passed; full final regression remains open. |
| FR-010 | Pending | Same workspace/provider/repository duplicate connections are blocked. |
| FR-011 | Pending | Mixed GitHub/GitLab status, event, snapshot, and history stay separated. |
| FR-012 | Pending | Unauthorized repository access blocks connection creation. |
| FR-012a | Pending | Personal provider grant alone cannot create active connections. |
| FR-012b | Partial | Create rejects auth-failed and write-capable credentials without creating rows; expired/revoked remediation remains US3. |
| FR-013 | Pending | Empty candidate state is not treated as an error. |
| FR-014 | Verified | Legacy planning trace projections remain visible for GitHub/GitLab list/detail, verification, snapshot, and webhook coverage. |
| FR-014a | Verified | Persisted legacy planning row keeps existing `workspace_id` as canonical list/detail scope. |
| FR-014b | Verified | Missing or cross-workspace legacy planning references are visible as `legacy_unassigned`; mismatched planning trace is hidden from API/operator/snapshot detail. |
| FR-015 | Partial | Legacy GitHub/GitLab verify, snapshot, and webhook flows pass; final full provider regression remains open. |
| FR-016 | Verified | Planning-free connection verification, collection, snapshot, detail, status paths are covered by focused regression. |
| SC-001 | Pending | Six operator timing attempts, 5 of 6 within 10 minutes. |
| SC-002 | Pending | Planning-free create/detail acceptance coverage. |
| SC-003 | Pending | Existing GitHub/GitLab baseline scenarios pass. |
| SC-004 | Pending | Mixed-provider identification rehearsal, 57 of 60 correct. |
| SC-005 | Pending | Duplicate connection attempts are blocked or routed to existing connection. |
| SC-006 | Pending | Existing planning/spec/plan history remains accessible. |
| SC-007 | Partial | Auth-failed and write-capable create attempts create no connection; personal provider grant scenario remains US3. |

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

- 2026-04-29 RED: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_obsolete_planning_field_matrix_without_row tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_page_renders_existing_connection_summary tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_page_marks_legacy_planning_connections tests/integration/repository_connections/test_operator_connection_pages.py::test_connection_detail_page_renders_workspace_origin_without_planning_labels tests/integration/repository_connections/test_operator_connection_pages.py::test_connection_detail_page_preserves_legacy_planning_trace -q`
  - Result after setup correction: 1 passed, 4 failed because operator list/detail did not yet render origin state or nullable planning trace correctly.
- 2026-04-29 GREEN: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_obsolete_planning_field_matrix_without_row tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_page_renders_existing_connection_summary tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_page_marks_legacy_planning_connections tests/integration/repository_connections/test_operator_connection_pages.py::test_connection_detail_page_renders_workspace_origin_without_planning_labels tests/integration/repository_connections/test_operator_connection_pages.py::test_connection_detail_page_preserves_legacy_planning_trace -q`
  - Result: 5 passed.
- 2026-04-29 Focused US1/operator/API regression: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_github_gitlab_compatibility.py -q`
  - Result after US1/US2 evidence additions: 105 passed.
- 2026-04-30 RED: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_write_capable_credential_without_row tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_auth_failed_credential_without_row -q`
  - Result: 1 passed, 1 failed because the in-memory repository testkit could not express a write-capable readonly probe result yet.
- 2026-04-30 GREEN: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_write_capable_credential_without_row tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_auth_failed_credential_without_row -q`
  - Result: 2 passed.
- SC-001 operator timing rehearsal is not yet performed; keep SC-001 pending until 3 operators complete 6 recorded attempts.

## User Story 2 Evidence

- 2026-04-29 Legacy detail contract characterization correction: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_get_legacy_connection_detail_preserves_planning_reference -q`
  - Result: initial assertion used the wrong fixture source reference; corrected to assert the seeded planning reference values directly.
- 2026-04-29 Legacy detail contract GREEN: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_get_legacy_connection_detail_preserves_planning_reference -q`
  - Result: 1 passed.
- 2026-04-29 Persisted legacy workspace scope regression: `rtk pytest tests/integration/repository_connections/test_repository_first_migration.py::test_persisted_legacy_planning_row_keeps_workspace_scope_and_trace -q`
  - Result: 1 passed.
- 2026-04-29 Focused US1/US2 regression: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_github_gitlab_compatibility.py -q`
  - Result after US1/US2 evidence additions: 105 passed.
- 2026-04-30 RED: `rtk proxy pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_github_planning_connection_remains_visible_and_operational -q`
  - Result: collection failed because `seed_legacy_planning_repository_connection` did not exist yet.
- 2026-04-30 GREEN: `rtk pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_github_planning_connection_remains_visible_and_operational tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_gitlab_planning_connection_remains_visible_and_operational tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_github_gitlab_webhooks_preserve_provider_isolation tests/integration/repository_connections/test_repository_first_legacy_compatibility.py::test_connection_with_missing_legacy_planning_reference_shows_compatibility_state -q`
  - Result: 4 passed.
- 2026-04-30 Focused US1/US2 regression: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/integration/repository_connections/test_operator_connection_pages.py -q`
  - Result: 98 passed.
- 2026-04-30 Reviewer remediation targeted checks: `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_connection_serialization.py -q`
  - Result after adding loaded cross-workspace planning reference coverage: 5 passed.
- 2026-04-30 Snapshot traceability remediation targeted checks: `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_snapshot_traceability.py -q`
  - Result after hiding cross-workspace planning references from snapshot detail: 5 passed.
- 2026-04-30 RED: `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py::test_detail_and_list_services_project_legacy_origin_state -q`
  - Result: 1 failed because `get_repository_connection_detail` returned a connection without a service-level `origin` projection.
- 2026-04-30 GREEN: `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py::test_detail_and_list_services_project_legacy_origin_state -q`
  - Result: 1 passed after projecting origin in detail and list services.
- 2026-04-30 Origin projection focused regression: `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_repository_connection_origin.py -q`
  - Result: 9 passed.
- 2026-04-30 Origin projection focused typing: `rtk mypy src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_connections.py src/tci/domain/services/repository_connection_support.py src/tci/api/schemas/repository_connection.py`
  - Result: no issues found.
- 2026-04-30 Final focused US1/US2 regression: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/integration/repository_connections/test_operator_connection_pages.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py -q`
  - Result: 105 passed.
- 2026-04-30 Reviewer loop:
  - General reviewer: initial T034/FR-014b overclaim finding fixed; snapshot traceability leak finding fixed; final re-review approved with no remaining findings.
  - Python reviewer: no findings.
  - Security reviewer: initial snapshot traceability leak finding fixed; final re-review no remaining security findings.

## User Story 3 Evidence

- 2026-04-30 RED: `rtk proxy pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py -q`
  - Result: collection failed because `tci.domain.services.list_repository_candidates` did not exist.
- 2026-04-30 GREEN: `rtk pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py -q`
  - Result: 2 passed after adding candidate schema, service, route, and app registration.
- 2026-04-30 Candidate configured-scope contract regression: `rtk pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py -q`
  - Result: 3 passed after adding route-level configured provider-scope candidate coverage.
- 2026-04-30 Candidate foundation focused regression: `rtk pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py tests/contract/repository_ingestion/test_repository_connection_contract.py::test_repository_management_routes_require_operator_token tests/contract/repository_ingestion/test_repository_connection_contract.py::test_repository_connection_routes_require_workspace_header -q`
  - Result: 5 passed.
- 2026-04-30 Candidate foundation focused typing: `rtk mypy src/tci/api/schemas/repository_candidate.py src/tci/domain/services/list_repository_candidates.py src/tci/api/routes/repository_candidates.py src/tci/app.py`
  - Result: no issues found.
- 2026-04-30 Candidate foundation focused lint: `rtk ruff check src/tci/api/schemas/repository_candidate.py src/tci/domain/services/list_repository_candidates.py src/tci/api/routes/repository_candidates.py src/tci/app.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py`
  - Result: no issues found.
- 2026-04-30 Security review remediation RED: `rtk pytest tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_filters_candidates_from_other_workspaces tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_removes_secret_bearing_remote_urls -q`
  - Result: 2 failed because candidate projections did not carry workspace ownership and secret-bearing remote URLs were returned directly.
- 2026-04-30 Security review remediation GREEN: `rtk pytest tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_filters_candidates_from_other_workspaces tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_removes_secret_bearing_remote_urls -q`
  - Result: 2 passed after enforcing candidate workspace ownership and suppressing remote URLs with userinfo, query strings, or fragments.
- 2026-04-30 Candidate security remediation regression: `rtk pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py -q`
  - Result: 5 passed.
- 2026-04-30 Candidate security remediation focused typing: `rtk mypy src/tci/domain/services/list_repository_candidates.py tests/unit/repository_connections/test_repository_candidates.py`
  - Result: no issues found.
- 2026-04-30 Security/Python re-review remediation RED: `rtk pytest tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_removes_malformed_or_unsafe_remote_urls -q`
  - Result: 1 failed because `_safe_remote_url` still returned malformed or unsafe-scheme URLs.
- 2026-04-30 Security/Python re-review remediation GREEN: `rtk pytest tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_removes_malformed_or_unsafe_remote_urls tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_removes_secret_bearing_remote_urls tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_filters_candidates_from_other_workspaces tests/integration/repository_connections/test_repository_first_legacy_compatibility.py::test_detail_and_list_services_project_legacy_origin_state -q`
  - Result: 4 passed after restricting candidate `remoteUrl` to structurally valid `http`/`https` URLs and typing the candidate source dependency with a Protocol.
- 2026-04-30 Re-review remediation typing: `rtk mypy src/tci/app.py src/tci/domain/services/list_repository_candidates.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_candidates.py`
  - Result: no issues found.
- 2026-04-30 Python re-review dependency typing remediation: `rtk mypy src/tci/domain/services/list_repository_candidates.py tests/unit/repository_connections/test_repository_candidates.py`
  - Result: no issues found after adding `RepositoryCandidateDependencies` and repository projection Protocols.
- 2026-04-30 Python re-review dependency typing focused regression: `rtk pytest tests/unit/repository_connections/test_repository_candidates.py tests/contract/repository_ingestion/test_repository_candidate_contract.py -q`
  - Result: 6 passed.
- 2026-04-30 Reviewer loop:
  - Security reviewer: candidate workspace isolation and secret-bearing URL echo findings fixed; second pass found malformed/unsafe-scheme URL gap; final re-review reported no remaining security findings.
  - Python reviewer: candidate source dependency typing finding fixed with Protocols; final re-review approved with no Python findings.
  - General reviewer: no confirmed findings; first review was incomplete due local `Too many open files` tooling issue, so security/Python final re-reviews and focused checks were used as the closure gate for this slice.
- 2026-04-30 Final candidate/origin focused regression: `rtk pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_repository_connection_origin.py -q`
  - Result: 15 passed.
- 2026-04-30 Final candidate/origin formatting check: `rtk black --check .`
  - Result: 158 files would be left unchanged.
- 2026-04-30 Final candidate/origin lint: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-30 Final candidate/origin focused typing: `rtk mypy src/tci/api/schemas/repository_candidate.py src/tci/domain/services/list_repository_candidates.py src/tci/api/routes/repository_candidates.py src/tci/app.py src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_connections.py src/tci/domain/services/repository_connection_support.py src/tci/api/schemas/repository_connection.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_candidates.py`
  - Result: no issues found.
- 2026-04-30 Final repository ingestion regression: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 571 passed.
- 2026-04-30 Final Alembic graph check: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-30 Final diff whitespace check: `rtk proxy git diff --check`
  - Result: passed.

## Final Evidence

- 2026-04-29 Formatting check: `rtk black --check .`
  - Result: 152 files would be left unchanged.
- 2026-04-29 Lint check: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-29 Production focused typing: `rtk mypy src/tci/api/schemas/repository_connection.py src/tci/web/routes/repository_connection_detail.py`
  - Result: no issues found.
- 2026-04-29 Test-file typing attempt: `rtk mypy src/tci/api/schemas/repository_connection.py src/tci/web/routes/repository_connection_detail.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_operator_connection_pages.py`
  - Result: failed on existing TestClient/test payload typing noise in the test files; production focused typing passed separately.
- 2026-04-29 Alembic graph check: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-29 Focused US1/US2 regression: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_github_gitlab_compatibility.py -q`
  - Result: 105 passed.
- 2026-04-29 Broad repository ingestion regression: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result after persisted legacy workspace scope regression: 555 passed.
- 2026-04-30 Final formatting check: `rtk black --check .`
  - Result: 153 files would be left unchanged.
- 2026-04-30 Final lint check: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-30 Final focused typing: `rtk mypy src/tci/api/schemas/repository_connection.py src/tci/domain/services/get_code_snapshot_detail.py src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_connections.py tests/support/repository_connection_testkit.py`
  - Result: no issues found.
- 2026-04-30 Final Alembic graph check: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-30 Final broad repository ingestion regression: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 564 passed.
- 2026-04-30 Final diff whitespace check: `rtk proxy git diff --check`
  - Result: passed.
