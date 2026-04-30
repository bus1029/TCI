# 짧은 요약

- `003-repository-first-connections` Foundation은 이전 커밋 `4515a12 feat: 저장소 연결을 워크스페이스 기준으로 전환`에 들어간 상태다.
- 이번 세션은 `US1` 수동 URL 기반 repository-first MVP와 `US2` 일부 legacy compatibility gap을 TDD로 보강했다.
- operator 목록/상세 UI가 `origin`과 nullable `traceability.planningInputReference`를 안전하게 표시한다.
- obsolete planning/spec/plan field rejection matrix와 persisted legacy planning row의 workspace scope/trace 보존 테스트를 추가했다.
- 리뷰어 루프를 돌렸고 최종 General/Python/Security/DB 리뷰는 `approve` 또는 `no findings` 상태다.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 브랜치: `003-repository-first-connections`
- 현재 worktree는 uncommitted 변경 7개가 있다.
- 변경 파일:
  - `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_migration.py`
  - `specs/003-repository-first-connections/delivery-evidence.md`
  - `specs/003-repository-first-connections/tasks.md`
- `git diff --stat` 기준: `7 files changed, 474 insertions(+), 39 deletions(-)`.
- `tasks.md` 주요 완료 상태:
  - 완료: `T017`, `T018`, `T020-T029`, `T031`, `T035`, `T039-T042`
  - 아직 미완료: `T019`, `T030`, `T032-T034`, `T036-T038`, `T043-T044`, `US3`, Final phase

# 이번 세션에서 바뀐 것

- `connections/index.html`
  - 연결 목록에 `출처: 워크스페이스 저장소 연결`, `출처: 기존 planning trace`, `출처: 호환성 확인 필요`를 표시한다.
  - 실제 create/list UI 파일은 `connections/index.html`이다. `create.html`, `list.html` 경로는 stale path로 정리했다.
- `connections/detail.html`
  - `연결 출처` 섹션을 추가해 `connection.origin.message`와 `compatibilityState`를 표시한다.
  - `planningInputReference`가 있을 때만 승인된 스펙/계획/계획 입력 참조를 표시한다.
  - 새 workspace 기반 연결에는 planning/spec/plan trace가 저장되지 않는다는 문구를 표시한다.
- `test_repository_connection_contract.py`
  - legacy detail이 non-null planning reference와 `origin.kind = legacy_planning`을 반환하는 contract test를 추가했다.
  - `planningInputReferenceId`, `planningInputReference`, `planningTrace`, `traceability`, `approvedSpecPath`, `approvedPlanPath`, `specPath`, `planPath` rejection matrix를 추가했다.
  - 각 obsolete field 요청은 `400 INVALID_INPUT`이고 connection row가 생성되지 않아야 한다.
- `test_operator_connection_pages.py`
  - 목록에서 workspace/legacy origin label을 검증한다.
  - 새 workspace connection 상세에서 승인된 스펙/계획 라벨이 숨겨지는지 검증한다.
  - legacy planning trace가 있는 상세에서는 기존 trace가 표시되는지 검증한다.
- `test_repository_first_migration.py`
  - persisted SQLite legacy row를 직접 삽입한 뒤 `RepositoryConnectionRepository.list_for_workspace/get`과 serializer를 통해 `workspace_id` scope, wrong-workspace isolation, `legacy_planning` origin, trace 보존을 검증한다.
- `tasks.md`
  - 실제 완료된 task만 `[x]`로 갱신했다.
  - nonexistent `test_repository_first_connection_flow.py`, `connections/create.html`, `connections/list.html` 경로를 현재 실제 파일 구조에 맞춰 정리했다.
- `delivery-evidence.md`
  - US1/US2 evidence와 최종 검증 결과를 기록했다.
  - `SC-001`, `SC-004`는 실제 운영자 리허설이 아직 없어 `Pending`으로 유지했다.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md`
  - 현재 완료/미완료 task 기준선.
- `specs/003-repository-first-connections/delivery-evidence.md`
  - 이번 세션 RED/GREEN, focused regression, broad regression, reviewer loop 후 검증 근거.
- `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
  - operator create/list 통합 화면. `create.html`, `list.html`은 현재 없다.
- `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
  - nullable planning trace와 origin 표시 핵심.
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - obsolete field rejection matrix와 legacy detail contract.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
  - operator UI origin/trace regression.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_migration.py`
  - migration text checks와 persisted legacy workspace scope regression.

# 꼭 유지해야 할 기준

- 새 repository connection create는 `planningInputReferenceId` 또는 planning/spec/plan 출처 필드를 받지 않아야 한다.
- obsolete planning/spec/plan field는 compatibility로 수용하지 말고 `400 INVALID_INPUT`으로 거부해야 한다.
- 새 connection은 `planning_input_reference_id=None`이어야 한다.
- legacy planning trace는 삭제하거나 덮어쓰지 말아야 한다.
- 새 workspace 기반 연결에서 `traceability.planningInputReference = null`은 정상 상태다.
- operator UI는 새 연결에 `승인된 스펙`, `승인된 계획`, `계획 입력 참조` 라벨을 보여주면 안 된다.
- legacy planning trace가 있는 연결은 API/detail/operator UI에서 trace를 보존해서 보여줘야 한다.
- API validation error와 web form error는 credential secret을 echo하지 않아야 한다.
- `connections/index.html`이 create/list 통합 템플릿이다. nonexistent `connections/create.html`, `connections/list.html` 경로를 다시 쓰지 말아야 한다.
- `SC-001`, `SC-004`는 실제 운영자 리허설 없이 완료 처리하지 말아야 한다.

# 다시 논의하지 말아야 할 결정

- repository-first create에서 planning/spec/plan reference를 요구하지 않는다.
- obsolete planning/spec/plan create field는 호환 수용하지 않고 명시적으로 거부한다.
- `origin`은 detail-only가 아니라 create/list/detail response와 operator UI 이해 모델에 필요하다.
- GitHub/GitLab provider semantics, webhook 의미, snapshot trigger rule은 이번 범위에서 재설계하지 않는다.
- 후보 목록 기반 판단 지원은 `US3` 범위다. `US1` MVP는 수동 URL 입력으로 독립 검증한다.
- persisted legacy row의 workspace scope는 기존 `workspace_id`를 canonical로 사용한다.

# 이번 세션에서 얻은 중요한 메모

- `tasks.md`에는 이전 계획 단계의 예상 파일명이 남아 있을 수 있다. 실제 repo 파일 구조와 맞춰야 한다.
- legacy detail 테스트에서 in-memory store mutation만으로는 persisted legacy row 보존을 검증했다고 말할 수 없다.
  - 이를 닫기 위해 `test_persisted_legacy_planning_row_keeps_workspace_scope_and_trace`를 추가했다.
- SQLite에서는 현재 full model metadata create가 PostgreSQL regex check constraint 때문에 바로 돌기 어렵다.
  - persisted legacy row regression은 필요한 projection table만 직접 생성해 `RepositoryConnectionRepository` read path를 검증한다.
- test-file focused `mypy`는 기존 `TestClient` typing noise가 있다.
  - 이번 세션에서 새로 추가한 production path와 migration test focused mypy는 통과했다.
- dependency/lockfile 변경은 없다. dependency audit는 이번 세션 범위에서 실행하지 않았다.

# 테스트와 검증 상태

- 최종 검증 통과.
- 실행한 주요 명령:
  - `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_get_legacy_connection_detail_preserves_planning_reference -q`
    - 결과: `1 passed`
  - `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_obsolete_planning_field_matrix_without_row ... -q`
    - 결과: 관련 RED 후 GREEN, 최종 targeted `6 passed`
  - `rtk pytest tests/integration/repository_connections/test_repository_first_migration.py::test_persisted_legacy_planning_row_keeps_workspace_scope_and_trace -q`
    - 결과: `1 passed`
  - `rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_github_gitlab_compatibility.py -q`
    - 결과: `105 passed`
  - `rtk black --check .`
    - 결과: `152 files would be left unchanged`
  - `rtk ruff check .`
    - 결과: no issues found
  - `rtk mypy src/tci/api/schemas/repository_connection.py src/tci/web/routes/repository_connection_detail.py tests/integration/repository_connections/test_repository_first_migration.py`
    - 결과: no issues found
  - `rtk alembic heads`
    - 결과: `009_repository_first_connections (head)`
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
    - 결과: `555 passed`
  - `rtk proxy git diff --check`
    - 결과: 통과
- 리뷰어 최종 상태:
  - General reviewer: initial low finding 수정 후 approve
  - Python reviewer: no findings / approve
  - Security reviewer: no blocking findings
  - DB reviewer: persisted legacy-row evidence finding 수정 후 final no findings
- 미검증 또는 잔여 리스크:
  - `full mypy .`는 실행하지 않았다. 기존 project-wide typing noise가 있다.
  - dependency audit는 실행하지 않았다. dependency/lockfile 변경 없음.
  - `T019`, `T030`, `T032-T034`, `T036-T038`, `T043-T044`, `US3`, Final phase는 아직 남아 있다.
  - `SC-001`, `SC-004` 운영자 리허설은 아직 수행하지 않았다.

# 다음 세션의 시작 순서

1. `rtk proxy git status --short`와 `rtk proxy git diff --stat`로 현재 7개 변경 파일을 확인한다.
2. 커밋 요청이 있으면 이번 변경을 `test/docs/ui` 성격의 하나의 커밋으로 묶을지 먼저 결정한다.
3. 다음 개발은 `tasks.md`의 남은 항목 중 우선순위에 따라 시작한다.
   - `US1`을 더 닫으려면 `T019`, `T030`
   - `US2`를 더 닫으려면 `T032-T034`, `T036-T038`, `T043-T044`
   - candidate/manual 판단 지원은 `US3`부터
4. 새 작업 전 `delivery-evidence.md`의 해당 section에 RED/GREEN/검증 명령을 이어서 기록한다.
5. `SC-001`, `SC-004`는 실제 리허설 데이터가 생기기 전까지 Pending으로 유지한다.

# 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - persisted legacy row regression 추가.
  - formatter, lint, focused mypy, Alembic head, focused pytest, broad repository ingestion pytest `555 passed` 확인.
  - DB final re-review에서 `no findings` 확인.
- 바로 다음 액션:
  - 변경 diff를 최종 리뷰하고 커밋 여부를 결정한다.
  - 구현을 계속한다면 `T019` 또는 `T032-T034/T036` 중 하나를 골라 TDD로 시작한다.

# 병렬 작업과 소유권

- 이번 세션에서 subagent reviewer를 사용했다. 모든 subagent는 read-only였다.
- 사용한 reviewer:
  - General reviewer: task/template path mismatch 지적 후 수정 완료
  - Python reviewer: no findings
  - Security reviewer: no blocking findings
  - DB reviewer: stale path와 persisted legacy-row evidence 지적 후 수정 완료, 최종 no findings
- subagent가 파일을 직접 수정하지 않았다. 모든 파일 수정은 메인 세션에서 수행했다.
