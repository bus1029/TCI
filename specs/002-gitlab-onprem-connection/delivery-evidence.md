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
| Phase 2 | mixed-provider 공통 기반 구축 | in_progress | T005, T006, T007, T011 |
| Phase 3 | US1 GitLab 연결과 초기 snapshot | in_progress | T013, T016, create/verify/default-ref/snapshot allowlist slice |
| Phase 4 | US2 scope/ref 관리 | in_progress | scope preview allowlist rejection slice |
| Phase 5 | US3 webhook 최신화 | pending | - |
| Phase 6 | polish, quickstart, latency 검증 | pending | - |

## User Story Verification

### User Story 1

- 상태: in_progress
- 범위
  - GitLab self-managed 저장소 연결 생성
  - verify 성공 및 `reauth_required` / `ref_missing` 전이
  - 초기 snapshot 생성
  - GitHub compatibility regression
- 근거
  - Contract
    - Phase 1 scaffold: `tests/contract/repository_ingestion/test_gitlab_connection_contract.py`
    - Implemented coverage: `tests/contract/repository_ingestion/test_repository_connection_contract.py`
      - GitLab provider create and derived metadata
      - allowlist rejection before git access
      - custom HTTPS/SSH port allowlist behavior
      - `/gitlab` path prefix as project namespace
      - GitLab detail response shape compatibility
      - default-ref patch allowlist rejection
  - Integration
    - Phase 1 scaffold: `tests/integration/repository_connections/test_gitlab_provider_flows.py`
    - Phase 1 scaffold: `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
    - Planned follow-up split in `T014`: `tests/integration/repository_connections/test_gitlab_connection_lifecycle.py`
  - 실행 결과
    - `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections tests/contract/repository_ingestion`
    - 결과: `244 passed, 9 skipped in 7.52s`

### User Story 2

- 상태: in_progress
- 범위
  - GitLab ref 변경 관리
  - scope rule 저장과 경고
  - filtered snapshot 생성
  - GitHub compatibility regression
- 근거
  - Contract
    - Phase 1 scaffold: `tests/contract/repository_ingestion/test_gitlab_connection_contract.py`
    - Implemented coverage: `tests/contract/repository_ingestion/test_repository_scope_contract.py`
      - GitLab allowlist rejection is propagated before preview git access
  - Integration
    - Phase 1 scaffold: `tests/integration/repository_connections/test_gitlab_provider_flows.py`
    - Phase 1 scaffold: `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - 실행 결과
    - `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections tests/contract/repository_ingestion`
    - 결과: `244 passed, 9 skipped in 7.52s`

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
| FR-001 | GitHub Cloud 기준선 유지 + GitLab self-managed 추가 | US1/US3 regression tests; GitLab parser keeps GitHub parser path intact |
| FR-002 | provider, remote, transport, credential, status 등록 | GitLab connection contract/integration; create contract now verifies derived metadata |
| FR-002a | 읽기 전용 credential만 허용 | GitLab readonly validator unit/integration |
| FR-003 | 연결 등록 시 접근 가능 여부 검증 | create/verify contract/integration; allowlist rejection before git access covered |
| FR-004 | GitHub 기존 흐름 유지 | GitHub compatibility regression |
| FR-004a | canonical status는 `active`, `reauth_required`, `ref_missing`만 사용 | phase2 foundation/unit |
| FR-005 | 기본 분석 대상 ref 1개 선택/변경 | connection patch and verify tests; GitLab allowlist check covered on patch |
| FR-006 | ref 변경 후 기존 snapshot/event 이력 보존 | integration lifecycle tests |
| FR-007 | 조치 필요 상태에서 새 수집 차단 | blocked snapshot/webhook integration; snapshot allowlist rejection before git access covered |
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
| FR-018 | connection/scope/event/snapshot traceability 유지 | detail and evidence trace checks; GitLab `provider_instance_url` and `provider_project_path` persistence covered |
| FR-019 | 빈 수집 위험 경고와 empty snapshot 실패 처리 | scope warning and snapshot tests; allowlist rejection is not swallowed by preview failure handling |
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

### 2026-04-24 Implemented Coverage

- Contract
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `tests/contract/repository_ingestion/test_repository_scope_contract.py`
- Unit
  - `tests/unit/repository_connections/test_gitlab_provider_parsing.py`
  - `tests/unit/repository_connections/test_gitlab_foundation.py`
  - `tests/unit/repository_connections/test_verify_repository_connection.py`
  - `tests/unit/repository_connections/test_webhook_sync_task.py`
  - `tests/unit/repository_connections/test_settings.py`

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

## Phase 2/US1 Security Slice Evidence

- T007: provider parsing and remote validation entry point refactor 완료
  - 근거 파일
    - `pilot-git-repo-connection/src/tci/infrastructure/git/remote_parsers.py`
    - `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
    - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - 검증 범위
    - GitLab HTTPS, SCP-like SSH, `ssh://` remote parsing
    - `/gitlab` path prefix를 project namespace로 처리
    - localhost/private IPv4/custom HTTPS/custom SSH port parsing
    - GitHub host, trailing-dot host, IPv6, userinfo, query/fragment, whitespace/control chars, dot segment, malformed port 거부
- T013: GitLab connection contract coverage 추가 완료
  - 근거 파일
    - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - 중요 메모
    - Phase 1 scaffold 파일인 `test_gitlab_connection_contract.py`는 유지한다.
    - 실제 coverage는 기존 provider-neutral contract suite에 추가했다.
- T016: GitLab remote URL parser와 namespace/project extraction 구현 완료
  - 근거 파일
    - `pilot-git-repo-connection/src/tci/infrastructure/git/remote_parsers.py`
- Additional security coverage
  - `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS` 설정 추가
  - create, verify, default-ref update, scope preview, snapshot build 경로에서 outbound git 접근 전 allowlist 검증
  - Scope preview는 allowlist rejection을 preview failure로 삼키지 않고 전파

## 2026-04-24 Verification Snapshot

- 테스트
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections tests/contract/repository_ingestion`
  - 결과: `244 passed, 9 skipped in 7.52s`
- 타입/정적 검증
  - `PYTHONDONTWRITEBYTECODE=1 mypy src/tci/settings.py src/tci/infrastructure/git/remote_parsers.py src/tci/domain/services/create_repository_connection.py src/tci/domain/services/repository_connection_support.py src/tci/domain/services/verify_repository_connection.py src/tci/domain/services/update_default_ref.py src/tci/domain/services/build_code_snapshot.py src/tci/domain/services/evaluate_scope_rule_warning.py src/tci/infrastructure/persistence/repository_connection_repository.py tests/unit/repository_connections/test_gitlab_provider_parsing.py tests/unit/repository_connections/test_gitlab_foundation.py tests/unit/repository_connections/test_settings.py`
  - 결과: `Success: no issues found in 12 source files`
- 스타일/포맷 검증
  - focused `ruff check` 통과
  - focused `black --check` 통과: `17 files would be left unchanged`
- diff hygiene
  - `git diff --check` 통과
- Reviewer loop
  - `reviewer`: findings 없음
  - `python-reviewer`: findings 없음
  - `security-reviewer`: findings 없음
- Residual risks
  - 해소됨: 실제 PostgreSQL Alembic migration 적용 검증은 2026-04-24 DB follow-up에서 완료했다.
  - 해소됨: `update_default_ref.py` decrypt-before-allowlist 순서는 2026-04-24 US1 follow-up에서 allowlist-before-decrypt로 수정했다.
  - 해소됨: stored SSH custom-port의 scope preview와 snapshot build 직접 검증은 2026-04-24 US1 follow-up에서 positive/negative control로 추가했다.

## 2026-04-24 US1 Follow-up TDD Evidence

- 사전 점검
  - `git status --short`
  - 결과: clean
  - tracked `.pyc` 확인 결과:
    - `pilot-git-repo-connection/alembic/__pycache__/env.cpython-313.pyc`
    - `pilot-git-repo-connection/alembic/versions/__pycache__/001_repository_ingestion_core.cpython-313.pyc`
- 실제 PostgreSQL Alembic 검증 사전 상태
  - `PYTHONDONTWRITEBYTECODE=1 alembic current`
  - 결과: `TCI_DATABASE_URL` 또는 `alembic.ini`의 `sqlalchemy.url` 미설정으로 실행 불가
  - 상태: 당시에는 residual risk였으나, 2026-04-24 DB follow-up에서 해소했다.
- RED
  - 추가 테스트: `tests/unit/repository_connections/test_update_default_ref.py`
  - 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections/test_update_default_ref.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py -q`
  - 결과: `test_update_default_ref_rejects_unallowlisted_gitlab_before_credential_decrypt` 실패
  - 의도한 실패 이유: `update_default_ref.py`가 GitLab allowlist 검사 전에 credential decrypt를 수행함
- GREEN
  - 구현: `update_default_ref.py`에서 encrypted secret만 context로 로드하고, GitLab allowlist 통과 후 decrypt하도록 순서 변경
  - 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections/test_update_default_ref.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py -q`
  - 결과: `4 passed in 0.95s`
- 추가 US1/T015 회귀 고정
  - 추가 테스트:
    - `tests/integration/repository_connections/test_gitlab_connection_lifecycle.py`
    - `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - 검증 범위:
    - SSH custom-port GitLab remote가 `host:port` allowlist로 verify, scope preview, snapshot build 경로를 통과
    - SSH custom-port GitLab remote가 host-only allowlist에서는 verify, scope preview, snapshot build 경로에서 git 접근 전 거부
    - SSH custom-port default-ref update가 host-only allowlist에서 credential decrypt 전 거부
    - snapshot build allowlist rejection은 credential failure/`reauth_required`로 오분류하지 않고 `MIRROR_SYNC_FAILED`와 기존 connection status 유지로 기록
    - `reauth_required` / `ref_missing` GitLab 연결의 manual snapshot 차단
    - GitHub/GitLab connection verify와 snapshot flow coexistence, credential revision/mirror/snapshot ownership 분리
  - 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections/test_update_default_ref.py tests/unit/repository_connections/test_verify_repository_connection.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_gitlab_compatibility.py -q`
  - 결과: `15 passed, 3 skipped in 1.09s`
- Python/security reviewer follow-up
  - 지적: snapshot allowlist rejection이 `AUTH_FAILED`/`reauth_required`로 오분류될 수 있음
  - 조치: `build_code_snapshot.py`의 `ProblemCode.INVALID_INPUT` 분류를 `MIRROR_SYNC_FAILED`, connection status unchanged로 변경하고 테스트 보강
  - 재검증:
    - `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections tests/contract/repository_ingestion tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_gitlab_compatibility.py -q`
    - 결과: `253 passed, 12 skipped in 7.31s`

## 2026-04-24 DB Migration Follow-up Evidence

- 실제 PostgreSQL 연결
  - compose: `specs/001-git-repo-connection/docker-compose/docker-compose-test.yaml`
  - DSN: `postgresql+psycopg://tci:tci@127.0.0.1:5433/tci_test`
  - 결과: `('tci_test', 'tci')`
- RED
  - 명령: `TCI_TEST_DATABASE_URL='postgresql+psycopg://tci:tci@127.0.0.1:5433/tci_test' TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1 PYTHONDONTWRITEBYTECODE=1 pytest tests/integration/repository_connections/test_phase2_migration_smoke.py -q`
  - 결과: 실패
  - 실패 원인: `004_gitlab_self_managed_provider_support.py` downgrade가 raw SQL `NOT VALID` constraint를 삭제할 때 naming convention이 적용되어 `ck_repository_events_ck_repo_event_verified_secret_pair` 삭제를 시도함
- GREEN
  - 구현: raw SQL `NOT VALID` check constraint 생성/검증/삭제를 SQLAlchemy naming convention 및 PostgreSQL identifier truncation/hash 규칙과 일치하도록 수정
  - 명령: `TCI_TEST_DATABASE_URL='postgresql+psycopg://tci:tci@127.0.0.1:5433/tci_test' TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1 PYTHONDONTWRITEBYTECODE=1 pytest tests/integration/repository_connections/test_phase2_migration_smoke.py -q`
  - 결과: `1 passed in 2.74s`
- Database-reviewer follow-up
  - 지적: immediate downgrade failure는 고쳤지만 live DB constraint name과 SQLAlchemy metadata naming convention drift가 남을 수 있음
  - 조치: `test_phase2_migration_smoke.py`에 live PostgreSQL check constraint name이 metadata의 PostgreSQL-rendered name을 포함하는지 검증하는 regression 추가
  - 재검증: `1 passed in 2.74s`
- 실DB bootstrap 검증
  - 명령: `TCI_MIGRATION_TEST_DATABASE_URL='postgresql+psycopg://tci:tci@127.0.0.1:5433/tci_test' TCI_MIGRATION_TEST_DATABASE_URL_ACK='postgresql+psycopg://tci:tci@127.0.0.1:5433/tci_test' TCI_MIGRATION_TEST_DATABASE_NAME='tci_test' TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1 PYTHONDONTWRITEBYTECODE=1 pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_planning_input_reference_create_bootstraps_connection_creation_with_real_db -q`
  - 결과: `1 passed in 2.08s`
- 전체 변경 범위 재검증
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections tests/contract/repository_ingestion tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_phase2_migration_smoke.py -q`
  - 결과: `253 passed, 13 skipped in 7.38s`
  - focused `mypy`: `Success: no issues found in 8 source files`
  - focused `ruff check`: `All checks passed!`
  - focused `black --check`: `8 files would be left unchanged`
- 최종 reviewer loop
  - `reviewer`: findings 없음
  - `python-reviewer`: findings 없음
  - `database-reviewer`: findings 없음
  - 로컬 destructive Alembic round-trip은 실제 `tci_test` PostgreSQL DB에서 통과했다.

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

- 수동 quickstart 검증 메모
- latency 측정 결과
- GitHub regression 실행 결과
- GitLab webhook flow 구현 후 reviewer / python-reviewer / security-reviewer 최종 재검토 결과

## 변경 이력

- 2026-04-23: Phase 1 evidence scaffold 생성
- 2026-04-23: Phase 2 foundation partial evidence 추가 (`T005`, `T006`, `T011`)
- 2026-04-24: GitLab remote parser, allowlist, localhost/private-IP/custom-port, fail-closed outbound guard evidence 추가 (`T007`, `T013`, `T016` 및 security slice)
- 2026-04-24: 실제 PostgreSQL migration smoke와 실DB bootstrap 검증 완료, 004 downgrade/check constraint naming bug 수정
