# Implementation Plan: ZIP 업로드 스냅샷과 워크스페이스 삭제

**Branch**: `004-zip-upload-workspace-delete` | **Date**: 2026-05-06 | **Spec**: `/specs/004-zip-upload-workspace-delete/spec.md`

**Input**: Feature specification from `/specs/004-zip-upload-workspace-delete/spec.md`

## Summary

이 계획은 기존 `pilot-git-repo-connection` 런타임에 GitHub/GitLab 원격 연결 없이 ZIP 파일을 업로드해 코드 스냅샷을 생성하는 Local Upload 출처를 추가하고, 워크스페이스 soft delete를 도입한다. 핵심 전략은 `RepositoryConnection`을 Local Upload에 재사용하지 않고 `CodeSnapshot`을 connection-backed snapshot과 local-upload-backed snapshot을 모두 표현할 수 있게 확장하는 것이다. 기존 GitHub Cloud/GitLab Self-Managed 연결, webhook, credential, candidate, mirror sync 의미는 변경하지 않고 compatibility regression 대상으로 고정한다.

## Change Traceability

**Planning Input**: 2026-05-06 사용자 요청 "기존 GitLab/GitHub 연동 기능에 ZIP 로컬 업로드 스냅샷 생성과 워크스페이스 삭제 기능을 추가", 제약 "clarify 항목을 계획에서 구체화", "기존 GitHub Cloud, GitLab 연동 코드 호환성 고려"

**Spec Scope Baseline**: `/specs/004-zip-upload-workspace-delete/spec.md`에 2026-05-06 clarification 5건이 반영된 Draft scope

**Clarification Decisions Frozen in Plan**:

- 워크스페이스 삭제는 soft delete다.
- 삭제된 워크스페이스는 활성 목록과 일반 작업 흐름에서 제거된다.
- 삭제 완료 후 프로젝트 내용과 스냅샷 파일은 제거하고 최소 감사 메타데이터만 보존한다.
- 로컬 ZIP 업로드는 `RepositoryConnection`이 아니며 별도 `Local Upload` 출처로 관리한다.
- Local Upload 스냅샷은 업로드마다 독립 생성되고, 최신 Local Upload 스냅샷을 기본 표시한다.
- 워크스페이스 삭제는 워크스페이스 소유자 또는 관리자만 수행할 수 있다.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography, Python standard `zipfile`/`pathlib` for archive inspection and extraction

**Storage**: PostgreSQL 16 for workspace deletion metadata, local upload metadata, repository connection metadata, events, sync runs, and snapshot metadata; Redis 7 for async snapshot jobs; local disk mirror cache under `pilot-git-repo-connection/.runtime/git-mirrors`; local snapshot archive under `pilot-git-repo-connection/.runtime/code-snapshots`

**Testing**: `pytest`, `pytest-asyncio`, `httpx`, existing contract/integration/unit tests under `pilot-git-repo-connection/tests`, operator UI integration tests, existing GitHub/GitLab regression fixtures

**Target Platform**: Linux-based FastAPI/operator UI/worker runtime with local disk snapshot archive and optional Redis queue

**Project Type**: Python web application with JSON API, async worker, and server-rendered operator UI

**Performance Goals**: Valid ZIP upload acceptance path completes upload request and queues processing within 10 seconds for accepted archives; representative operators complete upload-to-snapshot in under 5 minutes; workspace delete confirmation completes user-visible soft delete in under 30 seconds and schedules/removes project content without leaving active workspace access

**Constraints**: Pilot implementation gate remains manual; Local Upload MUST NOT become `RepositoryConnection`; GitHub/GitLab provider, credential, webhook, candidate, and mirror sync semantics remain unchanged; ZIP entries must be validated before extraction; path traversal, absolute paths, duplicate logical paths, reserved manifest overwrite, unsupported special file entries, archive bombs, and configured size/count limit violations are rejected before active snapshot creation; deleted workspaces reject new GitHub/GitLab connection, ZIP upload, snapshot creation, verify, and webhook-driven mutation in that workspace; raw uploaded ZIPs are not retained after successful snapshot archive creation; deleted workspace project contents and snapshot files are removed while minimum deletion audit metadata remains

**Scale/Scope**: Internal operator usage; low hundreds of workspaces; per-ZIP plan limit fixed at 250 MiB compressed upload, 1 GiB total uncompressed bytes, 25,000 file entries, 25 MiB per individual file, nesting depth up to 50 path segments; limits are centralized settings with the above defaults

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Planning input is linked and translated into concrete design scope.
- [x] `spec.md` is the active scope baseline for this plan.
- [x] Plan scope stays inside the accepted spec: Local Upload ZIP snapshot, workspace soft delete, deletion audit, GitHub/GitLab compatibility.
- [x] End-to-end traceability remains planning input -> spec -> plan -> research/data model/contracts/quickstart -> future tasks/evidence.
- [x] Pilot rule acknowledged: implementation will not auto-run and requires explicit human approval after tasks are reviewed.
- [x] Validation evidence is defined for Local Upload success/failure, deletion permissions/content removal, latest snapshot default, and GitHub/GitLab regression compatibility.

## Project Structure

### Documentation (this feature)

```text
specs/004-zip-upload-workspace-delete/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── local-upload-workspace-delete.openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md              # Created by /speckit-tasks, not /speckit-plan
```

### Source Code (planned implementation structure)

```text
pilot-git-repo-connection/
├── src/tci/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── local_uploads.py              # New Local Upload API
│   │   │   ├── workspaces.py                 # New workspace deletion API
│   │   │   ├── repository_connections.py     # Guard deleted workspace only
│   │   │   └── repository_snapshots.py       # Preserve connection-backed routes
│   │   └── schemas/
│   │       ├── local_upload.py               # New request/response schemas
│   │       ├── workspace.py                  # Deletion response schemas
│   │       └── repository_connection.py      # Snapshot serialization extension
│   ├── domain/services/
│   │   ├── create_local_upload_snapshot.py   # New ZIP validation and snapshot command
│   │   ├── delete_workspace.py               # New soft delete command
│   │   ├── get_code_snapshot_detail.py       # Source-aware snapshot detail
│   │   ├── list_repository_connections.py    # Exclude deleted workspace
│   │   └── repository_connection_support.py  # Existing provider behavior unchanged
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── models.py                     # Add workspace/local upload/source fields
│   │   │   ├── local_upload_repository.py    # New
│   │   │   ├── workspace_repository.py       # New
│   │   │   └── code_snapshot_repository.py   # Source-aware create/get_latest
│   │   ├── snapshots/
│   │   │   ├── local_zip_extractor.py        # New safe ZIP reader
│   │   │   ├── snapshot_archive_store.py     # Reuse with safe entries
│   │   │   └── snapshot_manifest_writer.py   # Extend traceability source
│   │   └── queue/
│   │       └── repository_ingestion_tasks.py # Add Local Upload snapshot task
│   ├── web/routes/
│   │   ├── local_uploads.py                  # New operator UI route
│   │   └── workspaces.py                     # New delete flow route
│   └── web/templates/
│       ├── local_uploads/
│       └── workspaces/
├── alembic/versions/
└── tests/
    ├── contract/local_uploads/
    ├── contract/workspaces/
    ├── integration/local_uploads/
    ├── integration/workspaces/
    ├── integration/repository_connections/  # Existing GitHub/GitLab regressions
    └── unit/local_uploads/
```

**Structure Decision**: Keep the existing `pilot-git-repo-connection` project. Add Local Upload and Workspace services next to existing repository ingestion services, but keep GitHub/GitLab provider code in place. Extend snapshot persistence to support a nullable `connection_id` for Local Upload snapshots or an explicit `source_kind` owner constraint; do not create fake repository connections for ZIP uploads.

## Phase 0: Research Summary

`research.md` resolves plan-level decisions that remained concrete enough to affect architecture:

- Local Upload source model is separate from `RepositoryConnection`.
- Snapshot ownership becomes source-aware.
- ZIP safety defaults are fixed.
- Workspace delete uses soft delete plus content purge.
- Deleted workspace guards apply to all mutation paths.
- GitHub/GitLab compatibility tests stay mandatory.

## Phase 1: Design Summary

- `data-model.md` defines `Workspace`, `LocalUpload`, `CodeSnapshot`, `CodeSnapshotFile`, `RepositoryConnection`, and `WorkspaceDeletionRecord`.
- `contracts/local-upload-workspace-delete.openapi.yaml` defines Local Upload, Local Upload snapshot detail, workspace delete, and active workspace guard problem contracts.
- `quickstart.md` defines operator rehearsal and developer verification with redaction boundaries.
- AGENTS.md now points the Spec Kit context block at this plan.

## Implementation Strategy

### Slice 1. Workspace Lifecycle Foundation

- Add persisted `workspaces` state if absent in the pilot runtime, or introduce a minimal workspace lifecycle table keyed by existing `workspace_id`.
- Add states `active`, `deleting`, `deleted`; include `deleted_at`, `deleted_by`, and deletion reason metadata.
- Add `workspace_deletion_records` for audit-only metadata and content purge result.
- Add a shared domain guard that rejects mutation paths when workspace is `deleting` or `deleted`.
- Apply the guard to repository connection create/update/verify, repository snapshot create, candidate-selected/manual connection creation, Local Upload upload, and worker task entry points.

### Slice 2. Source-Aware Snapshot Model

- Add `snapshot_source_kind` with values `repository_connection` and `local_upload`.
- Add `local_upload_id` on `code_snapshots` and allow `connection_id`, `sync_run_id`, `scope_rule_version_id`, `requested_ref_type`, `requested_ref_name`, `resolved_commit_sha`, and `tree_sha` to be nullable only for Local Upload snapshots.
- Add database check constraints so repository snapshots still require existing connection/sync/scope/ref/git identifiers, while Local Upload snapshots require `local_upload_id` and must not require repository fields.
- Extend `CodeSnapshotRepository` with source-aware create/get/latest methods without breaking existing `get(connection_id, snapshot_id)` and `get_latest_for_connection`.
- Extend snapshot serializers with `source.kind`, `localUpload`, and nullable repository-only fields.

### Slice 3. Safe Local ZIP Intake

- Add `LocalUpload` metadata with original filename, content hash, compressed size, uncompressed size, file count, status, failure code/message, created_by, and timestamps.
- Add safe ZIP reader that validates central directory before extraction and rejects path traversal, absolute paths, `.`/`..`, duplicate case-folded paths, reserved root `manifest.json`, symlink/special file entries, encrypted entries, excessive compression ratio, nested depth over 50, unsupported zero-file archives, and configured size/count limit violations.
- Do not retain raw ZIP content after the snapshot archive is created or after a failure is recorded.
- Convert valid ZIP entries directly into `SnapshotArchiveEntryDraft` and reuse `SnapshotArchiveStore.store()`.
- Preserve empty directories in Local Upload metadata/manifest if needed for tree display; `CodeSnapshotFile` remains file-focused.

### Slice 4. Local Upload Snapshot Creation

- Add `POST /api/local-uploads` to accept multipart ZIP uploads and create a pending Local Upload.
- If Redis is configured, queue `run_local_upload_snapshot_task`; otherwise support a deterministic synchronous test path only in test/development.
- Add `create_local_upload_snapshot` service that writes the archive, writes manifest traceability, creates source-aware `CodeSnapshot`, marks Local Upload `succeeded`, and updates latest Local Upload pointer/read model.
- Failure must leave no active snapshot, remove any partial archive, mark Local Upload `failed`, and return user-actionable problem details.
- Latest Local Upload snapshot for a workspace is ordered by snapshot `created_at`, then ID.

### Slice 5. Workspace Delete and Content Purge

- Add `DELETE /api/workspaces/{workspace_id}` with owner/admin authorization, confirmation token or confirmation phrase, and deletion impact summary.
- Soft delete first by transitioning `active -> deleting -> deleted`.
- After soft delete, purge project contents and snapshot files under the workspace: Local Upload snapshot archives, Local Upload raw temp files, and repository connection snapshot archives for that workspace.
- Preserve only minimum audit metadata: workspace ID, deleted_by, deleted_at, counts, purge status, and high-level source counts. Do not preserve file paths, raw ZIP names beyond a redacted/display-safe original filename, credentials, remote URLs with secrets, or snapshot archive file contents.
- Existing GitHub/GitLab provider rows for deleted workspace are not used for new operations; provider semantics for other workspaces remain unchanged.

### Slice 6. Operator UI

- Add Local Upload entry point in workspace snapshot area, not in repository connection creation.
- Show Local Upload snapshots with source label, upload time, uploaded-by, original filename display, file count, total bytes, and latest marker.
- Show GitHub/GitLab connections separately from Local Upload source.
- Add workspace deletion confirmation that shows affected counts and makes the irreversible content purge explicit.
- Hide deleted workspaces from active lists and show a deleted-state page for direct access.

### Slice 7. Compatibility and Regression Guard

- Existing GitHub/GitLab `RepositoryConnection` create/detail/verify/snapshot/webhook contracts remain unchanged except for deleted-workspace guard.
- Existing `GET /api/repository-connections/{id}` and `/api/repository-connections/{id}/snapshots/{snapshot_id}` continue to work for connection-backed snapshots.
- Existing GitHub/GitLab webhook endpoints do not accept Local Upload IDs and do not create Local Upload snapshots.
- Existing candidate discovery remains provider-scoped and independent from Local Upload.
- Existing repository-first tests remain regression gates; add targeted Local Upload and workspace deletion tests without replacing GitHub/GitLab fixtures.

## Validation Strategy

- Unit
  - ZIP validator rejects traversal, absolute paths, duplicate logical paths, encrypted entries, symlink/special files, reserved manifest overwrite, zero-file archives, and limit violations.
  - ZIP validator accepts nested files, hidden files, empty directory metadata, and normal root-folder archives.
  - Local Upload snapshot service creates independent snapshots for repeated uploads and marks latest correctly.
  - Local Upload failure removes partial archive and does not create active `CodeSnapshot`.
  - Workspace deletion guard rejects all mutation commands for `deleting` and `deleted` workspaces.
  - Workspace deletion purge records only minimum audit metadata.
  - Source-aware `CodeSnapshot` constraints reject invalid mixed source ownership.
- Contract
  - `POST /api/local-uploads` accepts multipart ZIP and returns pending/succeeded metadata.
  - `GET /api/local-uploads/{id}` returns status, latest snapshot, and failure details.
  - `GET /api/local-uploads/{id}/snapshots/{snapshot_id}` returns source-aware snapshot detail.
  - `DELETE /api/workspaces/{workspace_id}` requires owner/admin and confirmation.
  - Non-owner/admin delete attempt returns permission problem and leaves state unchanged.
  - Deleted workspace mutation attempts return deleted-state problem.
- Integration
  - Valid ZIP upload -> Local Upload succeeded -> source-aware snapshot detail matches extracted tree.
  - Three sequential ZIP uploads -> three independent snapshots -> latest is default.
  - Corrupt ZIP/unsafe path/limit exceeded -> failed Local Upload -> no active snapshot.
  - Workspace delete -> active list exclusion -> mutation guard -> content archive removal -> audit metadata remains.
  - GitHub connection in active workspace -> create/detail/snapshot/webhook regression passes.
  - GitLab connection in active workspace -> create/detail/snapshot/webhook regression passes.
  - Mixed workspace with GitHub, GitLab, and Local Upload -> source identification and existing provider details stay distinct.
- Delivery evidence
  - SC-001 operator rehearsal: 3 operators upload ZIP without GitHub/GitLab, all complete within 5 minutes.
  - SC-002 tree parity evidence for representative root-folder and nested-folder ZIPs.
  - SC-003 failure matrix for corrupt ZIP, unsafe path, and limit exceeded.
  - SC-004 GitHub/GitLab baseline regression evidence.
  - SC-005 30 source identification tasks with at least 29 correct answers.
  - SC-006 through SC-009 deletion permission, active-list exclusion, mutation denial, content purge, and audit metadata evidence.
  - SC-010 repeated upload evidence with three independent snapshots and latest default.

## Post-Design Constitution Check

- [x] Planning input remains linked in spec, plan, research, data model, contracts, and quickstart.
- [x] No implementation starts from this plan; `/speckit-tasks` and explicit human approval are still required.
- [x] Plan does not introduce unapproved provider changes or hard delete behavior absent from spec.
- [x] Traceability is preserved through Local Upload metadata, source-aware snapshot detail, deletion audit metadata, and future delivery evidence.
- [x] Validation strategy defines evidence for every success criterion and compatibility constraint.

## Complexity Tracking

No constitution violation is introduced. The unavoidable complexity is source-aware snapshot ownership because current `CodeSnapshot` is connection-backed, while the clarified spec forbids representing Local Upload as `RepositoryConnection`.

| Risk | Why Needed | Simpler Alternative Rejected Because |
|------|------------|--------------------------------------|
| Source-aware snapshot schema | Local Upload snapshots need to reuse snapshot listing/detail/archive behavior without fake repository connections | Creating Local Upload as a repository connection would violate clarification and risk GitHub/GitLab provider semantics |
| Workspace lifecycle table/guard | Deletion must block all new work and hide active workspace flows consistently | UI-only hiding would allow API/worker mutations against deleted workspaces |
| Content purge after soft delete | Spec requires project contents and snapshot files removed while audit metadata remains | Keeping files hidden would violate deletion clarification and increase data exposure risk |
