# Research: ZIP 업로드 스냅샷과 워크스페이스 삭제

## Decision: Local Upload is a separate source, not a Repository Connection

**Rationale**: The clarified spec requires Local Upload to be represented outside `RepositoryConnection`. Existing GitHub/GitLab code has provider-specific constraints, credentials, webhooks, mirror paths, candidate selection, and remote URL validation. Reusing that model for ZIP files would create fake provider behavior and increase regression risk.

**Alternatives considered**:

- Local Upload as a third repository provider: rejected because it would force provider/webhook/credential semantics that do not exist for ZIP files.
- Local Upload as temporary repository connection: rejected because it would blur the product model and make deleted-workspace purge harder.

## Decision: Extend snapshots to be source-aware

**Rationale**: Existing `CodeSnapshot` is connection-backed. Local Upload still needs the same archive/detail/file-list behavior, but without a repository connection, sync run, ref, commit, tree SHA, or scope rule. A `snapshot_source_kind` with owner constraints keeps repository snapshots strict and gives Local Upload snapshots a first-class path.

**Alternatives considered**:

- Create a parallel `local_code_snapshots` table: rejected because it duplicates archive/detail/list behavior and complicates mixed source display.
- Store Local Upload only in files without metadata rows: rejected because success criteria require list/detail/latest behavior and deletion audit counts.

## Decision: Safe ZIP validation uses fixed defaults before extraction

**Rationale**: ZIP upload accepts untrusted local files. Validation must happen before archive materialization to prevent path traversal, zip bombs, duplicate path ambiguity, and unsupported filesystem entries. Defaults are fixed for plan scope: 250 MiB compressed upload, 1 GiB total uncompressed bytes, 25,000 file entries, 25 MiB per individual file, and 50 path segments.

**Alternatives considered**:

- Defer all limits to environment configuration: rejected because tasks and tests need concrete limits.
- Trust extraction into a temp directory and validate after: rejected because unsafe paths and zip bombs must be stopped before writing arbitrary content.

## Decision: Raw ZIP files are not retained

**Rationale**: The feature requires preserving the extracted snapshot, not the original ZIP. Avoiding raw ZIP retention reduces storage, privacy, and deletion burden. The system keeps safe metadata such as original filename display, upload hash, sizes, status, and timestamps.

**Alternatives considered**:

- Retain raw ZIP for download/reprocessing: rejected because not requested and increases sensitive data retention.
- Retain raw ZIP for a short grace period: rejected because clarification requires deletion to remove project contents and keeping raw uploads adds another purge target.

## Decision: Workspace deletion is soft delete plus content purge

**Rationale**: Q1 fixed soft delete for product behavior and audit metadata. Q3 fixed removal of project contents and snapshot files. The combined model is `active -> deleting -> deleted`: users lose access immediately, mutations are blocked, content archives are purged, and audit metadata remains.

**Alternatives considered**:

- Hard delete database rows: rejected because minimum audit metadata must remain.
- Hide workspace only: rejected because project contents and snapshot files would remain available to internal paths.

## Decision: Deleted workspace guard is domain-level and route-level

**Rationale**: Deletion must block ZIP upload, repository connection creation, snapshot creation, verify, and worker mutation paths. A shared guard prevents bypass through API routes, web routes, and queued tasks.

**Alternatives considered**:

- UI-only delete hiding: rejected because API and worker paths could still mutate state.
- Per-route ad hoc checks only: rejected because worker and service paths need the same invariant.

## Decision: GitHub/GitLab compatibility is regression-gated, not refactored

**Rationale**: Existing provider code already handles remote parsing, credential validation, candidate discovery, sync runs, snapshot archives, and webhooks. This feature should add Local Upload and workspace deletion without changing provider semantics. Deleted-workspace guards are allowed because they are workspace lifecycle constraints, not provider behavior changes.

**Alternatives considered**:

- Refactor all snapshots and provider flows into a generic source framework first: rejected because it would expand scope beyond the user request.
- Migrate GitHub/GitLab snapshots into Local Upload-like flows: rejected because it would break webhook/sync semantics and existing evidence paths.
