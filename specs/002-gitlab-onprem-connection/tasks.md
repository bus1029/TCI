# Tasks: 온프레미스 GitLab 코드 저장소 연동

**Input**: Design documents from `/specs/002-gitlab-onprem-connection/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/repository-ingestion.openapi.yaml, quickstart.md

**Tests**: 이 기능은 spec의 `User Scenarios & Testing`과 사용자 요청을 반영해 각 사용자 스토리마다 contract/integration/unit 테스트 작업을 포함한다. GitLab 신규 흐름뿐 아니라 기존 GitHub Cloud 회귀도 별도 테스트 작업으로 포함한다.

**Organization**: 작업은 `공통 기반 작업`과 `사용자 가치 기준 작업`으로 구분한다. 공통 기반 작업은 모든 후속 작업의 선행 조건이며, 사용자 가치 작업은 US1~US3 단위로 독립 구현과 독립 검증이 가능하도록 정리한다.

**Pilot Control**: Creating `tasks.md` does NOT authorize automatic execution of the implement phase. During the initial pilot, implementation begins only after explicit human approval.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 선행 작업이 끝난 뒤 다른 파일 세트에서 병렬로 진행 가능
- **[Story]**: 사용자 스토리 소속 작업만 `[US1]`, `[US2]`, `[US3]`를 붙인다
- 모든 작업은 backlog/issue로 바로 옮길 수 있도록 정확한 파일 경로를 포함한다
- 이 문서의 구현 경로는 모두 `pilot-git-repo-connection/` 실행 루트를 기준으로 해석한다

## Phase 1: Setup (공통 기반 작업)

**Purpose**: GitLab feature용 설계·검증 산출물과 테스트 골격을 준비한다.

- [ ] T001 Create feature delivery evidence scaffold for FR-001 through FR-023 and SC-001 through SC-005 in `specs/002-gitlab-onprem-connection/delivery-evidence.md`
- [ ] T002 [P] Add GitLab contract and integration test skeleton files in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_gitlab_connection_contract.py`, `pilot-git-repo-connection/tests/contract/repository_ingestion/test_gitlab_webhook_contract.py`, and `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_provider_flows.py`
- [ ] T003 [P] Add GitLab/unit regression test skeleton files in `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_provider_parsing.py`, `pilot-git-repo-connection/tests/unit/repository_connections/test_process_gitlab_event.py`, and `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- [ ] T004 Capture feature-level trace references for plan/spec/research/data-model/contracts/quickstart in `specs/002-gitlab-onprem-connection/delivery-evidence.md`

---

## Phase 2: Foundational (공통 기반 작업)

**Purpose**: GitHub와 GitLab이 함께 동작할 수 있는 provider 공통 기반을 먼저 고정한다.

**⚠️ CRITICAL**: 이 단계가 완료되기 전에는 어떤 사용자 스토리도 시작하지 않는다.

- [ ] T005 Extend provider enums, canonical state helpers, and shared persistence models for `gitlab_self_managed`, `provider_instance_url`, delivery-id source, health projection, and `webhook_merge_request` trigger support in `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
- [ ] T006 Create additive Alembic migration for mixed-provider repository ingestion schema changes in `pilot-git-repo-connection/alembic/versions/004_gitlab_self_managed_provider_support.py`
- [ ] T007 [P] Refactor provider parsing and remote validation entry points to support GitHub/GitLab side by side in `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py` and `pilot-git-repo-connection/src/tci/infrastructure/git/remote_parsers.py`
- [ ] T008 [P] Introduce shared provider event types and normalized event DTOs in `pilot-git-repo-connection/src/tci/infrastructure/webhooks/provider_event_types.py` and `pilot-git-repo-connection/src/tci/domain/services/repository_event_processing.py`
- [ ] T009 [P] Extend repository connection, event, cursor, sync run, and snapshot repositories for mixed-provider reads/writes in `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`, `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_event_repository.py`, `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_event_cursor_repository.py`, `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_sync_run_repository.py`, and `pilot-git-repo-connection/src/tci/infrastructure/persistence/code_snapshot_repository.py`
- [ ] T010 [P] Extend shared API schemas for mixed-provider connection detail, webhook health, and traceability fields in `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`, `pilot-git-repo-connection/src/tci/api/schemas/repository_scope.py`, and `pilot-git-repo-connection/src/tci/api/schemas/_base.py`
- [ ] T011 [P] Add foundational unit tests for mixed-provider model invariants, canonical status rules, and additive migration expectations in `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_foundation.py`
- [ ] T012 Wire new provider routes and shared dependencies into the FastAPI app in `pilot-git-repo-connection/src/tci/app.py`

**Checkpoint**: mixed-provider 공통 기반이 준비되어 GitLab 기능을 스토리 단위로 구현할 수 있다.

---

## Phase 3: User Story 1 - 온프레미스 GitLab 저장소 연결과 초기 스냅샷 생성 (Priority: P1) 🎯 MVP

**Goal**: 운영자가 GitLab self-managed 저장소를 읽기 전용으로 연결하고, 기본 ref를 검증한 뒤 첫 snapshot을 생성하며, 조치 필요 상태에서는 새 수집이 차단되고 기존 GitHub 연결이 깨지지 않았음을 확인한다.

**Independent Test**: `provider=gitlab_self_managed` 연결 생성, verify 성공, 초기 snapshot 성공, `reauth_required`/`ref_missing` 상태에서 manual snapshot 차단, detail traceability 조회 성공, 기존 GitHub connection 생성/verify/snapshot 회귀 성공

### Tests for User Story 1

- [ ] T013 [P] [US1] Add contract tests for GitLab repository connection create/get/patch/verify flows and provider validation in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_gitlab_connection_contract.py`
- [ ] T014 [P] [US1] Add integration tests for GitLab connection verify, `reauth_required`, `ref_missing`, blocked manual collection, and initial snapshot creation in `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_connection_lifecycle.py`
- [ ] T015 [P] [US1] Add GitHub compatibility regression tests for connection create/verify/manual snapshot in `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`

### Implementation for User Story 1

- [ ] T016 [P] [US1] Implement GitLab remote URL parser and namespace/project extraction in `pilot-git-repo-connection/src/tci/infrastructure/git/gitlab_remote_parser.py`
- [ ] T017 [P] [US1] Implement GitLab credential scope validation and read-only token probing in `pilot-git-repo-connection/src/tci/infrastructure/git/gitlab_readonly_validator.py`
- [ ] T018 [US1] Extend repository connection creation service for GitLab read-only credential validation, repository-address-based provider detection, and mixed-provider error mapping in `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
- [ ] T019 [US1] Extend repository connection verify and default-ref update services for GitLab `reauth_required`/`ref_missing` transitions in `pilot-git-repo-connection/src/tci/domain/services/verify_repository_connection.py` and `pilot-git-repo-connection/src/tci/domain/services/update_default_ref.py`
- [ ] T020 [US1] Extend manual snapshot trigger and snapshot build services for GitLab provider provenance and `reauth_required`/`ref_missing` collection blocking in `pilot-git-repo-connection/src/tci/domain/services/create_initial_snapshot.py` and `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
- [ ] T021 [US1] Implement GitLab-capable repository connection API handlers in `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
- [ ] T022 [US1] Extend connection detail query service and operator detail template for mixed-provider summaries and traceability in `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`, `pilot-git-repo-connection/src/tci/web/routes/repository_connection_detail.py`, and `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
- [ ] T023 [US1] Capture User Story 1 verification evidence for GitLab MVP and GitHub regression in `specs/002-gitlab-onprem-connection/delivery-evidence.md`

**Checkpoint**: GitLab 연결과 초기 snapshot이 독립적으로 동작하고 GitHub 기존 흐름도 유지되어야 한다.

---

## Phase 4: User Story 2 - 수집 범위와 분석 대상 ref 관리 (Priority: P2)

**Goal**: 운영자가 GitLab 연결에도 기존과 동일한 scope rule, hard exclude, empty-result 경고를 적용하고, 해당 규칙이 snapshot 결과와 traceability에 반영되는 것을 확인할 수 있게 한다.

**Independent Test**: GitLab 연결에 scope rule 저장, empty-result warning 확인, hard exclude 유지, scoped snapshot 생성, scope version traceability 확인

### Tests for User Story 2

- [ ] T024 [P] [US2] Add contract tests for GitLab scope rule save and scope detail projections in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_gitlab_scope_contract.py`
- [ ] T025 [P] [US2] Add unit tests for provider-neutral scope precedence, hard excludes, and `5 MiB` guard in `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_scope_rules.py`
- [ ] T026 [P] [US2] Add integration tests for scoped GitLab snapshots, empty-result blocking, and scope traceability in `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_scoped_snapshot.py`

### Implementation for User Story 2

- [ ] T027 [P] [US2] Extend default scope policy and scope filter engine for provider-neutral GitLab/GitHub behavior in `pilot-git-repo-connection/src/tci/domain/services/default_scope_policy.py` and `pilot-git-repo-connection/src/tci/domain/services/scope_filter_engine.py`
- [ ] T028 [US2] Extend scope warning evaluation and scope rule persistence for GitLab connections in `pilot-git-repo-connection/src/tci/domain/services/evaluate_scope_rule_warning.py` and `pilot-git-repo-connection/src/tci/infrastructure/persistence/scope_rule_repository.py`
- [ ] T029 [US2] Integrate scope version stamping and `NO_INCLUDED_FILES` handling for GitLab manual snapshot flows in `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py` and `pilot-git-repo-connection/src/tci/domain/services/create_initial_snapshot.py`
- [ ] T030 [US2] Extend scope rule API and operator scope page for mixed-provider messaging and warning states in `pilot-git-repo-connection/src/tci/api/routes/repository_scope.py`, `pilot-git-repo-connection/src/tci/web/routes/repository_scope.py`, and `pilot-git-repo-connection/src/tci/web/templates/connections/scope.html`
- [ ] T031 [US2] Capture User Story 2 verification evidence for GitLab scope control in `specs/002-gitlab-onprem-connection/delivery-evidence.md`

**Checkpoint**: GitLab에서도 scope rule과 snapshot 결과가 독립적으로 검증 가능해야 한다.

---

## Phase 5: User Story 3 - 실시간 변경 이벤트 수신과 호환 운영 (Priority: P3)

**Goal**: 운영자가 GitLab Push/Merge Request webhook을 실시간 수신하고, commit 기록/queued/record-only/stale/deduped 처리를 확인하며, 동시에 GitHub webhook 회귀도 유지할 수 있게 한다.

**Independent Test**: GitLab Push webhook accepted, GitLab MR `open`/code-moving `update` snapshot queued, reviewer-only `update` record-only, duplicate/stale delivery skip, token mismatch health 반영, 조치 필요 상태에서 webhook-driven snapshot 차단, GitHub webhook regression 성공

### Tests for User Story 3

- [ ] T032 [P] [US3] Add contract tests for GitLab webhook intake, accepted response, and connection detail health projection in `pilot-git-repo-connection/tests/contract/repository_ingestion/test_gitlab_webhook_contract.py`
- [ ] T033 [P] [US3] Add unit tests for GitLab token verification, delivery-id extraction, and MR update gating in `pilot-git-repo-connection/tests/unit/repository_connections/test_process_gitlab_event.py`
- [ ] T034 [P] [US3] Add integration tests for GitLab push webhook, merge request webhook, duplicate delivery, stale head, token mismatch handling, and state-based webhook snapshot blocking in `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_provider_flows.py`
- [ ] T035 [P] [US3] Extend GitHub webhook regression tests to cover mixed-provider coexistence in `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`

### Implementation for User Story 3

- [ ] T036 [P] [US3] Implement GitLab webhook token verifier and delivery-id extractor in `pilot-git-repo-connection/src/tci/infrastructure/webhooks/gitlab_token_verifier.py` and `pilot-git-repo-connection/src/tci/infrastructure/webhooks/gitlab_delivery_id.py`
- [ ] T037 [P] [US3] Implement GitLab push and merge request payload parser in `pilot-git-repo-connection/src/tci/infrastructure/webhooks/gitlab_event_parser.py`
- [ ] T038 [US3] Implement GitLab event processing service for commit recording, record-only/queued decisions, dedupe, stale-head handling, and health updates in `pilot-git-repo-connection/src/tci/domain/services/process_gitlab_event.py`
- [ ] T039 [US3] Implement GitLab webhook intake route and Celery enqueue handoff in `pilot-git-repo-connection/src/tci/api/routes/gitlab_webhooks.py`
- [ ] T040 [US3] Extend queue tasks and sync-run execution for GitLab push and merge request source-branch snapshots with `reauth_required`/`ref_missing` blocking in `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- [ ] T041 [US3] Extend event list/detail query services and operator event timeline for mixed-provider event projections in `pilot-git-repo-connection/src/tci/domain/services/list_repository_events.py`, `pilot-git-repo-connection/src/tci/api/routes/repository_events.py`, `pilot-git-repo-connection/src/tci/web/routes/repository_events.py`, and `pilot-git-repo-connection/src/tci/web/templates/connections/events.html`
- [ ] T042 [US3] Extend connection detail read model and webhook health projection for GitLab single-secret validation failures and reachability health in `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py` and `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- [ ] T043 [US3] Capture User Story 3 verification evidence for GitLab realtime sync and GitHub compatibility in `specs/002-gitlab-onprem-connection/delivery-evidence.md`

**Checkpoint**: GitLab webhook 기반 최신화와 mixed-provider 호환 운영이 독립 검증 가능해야 한다.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: mixed-provider 회귀, quickstart, evidence를 마무리한다.

- [ ] T044 [P] Add end-to-end quickstart regression harness and operator-path duration validation for SC-001 across GitLab primary flow and GitHub compatibility flow in `pilot-git-repo-connection/tests/support/run_gitlab_quickstart_validation.py` and `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_quickstart_validation.py`
- [ ] T045 [P] Add mixed-provider latency and status-refresh validation for SC-002 and SC-004 in `pilot-git-repo-connection/tests/support/measure_gitlab_webhook_status_latency.py` and `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_webhook_status_latency.py`
- [ ] T046 Refresh final FR/SC trace coverage and story completion evidence in `specs/002-gitlab-onprem-connection/delivery-evidence.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: No dependencies
- **Phase 2: Foundational**: Depends on Phase 1 and blocks all user stories
- **Phase 3: US1**: Depends on Phase 2
- **Phase 4: US2**: Depends on Phase 2 and reuses snapshot/scope baseline from US1
- **Phase 5: US3**: Depends on Phase 2 and reuses connection/snapshot/state baseline from US1 and US2
- **Phase 6: Polish**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: 첫 번째 deliverable slice이며 MVP
- **US2 (P2)**: US1 이후 진행 권장. scope rule이 실제 GitLab snapshot에 반영돼야 하므로 US1 baseline 재사용
- **US3 (P3)**: US1/US2 이후 진행 권장. webhook 최신화는 connection lifecycle, scope filtering, snapshot pipeline을 모두 재사용

### Within Each User Story

- 테스트 작업이 먼저 온다
- parser/validator/repository 같은 기반 구성요소가 service보다 먼저 온다
- service가 route/worker/UI보다 먼저 온다
- verification evidence 작업이 마지막에 온다

## Parallel Opportunities

- **Setup**: T002, T003는 T001과 병렬 가능
- **Foundational**: T007, T008, T009, T010, T011은 T005/T006 이후 병렬 가능
- **US1**: T013, T014, T015는 병렬 가능; T016, T017은 병렬 가능
- **US2**: T024, T025, T026은 병렬 가능; T027, T028은 병렬 가능
- **US3**: T032, T033, T034, T035는 병렬 가능; T036, T037은 병렬 가능
- **Polish**: T044, T045는 병렬 가능

## Parallel Example: User Story 1

```bash
# Tests first
Task: "T013 [US1] contract tests in tests/contract/repository_ingestion/test_gitlab_connection_contract.py"
Task: "T014 [US1] integration tests in tests/integration/repository_connections/test_gitlab_connection_lifecycle.py"
Task: "T015 [US1] GitHub compatibility regression in tests/integration/repository_connections/test_github_gitlab_compatibility.py"

# Then independent implementation work
Task: "T016 [US1] GitLab remote parser in src/tci/infrastructure/git/gitlab_remote_parser.py"
Task: "T017 [US1] GitLab readonly validator in src/tci/infrastructure/git/gitlab_readonly_validator.py"
```

## Parallel Example: User Story 3

```bash
# Tests first
Task: "T032 [US3] contract tests in tests/contract/repository_ingestion/test_gitlab_webhook_contract.py"
Task: "T033 [US3] unit tests in tests/unit/repository_connections/test_process_gitlab_event.py"
Task: "T034 [US3] integration tests in tests/integration/repository_connections/test_gitlab_provider_flows.py"

# Then independent implementation work
Task: "T036 [US3] GitLab token verifier in src/tci/infrastructure/webhooks/gitlab_token_verifier.py"
Task: "T037 [US3] GitLab event parser in src/tci/infrastructure/webhooks/gitlab_event_parser.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2
2. Complete Phase 3 (US1) only
3. Validate GitLab connection + initial snapshot + GitHub regression
4. Stop for human review

### Incremental Delivery

1. 공통 기반 완성
2. US1로 GitLab 연결과 초기 snapshot 제공
3. US2로 scope rule과 filtered snapshot 제공
4. US3로 realtime webhook 최신화 제공
5. Polish에서 quickstart/latency/evidence 마감

### Backlog / Issue Transfer Guidance

- 각 task는 그대로 backlog/issue 1건으로 옮길 수 있는 크기로 유지했다
- T005, T006, T009, T010은 모든 후속 작업이 의존하므로 최우선 플랫폼 작업이다
- T016~T023, T027~T031, T036~T043은 story별로 묶어서 스프린트/issue epic으로 옮길 수 있다

## Notes

- 모든 작업은 required checklist format을 따른다
- 공통 기반 작업이 최우선으로 먼저 배치됐다
- 각 story마다 테스트와 verification evidence 작업을 포함했다
- GitLab 신규 가치와 GitHub 회귀를 동시에 만족하도록 작업을 구성했다
- 이 파일의 모든 작업이 완료되면 승인된 spec 범위를 충족하도록 설계했다
