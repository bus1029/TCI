# 짧은 요약

- 이번 세션은 `$tdd`로 `US1` credential failure 계약과 `US2` legacy GitHub/GitLab compatibility gap을 닫았다.
- `POST /api/repository-connections`는 auth-failed/write-capable credential을 row/credential/event/sync side effect 없이 거부한다.
- legacy GitHub/GitLab planning connection은 list/detail/verify/snapshot/webhook 경로에서 보존된다.
- cross-workspace 또는 missing legacy planning reference는 `legacy_unassigned`로 표시하고, mismatched planning trace는 API/operator/snapshot detail에서 노출하지 않는다.
- reviewer loop를 findings가 없을 때까지 반복했다. 최종 General approve, Python approve, Security no findings.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 브랜치: `003-repository-first-connections`
- 브랜치 상태: `origin/003-repository-first-connections`보다 `ahead 1`
- 현재 worktree는 uncommitted 변경이 있다.
- `git status --short` 기준 변경 파일:
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_legacy_compatibility.py`
  - `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_serialization.py`
  - `specs/003-repository-first-connections/delivery-evidence.md`
  - `specs/003-repository-first-connections/tasks.md`
  - `specs/003-repository-first-connections/handoff.md`
- `git diff --stat`는 untracked 파일을 제외하고 `10 files changed, 385 insertions(+), 19 deletions(-)`였다. `test_repository_first_legacy_compatibility.py`는 새 파일이다.
- `tasks.md` 주요 상태:
  - 완료: `T017-T029`, `T031-T036`, `T039-T044`
  - 아직 미완료: `T030`, `T037-T038`, `US3`, Final phase
  - `T030`은 permission problem evidence 일부는 기록됐지만 `SC-001` 실제 운영자 리허설이 없어 완료 처리하지 않았다.

# 이번 세션에서 바뀐 것

- `test_repository_connection_contract.py`
  - `test_create_connection_rejects_write_capable_credential_without_row` 추가.
  - `test_create_connection_rejects_auth_failed_credential_without_row` 추가.
  - 거부된 create가 `store.connections`, `store.credentials`, `store.repository_events`, `store.sync_runs`를 비워 둔다는 assertion을 추가했다.
  - 응답에 `top-secret-token`이 echo되지 않는 것도 고정했다.
- `repository_connection_testkit.py`
  - `InMemoryRepositoryStore.readonly_probe_result` 추가.
  - `FakeGitReadonlyValidator`가 store 기반 probe result를 반환하게 변경.
  - `seed_legacy_planning_repository_connection` helper 추가. GitHub/GitLab legacy planning connection을 `workspace_id`와 planning reference 포함해 seed한다.
- `test_github_gitlab_compatibility.py`
  - legacy GitHub planning connection list/detail/verify/snapshot regression 추가.
  - legacy GitLab planning connection list/detail/verify/snapshot regression 추가.
  - legacy GitHub/GitLab webhook provider isolation regression 추가.
- `test_repository_first_legacy_compatibility.py`
  - 새 파일.
  - missing legacy planning reference가 `legacy_unassigned`로 보이는지 검증.
  - cross-workspace planning reference가 loaded 상태여도 `legacy_unassigned`로 보이는지 검증.
  - cross-workspace planning reference가 snapshot detail traceability에서 `null`로 숨겨지는지 검증.
- `repository_connection.py`
  - connection detail `traceability.planningInputReference`는 planning reference의 `workspace_id`가 connection `workspace_id`와 같을 때만 serialize한다.
  - mismatched planning reference는 `origin.kind = legacy_unassigned`, `compatibilityState = workspace_assignment_unclear`로 분류한다.
- `get_code_snapshot_detail.py`
  - snapshot detail도 same-workspace planning reference만 넘긴다.
  - reviewer/security finding으로 잡힌 cross-workspace planning trace leak을 막았다.
- `connections/index.html`
  - list UI가 planning reference 존재 여부만 보지 않고 same-workspace reference인지 확인한 뒤 `출처: 기존 planning trace`를 표시한다.
  - mismatched/missing reference는 `출처: 호환성 확인 필요`로 표시한다.
- `connections/detail.html`
  - `legacy_unassigned` 상세 화면에 `호환성 확인 필요` 문구를 표시한다.
- `test_repository_connection_serialization.py`
  - cross-workspace planning reference가 connection detail에서 숨겨지고 `legacy_unassigned`가 되는 unit regression 추가.
- `tasks.md`
  - `T019`, `T032-T036`, `T043-T044`를 완료 처리했다.
  - `T030`, `T037-T038`, `US3`, Final phase는 미완료 유지했다.
- `delivery-evidence.md`
  - `FR-014b`를 “missing/cross-workspace legacy planning reference는 `legacy_unassigned`, mismatched trace는 숨김”으로 갱신.
  - RED/GREEN, focused/broad 검증, reviewer remediation 결과를 추가했다.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md`
  - 현재 완료/미완료 task 기준선.
- `specs/003-repository-first-connections/delivery-evidence.md`
  - 이번 세션 RED/GREEN, reviewer remediation, 최종 검증 근거.
- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - same-workspace planning reference guard와 `origin` 분류 핵심.
- `pilot-git-repo-connection/src/tci/domain/services/get_code_snapshot_detail.py`
  - snapshot detail의 cross-workspace planning trace leak 방지 핵심.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_legacy_compatibility.py`
  - `legacy_unassigned`, cross-workspace reference, snapshot traceability leak regression.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - legacy GitHub/GitLab visibility, verify/snapshot, webhook no-regression.
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - credential failure contract와 no-side-effect/no-secret-echo assertions.
- `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
  - fake readonly probe와 legacy planning connection helper.
- `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
  - operator create/list 통합 화면. `connections/create.html`, `connections/list.html`은 없다.
- `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
  - operator detail origin/compatibility 표시.

# 꼭 유지해야 할 기준

- 새 repository connection create는 `planningInputReferenceId` 또는 planning/spec/plan 출처 필드를 받지 않아야 한다.
- obsolete planning/spec/plan field는 compatibility로 수용하지 말고 `400 INVALID_INPUT`으로 거부해야 한다.
- 새 workspace 기반 connection은 `planning_input_reference_id=None`이어야 한다.
- 새 workspace 기반 연결에서 `traceability.planningInputReference = null`은 정상 상태다.
- legacy planning trace는 같은 workspace에 속할 때만 보존/노출해야 한다.
- missing 또는 cross-workspace legacy planning reference는 `legacy_unassigned`로 표시해야 한다.
- cross-workspace planning reference의 `sourceReference`, `approvedSpecPath`, `approvedPlanPath`는 connection detail과 snapshot detail에서 노출하지 말아야 한다.
- API validation error와 web form error는 credential secret을 echo하지 않아야 한다.
- rejected create는 connection/credential/event/sync side effect를 만들지 않아야 한다.
- `connections/index.html`이 create/list 통합 템플릿이다. nonexistent `connections/create.html`, `connections/list.html` 경로를 다시 쓰지 말아야 한다.
- `SC-001`, `SC-004`는 실제 운영자 리허설 없이 완료 처리하지 말아야 한다.

# 다시 논의하지 말아야 할 결정

- repository-first create에서 planning/spec/plan reference를 요구하지 않는다.
- obsolete planning/spec/plan create field는 호환 수용하지 않고 명시적으로 거부한다.
- `origin`은 detail-only가 아니라 create/list/detail response와 operator UI 이해 모델에 필요하다.
- GitHub/GitLab provider semantics, webhook 의미, snapshot trigger rule은 이번 범위에서 재설계하지 않는다.
- 후보 목록 기반 판단 지원은 `US3` 범위다. `US1` MVP는 수동 URL 입력으로 독립 검증한다.
- persisted legacy row의 workspace scope는 기존 `workspace_id`를 canonical로 사용한다.
- cross-workspace planning reference는 legacy trace 보존 대상이 아니다. compatibility 상태로 보여주고 trace 내용은 숨긴다.

# 이번 세션에서 얻은 중요한 메모

- `T037`, `T038`은 아직 체크하지 않았다. 현재 `origin` 계산은 serializer/template 쪽에서 동작하지만 task 문구는 service-level 구현을 말한다. 다음 세션에서 “이미 충족”으로 볼지 “service projection으로 옮길지”를 명시적으로 판단해야 한다.
- `T030`은 아직 미완료다. US1 permission problem evidence는 추가됐지만 `SC-001` 6회 운영자 timing rehearsal이 없어 완료 처리하면 안 된다.
- reviewer가 두 번 중요한 gap을 잡았다.
  - 첫 번째: cross-workspace planning reference test가 reference를 `None`으로 만들어 과소검증했다.
  - 두 번째: snapshot detail이 cross-workspace planning trace를 노출할 수 있었다.
  - 둘 다 수정됐고 최종 reviewer re-review에서 no findings/approve를 받았다.
- `full mypy .`는 실행하지 않았다. 기존 test `TestClient` typing noise가 있다.
- dependency/lockfile 변경은 없다. dependency audit는 이번 세션 범위에서 실행하지 않았다.

# 테스트와 검증 상태

- 최종 검증 통과.
- 주요 RED/GREEN:
  - `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_write_capable_credential_without_row tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_auth_failed_credential_without_row -q`
    - RED: `1 passed, 1 failed` because testkit could not express write-capable readonly probe.
    - GREEN: `2 passed`.
  - `rtk proxy pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_github_planning_connection_remains_visible_and_operational -q`
    - RED: collection failed because `seed_legacy_planning_repository_connection` did not exist.
  - `rtk pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_github_planning_connection_remains_visible_and_operational tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_gitlab_planning_connection_remains_visible_and_operational tests/integration/repository_connections/test_github_gitlab_compatibility.py::test_legacy_github_gitlab_webhooks_preserve_provider_isolation tests/integration/repository_connections/test_repository_first_legacy_compatibility.py::test_connection_with_missing_legacy_planning_reference_shows_compatibility_state -q`
    - GREEN: `4 passed`.
- reviewer remediation checks:
  - `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_connection_serialization.py -q`
    - 결과: `5 passed`.
  - `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_snapshot_traceability.py -q`
    - 결과: `5 passed`.
- 최종 focused regression:
  - `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/integration/repository_connections/test_operator_connection_pages.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py -q`
  - 결과: `105 passed`.
- 최종 broad regression:
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - 결과: `564 passed`.
- 최종 static checks:
  - `rtk black --check .`
    - 결과: `153 files would be left unchanged`.
  - `rtk ruff check .`
    - 결과: no issues found.
  - `rtk mypy src/tci/api/schemas/repository_connection.py src/tci/domain/services/get_code_snapshot_detail.py src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_connections.py tests/support/repository_connection_testkit.py`
    - 결과: no issues found.
  - `rtk alembic heads`
    - 결과: `009_repository_first_connections (head)`.
  - `rtk proxy git diff --check`
    - 결과: 통과.
- reviewer 최종 상태:
  - Python reviewer: no findings / approve.
  - General reviewer: T034/FR-014b overclaim, snapshot traceability leak 지적 후 수정. 최종 `APPROVE`.
  - Security reviewer: snapshot traceability leak 지적 후 수정. 최종 no remaining security findings.

# 다음 세션의 시작 순서

1. `rtk proxy git status -sb`와 `rtk proxy git diff --stat`로 현재 변경 파일을 확인한다.
2. 커밋 요청이 있으면 이번 변경을 하나의 `test:` 또는 `fix:` 성격 커밋으로 묶을지 먼저 결정한다.
3. `T037`, `T038`을 어떻게 처리할지 결정한다.
   - 현재 behavior는 serializer/list template에서 통과한다.
   - task 문구상 service-level origin projection이 필요하면 `get_repository_connection_detail.py`, `list_repository_connections.py`에 명시 projection을 추가하고 tests를 보강한다.
4. `T030`은 `SC-001` 실제 운영자 리허설이 생기기 전까지 완료 처리하지 않는다.
5. 구현을 계속하면 `US3` candidate API slice부터 시작한다.
   - 우선 `T045-T058`: candidate contract/unit/service/route/app registration.
6. 새 작업 전 `delivery-evidence.md` 해당 section에 RED/GREEN/검증 명령을 이어서 기록한다.

# 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - `handoff.md`를 현재 상태로 갱신했다.
  - 최종 검증 결과와 reviewer loop 결과를 반영했다.
- 바로 다음 액션:
  - 커밋 여부를 결정한다.
  - 커밋하지 않고 계속 개발하면 `T037/T038` 처리 방식을 먼저 정하고, 이후 `US3` candidate API slice로 넘어간다.

# 병렬 작업과 소유권

- 이번 세션에서 subagent reviewer를 사용했다. 모두 read-only였고 파일 수정은 메인 세션에서만 수행했다.
- 사용한 reviewer:
  - Python reviewer: no findings / approve.
  - General reviewer: T034/FR-014b overclaim, snapshot traceability leak findings. 모두 수정 후 final approve.
  - Security reviewer: snapshot traceability leak finding. 수정 후 no remaining security findings.
- reviewer findings를 수정한 뒤 같은 reviewer 계열을 다시 호출했고, 최종 no findings 상태까지 반복했다.
