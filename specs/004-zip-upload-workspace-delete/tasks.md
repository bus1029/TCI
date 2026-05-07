# Tasks: ZIP 업로드 스냅샷과 워크스페이스 삭제

**Input**: Design documents from `/specs/004-zip-upload-workspace-delete/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/local-upload-workspace-delete.openapi.yaml`, `quickstart.md`

**Tests**: Required by user request. Every user-story phase starts with contract, unit, or integration tests that can fail before implementation.

**Organization**: Tasks are grouped as shared setup, blocking common foundation, and independently testable user-value slices.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and does not depend on another incomplete task in the same phase.
- **[Story]**: Maps a task to a user story. Setup, foundational, and polish tasks intentionally have no story label.
- Every task includes an exact file path so it can be moved directly into a backlog or issue.

## Requirement Traceability

| Requirement / Criterion | Primary Task Coverage |
|-------------------------|-----------------------|
| FR-001, FR-002, FR-003, FR-006, FR-007, FR-007a, SC-002, SC-003, SC-010 | T018-T035 |
| FR-004 | T010, T012, T020, T025, T028, T031, T034 |
| FR-005 | T018, T022, T023, T029, T034, T035 |
| FR-008, FR-009, FR-010, SC-004, SC-005 | T053-T063, T067, T069 |
| FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019, SC-006, SC-007, SC-008, SC-009 | T036-T052, T068 |
| SC-001 | T005, T066, T070 |
| Cross-cutting evidence and final validation | T064-T070 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare test scaffolding, configuration entry points, and documentation evidence files used by later implementation tasks.

- [x] T001 Create Local Upload test package markers in `pilot-git-repo-connection/tests/unit/local_uploads/__init__.py`, `pilot-git-repo-connection/tests/contract/local_uploads/__init__.py`, and `pilot-git-repo-connection/tests/integration/local_uploads/__init__.py`
- [x] T002 Create workspace lifecycle test package markers in `pilot-git-repo-connection/tests/contract/workspaces/__init__.py` and `pilot-git-repo-connection/tests/integration/workspaces/__init__.py`
- [x] T003 [P] Add reusable ZIP fixture builders and unsafe archive helpers in `pilot-git-repo-connection/tests/support/local_upload_testkit.py`
- [x] T004 [P] Add Local Upload ZIP limit settings with defaults in `pilot-git-repo-connection/src/tci/settings.py`
- [x] T005 [P] Add delivery evidence tracking scaffold for SC-001 through SC-010 in `specs/004-zip-upload-workspace-delete/delivery-evidence.md`

---

## Phase 2: Foundational (Blocking Common Work)

**Purpose**: Core persistence, lifecycle, and source-aware snapshot infrastructure that must be complete before Local Upload, workspace deletion, or compatibility work starts.

**Critical**: No user story implementation should begin until this phase is complete.

- [x] T006 [P] Add failing model tests for `Workspace`, `LocalUpload`, `WorkspaceDeletionRecord`, and source-aware `CodeSnapshot` constraints in `pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_lifecycle_models.py`
- [x] T007 [P] Add failing repository tests for source-aware snapshot create, lookup, and latest Local Upload selection in `pilot-git-repo-connection/tests/unit/local_uploads/test_source_aware_snapshot_repository.py`
- [x] T008 [P] Add failing workspace guard tests for active, deleting, and deleted states in `pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_lifecycle_guard.py`
- [x] T009 Add Alembic migration for `workspaces`, `local_uploads`, `workspace_deletion_records`, and source-aware `code_snapshots` fields in `pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py`
- [x] T010 Update SQLAlchemy models for workspace lifecycle, Local Upload metadata, deletion audit records, and source-aware snapshots in `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
- [x] T011 Implement workspace persistence methods for create, get, status transition, active list, and deletion audit lookup in `pilot-git-repo-connection/src/tci/infrastructure/persistence/workspace_repository.py`
- [x] T012 Implement Local Upload persistence methods for create, mark processing, mark succeeded, mark failed, and latest snapshot linkage in `pilot-git-repo-connection/src/tci/infrastructure/persistence/local_upload_repository.py`
- [x] T013 Extend snapshot persistence for Local Upload drafts, source owner validation, workspace snapshot listing, and latest Local Upload lookup in `pilot-git-repo-connection/src/tci/infrastructure/persistence/code_snapshot_repository.py`
- [x] T014 Add shared workspace lifecycle guard and problem codes for non-active workspaces in `pilot-git-repo-connection/src/tci/domain/services/workspace_lifecycle.py`
- [x] T015 Wire workspace, Local Upload, and source-aware snapshot repositories into application dependencies in `pilot-git-repo-connection/src/tci/app.py`
- [x] T016 Update testkit fakes for workspaces, Local Uploads, deletion records, and source-aware snapshots in `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- [x] T017 Run foundational database and unit checks with `rtk pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/local_uploads/test_source_aware_snapshot_repository.py tests/unit/local_uploads/test_workspace_lifecycle_guard.py` from `pilot-git-repo-connection/`

**Checkpoint**: Workspace lifecycle, source-aware snapshots, and shared guards are ready for user-story implementation.

---

## Phase 3: User Story 1 - ZIP 파일로 프로젝트 스냅샷 생성 (Priority: P1) MVP

**Goal**: A workspace manager can upload a local project ZIP and receive a source-aware Local Upload snapshot that preserves the extracted folder/file structure.

**Independent Test**: Upload a valid ZIP in a new active workspace, then verify the snapshot list/detail shows `Local Upload`, the extracted tree matches the ZIP structure, and no GitHub/GitLab connection is required.

### Tests for User Story 1

- [x] T018 [P] [US1] Add ZIP validation unit tests for corrupt archives, traversal paths, absolute paths, encrypted entries, duplicate logical paths, reserved `manifest.json`, zero-file archives, and size/count limits in `pilot-git-repo-connection/tests/unit/local_uploads/test_local_zip_extractor.py`
- [x] T019 [P] [US1] Add Local Upload snapshot service unit tests for success, repeated uploads, latest snapshot default, failure cleanup, and no active snapshot on failure in `pilot-git-repo-connection/tests/unit/local_uploads/test_create_local_upload_snapshot.py`
- [x] T020 [P] [US1] Add contract tests for `POST /api/local-uploads`, `GET /api/local-uploads/{uploadId}`, and `GET /api/local-uploads/{uploadId}/snapshots/{snapshotId}`, including Local Upload source, uploaded-by, uploaded-at, sanitized filename, and limit-exceeded problem details in `pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py`
- [x] T021 [P] [US1] Add integration tests for valid root-folder ZIP, nested ZIP, hidden files, empty directory metadata, and three repeated uploads in `pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_snapshot_flow.py`
- [x] T022 [P] [US1] Add integration tests for corrupt ZIP, unsafe path ZIP, and limit-exceeded ZIP leaving no active snapshot and showing allowed limits plus retry guidance in `pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_failure_flow.py`

### Implementation for User Story 1

- [x] T023 [US1] Implement safe ZIP central-directory validation and entry normalization in `pilot-git-repo-connection/src/tci/infrastructure/snapshots/local_zip_extractor.py`
- [x] T024 [US1] Extend snapshot archive storage for Local Upload entry drafts and partial archive cleanup in `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`
- [x] T025 [US1] Extend snapshot manifest metadata with `source.kind`, Local Upload ID, sanitized original filename, upload hash, file count, and byte totals in `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`
- [x] T026 [US1] Implement Local Upload snapshot creation command with success/failure transitions and latest snapshot selection in `pilot-git-repo-connection/src/tci/domain/services/create_local_upload_snapshot.py`
- [x] T027 [US1] Add Local Upload ingestion task entry point and synchronous test/development fallback in `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- [x] T028 [US1] Add Local Upload API request and response schemas with source, uploaded-by, uploaded-at, sanitized original filename, file count, byte totals, latest snapshot, and failure problem fields in `pilot-git-repo-connection/src/tci/api/schemas/local_upload.py`
- [x] T029 [US1] Implement Local Upload API routes for upload, status, and snapshot detail in `pilot-git-repo-connection/src/tci/api/routes/local_uploads.py`
- [x] T030 [US1] Register Local Upload API routes in `pilot-git-repo-connection/src/tci/app.py`
- [x] T031 [US1] Extend snapshot detail service to return Local Upload source metadata, uploaded-by, uploaded-at, sanitized original filename, and nullable repository-only fields in `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
- [x] T032 [US1] Extend snapshot serializers for Local Upload source details in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [x] T033 [US1] Add operator UI route for Local Upload form, status, and latest snapshot redirect in `pilot-git-repo-connection/src/tci/web/routes/local_uploads.py`
- [x] T034 [US1] Add Local Upload operator templates for upload form, status panel, failure details with allowed limits and retry guidance, source label, uploaded-by, uploaded-at, and latest marker in `pilot-git-repo-connection/src/tci/web/templates/local_uploads/index.html`
- [x] T035 [US1] Run User Story 1 checks with `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/local_uploads/test_local_upload_failure_flow.py` from `pilot-git-repo-connection/`

**Checkpoint**: User Story 1 is independently functional and testable as the MVP.

---

## Phase 4: User Story 2 - 생성된 워크스페이스 삭제 (Priority: P2)

**Goal**: A workspace owner or admin can soft-delete a workspace, remove project content and snapshot files, preserve minimum audit metadata, and block further mutations.

**Independent Test**: Delete a workspace through the confirmation flow, then verify active lists exclude it, direct access shows deleted state, new operations are blocked, snapshot archive files are removed, and audit metadata remains.

### Tests for User Story 2

- [ ] T036 [P] [US2] Add contract tests for `GET /api/workspaces/{workspaceId}/deletion-impact` and `DELETE /api/workspaces/{workspaceId}` in `pilot-git-repo-connection/tests/contract/workspaces/test_workspace_delete_contract.py`
- [ ] T037 [P] [US2] Add unit tests for delete authorization, confirmation, idempotent deleted-state response, purge summary, and audit metadata minimization in `pilot-git-repo-connection/tests/unit/local_uploads/test_delete_workspace.py`
- [ ] T038 [P] [US2] Add integration tests for owner/admin deletion, non-owner rejection, active-list exclusion, direct deleted-state access with next-action guidance, and content purge in `pilot-git-repo-connection/tests/integration/workspaces/test_workspace_delete_flow.py`
- [ ] T039 [P] [US2] Add integration tests that deleted or deleting workspaces reject Local Upload, GitHub connection, GitLab connection, snapshot creation, and worker mutations in `pilot-git-repo-connection/tests/integration/workspaces/test_deleted_workspace_guards.py`

### Implementation for User Story 2

- [ ] T040 [US2] Add workspace deletion impact and deletion response schemas in `pilot-git-repo-connection/src/tci/api/schemas/workspace.py`
- [ ] T041 [US2] Implement deletion impact summary, owner/admin authorization, confirmation validation, soft delete, purge, and audit record creation in `pilot-git-repo-connection/src/tci/domain/services/delete_workspace.py`
- [ ] T042 [US2] Add archive purge operations for workspace-scoped snapshots in `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`
- [ ] T043 [US2] Implement workspace API routes for deletion impact and delete request handling in `pilot-git-repo-connection/src/tci/api/routes/workspaces.py`
- [ ] T044 [US2] Register workspace deletion API routes in `pilot-git-repo-connection/src/tci/app.py`
- [ ] T045 [US2] Apply active-workspace guard to repository connection create, verify, and detail mutation paths in `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
- [ ] T046 [US2] Apply active-workspace guard to repository snapshot creation and lookup mutation paths in `pilot-git-repo-connection/src/tci/api/routes/repository_snapshots.py`
- [ ] T047 [US2] Apply active-workspace guard to candidate/manual repository creation services in `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py` and `pilot-git-repo-connection/src/tci/domain/services/list_repository_candidates.py`
- [ ] T048 [US2] Apply active-workspace guard to repository snapshot and webhook-driven worker entry points in `pilot-git-repo-connection/src/tci/domain/services/create_initial_snapshot.py`, `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`, and `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- [ ] T049 [US2] Exclude deleted workspaces from active connection and snapshot list queries in `pilot-git-repo-connection/src/tci/domain/services/list_repository_connections.py`
- [ ] T050 [US2] Add operator UI route for workspace deletion impact, confirmation, and deleted-state page in `pilot-git-repo-connection/src/tci/web/routes/workspaces.py`
- [ ] T051 [US2] Add workspace deletion confirmation and deleted-state templates with available next actions in `pilot-git-repo-connection/src/tci/web/templates/workspaces/delete.html` and `pilot-git-repo-connection/src/tci/web/templates/workspaces/deleted.html`
- [ ] T052 [US2] Run User Story 2 checks with `rtk pytest -q tests/contract/workspaces/test_workspace_delete_contract.py tests/unit/local_uploads/test_delete_workspace.py tests/integration/workspaces/test_workspace_delete_flow.py tests/integration/workspaces/test_deleted_workspace_guards.py` from `pilot-git-repo-connection/`

**Checkpoint**: User Stories 1 and 2 both work independently, and deleted workspaces cannot start new work.

---

## Phase 5: User Story 3 - 기존 GitHub/GitLab 연결과 로컬 업로드 호환성 유지 (Priority: P3)

**Goal**: GitHub, GitLab, and Local Upload sources remain visually and behaviorally distinct, and existing GitHub/GitLab flows keep their previous semantics except for deleted-workspace guards.

**Independent Test**: In a mixed workspace with GitHub, GitLab, and Local Upload data, verify source labels are correct and existing GitHub/GitLab list, detail, event, webhook, and snapshot tests still pass.

### Tests for User Story 3

- [ ] T053 [P] [US3] Add mixed-source integration tests for GitHub, GitLab, and Local Upload list/detail/source labels in `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py`
- [ ] T054 [P] [US3] Add operator source-identification regression tests for mixed GitHub, GitLab, and Local Upload screens in `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_local_upload_source_identification.py`
- [ ] T055 [P] [US3] Extend repository connection contract regression coverage for unchanged GitHub/GitLab response fields and deleted-workspace problem details in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- [ ] T056 [P] [US3] Extend existing GitHub/GitLab compatibility regression to include Local Upload coexistence without provider behavior changes in `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`

### Implementation for User Story 3

- [ ] T057 [US3] Update repository connection serializers to keep provider fields unchanged while exposing source-aware snapshot labels in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [ ] T058 [US3] Update repository connection API routes so GitHub/GitLab routes reject deleted workspaces but never treat Local Upload as a provider in `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
- [ ] T059 [US3] Update GitHub and GitLab webhook routes to guard deleted workspaces without accepting Local Upload IDs in `pilot-git-repo-connection/src/tci/api/routes/github_webhooks.py` and `pilot-git-repo-connection/src/tci/api/routes/gitlab_webhooks.py`
- [ ] T060 [US3] Update candidate discovery to remain provider-scoped and independent of Local Upload history in `pilot-git-repo-connection/src/tci/api/routes/repository_candidates.py`
- [ ] T061 [US3] Update operator connection list/detail templates to display GitHub, GitLab, and Local Upload sources without mixing connection state with upload snapshots in `pilot-git-repo-connection/src/tci/web/templates/connections/index.html` and `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
- [ ] T062 [US3] Update operator connection routes to provide mixed-source view models without changing existing GitHub/GitLab route semantics in `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py` and `pilot-git-repo-connection/src/tci/web/routes/repository_connection_detail.py`
- [ ] T063 [US3] Run User Story 3 checks with `rtk pytest -q tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py tests/integration/repository_connections/test_operator_local_upload_source_identification.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py` from `pilot-git-repo-connection/`

**Checkpoint**: All user stories are independently functional, and existing GitHub/GitLab behavior remains compatible.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final documentation, security, evidence, and regression checks across all stories.

- [ ] T064 [P] Update quickstart verification steps for Local Upload, workspace deletion, and mixed-provider regression in `specs/004-zip-upload-workspace-delete/quickstart.md`
- [ ] T065 [P] Update operator rehearsal and redacted validation evidence for SC-001 through SC-010 in `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- [ ] T066 Execute SC-001 operator rehearsal for three operators uploading ZIP without GitHub/GitLab and record redacted timing evidence in `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- [ ] T067 Execute SC-005 mixed-source identification exercise with 30 GitHub, GitLab, and Local Upload source-identification tasks and record redacted results in `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- [ ] T068 Run security-focused ZIP and deletion tests with `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/integration/local_uploads/test_local_upload_failure_flow.py tests/integration/workspaces/test_workspace_delete_flow.py` from `pilot-git-repo-connection/`
- [ ] T069 Run full repository connection and Local Upload regression with `rtk pytest -q tests/unit tests/contract tests/integration` from `pilot-git-repo-connection/`
- [ ] T070 Review final diff for secret redaction, provider compatibility, deleted-workspace guards, and scoped documentation updates in `specs/004-zip-upload-workspace-delete/delivery-evidence.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2. This is the MVP.
- **Phase 4 US2**: Depends on Phase 2. It can start in parallel with US1 after the shared foundation, but final purge verification benefits from US1 snapshot archives.
- **Phase 5 US3**: Depends on Phase 2 and is most useful after at least one Local Upload path from US1 exists.
- **Phase 6 Polish**: Depends on the desired user stories being implemented.

### User Story Dependencies

- **US1 (P1)**: Requires only Phase 2. Delivers Local Upload snapshots without GitHub/GitLab.
- **US2 (P2)**: Requires Phase 2. Can be tested with synthetic existing workspace content, but should be rerun after US1 for Local Upload purge coverage.
- **US3 (P3)**: Requires Phase 2 and mixed-source fixtures. Should run after US1 when validating Local Upload coexistence with GitHub/GitLab.

### Within Each Story

- Tests are written first and should fail before implementation.
- Persistence and model tasks precede services.
- Services precede API routes.
- API routes precede operator UI routes and templates.
- Each story checkpoint should pass before starting the next priority story in a sequential workflow.

---

## Parallel Opportunities

- **Setup**: T003, T004, and T005 can run in parallel.
- **Foundational tests**: T006, T007, and T008 can run in parallel.
- **US1 tests**: T018 through T022 can run in parallel.
- **US2 tests**: T036 through T039 can run in parallel.
- **US3 tests**: T053 through T056 can run in parallel.
- **Cross-story work**: After Phase 2, US1 and US2 can be assigned separately if teams coordinate around shared files `pilot-git-repo-connection/src/tci/app.py` and `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`.

### Parallel Example: User Story 1

```bash
Task: "T018 [P] [US1] Add ZIP validation unit tests in pilot-git-repo-connection/tests/unit/local_uploads/test_local_zip_extractor.py"
Task: "T020 [P] [US1] Add contract tests in pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py"
Task: "T021 [P] [US1] Add successful upload integration tests in pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_snapshot_flow.py"
Task: "T022 [P] [US1] Add failed upload integration tests in pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_failure_flow.py"
```

### Parallel Example: User Story 2

```bash
Task: "T036 [P] [US2] Add workspace deletion contract tests in pilot-git-repo-connection/tests/contract/workspaces/test_workspace_delete_contract.py"
Task: "T037 [P] [US2] Add deletion service unit tests in pilot-git-repo-connection/tests/unit/local_uploads/test_delete_workspace.py"
Task: "T038 [P] [US2] Add deletion flow integration tests in pilot-git-repo-connection/tests/integration/workspaces/test_workspace_delete_flow.py"
Task: "T039 [P] [US2] Add deleted workspace guard integration tests in pilot-git-repo-connection/tests/integration/workspaces/test_deleted_workspace_guards.py"
```

### Parallel Example: User Story 3

```bash
Task: "T053 [P] [US3] Add mixed-source integration tests in pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py"
Task: "T054 [P] [US3] Add operator source identification tests in pilot-git-repo-connection/tests/integration/repository_connections/test_operator_local_upload_source_identification.py"
Task: "T055 [P] [US3] Extend repository connection contract regression in pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py"
Task: "T056 [P] [US3] Extend GitHub/GitLab compatibility regression in pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational schema, repositories, and guards.
3. Complete Phase 3 User Story 1.
4. Stop and validate Local Upload independently with T035.
5. Use MVP evidence to confirm SC-001, SC-002, SC-003, and SC-010 before extending deletion and compatibility work.

### Incremental Delivery

1. **Foundation**: T001 through T017 establish shared workspace/source infrastructure.
2. **MVP**: T018 through T035 deliver Local Upload snapshots.
3. **Lifecycle**: T036 through T052 deliver workspace deletion and content purge.
4. **Compatibility**: T053 through T063 preserve GitHub/GitLab behavior and mixed-source clarity.
5. **Release Readiness**: T064 through T070 update evidence and run final regression.

### Review Boundaries

- Review Phase 2 as the shared schema and lifecycle foundation.
- Review Phase 3 as the ZIP intake and Local Upload snapshot slice.
- Review Phase 4 as the deletion, purge, and mutation guard slice.
- Review Phase 5 as compatibility and operator-source clarity.
- Keep unrelated GitHub/GitLab behavior changes out of Phase 3 and Phase 4 unless they are deleted-workspace guards explicitly listed above.
