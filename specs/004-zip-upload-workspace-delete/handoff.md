# Handoff: ZIP 업로드 스냅샷과 워크스페이스 삭제

## 짧은 요약

004 ZIP 업로드/워크스페이스 삭제 기능은 Phase 2 foundation과 User Story 1의 core Local Upload snapshot unit slice까지 완료됐다.

`tasks.md` 기준 완료 범위는 `T001-T019`, `T023-T026`이다. 이번 세션에서는 ZIP 검증기, Local Upload snapshot creation service, partial archive cleanup, Local Upload manifest metadata, 관련 unit tests와 evidence 갱신까지 끝냈다.

구현 후 `reviewer`, `python-reviewer`, `security-reviewer` 루프를 반복했고 최종 3개 리뷰 모두 `No findings`로 종료했다.

## 현재 상태

- 현재 브랜치: `004-zip-upload-workspace-delete`
- 완료됨: `T001-T019`, `T023-T026`
- 아직 미완료: `T020-T022`, `T027-T035`, `T036-T070`
- 다음 작업: `T020` Local Upload API contract tests 또는 `T027-T030` worker/API entry 개발
- 작업트리는 dirty 상태이며 커밋은 만들지 않았다.
- `rtk git status -sb` 기준 관련 없는 untracked path `mvp1-features/개발방법/`가 있다. 이번 feature scope가 아니므로 건드리지 말아야 한다.
- `T035` 전체 User Story 1 check는 아직 실행할 수 없다. contract/integration/API/UI tasks가 남아 있다.
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-005` 등은 아직 pending이다.

## 이번 세션에서 바뀐 것

- `pilot-git-repo-connection/tests/unit/local_uploads/test_local_zip_extractor.py`를 추가했다.
  - corrupt ZIP, traversal, absolute path, encrypted entry, duplicate logical path, reserved `manifest.json`, zero-file archive, configured limits, dot/empty segment, Windows drive-relative path, compression ratio, directory cap, in-memory cap, file/directory collision을 검증한다.
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/local_zip_extractor.py`를 추가했다.
  - ZIP central-directory preflight, path normalization, unsafe entry rejection, encrypted/special file rejection, compression-ratio guard, configurable in-memory cap, directory metadata extraction을 처리한다.
- `pilot-git-repo-connection/tests/unit/local_uploads/test_create_local_upload_snapshot.py`를 추가했다.
  - success, repeated upload latest selection, validation failure cleanup, storage failure cleanup, empty directory manifest metadata, upload hash mismatch, sanitized failure result를 검증한다.
- `pilot-git-repo-connection/src/tci/domain/services/create_local_upload_snapshot.py`를 추가했다.
  - `mark_processing -> hash 검증 -> extract -> archive store -> manifest write -> create_for_local_upload -> mark_succeeded` 흐름을 구현했다.
  - 실패 시 partial archive를 제거하고 `mark_failed`를 기록하며 active snapshot을 남기지 않는다.
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`에 `remove(snapshot_id=...)` cleanup helper를 추가했다.
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`에 `LocalUploadManifestSource`와 `source.kind=local_upload` manifest metadata를 추가했다.
  - 기존 repository snapshot manifest writer 호출은 유지된다.
- `pilot-git-repo-connection/src/tci/settings.py`에 `local_upload_max_in_memory_bytes` 설정을 추가했다.
  - 기본값은 `DEFAULT_LOCAL_UPLOAD_MAX_UNCOMPRESSED_BYTES`와 동일하게 맞췄다.
- `pilot-git-repo-connection/tests/support/local_upload_testkit.py`에 corrupt/empty ZIP fixture helpers를 추가했다.
- `pilot-git-repo-connection/tests/unit/repository_connections/test_settings.py`에 새 setting 기본값 검증을 추가했다.
- `specs/004-zip-upload-workspace-delete/tasks.md`에서 `T018`, `T019`, `T023-T026`을 완료 처리했다.
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`에 RED/GREEN, regression, static 검증 evidence를 갱신했다.

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/local_zip_extractor.py`
- `pilot-git-repo-connection/src/tci/domain/services/create_local_upload_snapshot.py`
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_manifest_writer.py`
- `pilot-git-repo-connection/src/tci/settings.py`
- `pilot-git-repo-connection/tests/unit/local_uploads/test_local_zip_extractor.py`
- `pilot-git-repo-connection/tests/unit/local_uploads/test_create_local_upload_snapshot.py`
- `pilot-git-repo-connection/tests/support/local_upload_testkit.py`
- `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`

## 꼭 유지해야 할 기준

- Local Upload는 GitHub/GitLab `RepositoryConnection` provider가 아니다.
- Local Upload snapshot은 `CodeSnapshot.source_kind=local_upload`와 `local_upload_id`로 표현한다.
- 기존 GitHub/GitLab provider semantics는 삭제 workspace guard를 제외하고 유지해야 한다.
- ZIP validator는 filesystem extraction을 하지 않고 archive store entry drafts로 넘긴다.
- ZIP path는 raw segment 기준으로 먼저 검사해야 한다. `PurePosixPath` 정규화 뒤에만 검사하면 `./file`, `dir/.`, `C:foo` 같은 경로가 빠질 수 있다.
- ZIP entry count, directory count, file count, size, compression ratio, in-memory processing cap을 유지해야 한다.
- 파일/디렉터리 경로 충돌은 `duplicate_zip_path`로 거부해야 한다.
- Local Upload worker/service는 persisted `LocalUpload.upload_sha256`와 실제 `zip_bytes` hash를 비교해야 한다.
- Raw ZIP contents, private file path, credential, token, secret-bearing URL, raw log는 docs/evidence/final response에 기록하지 않는다.
- Service result failure message도 path/secret-bearing raw exception을 그대로 노출하면 안 된다.
- 실제 operator rehearsal이 필요한 SC 항목은 자동 테스트만으로 완료 처리하지 않는다.
- untracked 파일 확인에는 `git diff --stat`이 부족하다. 항상 `rtk git status -sb`를 먼저 본다.

## 다시 논의하지 말아야 할 결정

- workspace 삭제는 soft delete다.
- 삭제 시 project contents와 snapshot archive 파일은 purge하고, 최소 audit metadata만 남긴다.
- Local Upload는 `RepositoryConnection`으로 만들지 않는다.
- 반복 upload에서는 최신 Local Upload snapshot을 기본값으로 선택한다.
- workspace deletion은 owner/admin 권한과 확인 입력을 요구한다.
- migration revision id는 Alembic 길이 제약 때문에 `010_local_upload_workspace_del`로 둔다.
- Phase 2에서 강화한 existing GitHub/GitLab deleting-workspace guard는 full US2 deletion flow를 대체하지 않는다.
- Empty directory는 `CodeSnapshotFile` row가 아니라 Local Upload manifest `source.directories`와 `LocalUpload.directory_count`로 보존한다.

## 이번 세션에서 얻은 중요한 메모

- `ZipFile(BytesIO(...))`는 central directory를 읽기 전에 내부 entry cap을 적용할 수 없다. 그래서 `_preflight_central_directory_count()`로 EOCD entry count를 먼저 검사한다.
- ZIP path 검증은 raw string segment에서 `""`, `.`, `..`, Windows drive prefix를 먼저 막아야 한다.
- `PurePosixPath`는 `./file`과 `dir/.`를 정규화하므로 raw 검증 전에 쓰면 안 된다.
- Case-insensitive duplicate path와 file/directory collision을 같이 봐야 archive/manifest incoherence를 막을 수 있다.
- `SnapshotArchiveEntryDraft.content`가 bytes를 들고 있으므로 streaming 구현 전까지 `local_upload_max_in_memory_bytes` cap이 필요하다. 현재 기본값은 spec의 uncompressed limit과 맞췄다.
- `CreateLocalUploadSnapshotResult.failure_message`도 향후 API/worker에서 노출될 수 있으므로 generic/sanitized message를 반환해야 한다.
- Fake repository factories를 `AppDependencies`에 넣는 tests는 mypy 대상에 포함하면 `cast(...)`가 필요하다.

## 테스트와 검증 상태

- RED: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py` from `pilot-git-repo-connection/`
  - 결과: expected missing implementation, `17 failed`
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/unit/repository_connections/test_snapshot_storage.py tests/unit/repository_connections/test_settings.py`
  - 결과: `78 passed`
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/local_uploads/test_source_aware_snapshot_repository.py tests/unit/local_uploads/test_workspace_lifecycle_guard.py tests/unit/local_uploads/test_workspace_local_upload_repositories.py`
  - 결과: `40 passed`
- GREEN: `rtk mypy src/tci/domain/services src/tci/infrastructure/snapshots src/tci/infrastructure/persistence src/tci/app.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/unit/local_uploads/test_local_zip_extractor.py`
  - 결과: `No issues found`
- GREEN: `rtk black --check src/tci tests`
- GREEN: `rtk ruff check src/tci tests`
- GREEN: `rtk git diff --check`
- 리뷰 루프:
  - 1차/2차/3차에서 ZIP safety, empty directory, hash integrity, test mypy 관련 findings를 수정했다.
  - 최종 `reviewer`, `python-reviewer`, `security-reviewer`: 모두 `No findings`
- 미검증:
  - `T020-T022` contract/integration tests는 아직 작성하지 않았다.
  - `T027-T034` worker/API/UI는 아직 구현하지 않았다.
  - 실제 PostgreSQL DB에 migration upgrade/downgrade 적용은 아직 하지 않았다.
  - 실제 operator rehearsal은 아직 하지 않았다.

## 다음 세션의 시작 순서

1. `rtk git status -sb`로 dirty/untracked 파일을 확인한다.
2. `specs/004-zip-upload-workspace-delete/tasks.md`와 `delivery-evidence.md`로 완료/미완료 상태를 확인한다.
3. `T020` contract tests를 `pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py`에 RED로 작성한다.
4. `T027` Local Upload ingestion task entry point와 sync test/development fallback을 설계한다.
5. `T028-T030` API schema/route/app registration을 TDD로 구현한다.
6. API가 GREEN이면 `T021-T022` integration tests로 success/failure flow를 고정한다.
7. `T031-T034` snapshot detail serialization과 operator UI는 API/contract가 안정된 뒤 진행한다.

## 마지막 액션과 바로 다음 액션

마지막 액션은 `T018`, `T019`, `T023-T026` 구현, 검증, reviewer loop closure, `tasks.md`/`delivery-evidence.md` 갱신이었다.

바로 다음 액션은 `T020`의 실패 contract test를 `pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py`에 작성하고 RED를 확인하는 것이다.

## 병렬 작업과 소유권

다음 세션에서 병렬 agent를 쓴다면 write ownership은 겹치지 않게 나눈다.

- `T020` 담당: `tests/contract/local_uploads/test_local_upload_contract.py`
- `T027` 담당: `src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- `T028-T030` 담당: `src/tci/api/schemas/local_upload.py`, `src/tci/api/routes/local_uploads.py`, `src/tci/app.py`
- `T021-T022` 담당: `tests/integration/local_uploads/test_local_upload_snapshot_flow.py`, `tests/integration/local_uploads/test_local_upload_failure_flow.py`
- 아직 `T031-T034`는 API surface가 안정된 뒤 시작하는 편이 안전하다.
