# Handoff: ZIP 업로드 스냅샷과 워크스페이스 삭제

## 짧은 요약

`004-zip-upload-workspace-delete`는 `tasks.md` 기준 `T001-T065`, `T068-T070`까지 완료됐다. Phase 2 foundation, US1 Local Upload, US2 workspace deletion, US3 mixed-source compatibility, quickstart/evidence polish, security-focused regression, full automated regression, final reviewer loop가 닫혔다.

아직 전체 개발 완료는 아니다. 실제 operator rehearsal이 필요한 `T066`, `T067`만 남아 있다. `SC-001`, `SC-004`, `SC-005`는 실제 evidence 전까지 `Pending`으로 유지한다.

## 현재 상태

- 현재 브랜치: `004-zip-upload-workspace-delete`
- 작업트리: dirty
- 완료됨: `T001-T065`, `T068-T070`
- 아직 미구현/미실행: `T066`, `T067`
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-004`, `SC-005`는 `Pending`
- 커밋은 아직 만들지 않았다.
- 관련 없는 untracked path `mvp1-features/개발방법/`가 있다. 이번 feature scope가 아니므로 건드리지 말아야 한다.

현재 feature-scope dirty 파일:

- `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_candidate_contract.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_scope_pages.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
- `specs/004-zip-upload-workspace-delete/quickstart.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/handoff.md`

## 이번 세션에서 바뀐 것

- `T064`로 `quickstart.md` developer verification을 최신 구현 기준으로 갱신했다.
  - Local Upload, workspace deletion, GitHub/GitLab compatibility, mixed-source, operator source-identification, full regression, focused security regression 경로를 명시했다.
  - `rtk alembic heads`를 다시 포함해 migration head 검증을 유지했다.
- `T065`로 `delivery-evidence.md`에 Phase 6 RED/GREEN, security-focused regression, full regression, hygiene, reviewer loop evidence를 추가했다.
- `T068` security-focused ZIP/deletion suite를 실행했다.
- `T069` full `tests/unit tests/contract tests/integration` regression을 실행했다.
- Full regression RED에서 드러난 테스트 fixture drift를 수정했다.
  - repository candidate/operator tests가 active workspace를 명시적으로 seed하도록 보강했다.
  - operator form POST tests가 same-origin header를 보내도록 보강했다.
  - repository-backed `latestSnapshot.source` expectation을 최신 계약에 맞췄다.
- `T070` final review loop를 완료했다.

## 병렬 작업과 소유권

- sub-agent는 read-only review만 수행했다. 파일 수정은 main 작업자가 통합했다.
- 최종 review 참여:
  - `reviewer`: quickstart migration-head verification 누락을 지적했고, 수정 후 follow-up에서 `No findings`를 반환했다.
  - `python-reviewer`: active workspace seed, same-origin header, repository snapshot source assertion 변경을 검토했고 `No findings`를 반환했다.
  - `security-reviewer`: CSRF/same-origin coverage, deleted/missing workspace metadata leak, secret redaction을 검토했고 `No findings`를 반환했다.

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `specs/004-zip-upload-workspace-delete/quickstart.md`
- `specs/004-zip-upload-workspace-delete/spec.md`
- `specs/004-zip-upload-workspace-delete/plan.md`
- `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_candidate_contract.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_scope_pages.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`

## 꼭 유지해야 할 기준

- `Local Upload`는 GitHub/GitLab `RepositoryConnection` provider가 아니다.
- `Local Upload` snapshot은 `source.kind=local_upload`로 표현하고, repository-backed snapshot은 `source.kind=repository_connection`으로 표현한다.
- GitHub/GitLab route는 `Local Upload` id를 provider connection처럼 받으면 안 된다.
- deleted/missing/deleting workspace에서는 candidate metadata, selected candidate URL, Local Upload filename, upload id, snapshot id, file tree를 노출하면 안 된다.
- workspace deletion은 soft delete다. project contents와 snapshot archive 파일은 purge하고, 최소 audit metadata만 남긴다.
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-004`, `SC-005`는 자동 테스트만으로 완료 처리하지 않는다.
- `rtk git status -sb`를 먼저 보고 untracked 파일을 확인한다. `git diff --stat`만으로는 부족하다.

## 다시 논의하지 말아야 할 결정

- workspace deletion은 hard delete가 아니라 soft delete다.
- 삭제 중 purge가 실패하면 workspace는 `DELETING`에 남고 재시도한다.
- 삭제 완료 후 active list에서는 빠지고, direct access는 deleted-state guidance를 보여준다.
- `Local Upload`는 `RepositoryConnection`으로 만들지 않는다.
- `Local Upload` source display는 `RepositoryConnection` display와 별도 섹션으로 둔다.
- Redis Local Upload 요청 경로는 full extraction을 하지 않는다.
- Queue worker는 task kwargs의 ZIP path를 신뢰하지 않고 `local_upload_id`에서 파생한 queue path만 사용한다.
- Migration revision id는 Alembic 길이 제약 때문에 `010_local_upload_workspace_del`로 둔다.

## 이번 세션에서 얻은 중요한 메모

- Full regression은 focused story suites보다 강한 fixture drift를 드러냈다. `create_test_client()`만 호출한 legacy tests는 active workspace를 암묵적으로 기대하면 안 된다.
- Candidate enumeration, operator create form, scope form 테스트는 의도한 validation path를 보려면 active workspace와 same-origin evidence를 명시해야 한다.
- `RepositoryConnection.latestSnapshot.source`는 repository-backed snapshot에도 포함된다. 기존 expectation에서 이 필드를 빠뜨리면 stale 계약이다.
- Quickstart에서 `rtk alembic heads`를 빼면 migration-owning feature의 final verification이 약해진다.
- broader mypy on touched operator test files still reports pre-existing Starlette `TestClient.app` attr-defined debt. 이번 세션에서는 focused mypy와 pytest/ruff/black으로 검증했다.

## 테스트와 검증 상태

- RED: `rtk rg -q "test_github_gitlab_local_upload_compatibility.py\|test_operator_local_upload_source_identification.py" specs/004-zip-upload-workspace-delete/quickstart.md`
  - 결과: exit 1. quickstart가 최신 US3 verification 경로를 명시하지 않았다.
- GREEN: 같은 `rtk rg -q ... quickstart.md`
  - 결과: exit 0.
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/integration/local_uploads/test_local_upload_failure_flow.py tests/integration/workspaces/test_workspace_delete_flow.py`
  - 결과: `33 passed`
- RED: `rtk pytest -q tests/unit tests/contract tests/integration`
  - 결과: `753 passed, 17 failed, 10 skipped`
  - 원인: legacy tests가 active workspace seed, same-origin form POST, repository-backed `latestSnapshot.source` 최신 계약을 반영하지 않았다.
- GREEN: `rtk pytest -q tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_operator_scope_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - 결과: `45 passed`
- GREEN: `rtk pytest -q tests/unit/local_uploads/test_local_zip_extractor.py tests/integration/local_uploads/test_local_upload_failure_flow.py tests/integration/workspaces/test_workspace_delete_flow.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_operator_scope_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - 결과: `78 passed`
- GREEN: `rtk pytest -q tests/unit tests/contract tests/integration`
  - 결과: `770 passed`
- GREEN: `rtk mypy tests/support/repository_connection_testkit.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_operator_scope_pages.py`
  - 결과: `No issues found`
- GREEN: `rtk black --check tests/support/repository_connection_testkit.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_operator_scope_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
- GREEN: `rtk ruff check tests/support/repository_connection_testkit.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_operator_scope_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
- GREEN: `rtk alembic heads`
  - 결과: `010_local_upload_workspace_del (head)`
- GREEN: `rtk git diff --check`
- Reviewer loop:
  - `reviewer`: quickstart에 `rtk alembic heads` 누락 finding 1건
  - 수정 후 follow-up `reviewer`: `No findings`
  - `python-reviewer`: `No findings`
  - `security-reviewer`: `No findings`

미검증:

- 실제 PostgreSQL DB에 migration upgrade/downgrade 적용은 이번 세션에서 실행하지 않았다.
- 실제 operator rehearsal은 아직 하지 않았다.
- dependency audit은 실행하지 않았다.
- broader mypy on touched operator test files still reports pre-existing Starlette `TestClient.app` attr-defined debt; focused mypy for changed support/contract/scope files is green.

## 다음 세션의 시작 순서

1. `rtk git status -sb`로 dirty/untracked 상태를 확인한다.
2. 관련 없는 `mvp1-features/개발방법/` untracked path는 그대로 둔다.
3. 실제 operator rehearsal evidence가 준비됐는지 확인한다.
4. 준비됐으면 `T066` SC-001 세 운영자 ZIP upload-to-snapshot 리허설을 수행하고 redacted timing evidence를 `delivery-evidence.md`에 기록한다.
5. 준비됐으면 `T067` SC-005 30개 source-identification exercise를 수행하고 redacted result를 `delivery-evidence.md`에 기록한다.
6. `SC-004`는 실제 GitHub/GitLab baseline validation evidence가 있을 때만 pending에서 변경한다.

## 마지막 액션과 바로 다음 액션

마지막 액션은 `T064`, `T065`, `T068`, `T069`, `T070` 구현/검증/reviewer loop closure와 `tasks.md`/`delivery-evidence.md`/`handoff.md` 현재화다.

바로 다음 액션은 실제 operator rehearsal 가능 여부를 확인하는 것이다. 실제 evidence가 없다면 `T066`, `T067`, `SC-001`, `SC-004`, `SC-005`는 그대로 pending이다.
