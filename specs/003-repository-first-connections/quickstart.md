# Quickstart: 워크스페이스 기반 저장소 연결 시작점 전환

## Preconditions

- `pilot-git-repo-connection` dependencies are installed.
- PostgreSQL and Redis are available through the existing project test setup.
- Operator authentication is configured for API/UI checks.
- GitHub Cloud and GitLab Self-Managed regression fixtures remain available.

## Scenario 1: New Workspace-Based GitHub Connection

1. Create or choose a workspace ID.
2. Open repository connection create flow for that workspace.
3. Do not create or select a planning input reference.
4. Choose GitHub via candidate list if configured, or enter a GitHub remote URL manually.
5. Submit workspace shared read-only credential and default ref.
6. Verify response:
   - connection is created under the workspace
   - `planningInputReferenceId` was not required
   - detail returns `traceability.planningInputReference = null`
   - `origin.kind = workspace_repository`
   - repository verification uses the workspace shared read-only credential, not a personal provider grant
7. Trigger initial snapshot.
8. Verify snapshot detail still includes `connectionId`, `scopeRuleVersionId`, `syncRunId`, and nullable planning reference.

## Scenario 2: New Workspace-Based GitLab Connection

1. Create or choose a workspace ID.
2. If GitLab instance scope is configured, confirm candidates are shown only from that scope.
3. If no GitLab instance scope is configured, confirm candidates are empty and manual URL input remains available.
4. Enter or select GitLab remote URL.
5. Submit workspace shared read-only credential and default ref.
6. Verify connection reaches existing GitLab canonical states only: `active`, `reauth_required`, or `ref_missing`.
7. Trigger initial snapshot.
8. Verify GitLab provider metadata and snapshot traceability work without planning reference.

## Scenario 3: Existing Planning-Based Connections

1. Seed or use an existing GitHub connection with non-null planning reference.
2. Seed or use an existing GitLab connection with non-null planning reference.
3. Open workspace connection list.
4. Verify both connections appear under their existing `workspace_id`.
5. Open details.
6. Verify:
   - `origin.kind = legacy_planning`
   - legacy planning trace is still shown
   - provider-specific event and snapshot history remains accessible
7. Run existing GitHub/GitLab webhook regression checks.

## Scenario 4: Duplicate Prevention

1. Create a workspace-based connection through candidate selection.
2. Try to create the same provider/repository through manual URL input.
3. Verify duplicate prevention returns existing connection guidance.
4. Repeat in the opposite order.

## Scenario 5: Obsolete Planning Field Rejection Matrix

1. Create or choose a workspace ID.
2. Submit `POST /api/repository-connections` with otherwise valid repository fields plus `planningInputReferenceId`.
3. Verify the request is rejected with `code = obsolete_planning_reference`.
4. Verify no connection row, initial sync, or snapshot job is created from the rejected request.
5. Repeat the rejection check for `planningInputReference`, `planningTrace`, `traceability.planningInputReference`, `approvedSpecPath`, `approvedPlanPath`, `specPath`, and `planPath`.

## Scenario 6: Credential Boundary and Permission Failure

1. Configure a personal provider grant that can list candidates.
2. Open the candidate list and verify candidates can be displayed from the configured provider scope.
3. Submit a create request without a workspace shared read-only credential.
4. Verify the request fails with `code = shared_credential_required`.
5. Submit a create request with expired, revoked, or invalid shared read-only credential.
6. Verify the request fails with `code = shared_credential_invalid`, `repository_not_authorized`, or `provider_reauth_required` and includes remediation guidance.
7. Verify no active connection, mirror sync, or snapshot job is created for the failed request.
8. For a successfully created connection, run verification, collection, event processing, status lookup, and reverify checks with a personal provider grant removed or revoked.
9. Verify those operation paths continue to use the workspace shared read-only credential and never fall back to the personal provider grant.

## Scenario 7: Operator Rehearsal Evidence

Before recording `SC-001`, run the automated workspace-first checks below so the
manual rehearsal starts from a green baseline.

```bash
cd pilot-git-repo-connection
rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q
```

Latest automated output:

```text
Pytest: 140 passed
```

Evidence redaction rules:

- Use synthetic or throwaway repositories when possible.
- Record pseudonymous operator IDs such as `operator-01`; do not record real names, emails, usernames, cookies, session IDs, or auth headers.
- Record provider, sanitized repository label, start timestamp, completion timestamp, elapsed minutes, and pass/fail only.
- Do not record credentials, tokens, full remote URLs, credential-bearing URLs, screenshots, terminal raw logs, private repository paths, or provider account secrets.

1. Run the workspace-first GitHub connection rehearsal once per representative operator.
2. Run the workspace-first GitLab connection rehearsal once per representative operator.
3. Record 3 operators x 2 providers = 6 attempts in `delivery-evidence.md`.
4. For each attempt, record start timestamp, completion timestamp, elapsed minutes, provider, and success/failure.
5. Verify at least 5 of 6 attempts complete within 10 minutes.

## Scenario 8: Mixed-Provider Identification Evidence

Before recording `SC-004`, run the deterministic fixture check.

```bash
cd pilot-git-repo-connection
rtk pytest tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q
```

Latest automated output:

```text
Pytest: 1 passed
```

Evidence redaction rules:

- Use synthetic or throwaway mixed-provider repositories when possible.
- Record pseudonymous operator IDs and sanitized task IDs only.
- Record expected provider, sanitized repository label, answer provider/repository label, correctness, and aggregate score.
- Do not record screenshots, full remote URLs, private repository paths, operator names, cookies, tokens, raw browser logs, or provider account secrets.

1. Prepare a mixed-provider workspace screen with GitHub and GitLab connections/candidates that include similar names or paths.
2. Give each of 3 representative operators 20 provider/repository identification tasks.
3. Record all 60 task results in `delivery-evidence.md`.
4. Verify at least 57 of 60 answers are correct.

## Required Checks Before Task Completion

```bash
cd pilot-git-repo-connection
rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/contract/repository_ingestion/test_repository_candidate_contract.py -q
rtk pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q
rtk pytest tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q
rtk pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_webhook_refresh.py tests/integration/repository_connections/test_gitlab_provider_flows.py tests/integration/repository_connections/test_operator_event_pages.py tests/contract/repository_ingestion/test_github_webhook_contract.py tests/contract/repository_ingestion/test_gitlab_webhook_contract.py tests/contract/repository_ingestion/test_gitlab_connection_contract.py tests/contract/repository_ingestion/test_gitlab_scope_contract.py -q
rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q
rtk black --check .
rtk ruff check .
rtk mypy src/tci/api/schemas/repository_candidate.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_candidates.py src/tci/api/routes/repository_connections.py src/tci/api/routes/repository_events.py src/tci/app.py src/tci/domain/services/create_repository_connection.py src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/list_repository_connections.py src/tci/domain/services/list_repository_events.py src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py src/tci/domain/services/repository_connection_support.py src/tci/domain/services/verify_repository_connection.py src/tci/domain/services/build_code_snapshot.py src/tci/domain/services/update_default_ref.py src/tci/web/routes/repository_connections.py src/tci/web/routes/repository_events.py tests/support/operator_identification_rehearsal.py tests/unit/repository_connections/test_repository_candidates.py tests/unit/repository_connections/test_repository_connection_credentials.py tests/unit/repository_connections/test_repository_connection_identity.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py
rtk alembic heads
rtk proxy git diff --check
```

Latest automated outputs:

```text
T069 focused repository-first checks: Pytest: 140 passed
T070 GitHub/GitLab regression checks: Pytest: 113 passed
Broad repository ingestion regression: Pytest: 615 passed
black: 165 files would be left unchanged
ruff: No issues found
mypy: No issues found
alembic heads: 009_repository_first_connections (head)
git diff --check: passed
```

Add new focused tests for:

- create without `planningInputReferenceId`
- reject each obsolete planning/spec/plan reference field
- detail/snapshot nullable planning trace
- planning-free snapshot creation, manifest traceability, and snapshot detail loading
- repository candidate empty state
- personal provider grant cannot become operation credential
- shared read-only credential failure prevents active connection creation
- shared read-only credential is the only credential used across create, verify, collect, event, status, and reverify paths
- duplicate prevention across candidate/manual paths
- mixed GitHub/GitLab list/detail/event/snapshot/history separation
- SC-001 six-attempt timed rehearsal evidence
- SC-004 sixty-task mixed-provider identification evidence
