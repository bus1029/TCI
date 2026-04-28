# 다음 세션 인수인계

## 짧은 요약

이번 세션에서 `planningInputReferenceId`를 `/docs`에서 직접 발급할 수 있는
bootstrap API를 추가했다.

- 새 API: `POST /api/planning-input-references`
- 목적: 수동 DB insert 없이 `POST /api/repository-connections`까지 이어지는
  operator/manual 테스트 경로 복구
- 상태: contract/integration 테스트 및 reviewer/python-reviewer 최종 `No findings`

이제 다음 세션의 핵심 남은 일은 다시 두 가지로 좁혀졌다.

- 실제 GitHub webhook end-to-end 검증
- operator-facing webhook secret 발급/회전 surface 정리

## 현재 상태

- `planning input reference` bootstrap 경로 추가 완료
  - `POST /api/planning-input-references`
  - `X-TCI-Workspace-Id` 헤더 필수
  - body `workspaceId`는 헤더와 같아야 함
  - 허용 `sourceType`
    - `user_request`
    - `planning_brief`
    - `imported_note`
  - `approvedSpecPath` / `approvedPlanPath`
    - `specs/<feature>/spec.md`
    - `specs/<feature>/plan.md`
    - 같은 feature 디렉터리를 가리켜야 함

- bootstrap 이후 수동 operator 흐름
  1. `POST /api/planning-input-references`
  2. `POST /api/repository-connections`
  3. `POST /api/repository-connections/{connection_id}/scope-rules`
  4. `POST /api/repository-connections/{connection_id}/webhook-secret`
  5. `POST /api/repository-connections/{connection_id}/snapshots`

- snapshot / scope 규칙 관련 현재 동작
  - `scope-rules`는 `POST`를 다시 보내 새 active version을 만든다.
  - scope rule은 이후 생성되는 snapshot부터 적용된다.
  - snapshot `reason` 허용값
    - `manual_initial`
    - `manual_refresh`
  - scope rule을 바꾼 뒤 다시 수동 snapshot을 만들 때는
    `{"reason": "manual_refresh"}`를 쓰면 된다.

- 아직 비어 있을 수 있는 것
  - `/api/repository-connections/{id}/events`
  - `lastProcessedEventAt`
  - `lastProcessedEvent`
  - `traceability.latestEventId`
  - 이유
    - webhook ingestion을 아직 실제 GitHub delivery로 검증하지 않았기 때문

## 이번 세션에서 바뀐 것

- planning input reference API 추가
  - `pilot-git-repo-connection/src/tci/api/routes/planning_input_references.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/planning_input_reference.py`
  - `pilot-git-repo-connection/src/tci/domain/services/create_planning_input_reference.py`
  - `pilot-git-repo-connection/src/tci/app.py`

- OpenAPI / runtime 계약 정리
  - `/api/planning-input-references`는 OpenAPI에서도
    `X-TCI-Workspace-Id`를 필수로 노출한다.
  - 헤더 누락, UUID 형식 오류, header/body workspace mismatch를
    명시적으로 검증한다.

- DB unavailable 처리 추가
  - `session_factory is None`이면 503
  - configured-but-unreachable DB의 `OperationalError`도 503
  - migration/schema 오류까지 503로 숨기지는 않도록
    connection-availability 오류만 번역

- testkit 확장
  - `create_planning_input_reference_payload(...)` helper 추가
  - `create_test_client(..., use_real_repositories=True, database_url=...)`
    경로 추가
  - fake repository뿐 아니라 실제 repository/session path도 검증 가능하게 정리

- 실DB bootstrap integration test 추가
  - Alembic `downgrade base` -> `upgrade head`를 거친 뒤
    `planning-input-references -> repository-connections` 흐름 검증
  - destructive 실행 가드
    - `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1`
    - `TCI_MIGRATION_TEST_DATABASE_URL`
    - `TCI_MIGRATION_TEST_DATABASE_URL_ACK`
      - full DSN exact match
    - `TCI_MIGRATION_TEST_DATABASE_NAME`
      - parsed raw database name exact match

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/001-git-repo-connection/next-session-handoff.md`
- `specs/001-git-repo-connection/quickstart.md`
- `specs/001-git-repo-connection/manual/integration-test-manual.md`
- `pilot-git-repo-connection/src/tci/api/routes/planning_input_references.py`
- `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
- `pilot-git-repo-connection/src/tci/api/routes/github_webhooks.py`
- `pilot-git-repo-connection/src/tci/api/routes/repository_scope.py`
- `pilot-git-repo-connection/src/tci/api/routes/repository_snapshots.py`
- `pilot-git-repo-connection/src/tci/domain/services/create_planning_input_reference.py`
- `pilot-git-repo-connection/src/tci/domain/services/rotate_webhook_secret.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
- `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`

## 꼭 유지해야 할 기준

- webhook intake는 공개 엔드포인트이므로
  `X-TCI-Workspace-Id`를 요구하면 안 된다.
- 반대로 workspace-scoped operator API는
  `X-TCI-Workspace-Id`를 계속 요구해야 한다.
- `POST /api/planning-input-references`는
  header/body workspace mismatch를 허용하면 안 된다.
- `approvedSpecPath` / `approvedPlanPath`는
  repo-relative path여야 하고 같은 feature 디렉터리를 가리켜야 한다.
- webhook secret 평문은 최초 생성/회전 시점에만 1회 노출해야 한다.
- secret rotation grace semantics는 유지해야 한다.
  - `active`
  - `previous_grace`
  - `revoked`
- accepted webhook delivery audit은 이후 bad replay로 덮어쓰면 안 된다.
- scope rule 변경은 “새 active version 생성” 방식으로 유지해야 한다.
- scope rule은 이후 생성되는 snapshot에만 적용되고
  과거 snapshot을 소급 수정하면 안 된다.

## 다시 논의하지 말아야 할 결정

- v1 공식 지원 범위는 GitHub Cloud만 유지한다.
- manual snapshot `reason`은
  `manual_initial`, `manual_refresh`만 허용한다.
- manual snapshot은 operator-trigger 흐름이고,
  `/events`를 채우는 source of truth는 webhook ingestion이다.
- `planningInputReferenceId` bootstrap은
  `/api/planning-input-references`에서 먼저 만든 뒤
  `/api/repository-connections`로 이어간다.

## 중요한 메모

- 현재 코드베이스에서는 `workspace_id`를 external workspace table로
  FK 검증하지 않는다.
  - 따라서 local/manual 테스트에서는 임의 UUID를 써도 된다.
  - 단, `X-TCI-Workspace-Id`와 body `workspaceId`는 같아야 한다.
- scope rule 예시
  - 루트 `.cursor` 디렉터리 제외: `".cursor/**"`
  - 필요하면 `**/.cursor/**`까지 같이 써서 nested `.cursor`도 제외
- scope rule을 바꾼 뒤 다시 snapshot을 만들 때는
  `{"reason": "manual_refresh"}`를 사용하면 된다.
- real DB bootstrap test는 destructive migration을 수행하므로
  반드시 전용 DB에서만 돌려야 한다.

## 테스트와 검증 상태

- bootstrap contract + integration

```bash
cd pilot-git-repo-connection
python -m pytest -q \
  tests/contract/repository_ingestion/test_repository_connection_contract.py \
  tests/integration/repository_connections/test_connection_and_initial_snapshot.py
```

- 마지막 확인 결과
  - `39 passed, 1 skipped`

- 정적 검증

```bash
cd pilot-git-repo-connection
ruff check \
  src/tci/api/routes/planning_input_references.py \
  tests/contract/repository_ingestion/test_repository_connection_contract.py \
  tests/integration/repository_connections/test_connection_and_initial_snapshot.py

python -m mypy \
  src/tci/api/routes/planning_input_references.py \
  src/tci/domain/services/create_planning_input_reference.py
```

- 마지막 확인 결과
  - `ruff` 통과
  - `mypy` 통과

- reviewer 상태
  - `reviewer`: 최종 `No findings`
  - `python-reviewer`: 최종 `No findings`

## 다음 세션의 시작 순서

1. 이 handoff와 `quickstart.md`를 먼저 읽고
   현재 막힘이 bootstrap이 아니라 webhook/operator surface라는 점을 맞춘다.
2. `/api/repository-connections/{connection_id}/webhook-secret`와
   `github_webhooks.py`를 다시 읽는다.
3. 실제 GitHub webhook delivery를 붙여
   `/events`, `lastProcessedEvent*`, `traceability.latestEventId`가
   채워지는지 검증한다.
4. 필요하면 webhook secret operator flow를 `/docs` 기준으로 더 다듬고,
   quickstart/manual 문서를 갱신한다.

## 마지막 액션과 바로 다음 액션

- 마지막 액션
  - `planningInputReferenceId` bootstrap 공백을 API로 메웠다.
  - OpenAPI와 runtime workspace header 계약을 일치시켰다.
  - DB unavailable 경로를 503으로 정리했다.
  - fake/real DB 양쪽 bootstrap 테스트를 보강했다.
  - reviewer / python-reviewer 루프를 돌려 최종 `No findings`를 확인했다.

- 바로 다음 액션
  - 실제 GitHub webhook delivery를 연결한다.
  - event ingestion이 `/events`와 connection detail traceability에
    반영되는지 검증한다.
