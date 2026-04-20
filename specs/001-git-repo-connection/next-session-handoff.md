# 다음 세션 인수인계

## 짧은 요약

이번 세션에서 `US3`의 API 중심 웹훅 흐름을 실제로 구현했다. `GitHub webhook intake -> 서명 검증 -> 이벤트 기록/중복·stale 판정 -> sync run 생성 -> worker 실행 -> 연결 상세/이벤트 목록 반영`까지 `pilot-git-repo-connection` 코드에 들어갔고, 관련 테스트는 모두 통과했다. 다만 `specs/001-git-repo-connection/tasks.md`와 `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`는 아직 이번 구현 상태를 반영하지 못해 문서와 코드가 어긋나 있다. 다음 세션은 문서 정합성 복구, secret rotation 운영 가시성 보강, 그리고 큐 전송 시점의 커밋 이후 처리 정리부터 시작하는 것이 가장 안전하다.

## 현재 상태

- `Phase 1`, `Phase 2`, `US1`, `US2`는 완료 상태다.
- 이번 세션에서 `US3`의 핵심 백엔드/API 범위를 구현했다.
- 실제로 반영된 범위
  - webhook 계약 테스트
  - secret 검증과 rejection 분기
  - push/PR 이벤트 파싱
  - dedupe와 stale head 판정
  - 이벤트/커서/웹훅 시크릿 저장소
  - webhook intake API
  - repository event 목록 API
  - 연결 상세의 `webhookHealth`, `lastProcessedEvent`, `latestEventId`
  - webhook worker에서 snapshot 실행과 이벤트 상태 갱신
  - webhook 관련 Alembic 마이그레이션
- 아직 끝나지 않은 범위
  - `T052` webhook secret rotation 서비스
  - `T058` 운영 화면 event timeline 및 detail 화면 확장
  - `T059`, `T063` 증빙 문서 갱신
  - `SC-002`, `SC-005` 검증 근거 채우기
  - webhook enqueue를 커밋 이후로 보내는 구조 정리

## 이번 세션에서 바뀐 것

- 새 파일 추가
  - `pilot-git-repo-connection/src/tci/api/routes/github_webhooks.py`
  - `pilot-git-repo-connection/src/tci/api/routes/repository_events.py`
  - `pilot-git-repo-connection/src/tci/domain/services/process_github_event.py`
  - `pilot-git-repo-connection/src/tci/domain/services/list_repository_events.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/webhook_secret_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_event_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_event_cursor_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/webhooks/github_signature.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/webhooks/github_event_parser.py`
  - `pilot-git-repo-connection/alembic/versions/002_repository_ingestion_webhooks.py`
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_github_webhook_contract.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_github_webhook_refresh.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_process_github_event.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_webhook_sync_task.py`
- 핵심 수정 파일
  - `pilot-git-repo-connection/src/tci/app.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
  - `pilot-git-repo-connection/src/tci/domain/services/create_initial_snapshot.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_sync_run_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
  - `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- 외부 계약 변화
  - `POST /api/webhooks/github/{connectionId}`가 추가됐다.
  - `GET /api/repository-connections/{connectionId}/events`가 추가됐다.
  - 연결 상세 응답에 `webhookHealth`, `lastProcessedEvent`, `traceability.latestEventId`가 실제 값으로 채워진다.
  - snapshot detail의 `triggerEventId`가 webhook-triggered sync일 때 실제 값으로 채워진다.

## 다음 에이전트가 먼저 봐야 할 파일

- 구현 진입점
  - `pilot-git-repo-connection/src/tci/domain/services/process_github_event.py`
  - `pilot-git-repo-connection/src/tci/api/routes/github_webhooks.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
- 저장소/스키마
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
  - `pilot-git-repo-connection/alembic/versions/002_repository_ingestion_webhooks.py`
- 조회 모델
  - `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- 테스트 기준선
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_github_webhook_contract.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_github_webhook_refresh.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_process_github_event.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_webhook_sync_task.py`
- 문서 정합성 복구 대상
  - `specs/001-git-repo-connection/tasks.md`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`
  - `specs/001-git-repo-connection/quickstart.md`

## 꼭 유지해야 할 기준

- `VERIFY_REPOSITORY_CONNECTION_TASK_NAME`, `RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME`, `RUN_WEBHOOK_SYNC_TASK_NAME`는 stable task name으로 유지한다.
- 모든 API 라우트는 기존 규칙대로 `X-TCI-Workspace-Id` 헤더를 유지한다. 단, webhook intake는 공개 엔드포인트라 workspace header를 요구하지 않는다.
- `RepositoryConnection.default_ref_type`는 계속 `branch`, `tag`만 허용한다.
- non-default push는 snapshot 큐잉 대상이 아니라 `record_only`로 남겨야 한다.
- PR webhook snapshot은 source branch 기준이며, snapshot 메타데이터의 `requestedRefType`은 `pull_request_branch`를 보존해야 한다.
- webhook payload의 `repository.full_name`은 연결된 `repository_owner/repository_name`과 반드시 일치해야 한다.
- 저장된 webhook secret은 복호화한 평문으로만 HMAC 비교해야 하며, 응답/로그에 원문을 남기지 말아야 한다.
- 거부된 webhook과 중복 delivery 모두 멱등하게 처리해야 하며, 기존 `syncRunId`/`snapshotId` traceability를 덮어쓰면 안 된다.
- worker 실패 시 이벤트 `processingStatus`가 계속 `queued`로 남아 있으면 안 된다.

## 다시 논의하지 말아야 할 결정

- v1 공식 지원 범위는 GitHub Cloud만 사용한다.
- `PATCH`에서 credential 교체를 당장 지원하지 않는다.
- `verify`와 `snapshots`는 Redis 미설정 시 `503`으로 fail-fast 한다.
- `UpdateRepositoryConnectionRequest`에서 `credential` 입력은 제거된 상태를 유지한다.
- `US2`에서 scope rule 저장 시 미리보기 실패가 나도 저장 자체는 막지 않는다.
- snapshot 성공 시 active scope rule을 과거 버전으로 되돌리지 않는다.
- webhook rejection reason은 `secret_missing`, `secret_mismatch`, `signature_invalid`로 고정한다.
- `push`와 허용된 `pull_request` action만 sync 후보이며, 그 외 PR action은 `record_only`로 남긴다.

## 이번 세션에서 얻은 중요한 메모

- `tests/support/repository_connection_testkit.py`는 fake session 기반이라 integration 이름이어도 실제 DB 통합 테스트는 아니다.
- 이 환경에서는 `pytest ...`보다 `python -c "import pytest, sys; sys.exit(pytest.main([...]))"` 형태가 가장 안정적이었다.
- 테스트 실행 중 `pilot-git-repo-connection/src/tci/infrastructure/persistence/__pycache__/models.cpython-313.pyc`가 수정됐다. 코드 파일은 아니지만 working tree를 볼 때 잡음으로 보일 수 있다.
- 저장소 루트에는 이번 작업과 무관한 변경도 많다. 다음 세션은 `pilot-git-repo-connection/`과 관련 spec 문서 범위만 집중하는 편이 안전하다.
- 현재 코드에는 webhook enqueue가 트랜잭션 커밋 전에 호출되는 구조가 남아 있다. 테스트는 통과하지만 운영 race 가능성이 있어 다음 세션 첫 리팩터링 후보다.
- `get_repository_connection_detail()`의 secret rotation 운영 가시성 값은 아직 placeholder다. 응답 shape는 있으나 실제 계산은 안 붙었다.
- `tasks.md`는 여전히 `T043`~`T059`를 대부분 미완료로 표시한다. 실제 구현과 문서 상태가 어긋난다.

## 테스트와 검증 상태

- 마지막 전체 회귀 결과
  - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion','tests/integration/repository_connections','tests/unit/repository_connections','-q']))"` -> `147 passed, 1 skipped`
- 이번 세션에서 추가한 테스트
  - Contract
    - `tests/contract/repository_ingestion/test_github_webhook_contract.py`
  - Integration
    - `tests/integration/repository_connections/test_github_webhook_refresh.py`
  - Unit
    - `tests/unit/repository_connections/test_process_github_event.py`
    - `tests/unit/repository_connections/test_webhook_sync_task.py`
- 웹훅 관련 집중 검증
  - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion/test_github_webhook_contract.py','tests/unit/repository_connections/test_process_github_event.py','tests/unit/repository_connections/test_webhook_sync_task.py','tests/integration/repository_connections/test_github_webhook_refresh.py','-q']))"` -> `16 passed`
- 린트
  - 이번 세션에서 수정한 파일 기준 `ReadLints` 오류 없음
- 아직 실행 못 한 것
  - 실제 DB migration apply/rollback 스모크
  - secret rotation service가 붙은 뒤의 `SC-005` 운영 시나리오
  - event timeline 운영 화면 및 quickstart 전체 플로우

## 다음 세션의 시작 순서

1. `tasks.md`와 `delivery-evidence.md`를 실제 코드 상태에 맞게 갱신한다.
   - 최소한 이번 세션에서 구현한 `T043`~`T051`, `T053`~`T057` 범위의 상태를 다시 판정해야 한다.
   - `T052`, `T058`, `T059`, `T060`~`T063`는 아직 남은 범위로 정리해야 한다.
2. webhook enqueue를 커밋 이후로 보내는 구조로 정리한다.
   - 현재는 `process_github_event()` 안에서 task 전송이 일어난다.
   - `on-commit` 또는 outbox 형태로 바꾸는 편이 안전하다.
3. secret rotation 운영 가시성을 실제 값으로 채운다.
   - `graceUntil`
   - `previousSecretDeliveriesDuringGrace`
   - `lastPreviousSecretAcceptedAt`
4. 운영 화면 범위를 마저 구현한다.
   - `T058`의 event timeline route와 template
   - detail 화면에서 event/history 노출
5. `delivery-evidence.md`와 quickstart를 갱신하고 `SC-002`, `SC-005` 근거를 채운다.

## 마지막 액션과 바로 다음 액션

- 마지막 액션
  - webhook schema migration `002_repository_ingestion_webhooks.py`를 추가했다.
  - PR source branch snapshot 메타데이터 보존과 snapshot detail의 `triggerEventId` 연결을 맞췄다.
  - 전체 저장소 연결 회귀를 다시 돌려 `147 passed, 1 skipped`를 확인했다.
- 바로 다음 액션
  - `specs/001-git-repo-connection/tasks.md`와 `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`부터 현재 구현 상태에 맞게 갱신한다.

## 병렬 작업과 소유권

- 현재 활성 구현 흐름은 `001-git-repo-connection`의 `US3` 백엔드/API 후반부다.
- 별도 브랜치나 worktree를 새로 만든 작업은 없다.
- 다음 에이전트는 새 기능 구현을 무작정 이어가기보다, 먼저 문서 정합성과 남은 리스크 정리를 이어야 한다.
