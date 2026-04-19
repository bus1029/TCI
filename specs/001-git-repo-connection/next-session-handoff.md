# 다음 세션 인수인계

## 짧은 요약

`US1`의 첫 구현 사이클에서 저장소 자격 증명을 재사용 가능한 암호화 값으로 저장하도록 바꿨고, 기본 ref 변경과 `verify`가 저장된 활성 credential을 다시 사용하도록 연결했다. 새 `verify` 서비스와 Celery 위임 경로를 붙여 `active`, `reauth_required`, `ref_missing` 상태 전이는 코드상 구현됐다. 다만 `verify` HTTP 엔드포인트는 여전히 Redis가 있을 때만 실제 작업을 enqueue하고, Redis가 없으면 `202`만 반환한다. 초기 snapshot, snapshot detail, `latestSnapshot` 실데이터, 운영 화면, `tasks.md` 체크박스 갱신은 아직 남아 있다.

## 현재 상태

- `Phase 2`는 끝났고, `US1`은 진행 중이다.
- `tasks.md`의 체크박스는 아직 `T015` 이후가 미완료로 남아 있지만, 실제 코드는 `T015`, `T016`, `T017`, `T018`, `T021`, `T022`, `T023`, `T026` 일부까지는 이미 열려 있다.
- 이번 세션에서 실제 구현을 했다. 문서 정리만 한 세션이 아니다.
- 초기 snapshot 생성, snapshot detail 조회, `latestSnapshot` 채우기, `lastSuccessfulSnapshotAt`/`lastFailedSyncAt` 실투영, 운영 화면은 아직 미구현이다.

## 이번 세션에서 바뀐 것

- 저장소 credential 저장 방식:
  - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - `pilot-git-repo-connection/src/tci/settings.py`
  - `.env.example`
  - `pyproject.toml`
- 위 변경으로 `TCI_CREDENTIAL_ENCRYPTION_KEY`를 이용해 credential secret을 Fernet으로 암호화 저장한다.
- 기본 ref 변경 시 저장된 credential 재사용:
  - `pilot-git-repo-connection/src/tci/domain/services/update_default_ref.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/credential_revision_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- 재검증 서비스 추가:
  - 새 파일 `pilot-git-repo-connection/src/tci/domain/services/verify_repository_connection.py`
  - active credential이 없거나 복호화 실패/인증 실패면 `reauth_required`
  - 기본 ref가 사라졌으면 `ref_missing`
  - 검증 성공이면 `active`
- Celery 위임 경로 보강:
  - `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
  - `verify` task는 이제 `workspace_id`, `connection_id`를 받아 실제 `verify_repository_connection()`을 호출한다.
- Git 오류 문자열 마스킹:
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_ref_resolver.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_readonly_validator.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_mirror_manager.py`
  - `https://x-access-token:...@`와 basic auth 흔적은 에러 detail에서 `[REDACTED]`로 마스킹한다.
- OpenAPI 계약 정리:
  - `specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
  - `PATCH /api/repository-connections/{connectionId}`의 `credential` 입력은 현재 구현과 맞지 않아 계약에서 제거했다.
- 테스트 보강:
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_verify_repository_connection.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_ingestion_tasks.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_settings.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_git_foundation.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `pilot-git-repo-connection/tests/__init__.py`
  - `pilot-git-repo-connection/tests/support/__init__.py`

## 다음 에이전트가 먼저 봐야 할 파일

- 구현 진입점:
  - `pilot-git-repo-connection/src/tci/domain/services/verify_repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/update_default_ref.py`
  - `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
- API/워커 배선:
  - `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
  - `pilot-git-repo-connection/src/tci/workers/celery_app.py`
  - `pilot-git-repo-connection/src/tci/app.py`
- Git/보안 관련 인프라:
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_ref_resolver.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_readonly_validator.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_mirror_manager.py`
- 저장소 계층:
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/credential_revision_repository.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
  - `pilot-git-repo-connection/alembic/versions/001_repository_ingestion_core.py`
- 다음 구현 기준 문서:
  - `specs/001-git-repo-connection/tasks.md`
  - `specs/001-git-repo-connection/spec.md`
  - `specs/001-git-repo-connection/plan.md`
  - `specs/001-git-repo-connection/data-model.md`
  - `specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/implementation-reference-guide.md`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

## 꼭 유지해야 할 기준

- `RepositoryConnection.default_ref_type`는 `branch`, `tag`만 허용한다.
- canonical connection 상태는 `active`, `reauth_required`, `ref_missing`만 사용한다.
- `remote_url`은 GitHub Cloud 패턴만 허용하고 userinfo 포함 URL은 차단한다.
- 활성 credential은 `read_only_validated = true`여야 하며 connection당 `active`는 하나만 허용한다.
- `TCI_RUNTIME_ROOT`, `TCI_GIT_MIRROR_ROOT`, `TCI_CODE_SNAPSHOT_ROOT`는 모두 프로젝트 루트 아래여야 한다.
- `mirror_path`, `archive_path`, `archive_blob_path`는 절대경로와 `..`를 허용하지 않는다.
- `manifest.json`은 snapshot archive 루트의 예약 파일이다.
- `GitRefResolver`는 tag 해석 시 `refs/tags/<tag>^{}`의 peeled SHA를 우선 사용한다.
- `GitReadonlyValidator`는 `hook declined`, ruleset 차단, 기타 서버 훅 실패를 읽기 전용으로 간주하지 않는다.
- `PlanningInputReferenceRepository`는 `specs/<feature>/spec.md`, `specs/<feature>/plan.md` 경로와 `.`/`..` 금지를 전제로 한다.
- `GitMirrorManager`의 subprocess runner에서는 `GIT_TERMINAL_PROMPT=0`, `BatchMode=yes`, timeout 가드를 빼면 안 된다.
- `POST`, `GET`, `PATCH`, `verify` 저장소 연결 API는 모두 `X-TCI-Workspace-Id` 헤더를 요구한다.
- `POST /api/repository-connections`는 `planningInputReferenceId`를 반드시 받는다.
- `VERIFY_REPOSITORY_CONNECTION_TASK_NAME`, `RUN_MANUAL_SNAPSHOT_SYNC_TASK_NAME`, `RUN_WEBHOOK_SYNC_TASK_NAME`는 stable task name으로 유지한다.
- `PATCH /api/repository-connections/{connectionId}`는 현재 기본 ref 변경만 지원한다. credential 교체로 오해하게 만들면 안 된다.

## 다시 논의하지 말아야 할 결정

- v1 공식 지원 범위는 GitHub Cloud만이다.
- `PATCH`에서 credential 교체를 당장 지원하지 않는다.
- `verify` task name과 queue 이름은 바꾸지 않는다.
- `webhookSecret`은 현재 `US1` 최소 슬라이스의 필수 입력이 아니다.
- `UpdateRepositoryConnectionRequest`에서 `credential` 입력은 제거된 상태가 현재 구현과 일치한다.

## 이번 세션에서 얻은 중요한 메모

- `verify_repository_connection.py`는 검증 전후 DB 세션을 분리했다. 외부 Git 호출 중 세션을 물고 있지 않게 유지하려는 의도다.
- `TCI_CREDENTIAL_ENCRYPTION_KEY`는 형식을 `load_settings()`에서 검증한다. 잘못된 키는 설정 로딩 시점에 실패해야 한다.
- `create_repository_connection.py`는 원격 Git 호출 전에 encryption key 검증이 끝나도록 secret 암호화를 앞당겼다.
- `tests/support/repository_connection_testkit.py`는 fake session/fake repository 기반이다. integration 이름이지만 실제 DB 통합 테스트는 아니다.
- `pytest ...` 또는 `python -m pytest ...`는 이 환경에서 여전히 `No tests collected`를 출력할 수 있다. `tests/__init__.py`를 추가했지만 이 현상은 해결되지 않았다.
- HTTPS credential은 여전히 `https://x-access-token:<token>@...` 형태로 Git 명령 인자에 실린다. stderr 마스킹은 넣었지만, argv 노출 리스크는 아직 남아 있다.
- SSH 바인딩은 아직 프로세스 전역 `GIT_SSH_COMMAND`를 쓰므로 전역 lock으로 직렬화한다. 최종형은 요청별 subprocess env override다.
- `verify` HTTP 엔드포인트는 Redis가 없으면 실제 검증 없이 `202`만 반환한다. 코드상 의도와 quickstart 기대가 다를 수 있으니 다음 세션에서 정리해야 한다.

## 테스트와 검증 상태

- 이번 세션 마지막 기준으로 관련 회귀 `55 passed`.
- 이번 세션에서 특히 확인한 것:
  - 저장된 credential을 이용한 기본 ref 재검증
  - `verify`의 `active`, `reauth_required`, `ref_missing` 상태 전이
  - legacy/손상 secret 복호화 실패 시 `reauth_required` 전이
  - `TCI_CREDENTIAL_ENCRYPTION_KEY` 형식 검증
  - `verify` task의 workspace-scoped 위임
  - Git stderr의 token 마스킹
- `test_phase2_migration_smoke.py`는 여전히 조건부 skip 상태다.
  - `TCI_TEST_DATABASE_URL` 필요
  - `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1` 필요
  - URL에 `test`가 없으면 실행하지 않음
- `coverage` 도구는 현재 환경에 설치되어 있지 않아 커버리지 수치는 확인하지 못했다.
- 이 환경에서 안전했던 재실행 명령:

```bash
python -c "import pytest, sys; sys.exit(pytest.main([
  'tests/integration/repository_connections/test_connection_and_initial_snapshot.py',
  'tests/contract/repository_ingestion/test_repository_connection_contract.py',
  'tests/unit/repository_connections/test_repository_ingestion_tasks.py',
  'tests/unit/repository_connections/test_verify_repository_connection.py',
  'tests/unit/repository_connections/test_settings.py',
  'tests/unit/repository_connections/test_git_foundation.py',
  '-q',
]))"
```

## 다음 세션의 시작 순서

1. `T024`, `T025`, `T027` 방향으로 초기 snapshot 생성과 snapshot detail을 구현한다.
   - `create_initial_snapshot.py`
   - `build_code_snapshot.py`
   - `repository_snapshots.py`
   - `get_code_snapshot_detail.py`
2. `T028` 방향으로 connection detail의 `latestSnapshot`, `lastSuccessfulSnapshotAt`, `lastFailedSyncAt`를 실제 데이터로 채운다.
3. `verify` HTTP 경로의 Redis 미설정 동작을 정리한다.
   - 지금은 Redis가 없으면 실제 재검증 없이 `202`만 반환한다.
   - 동기 fallback을 넣을지, 계약을 명시적으로 유지할지 결정이 필요하다.
4. HTTPS credential이 Git argv에 직접 실리는 구조를 `askpass` 또는 env 기반으로 줄일지 검토한다.
5. `tasks.md` 체크 상태와 `delivery-evidence.md`를 현재 구현 상태에 맞게 갱신한다.

## 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - `specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`에서 `PATCH`의 `credential` 입력을 제거했고, 현재 상태에 맞게 이 handoff 문서를 갱신했다.
- 바로 다음 액션:
  - `repository_sync_run_repository.py`, `code_snapshot_repository.py`, `create_initial_snapshot.py` 설계를 읽고 RED 테스트부터 추가한다.

## 병렬 작업과 소유권

- 현재 활성 구현 흐름은 이 저장소의 `US1` 계속 구현이다.
- 별도 브랜치나 worktree를 새로 만든 작업은 없다.
- 다음 에이전트는 이 문서 기준으로 `초기 snapshot 파이프라인` 작업을 그대로 이어가면 된다.
