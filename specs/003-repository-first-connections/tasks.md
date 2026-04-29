# Tasks: 워크스페이스 기반 저장소 연결 시작점 전환

**Input**: Design documents from `/specs/003-repository-first-connections/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`  
**Tests**: Required by user request. Test tasks are listed before implementation tasks in each phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks in the same phase when file paths do not overlap
- **[Story]**: User story label for user-value phases only
- Every task includes a concrete file path and is sized for reviewable implementation

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create feature-specific scaffolding used by tests, evidence, and later issue/backlog conversion.

- [ ] T001 Create delivery evidence scaffold for repository-first connection verification in `specs/003-repository-first-connections/delivery-evidence.md`
- [ ] T002 [P] Add repository-first test helper skeleton for workspace/new-vs-legacy fixtures in `pilot-git-repo-connection/tests/support/repository_first_connection_testkit.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared DB/model/API traceability groundwork that MUST be complete before any user story implementation.

**Critical**: No user story work should begin until this phase passes. These tasks remove the old hard dependency on planning trace without changing provider semantics.

### Tests for Foundational Work

- [ ] T003 [P] Add Alembic migration regression tests for nullable planning references and preserved legacy rows in `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_migration.py`
- [ ] T004 [P] Add model/unit tests for connection origin classification in `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_origin.py`
- [ ] T005 [P] Add serializer unit tests for nullable `planningInputReference` and `origin` blocks in `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_serialization.py`
- [ ] T006 [P] Add snapshot traceability unit tests for connections with and without legacy planning references in `pilot-git-repo-connection/tests/unit/repository_connections/test_snapshot_traceability.py`

### Implementation for Foundational Work

- [ ] T007 Add Alembic migration making `repository_connections.planning_input_reference_id` nullable and preserving existing values in `pilot-git-repo-connection/alembic/versions/003_repository_first_connections.py`
- [ ] T008 Update SQLAlchemy models for nullable planning reference and connection origin support in `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
- [ ] T009 Update repository connection draft/create persistence to allow null planning reference and enforce workspace/provider/repository duplicate keys in `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- [ ] T010 Update connection detail/list persistence loading to tolerate missing planning reference in `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- [ ] T011 Update traceability builder to return optional legacy planning provenance in `pilot-git-repo-connection/src/tci/domain/services/build_traceability_reference.py`
- [ ] T012 Update repository connection schemas and serializers for nullable traceability and `origin` in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [ ] T013 Update shared connection test helpers for workspace-first and legacy-planning fixture creation in `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- [ ] T014 Record foundational migration/model/serializer verification commands in `specs/003-repository-first-connections/delivery-evidence.md`

**Checkpoint**: Foundation ready. New connections can be represented without planning trace, and legacy connections can still be loaded.

---

## Phase 3: User Story 1 - 워크스페이스에서 저장소 연결 시작 (Priority: P1)

**Goal**: A workspace owner can create GitHub or GitLab repository connections without selecting or storing planning/spec/plan trace.

**Independent Test**: Create a new workspace connection for GitHub and GitLab without `planningInputReferenceId`, verify active/detail/snapshot behavior, reject obsolete planning reference fields, and confirm `traceability.planningInputReference = null`.

### Tests for User Story 1

- [ ] T015 [P] [US1] Add contract tests for `POST /api/repository-connections` succeeding without `planningInputReferenceId` in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- [ ] T016 [P] [US1] Add contract tests proving `POST /api/repository-connections` rejects obsolete `planningInputReferenceId` and creates no connection in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- [ ] T017 [P] [US1] Add GitHub workspace-first create/detail/snapshot integration test in `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_connection_flow.py`
- [ ] T018 [P] [US1] Add GitLab workspace-first create/detail/snapshot integration test in `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_connection_flow.py`
- [ ] T019 [P] [US1] Add operator UI integration test for create form without planning input selection in `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`

### Implementation for User Story 1

- [ ] T020 [US1] Remove `planningInputReferenceId` from create request validation and reject obsolete planning reference fields in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [ ] T021 [US1] Update create route to build connection command from workspace header and repository fields only in `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
- [ ] T022 [US1] Update create command/service to skip planning reference lookup and store null planning reference for new rows in `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
- [ ] T023 [US1] Ensure manual URL create path still uses existing GitHub/GitLab parser, allowlist, shared read-only credential validator, and mirror sync in `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
- [ ] T024 [US1] Update snapshot creation/detail flow to work when connection planning reference is null in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [ ] T025 [US1] Update operator create route to remove planning input selection requirement in `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
- [ ] T026 [US1] Update operator connection create template to show workspace repository connection fields without planning input controls in `pilot-git-repo-connection/src/tci/web/templates/connections/create.html`
- [ ] T027 [US1] Record US1 GitHub/GitLab workspace-first and obsolete-field rejection validation evidence in `specs/003-repository-first-connections/delivery-evidence.md`

**Checkpoint**: User Story 1 is independently functional as MVP.

---

## Phase 4: User Story 2 - 기존 GitHub/GitLab 연결 호환성 유지 (Priority: P2)

**Goal**: Existing GitHub Cloud and GitLab Self-Managed connections with planning trace remain visible, operational, correctly workspace-scoped, and clearly marked as legacy provenance.

**Independent Test**: Seed existing planning-based GitHub and GitLab connections, then verify list/detail/snapshot/event/webhook flows still work, preserve legacy planning trace, and use the existing `workspace_id` as canonical workspace assignment.

### Tests for User Story 2

- [ ] T028 [P] [US2] Add contract test proving legacy connection detail still returns non-null planning reference in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- [ ] T029 [P] [US2] Add GitHub legacy planning connection visibility/regression test in `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- [ ] T030 [P] [US2] Add GitLab legacy planning connection visibility/regression test in `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- [ ] T031 [P] [US2] Add compatibility-state test for unclear legacy workspace assignment in `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_legacy_compatibility.py`
- [ ] T032 [P] [US2] Add regression test proving legacy rows keep existing `workspace_id` as canonical list/detail scope in `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_legacy_compatibility.py`
- [ ] T033 [P] [US2] Add GitHub/GitLab webhook no-regression tests after nullable planning change in `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`

### Implementation for User Story 2

- [ ] T034 [US2] Update connection detail service to compute `legacy_planning` and `legacy_unassigned` origin states in `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
- [ ] T035 [US2] Update connection listing service to include origin information and use existing `workspace_id` without dropping legacy rows in `pilot-git-repo-connection/src/tci/domain/services/list_repository_connections.py`
- [ ] T036 [US2] Update detail serializer to preserve legacy planning trace when present in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [ ] T037 [US2] Update snapshot detail serializer to preserve legacy planning trace when present in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [ ] T038 [US2] Update operator connection list template to distinguish workspace repository and legacy planning origins in `pilot-git-repo-connection/src/tci/web/templates/connections/list.html`
- [ ] T039 [US2] Update operator connection detail template to show legacy planning trace and compatibility state in `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
- [ ] T040 [US2] Update legacy fixture helper to seed GitHub/GitLab planning references and canonical `workspace_id` explicitly in `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- [ ] T041 [US2] Record US2 GitHub/GitLab compatibility and canonical workspace evidence in `specs/003-repository-first-connections/delivery-evidence.md`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - 워크스페이스 기준 연결 관리와 판단 지원 (Priority: P3)

**Goal**: Workspace managers can see configured provider candidates, use manual URL fallback, distinguish providers, avoid duplicate connections, and understand permission failures without mixing GitHub/GitLab operational history.

**Independent Test**: In a mixed GitHub/GitLab workspace, verify candidate empty states, configured-scope candidates, manual URL fallback, provider identity display, duplicate prevention across candidate/manual paths, credential boundary enforcement, and provider-separated list/detail/event/snapshot/history views.

### Tests for User Story 3

- [ ] T042 [P] [US3] Add contract tests for `GET /api/repository-candidates` scoped candidates and empty manual-url state in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_candidate_contract.py`
- [ ] T043 [P] [US3] Add unit tests for candidate service provider scope and access states in `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_candidates.py`
- [ ] T044 [P] [US3] Add unit tests for canonical duplicate key calculation across candidate and manual URL paths in `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_identity.py`
- [ ] T045 [P] [US3] Add operator integration test for candidate list, empty state, and manual URL fallback in `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
- [ ] T046 [P] [US3] Add integration test for duplicate prevention across candidate-selected and manual URL connections in `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_connection_flow.py`
- [ ] T047 [P] [US3] Add unit tests proving personal provider candidate grants are not persisted as operation credentials in `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_credentials.py`
- [ ] T048 [P] [US3] Add contract and integration tests for missing, expired, revoked, or invalid shared read-only credential create failures in `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_permission_failures.py`
- [ ] T049 [P] [US3] Add mixed-provider workspace integration test proving GitHub/GitLab status, event, snapshot, and history projections stay separated in `pilot-git-repo-connection/tests/integration/repository_connections/test_mixed_provider_workspace.py`

### Implementation for User Story 3

- [ ] T050 [P] [US3] Add repository candidate schema models in `pilot-git-repo-connection/src/tci/api/schemas/repository_candidate.py`
- [ ] T051 [P] [US3] Add candidate listing domain service with configured provider account/instance empty-state behavior in `pilot-git-repo-connection/src/tci/domain/services/list_repository_candidates.py`
- [ ] T052 [US3] Add repository candidates API route in `pilot-git-repo-connection/src/tci/api/routes/repository_candidates.py`
- [ ] T053 [US3] Register repository candidates route in FastAPI app in `pilot-git-repo-connection/src/tci/app.py`
- [ ] T054 [US3] Add canonical repository identity helper for provider+normalized repository comparison in `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
- [ ] T055 [US3] Apply canonical duplicate prevention in connection create persistence in `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- [ ] T056 [US3] Enforce candidate discovery grant versus workspace shared read-only operation credential boundary in `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
- [ ] T057 [US3] Map repository authorization, expired grant, revoked access, and shared credential validation failures to remediation problem responses in `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
- [ ] T058 [US3] Update operator create route to load candidate lists, manual URL guidance, and credential failure states in `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
- [ ] T059 [US3] Update operator create template to render provider candidates, empty state, provider identity, manual URL fallback, and credential remediation guidance in `pilot-git-repo-connection/src/tci/web/templates/connections/create.html`
- [ ] T060 [US3] Record US3 candidate/manual/duplicate/credential/mixed-provider evidence in `specs/003-repository-first-connections/delivery-evidence.md`

**Checkpoint**: All user stories are independently functional.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Validate full spec coverage, update contracts, and capture final evidence.

- [ ] T061 [P] Update implementation contract snapshot with final request/response examples including obsolete field rejection and permission problem responses in `specs/003-repository-first-connections/contracts/repository-first-connections.openapi.yaml`
- [ ] T062 [P] Update quickstart with actual command outputs and any finalized test names in `specs/003-repository-first-connections/quickstart.md`
- [ ] T063 Run repository-first focused contract and integration checks and record results in `specs/003-repository-first-connections/delivery-evidence.md`
- [ ] T064 Run existing GitHub/GitLab regression suite and record results in `specs/003-repository-first-connections/delivery-evidence.md`
- [ ] T065 Map completed evidence back to FR-001 through FR-016, FR-002a, FR-012a, FR-012b, FR-014a, FR-014b, and SC-001 through SC-007 in `specs/003-repository-first-connections/delivery-evidence.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1; blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2; MVP scope.
- **Phase 4 US2**: Depends on Phase 2; can run in parallel with US1 after shared serializers/services stabilize, but should be validated after US1 create path exists.
- **Phase 5 US3**: Depends on Phase 2; can run in parallel with US1/US2 except duplicate-prevention persistence task T055 and credential-boundary task T056 depend on foundational repository/create service changes.
- **Final Phase**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Requires foundational nullable provenance model. No dependency on US2 or US3.
- **US2 (P2)**: Requires foundational nullable provenance model. Verifies existing provider behavior survives US1-compatible changes.
- **US3 (P3)**: Requires foundational identity/dedupe model. Adds candidate discovery, duplicate prevention UX, credential boundary, and mixed-provider separation.

### Blocking Common Work

The following tasks are common prerequisites and must be treated as highest-priority development work: T003-T014. They define nullable planning provenance, origin read model, shared serializer behavior, and test fixture support.

---

## Parallel Opportunities

- **Setup**: T001 and T002 can run in parallel.
- **Foundational tests**: T003, T004, T005, and T006 can run in parallel.
- **US1 tests**: T015, T016, T017, T018, and T019 can run in parallel.
- **US2 tests**: T028, T029, T030, T031, T032, and T033 can run in parallel.
- **US3 tests**: T042, T043, T044, T045, T046, T047, T048, and T049 can run in parallel.
- **US3 implementation**: T050 and T051 can run in parallel before route registration.
- **Final docs**: T061 and T062 can run in parallel.

## Parallel Example: User Story 1

```text
Task: T015 Contract test for create without planningInputReferenceId
Task: T016 Contract test for obsolete planningInputReferenceId rejection
Task: T017 GitHub workspace-first integration test
Task: T018 GitLab workspace-first integration test
Task: T019 Operator UI create-form integration test
```

## Parallel Example: User Story 2

```text
Task: T028 Legacy detail contract test
Task: T029 GitHub legacy visibility regression
Task: T030 GitLab legacy visibility regression
Task: T031 Legacy unassigned compatibility-state test
Task: T032 Canonical workspace_id regression
Task: T033 Webhook no-regression test
```

## Parallel Example: User Story 3

```text
Task: T042 Repository candidates contract test
Task: T043 Candidate service unit test
Task: T044 Canonical duplicate key unit test
Task: T045 Operator candidate UI integration test
Task: T046 Candidate/manual duplicate prevention integration test
Task: T047 Credential boundary unit test
Task: T048 Permission failure integration test
Task: T049 Mixed-provider separation integration test
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational nullable provenance model.
3. Complete Phase 3 US1.
4. Stop and validate workspace-first GitHub/GitLab create/detail/snapshot without planning trace and obsolete planning field rejection.

### Incremental Delivery

1. Foundation: nullable legacy planning relation, origin read model, serializer/test helpers.
2. US1: repository-first create path and obsolete planning field rejection.
3. US2: legacy GitHub/GitLab compatibility and canonical workspace preservation.
4. US3: candidate list, manual URL fallback, duplicate prevention, credential boundary, permission failure handling, mixed-provider separation.
5. Final: evidence and full regression.

### Review Guidance

- Keep DB/model migration reviews separate from API/UX reviews.
- Do not change GitHub/GitLab webhook semantics in story tasks.
- Snapshot and webhook tasks are compatibility checks only; do not redesign collection, snapshot trigger, or webhook meaning.
- Every task touching provider behavior must include a regression test or evidence entry.
- Stop at each checkpoint and verify the independent test criteria before continuing.
