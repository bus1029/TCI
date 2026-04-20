# 다음 세션 인수인계

## 짧은 요약

`US1`이 닫혔다. `tasks.md` 기준으로 `T015`~`T031`이 완료됐고, 저장소 연결/API/초기 스냅샷/운영 화면/검증 증빙까지 현재 코드와 문서에 반영돼 있다. 다음 세션은 `US2`의 범위 규칙(`T032`~`T042`)을 TDD로 시작하면 된다.

## 현재 상태

- `Phase 1`, `Phase 2` 완료
- `US1` 완료
- `tasks.md` 기준 완료 범위는 `T015`~`T031`
- `US2`, `US3`, `Phase 6`은 아직 본격 착수 전
- 이번 세션은 실제 구현, 테스트, 검증 문서 갱신까지 포함했다

## 이번 세션에서 바뀐 것

- 운영 화면 추가
  - `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/web/routes/repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/web/routes/_common.py`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
  - `pilot-git-repo-connection/src/tci/app.py`
- 운영 화면 조회 기반 추가
  - `pilot-git-repo-connection/src/tci/domain/services/list_repository_connections.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- 운영 화면 테스트와 보안 보강
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
  - 오류 재렌더링 시 `credentialSecret` 재노출 차단
  - 동일 출처 검사 추가
  - web route는 OpenAPI 스키마에서 제외
- 검증 증빙과 작업표 갱신
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`
  - `pilot-git-repo-connection/tests/support/measure_us1_first_snapshot.py`
  - `specs/001-git-repo-connection/tasks.md`

## 다음 에이전트가 먼저 봐야 할 파일

- 다음 시작점
  - `specs/001-git-repo-connection/tasks.md`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`
  - `specs/001-git-repo-connection/quickstart.md`
- 현재 `US1` 기준선
  - `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/api/routes/repository_snapshots.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
- 운영 화면 기준선
  - `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/web/routes/repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`

## 꼭 유지해야 할 기준

- `RepositoryConnection.default_ref_type`는 `branch`, `tag`만 허용
- canonical connection 상태는 `active`, `reauth_required`, `ref_missing`만 사용
- `remote_url`은 GitHub Cloud 패턴만 허용하고 userinfo 포함 URL은 차단
- 활성 credential은 `read_only_validated = true`여야 하며 connection당 `active`는 하나만 허용
- `TCI_RUNTIME_ROOT`, `TCI_GIT_MIRROR_ROOT`, `TCI_CODE_SNAPSHOT_ROOT`는 모두 프로젝트 루트 아래여야 함
- `mirror_path`, `archive_path`, `archive_blob_path`는 절대경로와 `..`를 허용하지 않음
- 루트 `manifest.json`은 논리 경로로는 허용되지만 아카이브 내부에서는 예약 경로로 우회 저장됨
- `POST`, `GET`, `PATCH`, `verify`, `snapshots` 관련 API는 모두 `X-TCI-Workspace-Id` 헤더를 요구
- `PATCH /api/repository-connections/{connectionId}`는 기본 ref 변경만 지원
- `VERIFY_REPOSITORY_CONNECTION_TASK_NAME`, `RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME`, `RUN_WEBHOOK_SYNC_TASK_NAME`는 stable task name으로 유지

## 다시 논의하지 말아야 할 결정

- v1 공식 지원 범위는 GitHub Cloud만 사용
- `PATCH`에서 credential 교체를 당장 지원하지 않음
- `verify`와 `snapshots`는 Redis 미설정 시 `503`으로 fail-fast
- `UpdateRepositoryConnectionRequest`에서 `credential` 입력은 제거된 상태를 유지
- 현재 MVP 검토 지점은 `US1` 완료 후이며, 다음 구현 시작점은 `US2`

## 이번 세션에서 얻은 중요한 메모

- `tests/support/repository_connection_testkit.py`는 fake session 기반이라 integration 이름이어도 실제 DB 통합 테스트는 아님
- 이 환경에서는 `pytest ...` 대신 `python -c "import pytest, sys; sys.exit(pytest.main([...]))"` 형태가 가장 안정적이었다
- HTTPS credential은 여전히 `https://x-access-token:<token>@...` 형태 URL을 Git 인자에 싣는다
- stderr 마스킹과 origin 복구는 넣었지만, argv 노출 자체는 아직 남아 있는 보안 리스크다
- 스냅샷 요청 중복 제한, 총 리소스 상한, askpass 기반 인증 전환은 아직 미완이다
- 운영 화면은 `workspaceId` 쿼리 파라미터와 동일 출처 검사만 있는 상태라 인증/인가 계층이 붙기 전까지는 내부 개발용 기준선으로 봐야 한다
- 저장소 루트에는 이번 작업과 무관한 변경 파일도 많으니 다음 세션에서는 `pilot-git-repo-connection/`과 `specs/001-git-repo-connection/` 범위만 집중하는 편이 안전하다

## 테스트와 검증 상태

- 마지막 확인 기준 `US1` 관련 회귀 `34 passed`
- 마지막으로 통과한 검증 범위
  - contract: 저장소 연결 계약
  - integration: 연결 생성, 기본 ref 변경, 초기 스냅샷, 연결 상세, 운영 화면 목록/생성/상세
  - unit: app 배선
- `coverage` 도구는 현재 환경에 설치되어 있지 않아 수치는 확인하지 못함
- 마이그레이션 스모크 테스트는 여전히 조건부 skip 상태
- 재실행에 사용한 안전한 명령

```bash
python -c "import pytest, sys; sys.exit(pytest.main([
  'tests/integration/repository_connections/test_operator_connection_pages.py',
  'tests/integration/repository_connections/test_connection_and_initial_snapshot.py',
  'tests/unit/repository_connections/test_app.py',
  'tests/contract/repository_ingestion/test_repository_connection_contract.py',
  '-q',
]))"
```

## 다음 세션의 시작 순서

1. `T032`~`T034` RED 테스트부터 추가
   - scope rule 저장 계약
   - 필터 우선순위와 hard exclude 정책
   - 빈 결과 경고/차단과 scoped snapshot traceability
2. `T035`~`T040` 구현
   - scope rule 저장소
   - 경고 평가
   - 기본 hard exclude 정책
   - 필터 엔진
   - snapshot builder의 scope rule 통합
   - API 스키마/라우트
3. `T041` 운영 화면
   - `scope.html`과 관련 web route 추가
4. `T042`로 `delivery-evidence.md` 갱신
   - `SC-004`와 `NO_INCLUDED_FILES` 근거 반영

## 마지막 액션과 바로 다음 액션

- 마지막 액션
  - `specs/001-git-repo-connection/tasks.md`에 `T029`~`T031` 완료 상태를 반영
  - `delivery-evidence.md`에 `US1` 검증 근거와 `SC-001` 재현 명령을 반영
- 바로 다음 액션
  - `US2` contract/unit/integration RED 테스트부터 시작

## 병렬 작업과 소유권

- 현재 활성 구현 흐름은 `US2` 시작 전 상태
- 별도 브랜치나 worktree를 새로 만든 작업은 없음
- `US1`은 완료됐고, 다음 에이전트는 `US2`를 시작하기 전 현재 MVP 기준선을 먼저 검토해도 된다
