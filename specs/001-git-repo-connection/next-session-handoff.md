# 다음 세션 인수인계

## 현재 상태

- `Phase 2`는 끝났다
- `tasks.md` 기준 `T005`부터 `T014`까지 완료 처리했다
- 다음 작업 시작점은 `US1`의 `T015`, `T016`이다
- 아직 `US1` 구현은 시작하지 않았다

## 이번 세션에서 확정한 것

- `T010`, `T012`는 이미 핵심 구현이 있었고, 이번 세션에서는 보강 테스트로 완료 상태를 재확인했다
- `T008`은 `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`, `pilot-git-repo-connection/src/tci/workers/celery_app.py`로 최소 공통 배선을 만들었다
- `T014`는 `pilot-git-repo-connection/src/tci/app.py`로 FastAPI composition root와 공통 의존성 진입점을 만들었다
- `specs/001-git-repo-connection/tasks.md`와 이 문서는 현재 상태에 맞게 갱신했다

## 다음 에이전트가 바로 봐야 할 파일

- 공통 모델과 제약
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
  - `pilot-git-repo-connection/alembic/versions/001_repository_ingestion_core.py`
- Git 및 snapshot 기반
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_ref_resolver.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_readonly_validator.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/git/git_mirror_manager.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`
- 추적성 기반
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/planning_input_reference_repository.py`
  - `pilot-git-repo-connection/src/tci/domain/services/build_traceability_reference.py`
- 이번 세션에서 추가한 공통 배선
  - `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
  - `pilot-git-repo-connection/src/tci/workers/celery_app.py`
  - `pilot-git-repo-connection/src/tci/app.py`
- 다음 구현의 기준 문서
  - `specs/001-git-repo-connection/tasks.md`
  - `specs/001-git-repo-connection/spec.md`
  - `specs/001-git-repo-connection/plan.md`
  - `specs/001-git-repo-connection/data-model.md`
  - `specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
  - `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`

## 꼭 유지해야 할 기준

- `RepositoryConnection.default_ref_type`는 `branch`, `tag`만 허용
- `pull_request_branch`는 연결 기본 ref가 아니라 이벤트성 요청 ref에서만 사용
- 외부 canonical connection 상태는 `active`, `reauth_required`, `ref_missing`만 사용
- `remote_url`은 GitHub Cloud 패턴만 허용하고 userinfo 포함 URL은 차단
- 활성 credential은 `read_only_validated = true`여야 하며 connection당 `active`는 하나만 허용
- `TCI_RUNTIME_ROOT`, `TCI_GIT_MIRROR_ROOT`, `TCI_CODE_SNAPSHOT_ROOT`는 모두 프로젝트 루트 아래여야 함
- `mirror_path`, `archive_path`, `archive_blob_path`는 절대경로와 `..`를 허용하지 않음
- snapshot archive 루트의 `manifest.json`은 예약 파일
- `GitRefResolver`는 tag 해석 시 `refs/tags/<tag>^{}`의 peeled SHA를 우선 사용
- `GitReadonlyValidator`는 의도적으로 보수적이다. `hook declined`, ruleset 차단, 기타 서버 훅 실패를 읽기 전용으로 간주하지 않는다
- `PlanningInputReferenceRepository`는 `specs/<feature>/spec.md`, `specs/<feature>/plan.md`와 `.`/`..` 금지를 전제로 한다
- `GitMirrorManager`는 기존 mirror가 있으면 `origin` URL 갱신 후 `fetch --prune`한다
- `GitMirrorManager`의 subprocess runner에서 `GIT_TERMINAL_PROMPT=0`, `BatchMode=yes`, timeout 가드를 빼면 안 된다
- `SnapshotArchiveStore`는 임시 디렉터리에 먼저 쓰고 마지막에 `replace()`한다
- `SnapshotManifestWriter`는 `archive.snapshot_id`와 `traceability.snapshot_id`가 다르면 실패하고 기존 `manifest.json` overwrite도 막는다

## 이번 세션에서 얻은 유용한 구현 메모

- `repository_ingestion_tasks.py`의 task 함수는 실제 비즈니스 로직이 아니라 registration scaffolding이다
- 다음 스토리에서 실제 서비스 로직을 붙이더라도 stable task name은 그대로 유지하는 편이 안전하다
- `create_celery_app()`은 `TCI_REDIS_URL`이 없으면 실패하도록 만들었다
- `get_celery_app()`은 `@lru_cache`를 쓰므로, 테스트에서 환경 변수를 바꿀 때는 `get_settings.cache_clear()`와 `get_celery_app.cache_clear()`를 같이 호출해야 현재 환경이 반영된다
- `create_app()`은 lifespan에서 runtime 디렉터리를 준비하고 `app.state.settings`, `app.state.dependencies`를 올린다
- `AppDependencies`는 지금 공통 진입점만 만든 상태다. 세션이 필요한 저장소 어댑터는 factory로 들고 있으니 US1에서 실제 DB 세션 wiring을 붙일 때 이 경계를 유지하는 편이 안전하다
- `app.py`는 현재 `git_mirror_manager`의 비공개 심볼인 `_subprocess_git_runner`를 가져다 쓰고 있다. 지금 당장 문제는 없지만, 다음 리팩터링에서는 공용 runner 유틸로 올리거나 명시적 주입으로 바꾸는 편이 좋다

## 테스트와 검증 상태

- 관련 단위 테스트는 마지막 기준으로 `74 passed`
- 이번 세션에서 추가되거나 보강된 테스트
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_git_foundation.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_ingestion_tasks.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_celery_app.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_app.py`
- `test_phase2_migration_smoke.py`는 여전히 조건부 skip 상태다
  - `TCI_TEST_DATABASE_URL` 필요
  - `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1` 필요
  - URL에 `test`가 없으면 실행하지 않음
- 이 환경에서는 `pytest ...` 또는 `python -m pytest ...`가 간헐적으로 `No tests collected`를 출력했다
- 실제 검증은 아래 우회 방식으로 수행하는 편이 안전했다

```bash
python -c "import pytest, sys; sys.exit(pytest.main([
  'tests/unit/repository_connections/test_app.py',
  'tests/unit/repository_connections/test_celery_app.py',
  'tests/unit/repository_connections/test_settings.py',
  'tests/unit/repository_connections/test_phase2_foundation.py',
  'tests/unit/repository_connections/test_git_foundation.py',
  'tests/unit/repository_connections/test_repository_ingestion_tasks.py',
  'tests/unit/repository_connections/test_git_mirror_manager.py',
  'tests/unit/repository_connections/test_snapshot_storage.py',
  '-q',
]))"
```

- `coverage` 도구는 현재 환경에 설치되어 있지 않아 커버리지 수치는 확인하지 못했다

## 다음 세션의 시작 순서

1. `T015`, `T016`로 `US1` contract/integration RED 테스트부터 추가
2. `T017`~`T021`에서 저장소 어댑터와 API schema를 먼저 고정
3. `T022`~`T028`에서 connection 생성, 검증, 기본 ref 변경, 초기 snapshot, 조회 서비스를 구현
4. `T026`~`T030`에서 API route와 운영자 화면 연결
5. `T031`에서 `delivery-evidence.md`에 `US1` 검증 근거 반영

## 한 줄 정리

다음 세션은 `Phase 2` 마무리 세션이 아니라 `US1`을 여는 세션이다. 가장 먼저 `T015`, `T016` RED 테스트로 외부 계약과 통합 흐름을 고정한 뒤 구현으로 들어가는 것이 가장 안전하다.
