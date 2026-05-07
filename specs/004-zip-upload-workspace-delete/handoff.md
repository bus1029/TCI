# Handoff: ZIP 업로드 스냅샷과 워크스페이스 삭제

## 짧은 요약

`004-zip-upload-workspace-delete`는 Phase 2 foundation과 User Story 1 Local Upload MVP가 완료된 상태다.

`tasks.md` 기준 완료 범위는 `T001-T035`다. 이번 세션에서는 `T020-T035`를 TDD로 구현했고, `reviewer`, `python-reviewer`, `security-reviewer` 루프를 수정사항이 없어질 때까지 반복했다. 최종 세 리뷰 모두 `No findings`로 닫혔다.

다음 세션의 자연스러운 시작점은 `T036-T052` User Story 2 workspace deletion이다. 커밋은 아직 만들지 않았다.

## 현재 상태

- 현재 브랜치: `004-zip-upload-workspace-delete`
- 원격 대비 상태: `origin/004-zip-upload-workspace-delete`보다 `ahead 1`
- 작업트리: dirty
- 완료됨: `T001-T035`
- 아직 미구현: `T036-T070`
- User Story 1 Local Upload는 자동화 테스트 기준 독립 동작한다.
- Workspace deletion API/service/UI/purge는 아직 미구현이다.
- GitHub/GitLab/Local Upload mixed-source compatibility 작업은 아직 미구현이다.
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-004`, `SC-005`는 pending이다. 자동 테스트 결과만으로 완료 처리하지 말아야 한다.
- 관련 없는 untracked path `mvp1-features/개발방법/`가 있다. 이번 feature scope가 아니므로 건드리지 말아야 한다.

## 이번 세션에서 바뀐 것

- `pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py`
  - `POST /api/local-uploads`, `GET /api/local-uploads/{uploadId}`, `GET /api/local-uploads/{uploadId}/snapshots/{snapshotId}` contract를 추가했다.
  - sanitized filename, source metadata, limit problem details, Redis queue path, oversized multipart, cookie same-origin, queue staging failure를 검증한다.
- `pilot-git-repo-connection/src/tci/api/schemas/local_upload.py`
  - Local Upload status/response serialization을 추가했다.
- `pilot-git-repo-connection/src/tci/api/routes/local_uploads.py`
  - Local Upload upload/status/snapshot detail API를 추가했다.
  - multipart body는 configured compressed limit + 64KiB까지만 읽는다.
  - Redis 설정이 있으면 pending upload 생성, ZIP metadata preflight, temp ZIP staging, Celery enqueue 후 `202`를 반환한다.
  - Redis 설정이 없으면 test/development fallback으로 snapshot creation을 threadpool에서 동기 실행하고 `201`을 반환한다.
  - cookie-auth POST는 same-origin guard를 통과해야 한다.
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/local_zip_extractor.py`
  - `preflight_local_zip()`를 추가했다.
  - Redis enqueue 전 요청 경로에서는 ZIP file content를 읽지 않고 metadata/central-directory만 검증한다.
- `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
  - `RUN_LOCAL_UPLOAD_SNAPSHOT_TASK_NAME`와 Local Upload worker entry point를 추가했다.
  - worker는 task-supplied path를 신뢰하지 않고 `runtime_root/local-upload-queue/{local_upload_id}.zip`만 사용한다.
  - temp ZIP이 없거나 worker 실패가 나면 Local Upload를 failed로 마킹한다.
- `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
  - Local Upload snapshot detail source metadata를 반환하도록 확장했다.
- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - snapshot detail serializer가 repository source와 Local Upload source를 구분하도록 확장했다.
- `pilot-git-repo-connection/src/tci/web/routes/local_uploads.py`
  - `/local-uploads` form/status page와 upload POST를 추가했다.
  - Redis queue path, sync fallback, queue staging failure를 API와 같은 의미로 처리한다.
- `pilot-git-repo-connection/src/tci/web/templates/local_uploads/index.html`
  - operator Local Upload form, status list, failure panel, latest snapshot link를 추가했다.
- `pilot-git-repo-connection/src/tci/app.py`
  - Local Upload API/web routes를 등록했다.
- 테스트 패키지 충돌 방지를 위해 `tests/contract/__init__.py`, `tests/integration/__init__.py`, `tests/unit/__init__.py`를 추가했다.
- `specs/004-zip-upload-workspace-delete/tasks.md`
  - `T020-T035`를 완료 처리했다.
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
  - RED/GREEN, review remediation, focused regression, lint/typecheck evidence를 최신 결과로 갱신했다.

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `specs/004-zip-upload-workspace-delete/spec.md`
- `specs/004-zip-upload-workspace-delete/plan.md`
- `pilot-git-repo-connection/src/tci/api/routes/local_uploads.py`
- `pilot-git-repo-connection/src/tci/api/schemas/local_upload.py`
- `pilot-git-repo-connection/src/tci/web/routes/local_uploads.py`
- `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/local_zip_extractor.py`
- `pilot-git-repo-connection/src/tci/domain/services/create_local_upload_snapshot.py`
- `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
- `pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py`
- `pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_snapshot_flow.py`
- `pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_failure_flow.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_ingestion_tasks.py`

## 꼭 유지해야 할 기준

- Local Upload는 GitHub/GitLab `RepositoryConnection` provider가 아니다.
- Local Upload snapshot은 `CodeSnapshot.source_kind=local_upload`와 `local_upload_id`로 표현한다.
- 기존 GitHub/GitLab provider semantics는 삭제 workspace guard를 제외하고 유지해야 한다.
- Redis Local Upload 요청 경로는 전체 ZIP file content를 읽지 말아야 한다. 요청 경로는 bounded multipart read, metadata preflight, temp staging, enqueue까지만 한다.
- 실제 ZIP extraction과 snapshot creation은 worker 또는 non-Redis fallback threadpool에서 수행한다.
- Celery `send_task()`는 async route event loop에서 직접 호출하지 말고 threadpool 경계 안에서 호출해야 한다.
- Queue worker는 task kwargs의 ZIP path를 신뢰하지 말아야 한다. `local_upload_id`에서 파생한 queue path만 사용해야 한다.
- Queue staging 실패, queue unavailable, missing temp ZIP은 Local Upload를 pending으로 방치하면 안 된다.
- ZIP validator는 filesystem extraction을 하지 않고 archive store entry drafts로 넘긴다.
- ZIP path는 raw segment 기준으로 먼저 검사해야 한다. `PurePosixPath` 정규화 뒤에만 검사하면 `./file`, `dir/.`, `C:foo` 같은 경로가 빠질 수 있다.
- Raw ZIP contents, private file path, credential, token, secret-bearing URL, raw log는 docs/evidence/final response에 기록하지 않는다.
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-004`, `SC-005`는 자동 테스트만으로 완료 처리하지 않는다.
- untracked 파일 확인에는 `git diff --stat`이 부족하다. 항상 `rtk git status -sb`를 먼저 본다.

## 다시 논의하지 말아야 할 결정

- workspace deletion은 soft delete다.
- 삭제 시 project contents와 snapshot archive 파일은 purge하고, 최소 audit metadata만 남긴다.
- Local Upload는 `RepositoryConnection`으로 만들지 않는다.
- 반복 upload에서는 최신 Local Upload snapshot을 기본값으로 선택한다.
- Empty directory는 `CodeSnapshotFile` row가 아니라 Local Upload manifest `source.directories`와 `LocalUpload.directory_count`로 보존한다.
- Redis enqueue 전 preflight는 full extraction이 아니라 metadata validation이다.
- Non-Redis synchronous fallback은 test/development convenience로 유지하되 threadpool에서 실행한다.
- Phase 2에서 강화한 existing GitHub/GitLab deleting-workspace guard는 full `US2` deletion flow를 대체하지 않는다.
- Migration revision id는 Alembic 길이 제약 때문에 `010_local_upload_workspace_del`로 둔다.

## 이번 세션에서 얻은 중요한 메모

- `ZipFile.infolist()` 기반 metadata validation은 corrupt ZIP, unsafe path, encrypted entry, duplicate path, reserved manifest, size/count limits를 대부분 request path에서 걸러낼 수 있다.
- `archive.read(info)`는 요청 경로에서 호출하지 말아야 한다. 큰 ZIP이면 Redis queue path의 의미가 사라지고 event loop/threadpool 자원을 오래 잡는다.
- `run_in_threadpool()`은 ZIP preflight, temp staging, Celery dispatch, non-Redis fallback snapshot creation에 적용했다.
- `_write_temp_zip_for_queue()`는 `O_EXCL`과 mode `0600`으로 temp ZIP을 만들고, stale queue files는 24시간 기준으로 opportunistic purge한다.
- Queue worker는 temp ZIP을 `finally`에서 삭제한다.
- Missing temp ZIP worker case는 `local_upload_temp_missing`으로 failed 처리한다.
- API queue staging failure는 `503`과 `queue_staging_failed` problem을 반환한다.
- Web queue staging failure는 `503` page와 같은 failure code를 Local Upload에 기록한다.
- `python-multipart` dependency 없이 standard `email.parser.BytesParser`로 multipart를 파싱한다. 현재 목적은 bounded single ZIP upload다.

## 테스트와 검증 상태

- RED: `rtk pytest -q tests/contract/local_uploads/test_local_upload_contract.py` from `pilot-git-repo-connection/`
  - 결과: `/api/local-uploads` 미구현 상태에서 expected `6 failed`
- GREEN: `rtk pytest -q tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py`
  - 결과: `17 passed`
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py`
  - 결과: `42 passed`
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/local_uploads/test_local_upload_failure_flow.py`
  - 결과: `52 passed`
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/unit/repository_connections/test_repository_ingestion_tasks.py tests/unit/repository_connections/test_celery_app.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/local_uploads/test_local_upload_failure_flow.py tests/unit/repository_connections/test_snapshot_traceability.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_scoped_snapshot.py`
  - 결과: `93 passed`
- GREEN: `rtk mypy src/tci/api/routes/local_uploads.py src/tci/api/schemas/local_upload.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/get_code_snapshot_detail.py src/tci/infrastructure/queue/repository_ingestion_tasks.py src/tci/infrastructure/snapshots/local_zip_extractor.py src/tci/web/routes/local_uploads.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/local_uploads/test_local_upload_failure_flow.py`
  - 결과: `No issues found`
- GREEN: `rtk black --check src/tci tests/contract/local_uploads tests/integration/local_uploads tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/repository_connections/test_repository_ingestion_tasks.py tests/unit/repository_connections/test_celery_app.py`
- GREEN: `rtk ruff check src/tci tests/contract/local_uploads tests/integration/local_uploads tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/repository_connections/test_repository_ingestion_tasks.py tests/unit/repository_connections/test_celery_app.py`
- GREEN: `rtk git diff --check`
- Reviewer loop:
  - 1차에서 ZIP task path trust, unbounded multipart, temp retention, cookie CSRF, worker failure bookkeeping이 나왔다.
  - 2차에서 Redis deployments가 worker path를 쓰지 않는 문제가 나왔다.
  - 3차에서 async route blocking, queue staging pending leak, Redis pre-enqueue full extraction, sync Celery dispatch가 나왔다.
  - 모두 수정했고 최종 `reviewer`, `python-reviewer`, `security-reviewer`는 `No findings`다.
- 미검증:
  - 실제 PostgreSQL DB에 migration upgrade/downgrade 적용은 이번 세션에서 다시 실행하지 않았다.
  - 실제 operator rehearsal은 아직 하지 않았다.
  - Full `rtk pytest -q tests/unit tests/contract tests/integration`는 아직 실행하지 않았다.

## 다음 세션의 시작 순서

1. `rtk git status -sb`로 dirty/untracked 상태를 확인한다.
2. 커밋부터 할지, 바로 `T036-T052`를 이어갈지 사용자 의도를 확인한다. 커밋 요청이 없으면 커밋하지 않는다.
3. `specs/004-zip-upload-workspace-delete/tasks.md`에서 `T036-T052` User Story 2 범위를 다시 읽는다.
4. `T036-T039` 테스트를 먼저 작성한다.
   - `pilot-git-repo-connection/tests/contract/workspaces/test_workspace_delete_contract.py`
   - `pilot-git-repo-connection/tests/unit/local_uploads/test_delete_workspace.py`
   - `pilot-git-repo-connection/tests/integration/workspaces/test_workspace_delete_flow.py`
   - `pilot-git-repo-connection/tests/integration/workspaces/test_deleted_workspace_guards.py`
5. RED를 확인한 뒤 `T040-T052` implementation을 진행한다.
6. US2 구현 중 기존 GitHub/GitLab guard를 건드리면 `T035` Local Upload focused checks와 repository connection focused regression을 다시 돌린다.

## 마지막 액션과 바로 다음 액션

마지막 액션은 `T020-T035` 구현, reviewer loop closure, `tasks.md`/`delivery-evidence.md` 갱신, 그리고 이 `handoff.md` 현재화다.

바로 다음 액션은 `rtk git status -sb` 확인 후 `T036` contract test를 RED로 작성하는 것이다. 단, 사용자가 먼저 커밋을 요청하면 현재 `T001-T035` 변경 범위만 검토해서 커밋 메시지를 만들거나 커밋한다.
