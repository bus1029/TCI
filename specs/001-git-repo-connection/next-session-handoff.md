# 다음 세션 인수인계

## 짧은 요약

`US2`가 닫혔다. `tasks.md` 기준으로 `T032`~`T042`가 완료됐고, 범위 규칙 저장 API, 필터 엔진, scoped snapshot, 운영 화면, 검증 증빙까지 현재 코드와 문서에 반영돼 있다. 다음 세션은 `US3`의 webhook 계약과 이벤트 처리(`T043`~`T059`)를 TDD로 시작하면 된다. 시작점은 contract/unit/integration RED 테스트 3개를 먼저 추가하고, 그다음 모델 확장과 webhook 라우트/워커를 잇는 순서가 가장 안전하다.

## 현재 상태

- `Phase 1`, `Phase 2` 완료
- `US1`, `US2` 완료
- `tasks.md` 기준 완료 범위는 `T015`~`T042`
- 남은 범위는 `US3`와 `Phase 6`
- 이번 세션은 실제 구현, 테스트, 운영 화면 추가, 증빙 문서 갱신까지 포함했다

## 이번 세션에서 바뀐 것

- 범위 규칙 저장과 필터 엔진 추가
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/scope_rule_repository.py`
  - `pilot-git-repo-connection/src/tci/domain/services/default_scope_policy.py`
  - `pilot-git-repo-connection/src/tci/domain/services/scope_filter_engine.py`
  - `pilot-git-repo-connection/src/tci/domain/services/evaluate_scope_rule_warning.py`
  - `pilot-git-repo-connection/src/tci/domain/services/save_scope_rules.py`
- 스냅샷 파이프라인에 active scope rule 적용
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
  - snapshot 성공 시 active scope rule을 과거 버전으로 되돌리지 않게 수정함
- scope API와 스키마 추가
  - `pilot-git-repo-connection/src/tci/api/schemas/_base.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_scope.py`
  - `pilot-git-repo-connection/src/tci/api/routes/repository_scope.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- scope 운영 화면 추가
  - `pilot-git-repo-connection/src/tci/web/routes/repository_scope.py`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/scope.html`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
  - `pilot-git-repo-connection/src/tci/app.py`
- US2 테스트 추가
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_scope_contract.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_scope_filter_engine.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_scoped_snapshot.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_scope_pages.py`
  - `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- 작업표와 검증 증빙 갱신
  - `specs/001-git-repo-connection/tasks.md`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

## 다음 에이전트가 먼저 봐야 할 파일

- 다음 시작점
  - `specs/001-git-repo-connection/tasks.md`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`
  - `specs/001-git-repo-connection/quickstart.md`
- `US2` 기준선과 `US3` 진입점
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
  - `pilot-git-repo-connection/src/tci/api/routes/repository_scope.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
  - `pilot-git-repo-connection/src/tci/workers/celery_app.py`
- 다음 테스트 시작점
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_scope_contract.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_scope_filter_engine.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_scoped_snapshot.py`
  - 다음으로 만들 파일: `tests/contract/repository_ingestion/test_github_webhook_contract.py`
  - 다음으로 만들 파일: `tests/unit/repository_connections/test_process_github_event.py`
  - 다음으로 만들 파일: `tests/integration/repository_connections/test_github_webhook_refresh.py`

## 꼭 유지해야 할 기준

- `RepositoryConnection.default_ref_type`는 `branch`, `tag`만 허용
- canonical connection 상태는 `active`, `reauth_required`, `ref_missing`만 사용
- `remote_url`은 GitHub Cloud 패턴만 허용하고 userinfo 포함 URL은 차단
- 활성 credential은 `read_only_validated = true`여야 하며 connection당 `active`는 하나만 허용
- `TCI_RUNTIME_ROOT`, `TCI_GIT_MIRROR_ROOT`, `TCI_CODE_SNAPSHOT_ROOT`는 모두 프로젝트 루트 아래여야 함
- `mirror_path`, `archive_path`, `archive_blob_path`는 절대경로와 `..`를 허용하지 않음
- 루트 `manifest.json`은 논리 경로로는 허용되지만 아카이브 내부에서는 예약 경로로 우회 저장됨
- `POST`, `GET`, `PATCH`, `verify`, `snapshots`, `scope-rules` API는 모두 `X-TCI-Workspace-Id` 헤더를 요구
- `PATCH /api/repository-connections/{connectionId}`는 기본 ref 변경만 지원
- `SaveScopeRulesRequest.maxFileSizeBytes`는 `1` 이상이어야 하며 web 폼도 같은 검증을 따라야 함
- 범위 규칙 우선순위는 하드 제외 경로 -> 사용자 include -> 사용자 exclude -> 파일 타입 -> 바이너리/크기 가드 순서를 유지
- 바이너리, `5 MiB` 초과 파일, 하드 제외 경로는 v1에서 사용자 include가 있어도 계속 제외
- `VERIFY_REPOSITORY_CONNECTION_TASK_NAME`, `RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME`, `RUN_WEBHOOK_SYNC_TASK_NAME`는 stable task name으로 유지

## 다시 논의하지 말아야 할 결정

- v1 공식 지원 범위는 GitHub Cloud만 사용
- `PATCH`에서 credential 교체를 당장 지원하지 않음
- `verify`와 `snapshots`는 Redis 미설정 시 `503`으로 fail-fast
- `UpdateRepositoryConnectionRequest`에서 `credential` 입력은 제거된 상태를 유지
- `US2`에서 scope rule 저장 시 미리보기 실패가 나도 저장 자체는 막지 않고 `warningState = ok`로 저장한다
- snapshot 성공 시 active scope rule을 다시 덮어써 현재 규칙을 과거 버전으로 되돌리지 않는다
- 다음 구현 시작점은 `US3`다. `US2`를 다시 확장하기보다 webhook/event 흐름으로 넘어간다

## 이번 세션에서 얻은 중요한 메모

- `tests/support/repository_connection_testkit.py`는 fake session 기반이라 integration 이름이어도 실제 DB 통합 테스트는 아니다
- 이 환경에서는 `pytest ...` 대신 `python -c "import pytest, sys; sys.exit(pytest.main([...]))"` 형태가 가장 안정적이었다
- HTTPS credential은 여전히 `https://x-access-token:<token>@...` 형태 URL을 Git 인자에 싣는다
- stderr 마스킹과 origin 복구는 넣었지만, argv 노출 자체는 아직 남아 있는 보안 리스크다
- scope 경고 미리보기는 Git 접근 실패를 저장 차단 사유로 쓰지 않는다. 따라서 `warningState = ok`가 항상 “안전”을 뜻하는 것은 아니다
- 운영 화면은 `workspaceId` 쿼리 파라미터와 동일 출처 검사만 있는 상태라 인증/인가 계층이 붙기 전까지는 내부 개발용 기준선으로 봐야 한다
- 저장소 루트에는 이번 작업과 무관한 변경 파일도 많으니 다음 세션에서는 `pilot-git-repo-connection/`과 `specs/001-git-repo-connection/` 범위만 집중하는 편이 안전하다

## 테스트와 검증 상태

- 마지막 확인 기준 `US1` + `US2` 관련 회귀 `45 passed`
- 마지막으로 통과한 검증 범위
  - contract: 저장소 연결 계약, scope rule 저장 계약
  - integration: 연결 생성, 기본 ref 변경, 초기 스냅샷, scoped snapshot, 운영 화면 목록/생성/상세/scope
  - unit: app 배선, scope filter engine
- `coverage` 도구는 현재 환경에 설치되어 있지 않아 수치는 확인하지 못함
- 마이그레이션 스모크 테스트는 여전히 조건부 skip 상태
- 재실행에 사용한 안전한 명령

```bash
python -c "import pytest, sys; sys.exit(pytest.main([
  'tests/contract/repository_ingestion/test_repository_connection_contract.py',
  'tests/contract/repository_ingestion/test_repository_scope_contract.py',
  'tests/integration/repository_connections/test_connection_and_initial_snapshot.py',
  'tests/integration/repository_connections/test_scoped_snapshot.py',
  'tests/integration/repository_connections/test_operator_connection_pages.py',
  'tests/integration/repository_connections/test_operator_scope_pages.py',
  'tests/unit/repository_connections/test_scope_filter_engine.py',
  'tests/unit/repository_connections/test_app.py',
  '-q',
]))"
```

## 다음 세션의 시작 순서

1. `T043`~`T045` RED 테스트부터 추가
   - GitHub webhook 계약
   - PR action gating
   - secret 누락/불일치/서명 실패
   - delivery dedupe와 stale head skip
2. `T046`~`T047`로 모델/마이그레이션 확장
   - `WebhookSecretRevision`
   - `RepositoryEvent`
   - `RepositoryEventCursor`
   - `lastProcessedEvent` summary linkage
3. `T048`~`T056` 구현
   - webhook secret 저장소
   - event/cursor 저장소
   - GitHub signature 검증
   - payload parser
   - webhook intake route
   - enqueue/sync task
4. `T057`~`T059` 조회 모델, 운영 화면, 증빙 정리
   - connection detail summary refresh
   - event timeline
   - `delivery-evidence.md` 갱신

## 마지막 액션과 바로 다음 액션

- 마지막 액션
  - `evaluate_scope_rule_warning.py`를 정리해 미리보기 실패가 scope 저장을 깨지 않도록 수정
  - 관련 contract 테스트를 추가하고 회귀를 `45 passed`까지 다시 확인
  - `tasks.md`, `delivery-evidence.md`를 `US2` 완료 상태로 갱신
- 바로 다음 액션
  - `US3` contract/unit/integration RED 테스트 3개를 먼저 추가

## 병렬 작업과 소유권

- 현재 활성 구현 흐름은 `US3` 시작 전 상태
- 별도 브랜치나 worktree를 새로 만든 작업은 없음
- `US1`, `US2`는 완료됐고, 다음 에이전트는 `US3`부터 이어가면 된다
