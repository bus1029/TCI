# Quickstart: ZIP 업로드 스냅샷과 워크스페이스 삭제

## Scope

This quickstart validates the planned Local Upload and workspace deletion behavior before implementation is marked complete. It also preserves GitHub/GitLab compatibility evidence.

## Redaction Rules

Do not record credentials, tokens, raw ZIP contents, private file paths, raw remote URLs with secrets, cookies, screenshots containing private code, or raw logs that include sensitive values. Evidence should use redacted workspace IDs, source labels, counts, timestamps, and pass/fail outcomes.

## Developer Verification

Run from `pilot-git-repo-connection/` unless a task states otherwise.

```bash
rtk pytest tests/unit/local_uploads -q
rtk pytest tests/contract/local_uploads tests/contract/workspaces -q
rtk pytest tests/integration/local_uploads tests/integration/workspaces -q
rtk pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py -q
rtk pytest tests/integration/repository_connections/test_mixed_provider_workspace.py -q
rtk ruff check
rtk black --check .
rtk mypy src/tci/domain/services src/tci/api/schemas src/tci/infrastructure/persistence
rtk alembic heads
rtk git diff --check
```

If a focused test path does not exist yet, create it in the implementation tasks before claiming the check.

## Local Upload Rehearsal

1. Create or select an active workspace without GitHub/GitLab access.
2. Upload a valid ZIP with a root folder, nested files, hidden files, and at least one empty directory.
3. Confirm upload acceptance within 10 seconds.
4. Confirm Local Upload processing reaches `succeeded`.
5. Open the Local Upload snapshot detail.
6. Verify extracted tree paths match what a normal unzip operation shows.
7. Confirm source is `local_upload`, not `repository_connection`.
8. Repeat with two more ZIP files in the same workspace.
9. Confirm three independent Local Upload snapshots exist.
10. Confirm the latest Local Upload snapshot is the default display.

Evidence to capture:

- Operator identifier or role, redacted.
- Start and completion timestamps.
- ZIP fixture label, not raw filename if sensitive.
- File count and total bytes.
- Snapshot IDs or redacted IDs.
- Pass/fail result.

## Local Upload Failure Matrix

Validate each case leaves no active snapshot and returns an actionable problem:

- Corrupt ZIP.
- Path traversal entry.
- Absolute path entry.
- Duplicate logical path.
- Root `manifest.json` overwrite attempt.
- Encrypted ZIP entry.
- Symlink or special file entry.
- Empty ZIP.
- Compressed size over 250 MiB.
- Uncompressed total over 1 GiB.
- More than 25,000 files.
- Any single file over 25 MiB.

## Workspace Delete Rehearsal

1. Create a workspace with at least one GitHub or GitLab connection, one Local Upload, and multiple snapshots.
2. As a non-owner/non-admin, attempt delete and confirm the workspace remains active.
3. As owner/admin, open deletion impact summary.
4. Confirm the summary shows repository connection, Local Upload, and snapshot counts.
5. Submit deletion confirmation.
6. Confirm workspace is removed from active lists.
7. Confirm direct access shows deleted state.
8. Confirm new repository connection, Local Upload, snapshot creation, verify, and worker mutation are rejected for the deleted workspace.
9. Confirm project contents and snapshot archive files for the workspace are removed.
10. Confirm only minimum deletion audit metadata remains.

Evidence to capture:

- Role used for delete attempt.
- Deletion started/completed timestamps.
- Affected counts.
- Purge status and archive count.
- Confirmation that no project contents or snapshot files remain accessible through normal paths.

## GitHub/GitLab Compatibility Rehearsal

Run existing GitHub Cloud and GitLab Self-Managed baseline scenarios after Local Upload and workspace deletion changes:

- GitHub connection create/detail/snapshot.
- GitHub webhook event processing.
- GitLab connection create/detail/snapshot.
- GitLab webhook event processing.
- Mixed-provider workspace list/detail/source identification.
- Deleted workspace guard does not affect other active workspaces.

Do not mark SC-004 complete without real regression evidence for both providers.

## Success Criteria Evidence Map

| Success Criterion | Required Evidence |
|-------------------|-------------------|
| SC-001 | Three operator upload-to-snapshot attempts, all under 5 minutes |
| SC-002 | Tree parity for valid ZIP fixtures |
| SC-003 | Failure matrix with no active snapshots |
| SC-004 | Existing GitHub/GitLab baseline regression pass |
| SC-005 | 30 source identification tasks, at least 29 correct |
| SC-006 | Owner/admin delete removes workspace from active flows |
| SC-007 | Non-owner/non-admin delete denied with no state change |
| SC-008 | Deleted workspace mutation/access denied |
| SC-009 | Project contents and snapshot files removed, audit metadata remains |
| SC-010 | Three sequential uploads create three independent snapshots and latest default |
