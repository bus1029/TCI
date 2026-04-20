# 다음 세션 인수인계

## 짧은 요약

`US1`의 백엔드/API 범위는 끝났다. `tasks.md` 기준으로 `T015`~`T028`이 완료됐고, 현재 남은 `US1` 범위는 운영 화면 `T029`, `T030`과 검증 증빙 `T031`뿐이다. 초기 스냅샷 생성, 스냅샷 상세, 연결 상세의 `latestSnapshot`과 `latestSyncRun`, Redis 미설정 시 `503 fail-fast`까지 현재 코드와 계약에 반영돼 있다. 다음 세션은 `pilot-git-repo-connection/src/tci/web/` 아래 운영 화면 라우트와 템플릿을 TDD로 시작하고, `US1`을 닫은 뒤 멈춰서 검토하면 된다.

## 현재 상태

- `Phase 1`, `Phase 2` 완료
- `US1` 진행 중이지만 백엔드/API/테스트는 완료
- `tasks.md` 기준 완료 범위는 `T015`~`T028`
- 남은 `US1` 범위는 `T029`, `T030`, `T031`
- `US2`, `US3`, `Phase 6`은 아직 본격 착수 전
- 이번 세션은 실제 구현과 테스트, 문서 갱신을 포함했고 계획만 정리한 세션이 아니다

## 이번 세션에서 바뀐 것

- 초기 스냅샷 파이프라인 구현
  - `pilot-git-repo-connection/src/tci/domain/services/create_initial_snapshot.py`
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
  - `pilot-git-repo-connection/src/tci/api/routes/repository_snapshots.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_sync_run_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/code_snapshot_repository.py`
- 연결 상세 투영 보강
  - `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - `latestSnapshot`, `latestSyncRun`, `lastSuccessfulSnapshotAt`, `lastFailedSyncAt` 반영
- 비동기 API `fail-fast` 정책 반영
  - `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/api/routes/repository_snapshots.py`
  - Redis 미설정 시 `verify`, `snapshots`는 `503` 반환
- Git 미러와 스냅샷 저장 보강
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_mirror_manager.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_ref_resolver.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`
  - 임시 인증 URL 사용 뒤 origin 복구
  - 루트 `manifest.json` 파일 보관 지원
  - 아카이브 저장 경로 충돌 차단
- 계약과 테스트 갱신
  - `specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_git_foundation.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_git_mirror_manager.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_snapshot_storage.py`
  - `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- 작업 현황 문서 갱신
  - `specs/001-git-repo-connection/tasks.md`에서 `T015`~`T028` 체크 완료로 반영

## 다음 에이전트가 먼저 봐야 할 파일

- 남은 `US1` 시작점
  - `specs/001-git-repo-connection/tasks.md`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`
- 현재 백엔드 기준선
  - `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/api/routes/repository_snapshots.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
- 운영 화면 작업 진입점
  - `pilot-git-repo-connection/src/tci/web/__init__.py`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/`
  - `pilot-git-repo-connection/src/tci/app.py`
- 참고 문서
  - `specs/001-git-repo-connection/spec.md`
  - `specs/001-git-repo-connection/plan.md`
  - `specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`

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
- 현재 MVP 검토 지점은 `US1` 완료 후이며, `US2`는 그다음에 시작

## 이번 세션에서 얻은 중요한 메모

- `tests/support/repository_connection_testkit.py`는 fake session 기반이라 integration 이름이어도 실제 DB 통합 테스트는 아님
- 이 환경에서는 `pytest ...` 대신 `python -c "import pytest, sys; sys.exit(pytest.main([...]))"` 형태가 가장 안정적이었음
- HTTPS credential은 여전히 `https://x-access-token:<token>@...` 형태 URL을 Git 인자에 싣는다
- stderr 마스킹과 origin 복구는 넣었지만, argv 노출 자체는 아직 남아 있는 보안 리스크다
- 스냅샷 요청 중복 제한, 총 리소스 상한, askpass 기반 인증 전환은 아직 미완이다
- 테스트 실행으로 `__pycache__` 파일이 작업 트리에 같이 잡히니 커밋 전 정리 여부를 확인해야 한다
- 저장소 루트에는 이번 작업과 무관한 변경 파일도 많으니 다음 세션에서는 `pilot-git-repo-connection/`과 `specs/001-git-repo-connection/` 범위만 집중하는 편이 안전하다

## 테스트와 검증 상태

- 마지막 확인 기준 전체 회귀 `94 passed`
- 마지막으로 통과한 검증 범위
  - contract: 저장소 연결과 스냅샷 계약
  - integration: 연결 생성, 기본 ref 변경, 초기 스냅샷, 연결 상세
  - unit: queue task, verify 서비스, settings, Git foundation, mirror manager, snapshot storage
- `coverage` 도구는 현재 환경에 설치되어 있지 않아 수치는 확인하지 못함
- 마이그레이션 스모크 테스트는 여전히 조건부 skip 상태
- 재실행에 사용한 안전한 명령

```bash
python -c "import pytest, sys; sys.exit(pytest.main([
  'tests/integration/repository_connections/test_connection_and_initial_snapshot.py',
  'tests/contract/repository_ingestion/test_repository_connection_contract.py',
  'tests/unit/repository_connections/test_repository_ingestion_tasks.py',
  'tests/unit/repository_connections/test_verify_repository_connection.py',
  'tests/unit/repository_connections/test_settings.py',
  'tests/unit/repository_connections/test_git_foundation.py',
  'tests/unit/repository_connections/test_snapshot_storage.py',
  'tests/unit/repository_connections/test_git_mirror_manager.py',
  '-q',
]))"
```

## 다음 세션의 시작 순서

1. `T029` RED 테스트부터 추가
   - 연결 목록/생성 운영 화면 라우트와 템플릿 기대 동작 정의
2. `T029`, `T030` 구현
   - `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
   - `pilot-git-repo-connection/src/tci/web/routes/repository_connection_detail.py`
   - `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
   - `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
   - `pilot-git-repo-connection/src/tci/app.py`에 라우트 배선 필요 여부 확인
3. `T031`로 `delivery-evidence.md` 갱신
   - `SC-001` 근거와 현재 `US1` 검증 결과를 반영
4. `US1` 완료 기준으로 다시 검토하고 멈춤

## 마지막 액션과 바로 다음 액션

- 마지막 액션
  - `specs/001-git-repo-connection/tasks.md`에 `T015`~`T028` 완료 상태를 반영
  - 이 handoff 문서를 현재 기준으로 전면 갱신
- 바로 다음 액션
  - 운영 화면용 기존 web route/template 구조를 읽고 `T029` RED 테스트부터 시작

## 병렬 작업과 소유권

- 현재 활성 구현 흐름은 `US1` 잔여 `T029`~`T031`
- 별도 브랜치나 worktree를 새로 만든 작업은 없음
- 이전에 `US1` 잔여를 TDD로 시작하려던 시도는 중간에 끊겼고, 실제 코드 변경은 아직 없음
- 다음 에이전트는 `US1` 잔여만 마무리하고 그 지점에서 멈춰 검토를 받는 흐름을 이어야 함
