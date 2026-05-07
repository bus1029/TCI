# Handoff: ZIP 업로드 스냅샷과 워크스페이스 삭제

## 짧은 요약

`004-zip-upload-workspace-delete`는 Phase 2 foundation, User Story 1 Local Upload MVP, User Story 2 workspace deletion이 완료된 상태다.

`tasks.md` 기준 완료 범위는 `T001-T052`다. 이번 세션에서는 `T036-T052`를 TDD로 구현했고, `reviewer`, `security-reviewer`, `database-reviewer`, `python-reviewer` 루프를 수정사항이 없어질 때까지 반복했다. 최종 리뷰는 모두 `No findings`로 닫혔다.

다음 세션의 자연스러운 시작점은 `T053-T063` User Story 3 mixed-source compatibility다. 커밋은 아직 만들지 않았다.

## 현재 상태

- 현재 브랜치: `004-zip-upload-workspace-delete`
- 원격 대비 상태: `origin/004-zip-upload-workspace-delete`보다 `ahead 2`
- 작업트리: dirty
- 완료됨: `T001-T052`
- 아직 미구현: `T053-T070`
- User Story 1 Local Upload는 자동화 테스트 기준 독립 동작한다.
- User Story 2 workspace deletion은 자동화 테스트 기준 독립 동작한다.
- GitHub/GitLab/Local Upload mixed-source compatibility 작업은 아직 미구현이다.
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-004`, `SC-005`는 pending이다. 자동 테스트 결과만으로 완료 처리하지 말아야 한다.
- 관련 없는 untracked path `mvp1-features/개발방법/`가 있다. 이번 feature scope가 아니므로 건드리지 말아야 한다.

## 이번 세션에서 바뀐 것

- `pilot-git-repo-connection/src/tci/domain/services/delete_workspace.py`
  - workspace deletion impact, owner/admin authorization, confirmation validation, soft delete, purge, audit record, deleted-state response를 구현했다.
  - 삭제 confirmation은 `DELETE {workspace_id}` 형식이다.
  - 삭제는 `ACTIVE -> DELETING -> DELETED` 전이를 사용하고, purge 실패 시 `DELETING`과 최소 metadata를 남겨 재시도 가능하게 한다.
- `pilot-git-repo-connection/src/tci/api/schemas/workspace.py`
  - deletion impact, delete response, deleted workspace status schema를 추가했다.
- `pilot-git-repo-connection/src/tci/api/routes/workspaces.py`
  - `GET /api/workspaces/{workspaceId}/deletion-impact`
  - `DELETE /api/workspaces/{workspaceId}`
  - 삭제된 workspace 상태 조회 응답을 추가했다.
- `pilot-git-repo-connection/src/tci/web/routes/workspaces.py`
  - operator deletion confirmation flow, delete submit, deleted-state page route를 추가했다.
- `pilot-git-repo-connection/src/tci/web/templates/workspaces/delete.html`
  - 삭제 영향 요약, confirmation 입력, 삭제 불가/권한 실패 상태를 표시한다.
- `pilot-git-repo-connection/src/tci/web/templates/workspaces/deleted.html`
  - 삭제 완료 workspace의 최소 상태와 다음 액션을 표시한다.
- `pilot-git-repo-connection/src/tci/app.py`
  - workspace API/web routes를 등록했다.
- `pilot-git-repo-connection/src/tci/api/operator_auth.py`
  - client header를 신뢰하지 않는 `OperatorPrincipal`을 추가했다.
  - operator id/role은 server settings에서 읽는다.
- `pilot-git-repo-connection/src/tci/settings.py`
  - `TCI_OPERATOR_ID`, `TCI_OPERATOR_ROLE` 설정을 추가했다.
  - 기본 role은 `viewer`이며, 테스트 설정은 필요한 곳에서 `admin`을 명시한다.
- `pilot-git-repo-connection/src/tci/api/routes/local_uploads.py`
  - cookie-auth unsafe method same-origin guard를 missing Origin/Referer에서 fail closed로 강화했다.
  - deleting/deleted workspace에서 Local Upload mutation을 차단한다.
- `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
  - deleting/deleted workspace에서 repository connection create/verify/detail mutation을 차단한다.
- `pilot-git-repo-connection/src/tci/api/routes/repository_candidates.py`
  - deleting/deleted workspace에서 candidate/manual repository creation path를 차단한다.
- `pilot-git-repo-connection/src/tci/domain/services/verify_repository_connection.py`
  - worker/service 경계에 active workspace guard를 추가했다.
  - queued verify가 deletion 시작 후 connection 상태를 다시 변경하지 못하게 했다.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/workspace_repository.py`
  - deletion record 생성/갱신과 status transition helper를 확장했다.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/code_snapshot_repository.py`
  - workspace delete 시 snapshot metadata 정리 경로를 추가했다.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/local_upload_repository.py`
  - workspace delete 시 Local Upload metadata 정리 경로를 추가했다.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
  - workspace delete 시 repository connection metadata, active scope, credential refs, webhook refs, event cursor, sync run refs, repository event refs를 정리한다.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/planning_input_reference_repository.py`
  - workspace delete 시 legacy planning input references를 정리한다.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
  - `fk_local_upload_latest_snapshot_owner`를 deferrable FK로 조정했다.
- `pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py`
  - `fk_local_upload_latest_snapshot_owner`를 `deferrable=True, initially="DEFERRED"`로 맞췄다.
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`
  - workspace snapshot archive, Local Upload queue ZIP, git mirror purge를 추가했다.
  - `purged_archive_count`는 실제 존재해 삭제된 snapshot archive만 센다.
- `pilot-git-repo-connection/src/tci/web/routes/_common.py`
  - web form unsafe method same-origin check를 missing Origin/Referer에서 fail closed로 강화했다.
- 테스트 추가/수정
  - `pilot-git-repo-connection/tests/contract/workspaces/test_workspace_delete_contract.py`
  - `pilot-git-repo-connection/tests/unit/local_uploads/test_delete_workspace.py`
  - `pilot-git-repo-connection/tests/integration/workspaces/test_workspace_delete_flow.py`
  - `pilot-git-repo-connection/tests/integration/workspaces/test_deleted_workspace_guards.py`
  - Local Upload, repository connection, snapshot storage, verify guard 관련 기존 테스트를 US2 보안/삭제 semantics에 맞게 갱신했다.
- `specs/004-zip-upload-workspace-delete/tasks.md`
  - `T036-T052`를 완료 처리했다.
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
  - US2 RED/GREEN, regression, lint/typecheck, reviewer remediation evidence를 최신 상태로 갱신했다.

## 병렬 작업과 소유권

- `reviewer`: US2 deletion flow, deleted workspace guards, Local Upload/repository regression 관점에서 correctness와 missing test를 검토했다.
- `security-reviewer`: operator role trust boundary, cookie CSRF fail-closed, purge/audit redaction, client-visible error leakage를 검토했다.
- `database-reviewer`: deletion FK ordering, deferrable FK, metadata purge 순서, retry 가능한 deletion state를 검토했다.
- `python-reviewer`: Python typing, FastAPI route flow, context manager/exception behavior, maintainability를 검토했다.
- 모든 구현 수정은 main 작업자가 통합했다. sub-agent가 직접 파일을 수정하지 않았다.

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `specs/004-zip-upload-workspace-delete/spec.md`
- `specs/004-zip-upload-workspace-delete/plan.md`
- `pilot-git-repo-connection/src/tci/domain/services/delete_workspace.py`
- `pilot-git-repo-connection/src/tci/api/routes/workspaces.py`
- `pilot-git-repo-connection/src/tci/api/schemas/workspace.py`
- `pilot-git-repo-connection/src/tci/web/routes/workspaces.py`
- `pilot-git-repo-connection/src/tci/web/templates/workspaces/delete.html`
- `pilot-git-repo-connection/src/tci/web/templates/workspaces/deleted.html`
- `pilot-git-repo-connection/src/tci/api/operator_auth.py`
- `pilot-git-repo-connection/src/tci/infrastructure/snapshots/snapshot_archive_store.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- `pilot-git-repo-connection/tests/contract/workspaces/test_workspace_delete_contract.py`
- `pilot-git-repo-connection/tests/unit/local_uploads/test_delete_workspace.py`
- `pilot-git-repo-connection/tests/integration/workspaces/test_workspace_delete_flow.py`
- `pilot-git-repo-connection/tests/integration/workspaces/test_deleted_workspace_guards.py`

## 꼭 유지해야 할 기준

- Local Upload는 GitHub/GitLab `RepositoryConnection` provider가 아니다.
- Local Upload snapshot은 `CodeSnapshot.source_kind=local_upload`와 `local_upload_id`로 표현한다.
- Workspace deletion은 soft delete다. project contents와 snapshot archive 파일은 purge하고, 최소 audit metadata만 남긴다.
- Deletion audit에는 raw file path, secret, token, credential-bearing URL, raw purge exception을 남기지 않는다.
- Delete reason과 purge failure message는 redacted form만 저장/반환한다.
- Delete는 retry 가능해야 한다. purge 실패 시 metadata를 먼저 지우면 안 된다.
- `TCI_OPERATOR_ROLE` 기본값은 `viewer`다. 테스트나 로컬 운영에서 삭제가 필요하면 명시적으로 `admin` 또는 owner principal을 설정해야 한다.
- operator role/admin 여부는 client header를 신뢰하지 않는다.
- cookie-auth unsafe method는 Origin/Referer가 missing이면 fail closed 해야 한다.
- `fk_local_upload_latest_snapshot_owner`는 deferrable FK여야 한다. Local Upload latest snapshot FK cycle 때문에 삭제 순서만으로 해결하지 않는다.
- `verify_repository_connection`은 queued worker/service path 안에서도 active workspace guard를 유지해야 한다.
- `purged_archive_count`는 실제로 존재했고 삭제된 snapshot archive directory만 센다. queue ZIP이나 git mirror purge는 별도 summary로만 다룬다.
- 기존 GitHub/GitLab provider semantics는 deleted-workspace guard를 제외하고 유지해야 한다.
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-004`, `SC-005`는 자동 테스트만으로 완료 처리하지 않는다.
- untracked 파일 확인에는 `git diff --stat`이 부족하다. 항상 `rtk git status -sb`를 먼저 본다.

## 다시 논의하지 말아야 할 결정

- workspace deletion은 hard delete가 아니라 soft delete다.
- 삭제 중 purge가 실패하면 workspace는 `DELETING`에 남고 재시도한다.
- 삭제 완료 후 active list에서는 빠지고, direct access는 deleted-state guidance를 보여준다.
- Local Upload는 `RepositoryConnection`으로 만들지 않는다.
- GitHub/GitLab route는 Local Upload ID를 provider connection처럼 받지 않는다.
- Redis Local Upload 요청 경로는 full extraction을 하지 않는다.
- Queue worker는 task kwargs의 ZIP path를 신뢰하지 않고 `local_upload_id`에서 파생한 queue path만 사용한다.
- Migration revision id는 Alembic 길이 제약 때문에 `010_local_upload_workspace_del`로 둔다.

## 이번 세션에서 얻은 중요한 메모

- 삭제 경로에서는 `local_uploads.latest_snapshot_id -> code_snapshots.id` 순환 참조가 실제로 걸린다. FK를 deferrable로 두고 transaction 안에서 정리해야 한다.
- repository connection 삭제는 연결 row만 지우면 안 된다. active scope, credential/webhook refs, event cursor, sync run trigger refs, repository event snapshot/sync refs를 먼저 정리해야 한다.
- snapshot archive purge summary는 보안 감사에 유용하지만, raw exception 문자열은 local path나 secret-bearing value를 포함할 수 있다.
- deleted-state page는 active workspace fixture를 다시 생성하거나 보여주면 안 된다. 삭제된 workspace id 기준의 최소 상태만 보여줘야 한다.
- `contextmanager` 안에서 exception 객체를 frozen dataclass로 감싸면 리뷰에서 발견된 실패가 있었다. 삭제/verify guard 쪽에서는 명시적 예외 흐름이 더 안전했다.
- `pip-audit`는 현재 환경에서 사용할 수 없었다. dependency audit residual risk는 남아 있다.
- repo-wide `mypy src tests`는 기존 test typing debt가 있어 이번 scoped result와 별도로 봐야 한다.

## 테스트와 검증 상태

- RED: `rtk pytest -q tests/contract/workspaces/test_workspace_delete_contract.py tests/unit/local_uploads/test_delete_workspace.py tests/integration/workspaces/test_workspace_delete_flow.py tests/integration/workspaces/test_deleted_workspace_guards.py`
  - 결과: workspace deletion 미구현 상태에서 expected failures 확인 후 구현 진행
- GREEN: `rtk pytest -q tests/contract/workspaces/test_workspace_delete_contract.py tests/unit/local_uploads/test_delete_workspace.py tests/integration/workspaces/test_workspace_delete_flow.py tests/integration/workspaces/test_deleted_workspace_guards.py`
  - 결과: `24 passed`
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/unit/local_uploads/test_create_local_upload_snapshot.py tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/local_uploads/test_workspace_local_upload_repositories.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/local_uploads/test_local_upload_failure_flow.py tests/unit/repository_connections/test_phase2_foundation.py tests/unit/repository_connections/test_snapshot_traceability.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_scoped_snapshot.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/unit/repository_connections/test_git_mirror_manager.py tests/unit/repository_connections/test_snapshot_storage.py tests/unit/repository_connections/test_verify_repository_connection.py`
  - 결과: `258 passed`
- GREEN: `rtk pytest -q tests/unit/repository_connections/test_verify_repository_connection.py tests/unit/repository_connections/test_repository_ingestion_tasks.py tests/contract/workspaces/test_workspace_delete_contract.py tests/unit/local_uploads/test_delete_workspace.py tests/integration/workspaces/test_workspace_delete_flow.py tests/integration/workspaces/test_deleted_workspace_guards.py`
  - 결과: `43 passed`
- GREEN: `rtk black --check src tests/contract/workspaces tests/integration/workspaces tests/contract/local_uploads tests/integration/local_uploads tests/unit/local_uploads/test_delete_workspace.py tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/local_uploads/test_workspace_local_upload_repositories.py tests/unit/repository_connections/test_verify_repository_connection.py tests/support/repository_connection_testkit.py tests/unit/repository_connections/test_git_mirror_manager.py tests/unit/repository_connections/test_snapshot_storage.py`
- GREEN: `rtk ruff check src tests/contract/workspaces tests/integration/workspaces tests/contract/local_uploads tests/integration/local_uploads tests/unit/local_uploads/test_delete_workspace.py tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/local_uploads/test_workspace_local_upload_repositories.py tests/unit/repository_connections/test_verify_repository_connection.py tests/support/repository_connection_testkit.py tests/unit/repository_connections/test_git_mirror_manager.py tests/unit/repository_connections/test_snapshot_storage.py`
- GREEN: `rtk mypy src/tci/domain/services/verify_repository_connection.py src/tci/domain/services/delete_workspace.py src/tci/api/routes/workspaces.py src/tci/web/routes/workspaces.py src/tci/api/operator_auth.py src/tci/infrastructure/snapshots/snapshot_archive_store.py src/tci/infrastructure/persistence/planning_input_reference_repository.py src/tci/infrastructure/persistence/repository_connection_repository.py tests/unit/local_uploads/test_delete_workspace.py tests/contract/workspaces/test_workspace_delete_contract.py`
- GREEN: `rtk git diff --check`
- Reviewer loop:
  - 1차: client-trusted role, missing Origin/Referer CSRF, planning metadata retention, deleted page active render, raw purge failure leakage, purge count overcount, FK cycle, repository event FK order, queued verify mutation findings.
  - 2차 이후: 각 finding별 regression test와 implementation fix 추가.
  - 최종: `reviewer`, `security-reviewer`, `database-reviewer`, `python-reviewer` 모두 `No findings`.
- 미검증:
  - 실제 PostgreSQL DB에 migration upgrade/downgrade 적용은 이번 세션에서 다시 실행하지 않았다.
  - 실제 operator rehearsal은 아직 하지 않았다.
  - Full `rtk pytest -q tests/unit tests/contract tests/integration`는 아직 실행하지 않았다.
  - dependency audit은 `pip-audit` unavailable 때문에 실행하지 못했다.

## 다음 세션의 시작 순서

1. `rtk git status -sb`로 dirty/untracked 상태를 확인한다.
2. 관련 없는 `mvp1-features/개발방법/` untracked path는 그대로 둔다.
3. `specs/004-zip-upload-workspace-delete/tasks.md`에서 `T053-T063` User Story 3 범위를 다시 읽는다.
4. mixed-source 테스트를 먼저 작성한다.
   - `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py`
   - `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_local_upload_source_identification.py`
   - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
   - `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`
5. RED를 확인한 뒤 `T057-T063` implementation을 진행한다.
6. US3 구현 중 repository connection serializers/routes/templates를 건드리면 US1/US2 focused checks도 다시 돌린다.
7. `T064-T070` polish로 넘어가기 전 `delivery-evidence.md`와 `tasks.md`의 완료 표시가 실제 검증 결과와 맞는지 다시 확인한다.

## 마지막 액션과 바로 다음 액션

마지막 액션은 `T036-T052` 구현, reviewer loop closure, `tasks.md`/`delivery-evidence.md` 갱신, 그리고 이 `handoff.md` 현재화다.

바로 다음 액션은 `rtk git status -sb` 확인 후 `T053` mixed-source integration test를 RED로 작성하는 것이다. 단, 사용자가 먼저 커밋을 요청하면 현재 `T001-T052` 변경 범위만 검토해서 커밋 메시지를 만들거나 커밋한다.
