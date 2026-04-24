# Delivery Evidence

## 목적

이 문서는 `002-gitlab-onprem-connection` 구현이 어떤 검증 근거로 완료되었는지 기록한다. GitLab self-managed 신규 흐름과 기존 GitHub Cloud 회귀를 함께 추적할 수 있어야 하며, `FR-001`부터 `FR-023`, `SC-001`부터 `SC-005`까지의 근거를 한곳에서 연결해야 한다.

## 문서 사용 규칙

- Phase 1에서는 섹션, 추적 키, 기대 근거 슬롯만 먼저 준비한다.
- 각 구현 Phase가 끝날 때마다 관련 사용자 스토리, FR, SC 섹션에 검증 근거를 추가한다.
- 실행 로그는 명령, 결과 요약, 필요 시 수동 검증 메모를 함께 남긴다.
- GitLab 신규 검증과 GitHub 회귀 검증은 같은 섹션에 섞어 쓰지 않고 구분해서 기록한다.

## Feature Artifact Trace References

| Artifact | Path | Purpose | Phase 1 Status |
|----------|------|---------|----------------|
| Spec | `specs/002-gitlab-onprem-connection/spec.md` | 승인 범위와 FR/SC 기준선 | linked |
| Plan | `specs/002-gitlab-onprem-connection/plan.md` | 구현 전략과 mixed-provider 설계 규칙 | linked |
| Research | `specs/002-gitlab-onprem-connection/research.md` | provider adapter, webhook, credential 설계 근거 | linked |
| Data Model | `specs/002-gitlab-onprem-connection/data-model.md` | mixed-provider entity/state 확장 근거 | linked |
| Contract | `specs/002-gitlab-onprem-connection/contracts/repository-ingestion.openapi.yaml` | API/webhook 계약 기준선 | linked |
| Quickstart | `specs/002-gitlab-onprem-connection/quickstart.md` | 운영 검증 경로와 완료 기준 | linked |
| Tasks | `specs/002-gitlab-onprem-connection/tasks.md` | Phase/task 실행 순서 | linked |

## Phase Status

| Phase | Goal | Status | Evidence |
|------|------|--------|----------|
| Phase 1 | 증적 문서 및 테스트 골격 준비 | scaffolded | T001-T004 |
| Phase 2 | mixed-provider 공통 기반 구축 | in_progress | T005, T006, T011 |
| Phase 3 | US1 GitLab 연결과 초기 snapshot | pending | - |
| Phase 4 | US2 scope/ref 관리 | pending | - |
| Phase 5 | US3 webhook 최신화 | pending | - |
| Phase 6 | polish, quickstart, latency 검증 | pending | - |

## User Story Verification

### User Story 1

- 상태: pending
- 범위
  - GitLab self-managed 저장소 연결 생성
  - verify 성공 및 `reauth_required` / `ref_missing` 전이
  - 초기 snapshot 생성
  - GitHub compatibility regression
- 근거
  - Contract
    - Phase 1 scaffold: `tests/contract/repository_ingestion/test_gitlab_connection_contract.py`
  - Integration
    - Phase 1 scaffold: `tests/integration/repository_connections/test_gitlab_provider_flows.py`
    - Phase 1 scaffold: `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
    - Planned follow-up split in `T014`: `tests/integration/repository_connections/test_gitlab_connection_lifecycle.py`
  - 실행 결과
    - pending

### User Story 2

- 상태: pending
- 범위
  - GitLab ref 변경 관리
  - scope rule 저장과 경고
  - filtered snapshot 생성
  - GitHub compatibility regression
- 근거
  - Contract
    - Phase 1 scaffold: `tests/contract/repository_ingestion/test_gitlab_connection_contract.py`
  - Integration
    - Phase 1 scaffold: `tests/integration/repository_connections/test_gitlab_provider_flows.py`
    - Phase 1 scaffold: `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - 실행 결과
    - pending

### User Story 3

- 상태: pending
- 범위
  - GitLab push webhook
  - GitLab merge request webhook
  - dedupe, stale head, token mismatch health
  - GitHub webhook regression
- 근거
  - Contract
    - Phase 1 scaffold: `tests/contract/repository_ingestion/test_gitlab_webhook_contract.py`
  - Unit
    - Phase 1 scaffold: `tests/unit/repository_connections/test_process_gitlab_event.py`
  - Integration
    - Phase 1 scaffold: `tests/integration/repository_connections/test_gitlab_provider_flows.py`
    - Phase 1 scaffold: `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - 실행 결과
    - pending

## Functional Requirement Trace Matrix

| Requirement | Summary | Planned Evidence |
|-------------|---------|------------------|
| FR-001 | GitHub Cloud 기준선 유지 + GitLab self-managed 추가 | US1/US3 regression tests |
| FR-002 | provider, remote, transport, credential, status 등록 | GitLab connection contract/integration |
| FR-002a | 읽기 전용 credential만 허용 | GitLab readonly validator unit/integration |
| FR-003 | 연결 등록 시 접근 가능 여부 검증 | create/verify contract/integration |
| FR-004 | GitHub 기존 흐름 유지 | GitHub compatibility regression |
| FR-004a | canonical status는 `active`, `reauth_required`, `ref_missing`만 사용 | phase2 foundation/unit |
| FR-005 | 기본 분석 대상 ref 1개 선택/변경 | connection patch and verify tests |
| FR-006 | ref 변경 후 기존 snapshot/event 이력 보존 | integration lifecycle tests |
| FR-007 | 조치 필요 상태에서 새 수집 차단 | blocked snapshot/webhook integration |
| FR-007a | auth 실패 시 `reauth_required` | verify lifecycle tests |
| FR-007b | ref 조회 실패 시 `ref_missing` | verify lifecycle tests |
| FR-008 | include/exclude/file type 규칙 관리 | scope contract/integration |
| FR-009 | GitHub/GitLab 공통 scope semantics 유지 | mixed-provider regression |
| FR-009a | 텍스트 파일만 기본 수집, 바이너리/생성물/5 MiB 초과 제외 | scope engine and snapshot tests |
| FR-010 | provider/ref/scope/captured-at 포함 snapshot 생성 | snapshot integration/detail checks |
| FR-011 | 완전한 파일 집합 snapshot 보존 | snapshot storage integration |
| FR-012 | Commit/Push/Merge Request webhook 기록 | webhook contract/integration |
| FR-012a | commit 메타데이터는 기록 전용으로 저장 | process_gitlab_event unit/integration |
| FR-013 | Push/MR만 snapshot 최신화 기준 이벤트로 사용 | process_gitlab_event unit/integration |
| FR-014 | MR source branch 기준 snapshot 생성 | merge request integration |
| FR-014a | `opened`, `reopened`, code-moving `update`만 queued | process_gitlab_event unit |
| FR-015 | connection별 webhook secret 검증/거부 사유 기록 | webhook contract/integration |
| FR-015a | webhook 이상을 health 신호로 분리 | connection detail contract/integration |
| FR-016 | duplicate/stale webhook guard | webhook integration |
| FR-017 | latest success/failure/last processed event 요약 | detail/event contract |
| FR-018 | connection/scope/event/snapshot traceability 유지 | detail and evidence trace checks |
| FR-019 | 빈 수집 위험 경고와 empty snapshot 실패 처리 | scope warning and snapshot tests |
| FR-020 | mixed-provider 동시 운영 시 상태/이력 분리 | compatibility regression |
| FR-021 | 읽기 전용 공유 credential 운영 모델 유지 | validator/service tests |
| FR-022 | GitHub와 유사한 작업 순서/상태 해석 제공 | quickstart and operator flow |
| FR-023 | 계획 입력과 connection/snapshot traceability 유지 | detail traceability tests |

## Success Criteria Trace Matrix

| Criterion | Target | Planned Evidence | Status |
|-----------|--------|------------------|--------|
| SC-001 | GitLab 연결부터 첫 snapshot 완료까지 15분 이내 | quickstart harness + US1 integration | pending |
| SC-002 | 유효한 Push/MR 이벤트 95% 이상 1분 이내 처리 상태 반영 | latency harness + webhook integration | pending |
| SC-003 | snapshot 100% traceability | connection detail + snapshot detail checks | pending |
| SC-004 | GitHub 기준선 시나리오 모두 유지 | compatibility regression suite | pending |
| SC-005 | 스냅샷 100% scope rule 일치 | scope engine + filtered snapshot tests | pending |

## Test Evidence Index

### Phase 1 Scaffolded Files

- Contract
  - `tests/contract/repository_ingestion/test_gitlab_connection_contract.py`
  - `tests/contract/repository_ingestion/test_gitlab_webhook_contract.py`
- Unit
  - `tests/unit/repository_connections/test_gitlab_provider_parsing.py`
  - `tests/unit/repository_connections/test_process_gitlab_event.py`
- Integration
  - `tests/integration/repository_connections/test_gitlab_provider_flows.py`
  - `tests/integration/repository_connections/test_github_gitlab_compatibility.py`

### Planned Follow-up Additions

- Integration
  - `tests/integration/repository_connections/test_gitlab_connection_lifecycle.py` in `T014`

## Phase 1 Completion Evidence

- T001: `delivery-evidence.md` 스캐폴드 생성 완료
- T002: GitLab contract/integration 테스트 골격 파일 생성 완료
- T003: GitLab unit/regression 테스트 골격 파일 생성 완료
- T004: spec/plan/research/data-model/contracts/quickstart trace reference 반영 완료

## Phase 2 Partial Completion Evidence

- T005: mixed-provider foundation metadata 반영 완료
  - 근거 파일
    - `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
  - 검증
    - `tests/unit/repository_connections/test_phase2_foundation.py`
    - `tests/unit/repository_connections/test_gitlab_foundation.py`
- T006: additive GitLab foundation migration 작성 완료
  - 근거 파일
    - `pilot-git-repo-connection/alembic/versions/004_gitlab_self_managed_provider_support.py`
  - 중요 메모
    - `provider_project_path`는 rollout-safe 하게 migration에서는 nullable 유지
    - downgrade 시 004-only 인덱스 삭제까지 반영
- T011: mixed-provider foundation unit test 추가 완료
  - 근거 파일
    - `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_foundation.py`
    - `pilot-git-repo-connection/tests/unit/repository_connections/test_phase2_foundation.py`
  - 실행 결과
    - `python -m pytest pilot-git-repo-connection/tests/unit/repository_connections/test_phase2_foundation.py pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_foundation.py pilot-git-repo-connection/tests/unit/repository_connections/test_git_foundation.py pilot-git-repo-connection/tests/unit/repository_connections/test_process_github_event.py pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py -q`
    - 결과: `101 passed in 1.83s`

## Foundation Verification Snapshot

- 타입/정적 검증
  - `mypy pilot-git-repo-connection/src/tci/domain/services/process_github_event.py pilot-git-repo-connection/tests/unit/repository_connections/test_phase2_foundation.py pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_foundation.py`
  - 결과: `Success: no issues found in 3 source files`
- 스타일/포맷 검증
  - `ruff check` 대상 파일 세트 통과
  - `black --check` 대상 파일 세트 통과
- diff hygiene
  - `git diff --check` 통과

## Open Evidence Slots

- 실제 pytest 실행 명령과 pass/fail 결과
- 수동 quickstart 검증 메모
- latency 측정 결과
- GitHub regression 실행 결과
- reviewer / python-reviewer / database-reviewer 최종 재검토 결과
- security-reviewer 피드백과 조치 기록

## 변경 이력

- 2026-04-23: Phase 1 evidence scaffold 생성
- 2026-04-23: Phase 2 foundation partial evidence 추가 (`T005`, `T006`, `T011`)
