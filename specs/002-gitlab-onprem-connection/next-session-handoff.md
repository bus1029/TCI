# Next Session Handoff: GitLab Self-Managed Connection

## 1. 짧은 요약

GitLab self-managed 연결 작업은 US1~US3 구현, reviewer follow-up hardening, 최종 reviewer loop까지 clean 상태다.

- 전체 Python suite: `496 passed, 10 skipped, 1 warning in 20.75s`.
- 최종 reviewer 결과: `python-reviewer`, `security-reviewer`, `database-reviewer`, `pr-test-analyzer` 모두 blocking finding 없음.
- 일반 `reviewer`는 사용자 결정에 따라 제외했다.
- 다음 세션은 Phase 6(`T044`~`T046`) quickstart/latency/final evidence 작업부터 시작하면 된다.

## 2. 현재 상태

- 코드 변경은 아직 커밋되지 않았다.
- US1 GitLab 연결/초기 snapshot, US2 scope/ref, US3 webhook 최신화는 구현 완료다.
- `python-reviewer` HIGH findings 3개는 TDD로 수정됐다.
- running sync replay recovery, dispatch marker 유실/duplicate execution idempotency, in-memory webhook limiter thread safety가 보강됐다.
- PostgreSQL destructive migration smoke는 테스트가 추가됐지만 local env가 없어 skip 상태다.
- 남은 제품 범위는 Phase 6:
  - `T044` quickstart regression harness와 operator-path duration validation.
  - `T045` webhook status-refresh latency validation.
  - `T046` final FR/SC trace coverage와 evidence refresh.

현재 중요한 신규/수정 파일:

- `pilot-git-repo-connection/alembic/versions/007_sync_run_active_trigger_guard.py`
- `pilot-git-repo-connection/src/tci/api/operator_auth.py`
- `pilot-git-repo-connection/src/tci/api/routes/github_webhooks.py`
- `pilot-git-repo-connection/src/tci/api/routes/gitlab_webhooks.py`
- `pilot-git-repo-connection/src/tci/domain/services/process_github_event.py`
- `pilot-git-repo-connection/src/tci/domain/services/process_gitlab_event.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_sync_run_repository.py`
- `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- `pilot-git-repo-connection/src/tci/web/routes/_common.py`
- `pilot-git-repo-connection/src/tci/web/routes/operator_session.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_phase2_migration_smoke.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_sync_run_repository.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_webhook_rate_limit_thread_safety.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_webhook_sync_task.py`

## 3. 이번 세션에서 바뀐 것

- `requested_ref_key`를 추가해 같은 source branch를 공유하는 PR/MR stream을 `default_ref`, `pr:{number}`, `mr:{iid}` 단위로 분리했다.
- Alembic `007_sync_run_active_trigger_guard.py`가 `dispatch_enqueued_at`, `requested_ref_key`, active/blocked partial unique indexes, 기존 pending stale marker를 추가한다.
- migration backfill은 runtime과 같은 기준으로 `requested_ref_key`를 채운다.
- follow-up dispatch 실패가 sync/event를 terminal failed로 전환하고 cursor를 복구해 same-head retry가 다시 queue될 수 있게 했다.
- duplicate-head active pending event가 cursor를 오염시키지 않도록 실제 queued dispatch event에만 cursor를 전진시켰다.
- `_run_webhook_sync_task()`의 running replay recovery를 보강했다.
- marker 유실과 duplicate worker 실행이 sync/event를 잘못 failed로 덮어쓰지 않도록 idempotency를 보강했다.
- GitHub/GitLab in-memory webhook limiter에 thread-safety와 source pruning 보강을 추가했다.
- operator auth failure budget은 Redis Lua/in-memory lock 기반 atomic consume으로 바뀌었다.
- production operator token은 실제 `TCI_ENV` 기준으로 검증하며, non-development token은 43자 이상 base64url 형식이어야 한다.
- shared operator form body parser는 streaming 64 KiB cap을 적용하고 `/connections`, `/connections/{id}/scope`는 초과 시 `413`을 반환한다.
- Celery app은 `task_acks_late=True`, `task_reject_on_worker_lost=True`로 설정됐다.
- 선택적 destructive PostgreSQL migration smoke가 추가됐다.

## 4. 다음 에이전트가 먼저 봐야 할 파일

상태와 요구사항:

- `specs/002-gitlab-onprem-connection/tasks.md`
- `specs/002-gitlab-onprem-connection/delivery-evidence.md`
- `specs/002-gitlab-onprem-connection/spec.md`
- `specs/002-gitlab-onprem-connection/quickstart.md`

Phase 6 후보:

- `pilot-git-repo-connection/tests/support/run_gitlab_quickstart_validation.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_quickstart_validation.py`
- `pilot-git-repo-connection/tests/support/measure_gitlab_webhook_status_latency.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_webhook_status_latency.py`

Webhook/replay 핵심:

- `pilot-git-repo-connection/src/tci/api/routes/github_webhooks.py`
- `pilot-git-repo-connection/src/tci/api/routes/gitlab_webhooks.py`
- `pilot-git-repo-connection/src/tci/domain/services/process_github_event.py`
- `pilot-git-repo-connection/src/tci/domain/services/process_gitlab_event.py`
- `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_sync_run_repository.py`
- `pilot-git-repo-connection/alembic/versions/007_sync_run_active_trigger_guard.py`

## 5. 꼭 유지해야 할 기준

- `$tdd` 기준을 유지한다. Phase 6도 먼저 RED 또는 failing coverage gap을 만들고 GREEN으로 닫는다.
- 일반 `reviewer`는 호출하지 않는다.
- reviewer가 필요하면 `python-reviewer`, `security-reviewer`, `database-reviewer`, `pr-test-analyzer`만 사용한다.
- GitHub 기존 흐름은 GitLab 변경 때문에 깨지면 안 된다.
- Public webhook response는 인증/validation oracle을 만들면 안 된다.
- Redis limiter 장애는 raw `500`이나 stack trace로 새면 안 된다.
- 같은 requested ref의 active sync는 `pending`/`running` 하나만 허용한다.
- blocked follow-up은 같은 requested ref에서 하나만 유지하고 최신 이벤트로 교체한다.
- commit-to-enqueue crash gap은 `dispatch_enqueued_at is None` 상태를 통해 복구 가능해야 한다.
- duplicate worker와 replay path는 idempotent해야 한다.
- Stored credential은 GitLab allowlist 통과 전 decrypt하지 않는다.
- `webhookAuthMode`, `shared_token`, webhook secret 값은 general response/operator HTML에 노출하지 않는다.

## 6. 다시 논의하지 말아야 할 결정

- `T008`, `T013`~`T043`은 구현 완료 상태로 취급한다.
- 다음 제품 작업은 Phase 6(`T044`~`T046`)이다.
- GitLab instance URL을 사용자가 직접 입력하는 방식은 이번 범위에서 제외한다.
- GitLab instance subpath는 heuristic으로 추정하지 않는다.
- `/gitlab` path segment도 namespace/project path로 취급한다.
- `localhost`, private IPv4, 비표준 SSH/HTTPS 포트는 지원한다. 해당 origin은 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`에 명시되어야 한다.
- IPv6는 이번 범위에서 거부한다.
- `github.com`과 trailing-dot host는 GitLab self-managed provider로 받지 않는다.
- 공식 connection status는 `active`, `reauth_required`, `ref_missing`만 유지한다. Reachability/webhook 문제는 health로 분리한다.
- Operator browser 접근은 POST `/operator/session`의 `operatorToken`으로 발급하는 signed HttpOnly `tci_operator_token` cookie를 사용한다.
- `tci_operator_token` cookie에는 raw operator token을 저장하지 않는다.

## 7. 이번 세션에서 얻은 중요한 메모

- `dispatch_enqueued_at`는 outbox가 아니라 outbox-lite marker다.
- `requested_ref_key`는 active uniqueness의 핵심이다. source branch 이름만으로 PR/MR stream을 합치면 안 된다.
- revision 007 migration은 기존 data backfill과 active duplicate preflight가 중요하다.
- optional destructive migration tests는 `TCI_TEST_DATABASE_URL`과 `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1` 없이는 skip된다.
- 전체 pytest warning 1개는 `tests/support/repository_connection_testkit.py`의 `TestRepositoryEvent` dataclass collection warning이다. 기능 실패는 아니다.
- 기존 전체 `ruff check src tests`는 unrelated support measurement scripts의 `E402` 때문에 실패할 수 있다.
- 기존 전체 `mypy src/tci`는 Celery/Kombu missing stubs와 `github_signature.py` nullable issue 때문에 실패할 수 있다.
- `pip_audit`는 현재 workspace에 설치되어 있지 않다.

## 8. 테스트와 검증 상태

최신 전체 Python suite:

- 명령: `PYTHONDONTWRITEBYTECODE=1 pytest -q`
- 결과: `496 passed, 10 skipped, 1 warning in 20.75s`

최신 변경 범위 ruff:

- 명령: `ruff check src/tci/workers/celery_app.py src/tci/web/routes/_common.py src/tci/web/routes/repository_connections.py src/tci/web/routes/repository_scope.py src/tci/settings.py src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py alembic/versions/007_sync_run_active_trigger_guard.py tests/unit/repository_connections/test_repository_ingestion_tasks.py tests/integration/repository_connections/test_operator_connection_pages.py tests/unit/repository_connections/test_settings.py tests/unit/repository_connections/test_repository_sync_run_repository.py tests/unit/repository_connections/test_webhook_sync_task.py tests/unit/repository_connections/test_phase2_foundation.py tests/contract/repository_ingestion/test_github_webhook_contract.py tests/contract/repository_ingestion/test_gitlab_webhook_contract.py`
- 결과: `All checks passed!`

Migration smoke ruff:

- 명령: `ruff check tests/integration/repository_connections/test_phase2_migration_smoke.py`
- 결과: `All checks passed!`

Focused reviewer-follow-up tests:

- running replay recovery, dispatch duplicate idempotency, limiter thread-safety 관련 targeted pack: `35 passed`
- local migration smoke default: `3 skipped`

최종 reviewer loop:

- `python-reviewer`: No blocking findings, approve verdict.
- `security-reviewer`: No security findings.
- `database-reviewer`: No database findings.
- `pr-test-analyzer`: No material remaining test gaps found.

## 9. 다음 세션의 시작 순서

1. `git status --short`와 `git diff --stat`로 현재 diff를 확인한다.
2. `specs/002-gitlab-onprem-connection/tasks.md`의 Phase 6 gate가 ready인지 확인한다.
3. `T044`부터 시작한다. quickstart regression harness와 operator-path duration validation을 추가한다.
4. `T045`로 webhook status-refresh latency validation을 추가한다.
5. `T046`으로 `delivery-evidence.md`, `tasks.md`, `quickstart.md`, 이 handoff의 final FR/SC trace coverage를 갱신한다.
6. 변경 후 `PYTHONDONTWRITEBYTECODE=1 pytest -q`와 focused `ruff check`를 다시 실행한다.
7. reviewer가 필요하면 일반 `reviewer` 없이 지정된 reviewer set만 호출한다.

## 10. 마지막 액션과 바로 다음 액션

마지막 액션:

- reviewer loop clean 결과와 최신 검증 상태를 `tasks.md`, `delivery-evidence.md`, `spec.md`, `data-model.md`, `quickstart.md`, `plan.md`, 이 handoff에 반영했다.

바로 다음 액션:

- Phase 6 `T044` quickstart regression harness부터 TDD로 착수한다.

## 병렬 작업과 소유권

- 구현 소유권은 parent session이 가졌다.
- reviewer loop는 `python-reviewer`, `security-reviewer`, `database-reviewer`, `pr-test-analyzer`가 맡았다.
- 일반 `reviewer`는 사용자 결정에 따라 제외했다.
- 다음 세션에서 Phase 6을 병렬화한다면 quickstart harness(`T044`)와 latency harness(`T045`)는 서로 다른 파일 세트를 소유하게 나누는 것이 좋다.
