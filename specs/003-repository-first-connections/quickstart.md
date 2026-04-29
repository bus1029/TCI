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

## Scenario 5: Obsolete Planning Field Rejection

1. Create or choose a workspace ID.
2. Submit `POST /api/repository-connections` with otherwise valid repository fields plus `planningInputReferenceId`.
3. Verify the request is rejected with `code = obsolete_planning_reference`.
4. Verify no connection row, initial sync, or snapshot job is created from the rejected request.

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

1. Run the workspace-first GitHub connection rehearsal once per representative operator.
2. Run the workspace-first GitLab connection rehearsal once per representative operator.
3. Record 3 operators x 2 providers = 6 attempts in `delivery-evidence.md`.
4. For each attempt, record start timestamp, completion timestamp, elapsed minutes, provider, and success/failure.
5. Verify at least 5 of 6 attempts complete within 10 minutes.

## Scenario 8: Mixed-Provider Identification Evidence

1. Prepare a mixed-provider workspace screen with GitHub and GitLab connections/candidates that include similar names or paths.
2. Give each of 3 representative operators 20 provider/repository identification tasks.
3. Record all 60 task results in `delivery-evidence.md`.
4. Verify at least 57 of 60 answers are correct.

## Required Checks Before Task Completion

```bash
cd pilot-git-repo-connection
pytest tests/contract/repository_ingestion/test_repository_connection_contract.py -q
pytest tests/contract/repository_ingestion/test_gitlab_connection_contract.py -q
pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py -q
pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py -q
pytest tests/integration/repository_connections/test_gitlab_connection_lifecycle.py -q
```

Add new focused tests for:

- create without `planningInputReferenceId`
- reject obsolete `planningInputReferenceId`
- detail/snapshot nullable planning trace
- repository candidate empty state
- personal provider grant cannot become operation credential
- shared read-only credential failure prevents active connection creation
- shared read-only credential is the only credential used across create, verify, collect, event, status, and reverify paths
- duplicate prevention across candidate/manual paths
- mixed GitHub/GitLab list/detail/event/snapshot/history separation
- SC-001 six-attempt timed rehearsal evidence
- SC-004 sixty-task mixed-provider identification evidence
