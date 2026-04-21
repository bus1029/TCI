# Tasks: 코드 저장소 연동

**Input**: Design documents from `/specs/001-git-repo-connection/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/repository-ingestion.openapi.yaml, quickstart.md

**Tests**: 이 기능은 spec의 `User Scenarios & Testing`과 사용자 요청을 반영해 모든 사용자 스토리에 대해 contract/integration/unit 테스트 작업을 포함한다. `SC-001`은 MVP인 US1 검증 시점에서 수동/통합 검증 근거를 먼저 남기고, 이후 전체 회귀로 반복 확인한다. 추가로 `SC-002`와 `SC-005`를 위해 상태 반영 지연과 secret rotation grace continuity를 검증하는 회귀 작업을 포함한다.

**Organization**: 작업은 `공통 기반 작업`과 `사용자 가치 기준 작업`으로 구분한다. 공통 기반 작업은 모든 후속 작업의 선행 조건이며, 사용자 가치 작업은 US1~US3 단위로 독립 구현과 독립 검증이 가능하도록 정리한다.

**Pilot Control**: Creating `tasks.md` does NOT authorize automatic execution of the implement phase. During the initial pilot, implementation begins only after explicit human approval.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 선행 작업이 끝난 뒤 다른 파일 세트에서 병렬로 진행 가능
- **[Story]**: 사용자 스토리 소속 작업만 `[US1]`, `[US2]`, `[US3]`를 붙인다
- 모든 작업은 backlog/issue로 바로 옮길 수 있도록 정확한 파일 경로를 포함한다
- 이 문서에서 `src/`, `tests/`, `pyproject.toml`, `.env.example` 같은 구현 경로는 `pilot-git-repo-connection/` 실행 루트를 기준으로 해석한다

## Phase 1: Setup (공통 기반 작업)

**Purpose**: Python 애플리케이션 골격과 공통 검증 산출물을 만든다.

- [x] T001 Create Python package and template skeleton for FR-014 traceability and FR-012a event timeline surfaces in `pilot-git-repo-connection/src/tci/__init__.py`, `pilot-git-repo-connection/src/tci/api/__init__.py`, `pilot-git-repo-connection/src/tci/web/__init__.py`, and `pilot-git-repo-connection/src/tci/web/templates/connections/.gitkeep`
- [x] T002 Create repository ingestion test scaffolding for FR-014 traceability and US1-US3 validation suites in `pilot-git-repo-connection/tests/contract/repository_ingestion/.gitkeep`, `pilot-git-repo-connection/tests/integration/repository_connections/.gitkeep`, and `pilot-git-repo-connection/tests/unit/repository_connections/.gitkeep`
- [x] T003 [P] Configure Python project settings, dependencies, and runtime paths for FR-005a and FR-014 in `pilot-git-repo-connection/pyproject.toml`, `pilot-git-repo-connection/.env.example`, and `pilot-git-repo-connection/src/tci/settings.py`
- [x] T004 [P] Create feature verification evidence scaffold for FR-014 and SC-001 through SC-005 in `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

---

## Phase 2: Foundational (공통 기반 작업)

**Purpose**: 모든 사용자 스토리가 공유하는 핵심 인프라를 먼저 고정한다.

**⚠️ CRITICAL**: 이 단계가 완료되기 전에는 어떤 사용자 스토리도 시작하지 않는다.

- [x] T005 Model core repository ingestion entities and enums for FR-001b, FR-002a, FR-003b, FR-005a, and FR-014 in `src/tci/infrastructure/persistence/models.py`
- [x] T006 Create the core repository ingestion and provenance Alembic migration for FR-001b, FR-002a, FR-003b, FR-005a, and FR-014 in `alembic/versions/001_repository_ingestion_core.py`
- [x] T007 [P] Implement repository ingestion problem and failure code mapping for FR-002, FR-013, and FR-017 in `src/tci/api/problem_details.py`
- [x] T008 [P] Implement Celery app, queue definitions, and worker registration for FR-008, FR-009, FR-011, and SC-002 in `src/tci/workers/celery_app.py` and `src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- [x] T009 [P] Implement bare mirror management for FR-002, FR-005a, and FR-014 in `src/tci/infrastructure/git/git_mirror_manager.py`
- [x] T010 [P] Implement ref resolution and read-only credential probing for FR-001c, FR-002, FR-002a, FR-003, and FR-003b in `src/tci/infrastructure/git/git_ref_resolver.py` and `src/tci/infrastructure/git/git_readonly_validator.py`
- [x] T011 [P] Implement snapshot archive and manifest storage primitives for FR-005, FR-005a, and FR-014 in `src/tci/infrastructure/snapshots/snapshot_archive_store.py` and `src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`
- [x] T012 [P] Implement planning input reference persistence adapter and provenance helpers for FR-014 in `src/tci/infrastructure/persistence/planning_input_reference_repository.py` and `src/tci/domain/services/build_traceability_reference.py`
- [x] T013 [P] Add foundational unit tests for FR-001c, FR-005a, and FR-014 across mirror, ref resolution, credential probing, archive storage, and provenance helpers in `tests/unit/repository_connections/test_git_foundation.py`
- [x] T014 Implement FastAPI application composition root and dependency wiring for shared FR-012, FR-012a, and FR-014 dependencies in `src/tci/app.py`

**Checkpoint**: 공통 플랫폼이 준비되어 각 사용자 스토리를 독립적으로 시작할 수 있다.

---

## Phase 3: User Story 1 - 저장소 연결과 초기 스냅샷 생성 (Priority: P1) 🎯 MVP

**Goal**: 수집 담당자가 GitHub Cloud 저장소를 읽기 전용으로 연결하고, 기본 ref를 검증한 뒤 첫 완전 스냅샷을 생성하고 상태와 추적 정보를 확인할 수 있게 한다.

**Independent Test**: 유효한 GitHub Cloud 저장소 URL과 읽기 전용 credential을 등록하고 기본 ref를 선택한 뒤, 초기 스냅샷 생성 완료와 파일 목록/상태/traceability block이 조회되며 connection detail에서 최신 성공/실패 시각과 최신 snapshot 정보가 보이고, 추가 브랜치 상시 분석 시 `새 연결 생성` 또는 `기본 ref 교체` 선택지가 명확히 보이며, 비지원 provider 입력은 v1 지원 범위 안내와 함께 거부되면 된다.

### Tests for User Story 1

- [x] T015 [P] [US1] Add contract tests for repository connection create/get/patch/verify endpoints, unsupported-provider rejection for FR-001a, nullable `lastProcessedEvent` placeholder in connection detail, traceability blocks, and additional-ref guidance responses in `tests/contract/repository_ingestion/test_repository_connection_contract.py`
- [x] T016 [P] [US1] Add integration tests for GitHub Cloud-only validation, read-only credential validation, `reauth_required` and `ref_missing` recovery, default ref change preservation, latest success/failure summary projection, additional-ref guidance, and initial snapshot traceability in `tests/integration/repository_connections/test_connection_and_initial_snapshot.py`

### Implementation for User Story 1

- [x] T017 [P] [US1] Implement repository connection persistence adapter in `src/tci/infrastructure/persistence/repository_connection_repository.py`
- [x] T018 [P] [US1] Implement credential revision persistence adapter in `src/tci/infrastructure/persistence/credential_revision_repository.py`
- [x] T019 [P] [US1] Implement sync run persistence adapter in `src/tci/infrastructure/persistence/repository_sync_run_repository.py`
- [x] T020 [P] [US1] Implement code snapshot persistence adapter in `src/tci/infrastructure/persistence/code_snapshot_repository.py`
- [x] T021 [P] [US1] Implement repository connection request and response schemas with GitHub Cloud-only validation errors, latest success/failure summary, nullable `lastProcessedEvent`, traceability, and additional-ref guidance fields in `src/tci/api/schemas/repository_connection.py`
- [x] T022 [US1] Implement connection creation and verification services with GitHub Cloud-only validation, planning input reference binding, and `reauth_required` transition handling in `src/tci/domain/services/create_repository_connection.py` and `src/tci/domain/services/verify_repository_connection.py`
- [x] T023 [US1] Implement default ref update and additional-ref guidance service that preserves prior snapshots and events and supports `ref_missing` recovery in `src/tci/domain/services/update_default_ref.py`
- [x] T024 [US1] Implement manual snapshot trigger service with `AUTH_FAILED` and `MIRROR_SYNC_FAILED` failure handling for FR-013 in `src/tci/domain/services/create_initial_snapshot.py`
- [x] T025 [US1] Implement default-ref snapshot builder that stamps sync and provenance references in `src/tci/domain/services/build_code_snapshot.py`
- [x] T026 [US1] Implement repository connection API routes in `src/tci/api/routes/repository_connections.py`
- [x] T027 [US1] Implement repository snapshot detail query service and API routes with traceability block in `src/tci/domain/services/get_code_snapshot_detail.py` and `src/tci/api/routes/repository_snapshots.py`
- [x] T028 [US1] Implement repository connection detail query service with MVP summary projections (`lastSuccessfulSnapshotAt`, `lastFailedSyncAt`, nullable `lastProcessedEvent`, `latestSnapshot`), planning-input, and additional-ref guidance projections in `src/tci/domain/services/get_repository_connection_detail.py`
- [x] T029 [P] [US1] Implement operator connection list/create route and template in `src/tci/web/routes/repository_connections.py` and `src/tci/web/templates/connections/index.html`
- [x] T030 [US1] Implement operator connection detail route and template with latest success/failure summary cards, nullable `lastProcessedEvent` placeholder, additional-ref guidance, and traceability panel in `src/tci/web/routes/repository_connection_detail.py` and `src/tci/web/templates/connections/detail.html`
- [x] T031 [US1] Capture User Story 1 verification evidence, including `SC-001` timed first-snapshot validation, unsupported-provider rejection proof, and trace links in `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

**Checkpoint**: User Story 1은 단독으로 구현 및 검증 가능해야 하며 MVP 후보가 된다.

---

## Phase 4: User Story 2 - 수집 범위 제어 (Priority: P2)

**Goal**: 수집 담당자가 포함/제외 경로와 파일 타입 규칙을 저장하고, 빈 수집 위험을 미리 확인하며, 이후 스냅샷이 동일 규칙으로 생성되고 어떤 규칙 버전이 적용됐는지 추적할 수 있게 한다.

**Independent Test**: 연결된 저장소에 범위 규칙을 저장하고 새 스냅샷을 생성했을 때 포함 파일 목록, 경고 상태, 제외 결과가 규칙과 정확히 일치하고 snapshot detail에서 적용된 scope rule version을 확인할 수 있으면 된다.

### Tests for User Story 2

- [x] T032 [P] [US2] Add contract tests for scope rule save, validation warning responses, and scope version projection in `tests/contract/repository_ingestion/test_repository_scope_contract.py`
- [x] T033 [P] [US2] Add unit tests for include/exclude/type/binary/size precedence and FR-006 v1 hard-exclude behavior in `tests/unit/repository_connections/test_scope_filter_engine.py`
- [x] T034 [P] [US2] Add integration tests for empty-result blocking, filtered snapshot manifests, and scope version traceability in `tests/integration/repository_connections/test_scoped_snapshot.py`

### Implementation for User Story 2

- [x] T035 [P] [US2] Implement scope rule persistence adapter in `src/tci/infrastructure/persistence/scope_rule_repository.py`
- [x] T036 [P] [US2] Implement scope warning evaluator in `src/tci/domain/services/evaluate_scope_rule_warning.py`
- [x] T037 [P] [US2] Implement FR-006 v1 default hard-exclude and text/binary/size guard policy in `src/tci/domain/services/default_scope_policy.py`
- [x] T038 [US2] Implement scope filter engine with manifest inclusion reasons in `src/tci/domain/services/scope_filter_engine.py`
- [x] T039 [US2] Integrate active scope rule resolution, scope version stamping, and `NO_INCLUDED_FILES` failure handling into `src/tci/domain/services/build_code_snapshot.py`
- [x] T040 [US2] Implement scope rule schemas and API routes in `src/tci/api/schemas/repository_scope.py` and `src/tci/api/routes/repository_scope.py`
- [x] T041 [US2] Implement operator scope configuration route and template with warning states in `src/tci/web/routes/repository_scope.py` and `src/tci/web/templates/connections/scope.html`
- [x] T042 [US2] Capture User Story 2 verification evidence and trace links in `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

**Checkpoint**: User Stories 1 and 2는 각각 독립 검증 가능해야 하며, scoped snapshot 결과가 재현 가능해야 한다.

---

## Phase 5: User Story 3 - 변경 이벤트 기반 최신화 (Priority: P3)

**Goal**: 시스템 운영자가 GitHub webhook으로 Push/PR 이벤트를 실시간 수신하고, Commit 기록과 Push/PR 기반 스냅샷 최신화를 안전하게 처리하며, secret 누락/불일치/grace rotation/기타 서명 실패를 구분해 상태와 추적 정보를 확인할 수 있게 한다.

**Independent Test**: 유효한 서명으로 Push와 PR 이벤트를 보내면 각각 올바른 이력 기록과 최신화가 수행되고, `secret_missing`, `secret_mismatch`, `signature_invalid`, grace window, 중복 delivery, 오래된 SHA는 각각 올바른 거부 또는 skip 상태로 기록되며 connection detail summary와 event timeline에서 rotation 상태와 traceability가 보이면 된다.

### Tests for User Story 3

- [x] T043 [P] [US3] Add contract tests for GitHub webhook intake, PR action gating for FR-010a, FR-012a event timeline responses, connection detail summary refresh, webhook health, rotation grace projection, and event traceability responses in `tests/contract/repository_ingestion/test_github_webhook_contract.py`
- [x] T044 [P] [US3] Add unit tests for webhook rejection classification, previous-grace secret acceptance, and stale-head decisions in `tests/unit/repository_connections/test_process_github_event.py`
- [x] T045 [P] [US3] Add integration tests for `secret_missing`, `secret_mismatch`, `signature_invalid`, secret grace rotation, delivery dedupe, stale head skip, ignored PR actions, and PR source snapshots in `tests/integration/repository_connections/test_github_webhook_refresh.py`

### Implementation for User Story 3

- [x] T046 [P] [US3] Extend SQLAlchemy models for `WebhookSecretRevision`, `RepositoryEvent`, `RepositoryEventCursor`, `lastProcessedEvent` summary linkage, `verifiedSecretRevisionStatus`, and webhook health projection fields in `src/tci/infrastructure/persistence/models.py`
- [x] T047 [US3] Create the webhook and repository event Alembic migration in `alembic/versions/002_repository_ingestion_webhooks.py`
- [x] T048 [P] [US3] Implement webhook secret persistence adapter in `src/tci/infrastructure/persistence/webhook_secret_repository.py`
- [x] T049 [P] [US3] Implement repository event and cursor persistence adapters in `src/tci/infrastructure/persistence/repository_event_repository.py` and `src/tci/infrastructure/persistence/repository_event_cursor_repository.py`
- [x] T050 [P] [US3] Implement GitHub signature verification with active and previous-grace secret support in `src/tci/infrastructure/webhooks/github_signature.py`
- [x] T051 [P] [US3] Implement GitHub event payload parser in `src/tci/infrastructure/webhooks/github_event_parser.py`
- [x] T052 [US3] Implement webhook secret rotation service and repository connection schema updates for FR-016a, FR-017a, and FR-017b in `src/tci/domain/services/rotate_webhook_secret.py`, `src/tci/domain/services/get_repository_connection_detail.py`, and `src/tci/api/schemas/repository_connection.py`
- [x] T053 [US3] Implement webhook intake API route with raw-body validation and rejection logging in `src/tci/api/routes/github_webhooks.py`
- [x] T054 [US3] Implement event processing service for commit recording, target selection, PR action gating, dedupe, stale-head handling, FR-012 summary refresh, verified secret revision status, and webhook health updates in `src/tci/domain/services/process_github_event.py`
- [x] T055 [US3] Implement post-commit webhook enqueue handoff in `src/tci/api/routes/github_webhooks.py`
- [x] T056 [US3] Implement webhook sync Celery task for default ref and PR source snapshots with `AUTH_FAILED` and `MIRROR_SYNC_FAILED` operator remediation for FR-013 in `src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- [x] T057 [US3] Implement repository event query service and repository connection detail refresh paths for FR-012, FR-012a, FR-016a, FR-017a, and FR-017b in `src/tci/domain/services/list_repository_events.py`, `src/tci/domain/services/get_repository_connection_detail.py`, `src/tci/api/routes/repository_events.py`, and `src/tci/api/schemas/repository_connection.py`
- [x] T058 [US3] Implement operator event timeline route plus connection detail UI refresh for FR-012a, FR-016a, FR-017a, and FR-017b in `src/tci/web/routes/repository_events.py`, `src/tci/web/templates/connections/events.html`, `src/tci/web/routes/repository_connection_detail.py`, and `src/tci/web/templates/connections/detail.html`
- [x] T059 [US3] Capture User Story 3 verification evidence and trace links in `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

**Checkpoint**: All user stories should now be independently functional and together satisfy the approved spec.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 다중 스토리에 걸친 운영 안정성, SLA 검증, 회귀 검증, 추적 문서를 마무리한다.

- [ ] T060 [P] Add regression tests for FR-002a `reauth_required`, FR-003b `ref_missing`, FR-015a additional-ref guidance fallback, FR-016a/SC-005 webhook secret grace-expiry rejection, and bad-replay/operator edge-state preservation in `tests/integration/repository_connections/test_edge_state_regression.py`
- [ ] T061 [P] Add webhook processing status latency validation for FR-008, FR-012, and `SC-002` in `tests/integration/repository_connections/test_webhook_status_latency.py`
- [ ] T062 [P] Add full quickstart validation harness for FR-001 through FR-017b that repeats `SC-001` first-snapshot-under-10-min validation alongside release-scope flow coverage in `tests/integration/repository_connections/test_quickstart_validation.py`
- [ ] T063 Refresh FR-001 through FR-017b and SC-001 through SC-005 trace coverage and story completion evidence in `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: No dependencies
- **Phase 2: Foundational**: Depends on Phase 1 and blocks all user stories
- **Phase 3: US1**: Depends on Phase 2
- **Phase 4: US2**: Depends on Phase 2 and reuses the snapshot pipeline from US1
- **Phase 5: US3**: Depends on Phase 2 and reuses the connection/snapshot/scope capabilities from US1 and US2
- **Phase 6: Polish**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: First deliverable slice and suggested MVP
- **US2 (P2)**: Depends on US1 because scope rules must affect real snapshot generation, scope-version projection, and result presentation
- **US3 (P3)**: Depends on US1 and US2 because webhook-triggered refresh must reuse connection lifecycle, snapshot generation, scope filtering, and traceability projections

### Within Each User Story

- Tests come before implementation work for that story
- Persistence/schema tasks come before services and routes
- Services come before routes, workers, and UI integration
- UI tasks start only after the related query/command APIs and response shapes are fixed
- Verification evidence must be updated before a story is considered complete

## Parallel Opportunities

- **Setup**: T003 and T004 can run in parallel after T001 and T002
- **Foundational**: T007, T008, T009, T010, T011, and T012 can run in parallel after T005 and T006; T013 can run while T014 is being wired
- **US1**: T015 and T016 can run in parallel; T017, T018, T019, T020, and T021 can run in parallel; T029 can start once T026, T027, and T028 response contracts are stable
- **US2**: T032, T033, and T034 can run in parallel; T035, T036, and T037 can run in parallel
- **US3**: T043, T044, and T045 can run in parallel; T048, T049, T050, and T051 can run in parallel after T046 and T047
- **Polish**: T060, T061, and T062 can run in parallel; T063 proceeds after verification results are collected

## Parallel Example: User Story 1

```bash
# Tests first
Task: "T015 [US1] contract tests in tests/contract/repository_ingestion/test_repository_connection_contract.py"
Task: "T016 [US1] integration tests in tests/integration/repository_connections/test_connection_and_initial_snapshot.py"

# Then independent implementation work
Task: "T017 [US1] repository connection persistence adapter in src/tci/infrastructure/persistence/repository_connection_repository.py"
Task: "T018 [US1] credential revision persistence adapter in src/tci/infrastructure/persistence/credential_revision_repository.py"
Task: "T021 [US1] request/response schemas in src/tci/api/schemas/repository_connection.py"
```

## Parallel Example: User Story 3

```bash
# Tests first
Task: "T043 [US3] contract tests in tests/contract/repository_ingestion/test_github_webhook_contract.py"
Task: "T044 [US3] unit tests in tests/unit/repository_connections/test_process_github_event.py"
Task: "T045 [US3] integration tests in tests/integration/repository_connections/test_github_webhook_refresh.py"

# Then independent implementation work after schema migration
Task: "T048 [US3] webhook secret persistence adapter in src/tci/infrastructure/persistence/webhook_secret_repository.py"
Task: "T049 [US3] repository event and cursor adapters in src/tci/infrastructure/persistence/"
Task: "T050 [US3] signature verification in src/tci/infrastructure/webhooks/github_signature.py"
Task: "T051 [US3] event payload parser in src/tci/infrastructure/webhooks/github_event_parser.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2 as the shared platform baseline
2. Complete Phase 3 (US1) only
3. Validate the independent test for US1
4. Stop for human review before taking on additional user value slices

### Incremental Delivery

1. **Common foundation**: Phase 1 + Phase 2
2. **First user value**: US1 for repository connection, initial snapshot, additional-ref guidance, and traceability baseline
3. **Second user value**: US2 for scope control, warnings, and scope-version projection
4. **Third user value**: US3 for webhook-driven refresh, secret rotation grace, and event observability
5. **Cross-cutting hardening**: Phase 6

### Backlog / Issue Transfer Guidance

- One task equals one backlog item by default
- T005, T006, T046, and T047 are the highest-priority platform items because later work depends on them
- If issue volume must be reduced, merge only adjacent tasks that touch the same file set and preserve the same independent test boundary

## Notes

- All tasks follow the required checklist format: checkbox, Task ID, optional `[P]`, optional `[US#]`, exact file path
- 공통 기반 작업이 최우선으로 먼저 오도록 정렬했다
- 모든 사용자 스토리에 테스트 작업과 verification evidence 작업을 포함했다
- `SC-001`은 T031의 MVP 검증 증거로 먼저 확인하고 T062의 전체 quickstart 회귀로 반복 검증한다
- `FR-002a`, `FR-003b`, `FR-006`, `FR-010a`, `FR-012`, `FR-012a`, `FR-013`, `FR-014`, `FR-015a`, `FR-016a`, `FR-017a`, `FR-017b`, `SC-002`, `SC-005`, `ref_missing`, `reauth_required`, webhook grace rotation이 각각 작업 단위로 직접 추적 가능하도록 보강했다
- Completing all tasks in this file is intended to satisfy the full approved scope in `spec.md`
