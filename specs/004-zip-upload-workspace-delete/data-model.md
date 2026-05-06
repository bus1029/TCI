# Data Model: ZIP 업로드 스냅샷과 워크스페이스 삭제

## Workspace

Represents a workspace that owns repository connections, Local Uploads, and snapshots.

### Fields

- `id`: UUID primary identifier.
- `status`: `active`, `deleting`, or `deleted`.
- `created_at`: creation timestamp.
- `updated_at`: last lifecycle update timestamp.
- `deleted_at`: nullable deletion timestamp.
- `deleted_by`: nullable operator/user ID for owner/admin who confirmed deletion.
- `delete_reason`: nullable short reason or confirmation metadata.

### Relationships

- Has many `RepositoryConnection`.
- Has many `LocalUpload`.
- Has many `WorkspaceDeletionRecord`.

### Validation

- New uploads, repository connections, snapshot creation, verification, and webhook-driven mutation require `status = active`.
- `deleted_at` and `deleted_by` are required once status is `deleted`.

### State Transitions

```text
active -> deleting -> deleted
```

No transition from `deleted` back to `active` is planned.

## LocalUpload

Represents a ZIP file submitted to a workspace. It is not a `RepositoryConnection`.

### Fields

- `id`: UUID primary identifier.
- `workspace_id`: owning workspace UUID.
- `status`: `pending`, `processing`, `succeeded`, or `failed`.
- `original_filename_display`: sanitized filename for user display.
- `upload_sha256`: SHA-256 of uploaded ZIP bytes.
- `compressed_size_bytes`: uploaded ZIP size.
- `uncompressed_size_bytes`: total accepted uncompressed file bytes.
- `file_count`: accepted file count.
- `directory_count`: observed directory count for tree display metadata.
- `latest_snapshot_id`: nullable UUID pointing to the latest succeeded snapshot from this upload.
- `failure_code`: nullable failure code.
- `failure_message`: nullable user-actionable failure message.
- `created_by`: operator/user ID.
- `created_at`: upload creation timestamp.
- `completed_at`: nullable processing completion timestamp.

### Relationships

- Belongs to `Workspace`.
- Has one or more `CodeSnapshot` rows through `local_upload_id`.

### Validation

- `workspace_id` must reference an active workspace at upload start.
- Accepted ZIP defaults: max 250 MiB compressed, max 1 GiB uncompressed, max 25,000 files, max 25 MiB per file, max 50 path segments.
- Raw ZIP bytes are discarded after success or failure.
- `succeeded` requires at least one source-aware `CodeSnapshot`.
- `failed` must not create an active snapshot.

### State Transitions

```text
pending -> processing -> succeeded
pending -> processing -> failed
pending -> failed
```

## CodeSnapshot

Represents a stored project snapshot. Existing repository snapshots remain connection-backed; Local Upload snapshots are upload-backed.

### Fields

- `id`: UUID primary identifier.
- `workspace_id`: owning workspace UUID.
- `source_kind`: `repository_connection` or `local_upload`.
- `connection_id`: required for `repository_connection`, null for `local_upload`.
- `local_upload_id`: required for `local_upload`, null for `repository_connection`.
- `sync_run_id`: required for `repository_connection`, null for `local_upload`.
- `scope_rule_version_id`: required for `repository_connection`; optional/null for `local_upload`.
- `requested_ref_type`: required for `repository_connection`; null for `local_upload`.
- `requested_ref_name`: required for `repository_connection`; null for `local_upload`.
- `resolved_commit_sha`: required for `repository_connection`; null for `local_upload`.
- `tree_sha`: required for `repository_connection`; for `local_upload`, use deterministic snapshot tree hash derived from normalized paths and file content hashes or store in a local-upload-specific field.
- `archive_path`: project-relative archive path under `code_snapshot_root`.
- `file_count`: number of included files.
- `total_bytes`: total included file bytes.
- `created_at`: creation timestamp.

### Relationships

- Belongs to `RepositoryConnection` when source is `repository_connection`.
- Belongs to `LocalUpload` when source is `local_upload`.
- Has many `CodeSnapshotFile`.

### Validation

- Repository snapshots keep existing foreign keys and constraints.
- Local Upload snapshots require `workspace_id`, `local_upload_id`, `archive_path`, `file_count`, and `total_bytes`.
- Exactly one source owner must be set: `connection_id` or `local_upload_id`.
- `file_count` must be greater than zero.

## CodeSnapshotFile

Represents a file included in a snapshot archive.

### Fields

- `id`: UUID primary identifier.
- `snapshot_id`: parent snapshot UUID.
- `path`: safe normalized POSIX relative path.
- `extension`: nullable extension.
- `language_hint`: nullable language hint.
- `size_bytes`: file size.
- `content_sha256`: SHA-256 of content bytes.
- `archive_blob_path`: safe relative path inside stored archive.
- `included_by`: existing inclusion reason, with `local_upload_default` added or existing default policy reused for Local Upload.

### Validation

- Path must not be absolute and must not contain empty, `.`, or `..` segments.
- Paths are unique within a snapshot, case-folded.
- Root `manifest.json` remains reserved for snapshot metadata.

## RepositoryConnection

Existing GitHub/GitLab connection entity.

### Fields

Existing fields remain provider-specific. This feature does not add Local Upload values to `RepositoryProvider`.

### Relationships

- Belongs to active/non-deleted `Workspace`.
- Has repository-backed `CodeSnapshot` rows.

### Compatibility Rules

- GitHub/GitLab duplicate repository identity rules remain unchanged.
- GitHub/GitLab credential, webhook, candidate, event, and mirror behavior remain unchanged.
- Repository mutation routes must reject deleted workspaces.

## WorkspaceDeletionRecord

Audit-only metadata for workspace deletion.

### Fields

- `id`: UUID primary identifier.
- `workspace_id`: deleted workspace UUID.
- `deleted_by`: owner/admin operator ID.
- `requested_at`: deletion request timestamp.
- `completed_at`: deletion completion timestamp.
- `purge_status`: `pending`, `succeeded`, or `failed`.
- `repository_connection_count`: count at deletion time.
- `local_upload_count`: count at deletion time.
- `snapshot_count`: count at deletion time.
- `purged_archive_count`: count of removed snapshot archives.
- `failure_message`: nullable failure summary.

### Validation

- Must not contain raw credentials, raw remote URLs with secrets, raw ZIP contents, snapshot file contents, or full project file listings.
- One completed deletion record per workspace is expected.
