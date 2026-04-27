# Delivery Evidence

## 목적

이 문서는 `002-gitlab-onprem-connection`의 현재 구현/검증 상태를 빠르게 이어받기 위한 증적 요약이다. 오래된 RED/GREEN 상세 로그는 2026-04-27에 압축했고, 다음 세션 판단에 필요한 결정사항과 최신 검증 상태만 남긴다.

## 문서 사용 규칙

- 다음 세션은 먼저 `Current Handoff State`와 `Latest Verification`을 읽는다.
- 상세 요구사항은 `spec.md`, 실행 순서는 `tasks.md`, 운영 흐름은 `quickstart.md`를 기준으로 한다.
- 새 개발 증적은 최신 섹션에만 추가하고, 오래된 상세 명령 로그를 다시 누적하지 않는다.
- reviewer 사용 이력은 세션별 사용자 지시를 따른다. 최신 Phase 6 loop에서는 `reviewer`, `python-reviewer`, `pr-test-analyzer`를 사용했다.

## Feature Artifact Trace References

| Artifact | Path | Purpose |
|----------|------|---------|
| Spec | `specs/002-gitlab-onprem-connection/spec.md` | 승인 범위와 FR/SC 기준선 |
| Plan | `specs/002-gitlab-onprem-connection/plan.md` | 구현 전략과 mixed-provider 설계 규칙 |
| Research | `specs/002-gitlab-onprem-connection/research.md` | provider adapter, webhook, credential 설계 근거 |
| Data Model | `specs/002-gitlab-onprem-connection/data-model.md` | mixed-provider entity/state 확장 근거 |
| Contract | `specs/002-gitlab-onprem-connection/contracts/repository-ingestion.openapi.yaml` | API/webhook 계약 기준선 |
| Quickstart | `specs/002-gitlab-onprem-connection/quickstart.md` | 운영 검증 경로와 완료 기준 |
| Tasks | `specs/002-gitlab-onprem-connection/tasks.md` | Phase/task 실행 순서 |
| Handoff | `specs/002-gitlab-onprem-connection/next-session-handoff.md` | 다음 세션 시작 순서와 Phase 6 진입 기준 |

## Current Handoff State

- US1~US3 구현은 local GREEN이다.
- `python-reviewer` HIGH findings 3개는 TDD로 수정했고 이전 reviewer loop가 clean으로 끝났다.
- 이전 reviewer 결과:
  - `python-reviewer`: blocking findings 없음, approve verdict.
  - `security-reviewer`: security findings 없음.
  - `database-reviewer`: database findings 없음.
  - `pr-test-analyzer`: material remaining test gaps 없음.
- 최신 Phase 6 reviewer 결과:
  - `reviewer`: no blocking findings.
  - `python-reviewer`: no blocking findings, approve.
  - `pr-test-analyzer`: initial evidence overclaim findings resolved; final no material test gaps.
- Phase 6(`T044`~`T046`) quickstart/latency/evidence 작업까지 완료했다.

## Phase Status

| Phase | Goal | Status | Evidence |
|------|------|--------|----------|
| Phase 1 | 증적 문서 및 테스트 골격 준비 | complete | T001-T004 |
| Phase 2 | mixed-provider 공통 기반 구축 | complete | T005-T012 |
| Phase 3 | US1 GitLab 연결과 초기 snapshot | complete | T013-T023 |
| Phase 4 | US2 scope/ref 관리 | complete | T024-T031 |
| Phase 5 | US3 webhook 최신화 | complete | T008, T032-T043 |
| Phase 6 | polish, quickstart, latency 검증 | complete | T044-T046 |

## User Story Verification

### User Story 1

- 상태: complete
- 범위: GitLab self-managed 저장소 연결 생성, verify, status transition, 초기 snapshot, GitHub compatibility regression.
- 핵심 증적:
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `tests/integration/repository_connections/test_gitlab_connection_lifecycle.py`
  - `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - `tests/integration/repository_connections/test_operator_connection_pages.py`
  - `tests/unit/repository_connections/test_verify_repository_connection.py`
  - `tests/unit/repository_connections/test_update_default_ref.py`
- 보존 결정:
  - GitLab allowlist는 outbound git access와 credential decrypt 전에 검증한다.
  - `github.com`, trailing-dot host, IPv6, userinfo/query/fragment, malformed port는 GitLab self-managed remote로 거부한다.
  - `localhost`, private IPv4, custom SSH/HTTPS port는 allowlist에 명시된 경우 지원한다.
  - canonical connection status는 `active`, `reauth_required`, `ref_missing`만 유지한다.
  - `webhookAuthMode`, `shared_token`, raw operator token은 general response/operator HTML에 노출하지 않는다.

### User Story 2

- 상태: complete
- 범위: GitLab ref 변경 관리, scope rule 저장/경고, filtered snapshot, GitHub compatibility regression.
- 핵심 증적:
  - `tests/contract/repository_ingestion/test_gitlab_scope_contract.py`
  - `tests/contract/repository_ingestion/test_repository_scope_contract.py`
  - `tests/unit/repository_connections/test_gitlab_scope_rules.py`
  - `tests/integration/repository_connections/test_gitlab_scoped_snapshot.py`
  - `tests/integration/repository_connections/test_operator_scope_pages.py`
  - `tests/integration/repository_connections/test_scoped_snapshot.py`
- 보존 결정:
  - `excludeBinary=false`는 binary opt-in으로 처리하되 hard exclude와 `5 MiB` guard는 유지한다.
  - scope preview allowlist rejection은 preview failure로 삼키지 않고 management API problem response로 전파한다.
  - Git subprocess는 ambient `HOME`, `GIT_CONFIG_*`, `SSH_AUTH_SOCK`, `GIT_SSH_COMMAND`를 신뢰하지 않는다.
  - HTTPS PAT는 URL embedding 대신 askpass Unix socket flow를 사용한다.
  - SSH private key는 temp file 대신 isolated `ssh-agent`에 stdin으로 등록한다.
  - snapshot materialization은 scope filter 전 raw tree entry cap을 둔다.

### User Story 3

- 상태: complete, reviewer loop clean
- 범위: GitLab push/MR webhook, dedupe, stale head, token mismatch health, GitHub webhook regression.
- 핵심 증적:
  - `tests/contract/repository_ingestion/test_gitlab_webhook_contract.py`
  - `tests/contract/repository_ingestion/test_github_webhook_contract.py`
  - `tests/unit/repository_connections/test_process_gitlab_event.py`
  - `tests/unit/repository_connections/test_webhook_sync_task.py`
  - `tests/integration/repository_connections/test_gitlab_provider_flows.py`
  - `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - `tests/integration/repository_connections/test_github_webhook_refresh.py`
- 보존 결정:
  - Public webhook response는 auth/validation oracle을 만들지 않도록 authenticated malformed/invalid payload까지 uniform `202 {"status":"accepted"}`로 접는다.
  - Redis limiter 장애는 raw `500`이 아니라 webhook unavailable `503`으로 접는다.
  - GitHub/GitLab webhook limiter는 source-level pre-auth cap을 제거하고 connection bucket 중심으로 유지한다.
  - 같은 requested ref의 active sync는 `pending`/`running` 하나만 허용한다.
  - running sync 중 같은 ref에 새 head가 오면 blocked follow-up을 하나만 유지하고 최신 이벤트로 교체한다.
  - `RepositorySyncRun.dispatch_enqueued_at`는 Celery publish 성공 marker이며 outbox가 아니다.
  - `dispatch_enqueued_at is None`인 active pending sync는 commit-to-enqueue crash gap 복구 대상으로 본다.

## Requirement Trace Summary

| Range | Summary | Current Evidence Status |
|-------|---------|-------------------------|
| FR-001-FR-004 | GitHub 기준선 유지와 GitLab provider 추가 | covered by mixed-provider contract/integration regression |
| FR-005-FR-011 | ref, scope, filtered snapshot, snapshot traceability | covered by US1/US2 suites and Phase 6 traceability harness |
| FR-012-FR-017 | Push/MR webhook, health, dedupe, latest status | implemented; replay/dispatch/limiter reviewer findings fixed and clean-reviewed |
| FR-018-FR-023 | connection/snapshot traceability, operator flow, shared credential model | implemented for product flow; quickstart/latency harness complete |

## Success Criteria Trace Matrix

| Criterion | Target | Status |
|-----------|--------|--------|
| SC-001 | GitLab 연결부터 첫 snapshot 완료까지 15분 이내 | deterministic backend/API harness covered by `run_gitlab_quickstart_validation.py`; latest smoke `0.026890s` |
| SC-002 | 유효한 Push/MR 이벤트 95% 이상 1분 이내 처리 상태 반영 | synthetic TestClient + inline worker harness covered by `measure_gitlab_webhook_status_latency.py`; latest sample 5/5, p95 `0.013243s` |
| SC-003 | snapshot 100% traceability | covered by US1/US2 suites and Phase 6 quickstart traceability assertion |
| SC-004 | GitHub 기준선 시나리오 모두 유지 | covered by full suite and mixed-provider regression |
| SC-005 | 스냅샷 100% scope rule 일치 | covered by US2 scope/snapshot tests |

## Latest Verification

- Phase 6 RED:
  - 명령: `pytest -q tests/integration/repository_connections/test_gitlab_quickstart_validation.py tests/integration/repository_connections/test_gitlab_webhook_status_latency.py`
  - 결과: intended `ModuleNotFoundError` for missing support modules.
- Phase 6 focused GREEN:
  - 명령: `pytest -q tests/integration/repository_connections/test_gitlab_quickstart_validation.py tests/integration/repository_connections/test_gitlab_webhook_status_latency.py`
  - 결과: `2 passed`.
- Phase 6 support script smoke:
  - 명령: `python tests/support/run_gitlab_quickstart_validation.py`
  - 결과: deterministic backend/API path 기준 `SC001_GITLAB_FIRST_SNAPSHOT_SECONDS=0.026890`, Push/MR completed, GitHub compatibility `True`.
  - 명령: `python tests/support/measure_gitlab_webhook_status_latency.py`
  - 결과: synthetic TestClient + inline worker path 기준 sample `5/5`, max `0.013243s`, p95 `0.013243s`.
- Phase 6 focused ruff:
  - 명령: `ruff check tests/support/run_gitlab_quickstart_validation.py tests/support/measure_gitlab_webhook_status_latency.py tests/integration/repository_connections/test_gitlab_quickstart_validation.py tests/integration/repository_connections/test_gitlab_webhook_status_latency.py`
  - 결과: `No issues found`.
- 최신 전체 Python suite:
  - 명령: `PYTHONDONTWRITEBYTECODE=1 pytest -q`
  - 결과: `498 passed`
- 최신 reviewer follow-up targeted GREEN:
  - running sync replay recovery, dispatch marker duplicate idempotency, in-memory limiter thread safety, GitHub/GitLab webhook contract regressions covered.
  - targeted pack 결과: `35 passed`
- PostgreSQL migration smoke:
  - local default: `3 skipped` because `TCI_TEST_DATABASE_URL` / `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1` not set.
  - optional destructive cases cover revision `006 -> 007` backfill and duplicate active preflight with real PostgreSQL when env is provided.
- 변경 범위 정적 검증:
  - focused `ruff check`: `All checks passed!`
  - migration smoke `ruff check`: `All checks passed!`
- 알려진 전체 정적 검증 실패:
  - `uv run ruff check src tests alembic/versions/007_sync_run_active_trigger_guard.py`는 기존 support measurement scripts의 `E402` 때문에 실패한다.
  - `uv run mypy src/tci`는 Celery/Kombu missing stubs와 기존 `github_signature.py` nullable issue 때문에 실패한다.
  - `pip_audit`는 현재 workspace에 설치되어 있지 않다.
  - 전체 pytest warning: `tests/support/repository_connection_testkit.py`의 `TestRepositoryEvent` dataclass collection warning. 기능 실패는 아니다.

## Historical Evidence Summary

- 2026-04-23: Phase 1 evidence scaffold와 GitLab contract/unit/integration 테스트 골격을 생성했다.
- 2026-04-24: Phase 2 mixed-provider foundation, GitLab remote parser, allowlist, provider metadata, repository persistence/read model wiring을 완료했다.
- 2026-04-24: 실제 PostgreSQL migration smoke에서 004 downgrade/check constraint naming drift를 수정했고 destructive Alembic round-trip을 통과했다.
- 2026-04-24: US1 backend completion에서 GitLab read-only validator, detail metadata, default-ref failure transition, create/patch/detail response coverage를 완료했다.
- 2026-04-26: US1 operator detail에서 GitLab instance/project/scope traceability 렌더링과 secret/auth-mode 비노출을 확인했다.
- 2026-04-26: US2 scope/ref에서 `excludeBinary`, binary opt-in, allowlist-before-preview, scoped snapshot behavior를 완료했다.
- 2026-04-26: US2 reviewer loop에서 askpass, isolated SSH agent, Git env isolation, raw tree cap hardening을 완료했다.
- 2026-04-26: US3 webhook에서 GitLab push/MR parser, token verifier, delivery id, queue handoff, event/detail projection, GitHub parity hardening을 완료했다.
- 2026-04-26~2026-04-27: active sync uniqueness, follow-up coalescing, blocked handoff, operator session cookie, OpenAPI parity, Redis limiter branch, public webhook uniform response hardening을 반복 적용했다.
- 2026-04-27: 최종 `python-reviewer` HIGH findings 3개를 TDD로 수정했다.
  - `_run_webhook_sync_task()` running replay recovery 보강.
  - dispatch marker 유실/duplicate execution idempotency 보강.
  - GitHub/GitLab in-memory webhook limiter thread safety 보강.
- 2026-04-27: `python-reviewer`, `security-reviewer`, `database-reviewer`, `pr-test-analyzer` loop가 clean으로 종료됐다.

## Open Evidence Slots

- 없음. 선택적 PostgreSQL destructive migration smoke와 real worker/browser-backed latency smoke는 env/운영 QA 범위에서 별도 실행할 수 있다.

## Next Session Order

1. `git status --short`와 `git diff --stat`로 현재 diff를 확인한다.
2. final verification 결과와 reviewer loop 결과를 확인한다.
3. 선택적 destructive PostgreSQL migration smoke가 필요하면 `TCI_TEST_DATABASE_URL`과 `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1`을 설정해 실행한다.
4. release/commit 전 `git diff`와 focused/full test 결과를 다시 확인한다.

## 변경 이력

- 2026-04-23: Phase 1 evidence scaffold 생성.
- 2026-04-24: Phase 2 foundation, US1 backend, PostgreSQL migration smoke 증적 추가.
- 2026-04-26: US1 operator detail, US2 scope/ref, US3 webhook 최신화 증적 추가.
- 2026-04-27: webhook follow-up dispatch replay/crash hardening 후 중간 전체 Python suite를 통과했다.
- 2026-04-27: 최종 `python-reviewer` HIGH findings 3개를 TDD로 수정하고 reviewer loop를 clean으로 종료.
- 2026-04-27: 최신 전체 Python suite `498 passed`.
- 2026-04-27: 오래된 상세 RED/GREEN 로그를 핵심 결정사항 중심으로 압축.
- 2026-04-27: Phase 6 GitLab quickstart/latency harness와 final FR/SC trace refresh를 완료.
