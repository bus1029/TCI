# Handoff: ZIP 업로드 스냅샷과 워크스페이스 삭제

## 짧은 요약

`004-zip-upload-workspace-delete`는 `tasks.md` 기준 `T001-T063`까지 완료됐다. Phase 2 foundation, US1 Local Upload, US2 workspace deletion, US3 mixed-source compatibility는 자동화 테스트와 reviewer loop 기준으로 닫혔다.

아직 전체 개발 완료는 아니다. 남은 범위는 `T064-T070` polish, quickstart/evidence 정리, 실제 operator rehearsal, full regression, 최종 diff review다.

## 현재 상태

- 현재 브랜치: `004-zip-upload-workspace-delete`
- 원격 대비 상태: `rtk git status -sb` 기준 divergence 표시는 없다.
- 작업트리: dirty
- 완료됨: `T001-T063`
- 아직 미구현: `T064-T070`
- 실제 operator rehearsal이 필요한 `SC-001`, `SC-004`, `SC-005`는 `Pending`이다.
- 커밋은 아직 만들지 않았다.
- 관련 없는 untracked path `mvp1-features/개발방법/`가 있다. 이번 feature scope가 아니므로 건드리지 말아야 한다.

현재 dirty 파일:

- `pilot-git-repo-connection/src/tci/api/routes/local_uploads.py`
- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- `pilot-git-repo-connection/src/tci/web/routes/local_uploads.py`
- `pilot-git-repo-connection/src/tci/web/routes/repository_connection_detail.py`
- `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
- `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
- `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
- `pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- `pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_snapshot_flow.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_local_upload_source_identification.py`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `specs/004-zip-upload-workspace-delete/handoff.md`
- `specs/004-zip-upload-workspace-delete/tasks.md`

## 이번 세션에서 바뀐 것

- `T053-T063` US3 mixed-source compatibility를 TDD로 구현했다.
- `RepositoryConnection.latestSnapshot.source`에 repository-backed source 정보를 추가했다.
  - `source.kind`: `repository_connection`
  - `source.provider`: GitHub/GitLab provider
  - `source.connectionId`: connection id
- `/connections` operator 화면에서 `RepositoryConnection`과 `Local Upload`를 별도 출처 섹션으로 분리했다.
- connection detail 화면에서도 `Local Upload` 출처를 repository provider처럼 섞지 않고 별도 섹션으로 표시한다.
- deleted/missing/deleting workspace에서 candidate, selected candidate, retained Local Upload row가 노출되지 않도록 guard를 추가했다.
- `GET /api/local-uploads/{id}`와 `GET /api/local-uploads/{id}/snapshots/{snapshot_id}`에서도 inactive workspace read guard를 추가했다.
- Local Upload operator list/status 화면도 inactive workspace에서 retained filename, upload id, snapshot tree를 렌더링하지 않게 했다.
- `tasks.md`에서 `T053-T063`를 완료 처리했다.
- `delivery-evidence.md`에 US3 RED/GREEN, compatibility regression, typing/lint/format, reviewer loop evidence를 추가했다.

## 병렬 작업과 소유권

- sub-agent는 read-only review만 수행했다. 파일 수정은 main 작업자가 통합했다.
- 최종 review 참여:
  - `reviewer`: mixed-source behavior, deleted/missing workspace guard, regression coverage 검토
  - `security-reviewer`: candidate/local-upload metadata leak, deleted workspace exposure, secret echo risk 검토
  - `python-reviewer`: FastAPI route flow, typing, Jinja context, maintainability 검토
- 최종 결과는 모두 `No findings`다.

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `specs/004-zip-upload-workspace-delete/quickstart.md`
- `specs/004-zip-upload-workspace-delete/spec.md`
- `specs/004-zip-upload-workspace-delete/plan.md`
- `pilot-git-repo-connection/src/tci/api/routes/local_uploads.py`
- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
- `pilot-git-repo-connection/src/tci/web/routes/repository_connection_detail.py`
- `pilot-git-repo-connection/src/tci/web/routes/local_uploads.py`
- `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
- `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_local_upload_source_identification.py`
- `pilot-git-repo-connection/tests/contract/local_uploads/test_local_upload_contract.py`
- `pilot-git-repo-connection/tests/integration/local_uploads/test_local_upload_snapshot_flow.py`

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

- `/connections`는 inactive workspace check를 candidate enumeration보다 먼저 해야 한다. 그렇지 않으면 private repository metadata가 UI에 새어 나갈 수 있다.
- POST `/connections`도 selected candidate를 해석하기 전에 workspace active 상태를 확인해야 한다.
- missing workspace도 deleted workspace와 같은 방식으로 candidate/create path를 막아야 한다.
- Local Upload read path는 mutation이 아니어도 retained metadata와 file tree를 노출할 수 있으므로 active workspace guard가 필요하다.
- repo-wide `mypy src tests`는 기존 test typing debt가 있어 이번 scoped mypy 결과와 별도로 봐야 한다.
- `pip-audit`는 현재 환경에서 사용할 수 없었다. dependency audit residual risk는 남아 있다.

## 테스트와 검증 상태

- RED: `rtk pytest -q tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py tests/integration/repository_connections/test_operator_local_upload_source_identification.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - 결과: expected failures 확인. repository-backed `latestSnapshot.source`와 mixed-source operator display가 미구현이었다.
- GREEN: `rtk pytest -q tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py tests/integration/repository_connections/test_operator_local_upload_source_identification.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - 결과: `90 passed`
- GREEN: `rtk pytest -q tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py`
  - 결과: `21 passed`
- GREEN: `rtk pytest -q tests/integration/workspaces/test_deleted_workspace_guards.py tests/contract/workspaces/test_workspace_delete_contract.py`
  - 결과: `10 passed`
- GREEN: `rtk mypy src/tci/api/routes/local_uploads.py src/tci/web/routes/local_uploads.py src/tci/api/schemas/repository_connection.py src/tci/web/routes/repository_connections.py src/tci/web/routes/repository_connection_detail.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py tests/integration/repository_connections/test_operator_local_upload_source_identification.py tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - 결과: `No issues found`
- GREEN: `rtk black --check src/tci/api/routes/local_uploads.py src/tci/web/routes/local_uploads.py src/tci/api/schemas/repository_connection.py src/tci/web/routes/repository_connections.py src/tci/web/routes/repository_connection_detail.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py tests/integration/repository_connections/test_operator_local_upload_source_identification.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- GREEN: `rtk ruff check src/tci/api/routes/local_uploads.py src/tci/web/routes/local_uploads.py src/tci/api/schemas/repository_connection.py src/tci/web/routes/repository_connections.py src/tci/web/routes/repository_connection_detail.py tests/contract/local_uploads/test_local_upload_contract.py tests/integration/local_uploads/test_local_upload_snapshot_flow.py tests/integration/repository_connections/test_github_gitlab_local_upload_compatibility.py tests/integration/repository_connections/test_operator_local_upload_source_identification.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- GREEN: `rtk git diff --check`
- Reviewer loop:
  - fixed: `/connections` Local Upload retained metadata leak
  - fixed: deleted workspace candidate metadata leak
  - fixed: POST selected candidate leak
  - fixed: missing workspace candidate/create leak
  - fixed: Local Upload API/web read leak
  - final: `reviewer`, `security-reviewer`, `python-reviewer` 모두 `No findings`

미검증:

- 실제 PostgreSQL DB에 migration upgrade/downgrade 적용은 이번 세션에서 다시 실행하지 않았다.
- 실제 operator rehearsal은 아직 하지 않았다.
- full `rtk pytest -q tests/unit tests/contract tests/integration`는 아직 실행하지 않았다.
- dependency audit은 `pip-audit` unavailable 때문에 실행하지 못했다.

## 다음 세션의 시작 순서

1. `rtk git status -sb`로 dirty/untracked 상태를 확인한다.
2. 관련 없는 `mvp1-features/개발방법/` untracked path는 그대로 둔다.
3. `specs/004-zip-upload-workspace-delete/tasks.md`에서 `T064-T070`을 다시 읽는다.
4. `T064`로 `quickstart.md`의 Local Upload, workspace deletion, mixed-source verification 절차를 최신 구현 기준으로 정리한다.
5. `T065`로 `delivery-evidence.md`를 SC 상태 중심으로 정리하되, `SC-001`, `SC-004`, `SC-005`는 실제 evidence 전까지 pending으로 유지한다.
6. 시간이 충분하면 `T068` 보안 집중 테스트와 `T069` full regression을 실행한다.
7. 실제 운영자 리허설이 가능할 때만 `T066`과 `T067`을 완료 처리한다.

## 마지막 액션과 바로 다음 액션

마지막 액션은 `T053-T063` 구현, reviewer loop closure, `tasks.md`/`delivery-evidence.md`/`handoff.md` 현재화다.

바로 다음 액션은 `rtk git status -sb` 확인 후 `T064` quickstart polish를 시작하는 것이다. 사용자가 먼저 커밋을 요청하면 현재 `T001-T063` 변경 범위만 검토해서 커밋 메시지를 만들거나 커밋한다.
