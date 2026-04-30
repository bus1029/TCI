# Delivery Evidence: 워크스페이스 기반 저장소 연결 시작점 전환

## Coverage Map

| ID | Evidence Status | Notes |
|----|-----------------|-------|
| FR-001 | Verified | Manual URL workspace-start connection flow and operator candidate decision support are covered. |
| FR-002 | Verified | New connections do not require or store planning/spec/plan trace in create/detail/snapshot coverage. |
| FR-002a | Verified | Obsolete planning/spec/plan create fields are rejected and create no connection. |
| FR-003 | Verified | GitHub and GitLab are available in workspace-first manual URL flow. |
| FR-003a | Verified | Manual URL path, candidate list display, already-connected candidate state, and candidate-selected validation are covered. |
| FR-003b | Verified | Create, verify, collect, scope preview, event processing, event status lookup, and ref-update/reverify paths reject missing, revoked, or non-readonly operation credentials without falling back to personal provider grants. |
| FR-003c | Partial | Candidate endpoint returns configured provider-scope projections; real provider account/instance integration remains open. |
| FR-003d | Verified | Candidate endpoint and operator page return manual URL fallback empty state when provider candidates are not configured. |
| FR-004 | Verified | Operator list/detail/event pages expose workspace, provider, repository identity, origin, and mixed-provider separation context. |
| FR-005 | Verified | Legacy planning trace is preserved in API/operator detail coverage and final provider regression. |
| FR-006 | Verified | Planning trace is optional legacy provenance only. |
| FR-007 | Verified | Connection origin is visible in API and operator list/detail. |
| FR-008 | Verified | Existing GitHub Cloud compatibility, webhook, event, and mixed-provider regression passed. |
| FR-009 | Verified | Existing GitLab Self-Managed compatibility, lifecycle, scope, webhook, and provider regression passed. |
| FR-010 | Verified | Same workspace/provider/repository duplicate connections are blocked across manual and candidate-selected create payloads before git access. |
| FR-011 | Verified | Mixed GitHub/GitLab status, event, snapshot, sync history, and operator event timeline projections stay separated. |
| FR-012 | Verified | Candidate, credential, permission, and operator validation failures block connection creation without secret echo or side effects. |
| FR-012a | Verified | Candidate personal grant material is not persisted as an operation credential and cannot create an active connection without submitted workspace credential validation. |
| FR-012b | Verified | Create rejects auth-failed and write-capable credentials without creating rows; revoked/non-active stored operation credentials map to reauth-required remediation paths across repository operations. |
| FR-013 | Verified | Empty candidate state is rendered as manual URL fallback, not an error. |
| FR-014 | Verified | Legacy planning trace projections remain visible for GitHub/GitLab list/detail, verification, snapshot, and webhook coverage. |
| FR-014a | Verified | Persisted legacy planning row keeps existing `workspace_id` as canonical list/detail scope. |
| FR-014b | Verified | Missing or cross-workspace legacy planning references are visible as `legacy_unassigned`; mismatched planning trace is hidden from API/operator/snapshot detail. |
| FR-015 | Verified | Legacy and workspace-first GitHub/GitLab provider operations passed final regression. |
| FR-016 | Verified | Planning-free connection verification, collection, snapshot, detail, status paths are covered by focused regression. |
| SC-001 | Pending | Six operator timing attempts, 5 of 6 within 10 minutes. |
| SC-002 | Verified | Planning-free create/detail/snapshot and repository-first focused acceptance checks passed. |
| SC-003 | Verified | Existing GitHub/GitLab baseline regression passed. |
| SC-004 | Pending | Mixed-provider identification rehearsal, 57 of 60 correct. |
| SC-005 | Verified | Duplicate connection attempts are blocked before git access for manual and candidate-selected payloads. |
| SC-006 | Verified | Existing planning/spec/plan history remains accessible in legacy list/detail/snapshot/provider regression. |
| SC-007 | Verified | Failed create attempts with auth-failed, write-capable, or candidate-personal-grant-only credentials do not create connections or operation credentials, and rejected create/operator validation responses do not echo submitted credential material. |

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
- 2026-04-30 RED: `rtk proxy pytest tests/unit/repository_connections/test_repository_connection_identity.py -q`
  - Result: collection failed because `build_repository_identity` did not exist, confirming missing canonical identity helper for candidate/manual comparison.
- 2026-04-30 GREEN: `rtk pytest tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py tests/contract/repository_ingestion/test_repository_candidate_contract.py -q`
  - Result: 8 passed after adding shared repository identity helper and reusing it for candidate key/existing-connection comparison.
- 2026-04-30 RED: `rtk proxy pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_candidate_selected_connection_reuses_manual_duplicate_precheck -q`
  - Result: failed with 422 because `candidateId` was rejected as an extra create field before duplicate precheck.
- 2026-04-30 GREEN: `rtk pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_candidate_selected_connection_reuses_manual_duplicate_precheck -q`
  - Result: 1 passed after accepting `candidateId` and applying the shared canonical identity helper in create duplicate precheck.
- 2026-04-30 Candidate/manual duplicate focused regression: `rtk pytest tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_candidate_selected_connection_reuses_manual_duplicate_precheck tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_duplicate_before_git_access tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_serializes_duplicate_identity_before_git_access -q`
  - Result: 11 passed.
- 2026-04-30 Candidate/manual duplicate formatting check: `rtk black --check src/tci/domain/services/repository_connection_support.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/create_repository_connection.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_connections.py tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - Result: 8 files would be left unchanged.
- 2026-04-30 Candidate/manual duplicate lint: `rtk ruff check src/tci/domain/services/repository_connection_support.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/create_repository_connection.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_connections.py tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - Result: no issues found.
- 2026-04-30 Candidate/manual duplicate focused typing: `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/create_repository_connection.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_connections.py tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py`
  - Result: no issues found. Existing integration test mypy noise remains outside this focused typing target.
- 2026-04-30 Reviewer remediation RED: `rtk proxy pytest tests/unit/repository_connections/test_repository_connection_identity.py::test_github_identity_normalizes_repository_path_case tests/unit/repository_connections/test_repository_connection_identity.py::test_gitlab_identity_normalizes_default_https_port -q`
  - Result: 2 failed because canonical identity preserved GitHub path case and explicit GitLab default HTTPS port.
- 2026-04-30 Reviewer remediation RED: `rtk proxy pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_github_duplicate_precheck_normalizes_repository_path_case -q`
  - Result: failed because a mixed-case GitHub connection and lower-case GitHub connection could both be created.
- 2026-04-30 Reviewer remediation RED: `rtk proxy pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_gitlab_duplicate_precheck_normalizes_default_https_port -q`
  - Result: failed because explicit GitLab `:443` was treated as a separate allowlist origin instead of the default HTTPS port.
- 2026-04-30 Reviewer remediation GREEN: `rtk pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_github_duplicate_precheck_normalizes_repository_path_case tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_gitlab_duplicate_precheck_normalizes_default_https_port tests/unit/repository_connections/test_repository_connection_identity.py -q`
  - Result: 6 passed after lowercasing GitHub canonical identity, dropping default HTTP(S) ports from GitLab identities, and persisting new GitHub rows with canonical lower-case owner/name.
- 2026-04-30 Reviewer remediation focused regression: `rtk pytest tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_candidate_selected_connection_reuses_manual_duplicate_precheck tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_github_duplicate_precheck_normalizes_repository_path_case tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_gitlab_duplicate_precheck_normalizes_default_https_port tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_duplicate_before_git_access tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_serializes_duplicate_identity_before_git_access -q`
  - Result: 15 passed.
- 2026-04-30 Reviewer remediation formatting/lint/typing:
  - `rtk black --check .` result: 159 files would be left unchanged.
  - `rtk ruff check .` result: no issues found.
  - `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/create_repository_connection.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_connections.py tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py` result: no issues found.
- 2026-04-30 Security re-review remediation RED: `rtk proxy pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_gitlab_ssh_443_without_port_allowlist -q`
  - Result: failed because `ssh://git@gitlab.example.com:443/...` was allowed by a host-only allowlist.
- 2026-04-30 Security re-review remediation GREEN: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_gitlab_ssh_443_without_port_allowlist tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_unallowlisted_gitlab_ssh_port_before_git_access tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_gitlab_duplicate_precheck_normalizes_default_https_port tests/unit/repository_connections/test_repository_connection_identity.py -q`
  - Result: 7 passed after preserving explicit SSH remote ports in allowlist origin checks while still normalizing HTTP(S) default ports.
- 2026-04-30 Final reviewer loop:
  - General reviewer: initial canonical identity finding fixed; SSH `:443` allowlist finding fixed; final re-review no findings.
  - Security reviewer: initial canonical identity/default port finding fixed; SSH `:443` allowlist finding fixed; final re-review no security findings.
  - Python reviewer: approved with no findings; project-wide test-file mypy noise remains outside touched-source focused typing.
- 2026-04-30 Final candidate/manual duplicate broad regression: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 579 passed.
- 2026-04-30 Final candidate/manual duplicate formatting/lint/alembic:
  - `rtk black --check .` result: 159 files would be left unchanged.
  - `rtk ruff check .` result: no issues found.
  - `rtk alembic heads` result: `009_repository_first_connections (head)`.
- 2026-04-30 Final candidate/manual duplicate focused typing: `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/create_repository_connection.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_connections.py tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py`
  - Result: no issues found.
- 2026-04-30 Final candidate/manual duplicate diff whitespace check: `rtk proxy git diff --check`
  - Result: passed.
- 2026-04-30 Credential boundary RED: `rtk proxy pytest tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: collection failed because `require_active_operation_credential` did not exist, confirming the missing shared operation credential boundary helper.
- 2026-04-30 Credential boundary GREEN: `rtk pytest tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 10 passed after adding `require_active_operation_credential`, rejecting non-active or unvalidated operation credentials, and applying the helper to verify, snapshot collect, and default-ref reverify paths.
- 2026-04-30 Credential boundary focused regression:
  - `rtk pytest tests/unit/repository_connections/test_update_default_ref.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_github_and_gitlab_connection_verify_and_snapshot_flows_coexist -q`
  - Result: 13 passed.
  - `rtk pytest tests/unit/repository_connections/test_repository_operation_credentials.py tests/unit/repository_connections/test_snapshot_traceability.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py -q`
  - Result: 21 passed.
  - Post-format targeted rerun: `rtk pytest tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 10 passed.
- 2026-04-30 Reviewer loop findings:
  - General reviewer found scope preview bypassing the operation credential helper, `candidateId` tests not proving candidate source resolution, and task/evidence overclaim for event/status paths.
  - Python reviewer found the public operation credential helper lacked a concrete parameter type.
  - Security reviewer confirmed scope preview bypass and event/status overclaim, with no critical/high finding for secret echo or rejected-create side effects.
- 2026-04-30 Reviewer remediation RED: `rtk proxy pytest tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 3 failed because candidate source was not called, candidate identity mismatch still created a connection, and scope preview used a revoked credential.
- 2026-04-30 Reviewer remediation GREEN:
  - `rtk pytest tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 7 passed after validating configured candidate source identity and applying `require_active_operation_credential` to scope preview.
  - `rtk pytest tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 12 passed.
  - `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/domain/services/create_repository_connection.py src/tci/domain/services/evaluate_scope_rule_warning.py src/tci/domain/services/verify_repository_connection.py src/tci/domain/services/build_code_snapshot.py src/tci/domain/services/update_default_ref.py tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - Result: no issues found.
  - `rtk black <touched credential-boundary files>`
  - Result: 9 files left unchanged.
  - T052, T062, and T063 were returned to open because event/status operation-path coverage remains incomplete.
- 2026-04-30 Event/status credential boundary RED: `rtk proxy pytest tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 3 failed because GitHub event processing, GitLab event processing, and event status lookup accepted revoked operation credentials instead of returning `CONNECTION_AUTH_FAILED`.
- 2026-04-30 Event/status credential boundary GREEN:
  - `rtk pytest tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 7 passed after binding event head resolution to active workspace read-only operation credentials and mapping event status lookup boundary failures to remediation problem responses.
  - `rtk pytest tests/integration/repository_connections/test_github_webhook_refresh.py tests/integration/repository_connections/test_gitlab_provider_flows.py tests/integration/repository_connections/test_operator_event_pages.py -q`
  - Result: 23 passed.
  - `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py src/tci/domain/services/list_repository_events.py src/tci/api/routes/repository_events.py src/tci/web/routes/repository_events.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - Result: no issues found.
- 2026-04-30 Event/status reviewer remediation RED: `rtk proxy pytest tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 5 failed after adding rollbacking-session and provider-auth/duplicate-delivery coverage. Failures proved reauth status was lost on rollback, provider-side `GitConnectionAuthError` queued work instead of failing closed, and duplicate delivery required active operation credential.
- 2026-04-30 Event/status reviewer remediation GREEN:
  - `rtk pytest tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - Result: 17 passed after persisting `REAUTH_REQUIRED` through a separate successful session, failing provider-side auth/decrypt errors closed, skipping operation credential checks for non-retryable duplicate deliveries, preserving duplicate-delivery decisions across later status changes, skipping operation credential checks for static record-only PR/MR events, and recording non-active webhook events without repository access.
  - `rtk pytest tests/integration/repository_connections/test_github_webhook_refresh.py tests/integration/repository_connections/test_gitlab_provider_flows.py tests/integration/repository_connections/test_operator_event_pages.py -q`
  - Result: 23 passed.
  - `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py src/tci/domain/services/list_repository_events.py src/tci/api/routes/repository_events.py src/tci/web/routes/repository_events.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - Result: no issues found.
  - `rtk ruff check src/tci/domain/services/repository_connection_support.py src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py src/tci/domain/services/list_repository_events.py src/tci/api/routes/repository_events.py src/tci/web/routes/repository_events.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - Result: no issues found.
- 2026-04-30 Event/status credential boundary broad verification:
  - `rtk black --check .` result: 162 files would be left unchanged.
  - `rtk ruff check .` result: no issues found.
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q` result: 605 passed.
  - `rtk alembic heads` result: `009_repository_first_connections (head)`.
  - `rtk proxy git diff --check` result: passed.
- 2026-04-30 Operator candidate UI RED: `rtk proxy pytest tests/integration/repository_connections/test_operator_connection_pages.py -q`
  - Result: 4 failed and 29 passed because the operator page did not render candidate repositories, candidate empty state, already-connected candidate state, or pass `candidateId` through create validation.
- 2026-04-30 Operator candidate UI GREEN: `rtk pytest tests/integration/repository_connections/test_operator_connection_pages.py -q`
  - Result: 33 passed after loading candidate projections in the operator route, rendering candidate/manual fallback states, preserving secret sanitization, and forwarding `candidateId` into create validation.
- 2026-04-30 Mixed-provider workspace RED: `rtk proxy pytest tests/integration/repository_connections/test_mixed_provider_workspace.py -q`
  - Result: 1 failed because the operator list/event pages did not expose provider identity strongly enough for GitHub/GitLab distinction.
- 2026-04-30 Mixed-provider workspace GREEN: `rtk pytest tests/integration/repository_connections/test_mixed_provider_workspace.py -q`
  - Result: 1 passed after adding provider, GitLab instance, and project path context to the operator list and event timeline pages.
- 2026-04-30 SC-004 fixture RED: `rtk proxy pytest tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q`
  - Result: collection failed because the 60-task operator identification rehearsal fixture module did not exist.
- 2026-04-30 SC-004 fixture GREEN: `rtk pytest tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q`
  - Result: 1 passed after adding deterministic SC-004 fixture generation for 60 provider/repository/origin identification tasks. This is fixture evidence only; SC-004 remains pending until real operator answers are recorded in T072.
- 2026-04-30 US3 operator/mixed focused regression: `rtk pytest tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q`
  - Result: 35 passed.
- 2026-04-30 US3 operator/mixed broad verification:
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q` result: 611 passed.
  - `rtk black --check .` result: 165 files would be left unchanged.
  - `rtk ruff check .` result: no issues found.
  - `rtk mypy src/tci/web/routes/repository_connections.py tests/support/operator_identification_rehearsal.py` result: no issues found.
  - `rtk alembic heads` result: `009_repository_first_connections (head)`.
  - `rtk proxy git diff --check` result: passed.
- 2026-04-30 Reviewer remediation RED:
  - `rtk proxy pytest tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_uses_selected_gitlab_candidate_defaults tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_rejects_unselectable_candidate tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_redacts_secret_bearing_remote_url -q` result: 3 failed because candidate radio selection did not drive provider/remote URL defaults, non-selectable candidates were only disabled in HTML, and secret-bearing remote URLs were reflected on validation errors.
  - `rtk proxy pytest tests/integration/repository_connections/test_repository_first_permission_failures.py::test_candidate_selected_create_rejects_unavailable_candidate_without_side_effects -q` result: 1 failed because API create accepted a selected candidate with `access_status != available`.
  - `rtk proxy pytest tests/integration/repository_connections/test_mixed_provider_workspace.py -q` result: 1 failed because operator detail did not expose workspace context explicitly enough for mixed-provider identification evidence.
- 2026-04-30 Reviewer remediation GREEN:
  - `rtk pytest tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_uses_selected_gitlab_candidate_defaults tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_rejects_unselectable_candidate tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_redacts_secret_bearing_remote_url -q` result: 3 passed after deriving selected candidate provider/remote URL from sanitized candidate projections, rejecting non-selectable candidate submissions server-side, and clearing secret-bearing `remoteUrl` before error re-render.
  - `rtk pytest tests/integration/repository_connections/test_repository_first_permission_failures.py::test_candidate_selected_create_rejects_unavailable_candidate_without_side_effects -q` result: 1 passed after create service rejected selected candidates whose `access_status` is not `available`.
  - `rtk pytest tests/integration/repository_connections/test_mixed_provider_workspace.py -q` result: 1 passed after adding explicit workspace context to the operator detail page.
  - `rtk pytest tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q` result: 43 passed.
  - `rtk black --check src/tci/domain/services/create_repository_connection.py src/tci/web/routes/repository_connections.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_mixed_provider_workspace.py` result: 5 files would be left unchanged.
  - `rtk ruff check src/tci/domain/services/create_repository_connection.py src/tci/web/routes/repository_connections.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_mixed_provider_workspace.py` result: no issues found.
  - `rtk mypy src/tci/domain/services/create_repository_connection.py src/tci/web/routes/repository_connections.py tests/support/operator_identification_rehearsal.py` result: no issues found.
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q` result: 615 passed.
  - `rtk alembic heads` result: `009_repository_first_connections (head)`.
  - `rtk proxy git diff --check` result: passed.
- 2026-04-30 Reviewer re-review closure:
  - General reviewer: no findings; confirmed candidate selection defaults, server-side non-selectable candidate rejection, and detail/evidence scope.
  - Python reviewer: no findings; noted whole touched test-file mypy still has pre-existing `client.app.state` typing noise outside changed hunks.
  - Security reviewer: no findings; confirmed secret-bearing `remoteUrl` clearing, candidate trust boundary, sanitized candidate URL display, and preserved operator auth/same-origin behavior.
  - Security reviewer also ran `uvx pip-audit .`; result: no known vulnerabilities found.

## Final Evidence

- 2026-04-30 T069 repository-first focused final regression: `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q`
  - Result: 140 passed.
- 2026-04-30 T070 GitHub/GitLab final regression: `rtk pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_webhook_refresh.py tests/integration/repository_connections/test_gitlab_provider_flows.py tests/integration/repository_connections/test_operator_event_pages.py tests/contract/repository_ingestion/test_github_webhook_contract.py tests/contract/repository_ingestion/test_gitlab_webhook_contract.py tests/contract/repository_ingestion/test_gitlab_connection_contract.py tests/contract/repository_ingestion/test_gitlab_scope_contract.py -q`
  - Result: 113 passed.
- 2026-04-30 Final broad repository ingestion regression after T069/T070: `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - Result: 615 passed.
- 2026-04-30 Final formatting check after T068-T070: `rtk black --check .`
  - Result: 165 files would be left unchanged.
- 2026-04-30 Final lint check after T068-T070: `rtk ruff check .`
  - Result: no issues found.
- 2026-04-30 Final focused typing after T068-T070: `rtk mypy src/tci/api/schemas/repository_candidate.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_candidates.py src/tci/api/routes/repository_connections.py src/tci/api/routes/repository_events.py src/tci/app.py src/tci/domain/services/create_repository_connection.py src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/list_repository_connections.py src/tci/domain/services/list_repository_events.py src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py src/tci/domain/services/repository_connection_support.py src/tci/domain/services/verify_repository_connection.py src/tci/domain/services/build_code_snapshot.py src/tci/domain/services/update_default_ref.py src/tci/web/routes/repository_connections.py src/tci/web/routes/repository_events.py tests/support/operator_identification_rehearsal.py tests/unit/repository_connections/test_repository_candidates.py tests/unit/repository_connections/test_repository_connection_credentials.py tests/unit/repository_connections/test_repository_connection_identity.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - Result: no issues found.
- 2026-04-30 Final Alembic graph check after T068-T070: `rtk alembic heads`
  - Result: `009_repository_first_connections (head)`.
- 2026-04-30 Final diff whitespace check after T068-T070: `rtk proxy git diff --check`
  - Result: passed.
- 2026-04-30 Remaining real-operator evidence:
  - `SC-001` remains pending until 3 representative operators complete 6 GitHub/GitLab timed attempts and at least 5 complete within 10 minutes.
  - `SC-004` remains pending until 3 representative operators complete 60 mixed-provider identification tasks and at least 57 are correct.
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
