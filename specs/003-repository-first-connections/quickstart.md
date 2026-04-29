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
- detail/snapshot nullable planning trace
- repository candidate empty state
- duplicate prevention across candidate/manual paths
