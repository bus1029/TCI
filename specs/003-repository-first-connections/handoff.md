# 짧은 요약

- 이번 세션은 `$plan`으로 다음 개발 계획을 확정한 뒤 `$tdd`로 `US3`의 `T047`, `T049`, `T059`, `T060`을 구현했다.
- candidate 선택 경로와 manual URL 경로가 같은 canonical repository identity를 사용한다.
- `POST /api/repository-connections`는 `candidateId`를 수용한다. 연결 생성은 여전히 `remoteUrl`과 workspace shared read-only credential 검증을 필요로 한다.
- GitHub identity는 repository path 대소문자를 정규화한다.
- GitLab identity는 HTTP(S) 기본 포트 `80`/`443`을 정규화하되, SSH remote의 명시적 포트는 allowlist에서 그대로 요구한다.
- reviewer loop를 반복했고 최종 general reviewer와 security reviewer 모두 no findings였다.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 브랜치: `003-repository-first-connections`
- `git status -sb` 확인 결과: `origin/003-repository-first-connections`보다 `ahead 1`.
- 코드/문서 변경이 남아 있다. handoff 갱신 전 `git status -sb` 기준 변경 파일:
  - `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/list_repository_candidates.py`
  - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_identity.py`
  - `specs/003-repository-first-connections/delivery-evidence.md`
  - `specs/003-repository-first-connections/tasks.md`
- 이 handoff 갱신으로 `specs/003-repository-first-connections/handoff.md`도 변경됐다.
- `tasks.md` 현재 완료:
  - 완료: `T017-T029`, `T031-T049`, `T055-T060`
  - 아직 미완료: `T030`, `T050-T054`, `T061-T067`, Final phase
- `T030`과 `SC-001`은 실제 운영자 리허설이 없어 미완료다.
- `SC-004`도 실제 mixed-provider 식별 리허설이 없어 미완료다.

# 이번 세션에서 바뀐 것

- `repository_connection_support.py`
  - `RepositoryIdentity` dataclass와 `build_repository_identity`를 추가했다.
  - GitHub canonical identity는 `provider_project_path`를 lower-case로 정규화한다.
  - GitLab canonical identity는 `provider_instance_url`의 host case와 HTTP(S) 기본 포트를 정규화한다.
  - GitLab host allowlist 검사에서 HTTP(S) 기본 포트만 제거하고 SSH remote 명시 포트는 유지한다.
- `list_repository_candidates.py`
  - candidate의 `canonicalRepositoryKey`와 existing connection 매칭이 shared `build_repository_identity`를 사용한다.
  - GitLab candidate는 `provider_instance_url`이 없을 때 기존처럼 `provider_scope`를 instance source로 fallback한다.
- `create_repository_connection.py`
  - create orchestration이 parsed remote에서 shared identity를 만든 뒤 lock/precheck/persistence에 사용한다.
  - 새 GitHub row는 canonical lower-case owner/name/path로 저장된다.
  - `candidate_id` command field를 추가했다. 현재는 create request 수용과 추적용 입력이며, candidate source lookup은 아직 하지 않는다.
- `repository_connection.py`, `repository_connections.py`
  - create request schema와 route가 `candidateId`를 수용하고 command로 전달한다.
- `repository_connection_repository.py`
  - GitLab persisted `provider_instance_url`에서도 HTTP(S) 기본 포트를 제거한다.
- `test_repository_connection_identity.py`
  - candidate/manual identity 동등성, GitHub path case 정규화, GitLab default HTTPS port 정규화 regression을 추가했다.
- `test_connection_and_initial_snapshot.py`
  - candidate-selected payload가 manual duplicate precheck를 재사용하는 integration test를 추가했다.
  - GitHub mixed-case duplicate와 GitLab `:443` default port duplicate가 git access 전에 차단되는 regression을 추가했다.
- `test_repository_connection_contract.py`
  - SSH `:443` GitLab remote가 host-only allowlist를 우회하지 못하는 regression을 추가했다.
- `tasks.md`
  - `T047`, `T049`, `T059`, `T060`을 완료 처리했다.
- `delivery-evidence.md`
  - 이번 RED/GREEN, reviewer remediation, 최종 검증 결과를 추가했다.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md`
  - 현재 완료/미완료 task 기준선.
- `specs/003-repository-first-connections/delivery-evidence.md`
  - RED/GREEN, reviewer remediation, 최종 검증 근거.
- `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - shared identity helper, GitLab allowlist/default-port logic.
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - candidate/manual duplicate precheck와 다음 credential boundary 적용 지점.
- `pilot-git-repo-connection/src/tci/domain/services/list_repository_candidates.py`
  - candidate projection과 existing connection matching.
- `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_identity.py`
  - identity normalization 단위 regression.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - candidate/manual duplicate integration regression.
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - create contract, duplicate precheck, GitLab allowlist regression.
- `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_operation_credentials.py`
  - 다음 credential boundary 작업의 기존 출발점.

# 꼭 유지해야 할 기준

- 새 repository connection create는 `planningInputReferenceId` 또는 planning/spec/plan 출처 필드를 받지 않아야 한다.
- obsolete planning/spec/plan field는 compatibility로 수용하지 말고 `400 INVALID_INPUT`으로 거부해야 한다.
- `candidateId`는 수용하지만, 이것만으로 active connection을 만들면 안 된다. shared read-only credential 검증은 계속 필요하다.
- 새 workspace 기반 connection은 `planning_input_reference_id=None`이어야 한다.
- 새 workspace 기반 연결에서 `traceability.planningInputReference = null`은 정상 상태다.
- legacy planning trace는 같은 workspace에 속할 때만 보존/노출해야 한다.
- missing 또는 cross-workspace legacy planning reference는 `legacy_unassigned`로 표시해야 한다.
- cross-workspace planning reference의 `sourceReference`, `approvedSpecPath`, `approvedPlanPath`는 connection detail과 snapshot detail에서 노출하지 않아야 한다.
- candidate source가 반환한 항목도 반드시 requested `workspace_id`와 일치해야 serialization한다.
- candidate `remoteUrl`은 credential, token, query, fragment, unsafe scheme, malformed host/port/path를 echo하지 않아야 한다.
- candidate discovery 개인 grant는 operation credential로 저장하거나 승격하지 않아야 한다.
- API validation error와 web form error는 credential secret을 echo하지 않아야 한다.
- rejected create는 connection/credential/event/sync side effect를 만들지 않아야 한다.
- duplicate precheck는 git ref resolve, credential probe, mirror sync 전에 실패해야 한다.
- GitLab SSH remote의 명시적 포트는 allowlist에서 포트까지 요구해야 한다. `:443`도 SSH에서는 default HTTPS port로 취급하지 않는다.
- `connections/index.html`이 create/list 통합 템플릿이다. nonexistent `connections/create.html`, `connections/list.html` 경로를 다시 쓰지 말아야 한다.
- `SC-001`, `SC-004`는 실제 운영자 리허설 없이 완료 처리하지 말아야 한다.

# 다시 논의하지 말아야 할 결정

- repository-first create에서 planning/spec/plan reference를 요구하지 않는다.
- obsolete planning/spec/plan create field는 호환 수용하지 않고 명시적으로 거부한다.
- `origin`은 detail-only가 아니라 create/list/detail response와 operator UI 이해 모델에 필요하다.
- `origin` 계산 ownership은 domain helper와 detail/list service projection으로 둔다. serializer는 fallback만 제공한다.
- GitHub/GitLab provider semantics, webhook 의미, snapshot trigger rule은 이번 범위에서 재설계하지 않는다.
- 후보 목록 기반 판단 지원은 `US3` 범위다. `US1` MVP는 수동 URL 입력으로 독립 검증한다.
- persisted legacy row의 workspace scope는 기존 `workspace_id`를 canonical로 사용한다.
- cross-workspace planning reference는 legacy trace 보존 대상이 아니다. compatibility 상태로 보여주고 trace 내용은 숨긴다.
- candidate API foundation은 real provider discovery가 아니라 provider source 주입 계약과 response projection까지다.
- canonical identity helper는 candidate list와 create duplicate precheck의 shared source로 유지한다.

# 이번 세션에서 얻은 중요한 메모

- `T047/T049/T059/T060`은 완료됐다. 다음 시작점은 `T050-T052/T061-T063` credential boundary와 permission failure mapping이다.
- `candidateId`는 schema/route/command까지 전달되지만, 아직 candidate source에서 remote를 조회해 create payload를 대체하는 단계는 아니다.
- Reviewer가 identity normalization gap을 잡았다.
  - GitHub path case가 다르면 duplicate precheck가 우회될 수 있었다.
  - GitLab explicit default port가 있으면 duplicate key가 달라질 수 있었다.
  - SSH `:443`이 host-only allowlist를 우회할 수 있었다.
  - 모두 regression 추가 후 수정했고 final reviewer/security re-review는 no findings였다.
- Python reviewer는 이번 diff에 no findings였다.
- `Too many open files (os error 24)`가 세션 후반에 반복됐다. cmux pane 생성, subagent shell 실행, 일부 `rtk`/`git diff` 실행이 실패했다.
- `$git-commit pilot-git-repo-connection` 요청에 대해 scoped diff 명령 일부가 FD 한도 때문에 실패했지만, 직전 확인한 pilot 하위 변경 기준 commit message를 제안했다.
- cmux 실험 결과:
  - `cmux new-pane` + `codex --profile yololo` 실행은 성공했다.
  - 새 pane에서 `/resume`으로 현재 세션을 선택해 열 수 있었다.
  - 같은 세션을 동시에 열면 새 pane 쪽에 `Conversation interrupted`가 나타날 수 있다.
  - 내부 Codex subagent의 실제 화면을 cmux pane에 attach하는 API는 확인하지 못했다. 상태 미러링 pane은 가능해 보이나 FD 한도 때문에 실험 미완료.

# 테스트와 검증 상태

- 최종 검증 통과.
- 주요 RED/GREEN:
  - `rtk proxy pytest tests/unit/repository_connections/test_repository_connection_identity.py -q`
    - RED: `build_repository_identity`가 없어 collection 실패.
    - GREEN: helper 추가 후 identity/candidate focused tests 통과.
  - `rtk proxy pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_candidate_selected_connection_reuses_manual_duplicate_precheck -q`
    - RED: `candidateId`가 extra field로 422.
    - GREEN: `candidateId` 수용과 shared identity duplicate precheck 적용 후 통과.
  - `rtk proxy pytest tests/unit/repository_connections/test_repository_connection_identity.py::test_github_identity_normalizes_repository_path_case tests/unit/repository_connections/test_repository_connection_identity.py::test_gitlab_identity_normalizes_default_https_port -q`
    - RED: GitHub path case와 GitLab default port가 정규화되지 않음.
    - GREEN: identity normalization 보강 후 통과.
  - `rtk proxy pytest tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_github_duplicate_precheck_normalizes_repository_path_case -q`
    - RED: mixed-case GitHub connection과 lower-case GitHub connection이 모두 생성됨.
    - GREEN: 새 GitHub row를 canonical lower-case owner/name/path로 저장한 뒤 통과.
  - `rtk proxy pytest tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_gitlab_ssh_443_without_port_allowlist -q`
    - RED: SSH `:443` GitLab remote가 host-only allowlist로 허용됨.
    - GREEN: SSH 명시 포트 유지 후 통과.
- 최종 reviewer loop:
  - General reviewer: initial findings 모두 수정, final no findings.
  - Security reviewer: initial findings 모두 수정, final no security findings.
  - Python reviewer: no findings.
- 최종 focused regression:
  - `rtk pytest tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_candidate_selected_connection_reuses_manual_duplicate_precheck tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_github_duplicate_precheck_normalizes_repository_path_case tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_gitlab_duplicate_precheck_normalizes_default_https_port tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_duplicate_before_git_access tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_serializes_duplicate_identity_before_git_access -q`
  - 결과: `15 passed`.
- 최종 broad regression:
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - 결과: `579 passed`.
- 최종 static checks:
  - `rtk black --check .`
    - 결과: `159 files would be left unchanged`.
  - `rtk ruff check .`
    - 결과: no issues found.
  - focused `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/create_repository_connection.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_connections.py tests/unit/repository_connections/test_repository_connection_identity.py tests/unit/repository_connections/test_repository_candidates.py`
    - 결과: no issues found.
  - `rtk alembic heads`
    - 결과: `009_repository_first_connections (head)`.
  - `rtk proxy git diff --check`
    - 결과: 통과.
- project-wide/test-file mypy는 기존 TestClient/test payload typing noise가 있어 focused target만 사용했다.
- dependency/lockfile 변경은 없다. dependency audit는 실행하지 않았다.

# 다음 세션의 시작 순서

1. `git status -sb`로 staged/unstaged 상태를 확인한다. 가능하면 `rtk`를 쓰되 `Too many open files`가 나면 raw `git`로 fallback한다.
2. 현재 변경을 커밋할지 결정한다.
   - 제안된 scoped commit message:
     ```text
     feat: 저장소 identity 중복 판별 강화

     candidate 선택과 수동 URL 입력이 같은 저장소를 일관되게
     판별하도록 canonical identity helper를 추가한다.

     - GitHub 경로 대소문자와 GitLab 기본 포트를 정규화
     - candidateId create payload를 수용해 중복 precheck에 연결
     - SSH 포트 allowlist 우회가 없도록 regression을 보강
     ```
3. 계속 개발하면 `T050-T052` 테스트를 먼저 작성한다.
   - `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_credentials.py`
   - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_permission_failures.py`
   - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
4. 그 다음 `T061-T063` 구현으로 진행한다.
   - `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
   - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
   - `pilot-git-repo-connection/src/tci/api/routes/repository_connections.py`
5. Credential boundary와 permission failure가 안정된 뒤 `T048/T064-T066` operator candidate UI로 넘어간다.
6. 새 작업도 RED/GREEN과 reviewer loop 결과를 `delivery-evidence.md`에 이어서 기록한다.

# 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - `handoff.md`를 현재 세션 기준으로 갱신했다.
  - 직전 최종 검증은 모두 통과했다.
- 바로 다음 액션:
  - `git status -sb`로 staging 상태를 확인한다.
  - 커밋할지 결정한다.
  - 커밋하지 않고 계속 개발하면 `T050-T052/T061-T063` credential boundary loop부터 시작한다.

# 병렬 작업과 소유권

- 이번 세션에서 subagent reviewer를 사용했다. 모두 read-only였고 파일 수정은 메인 세션에서만 수행했다.
- 사용한 reviewer:
  - General reviewer: canonical identity normalization gap, SSH `:443` allowlist gap을 지적했고 수정 후 final no findings.
  - Security reviewer: duplicate/allowlist bypass risk를 지적했고 수정 후 final no security findings.
  - Python reviewer: no findings.
- 테스트용 worker subagent `Dirac`를 띄웠지만 `Too many open files (os error 24)`로 shell 실행을 못 했다. 종료/close 처리했다.
- cmux pane 실험 중 `pane:3`, `pane:4`에 `codex --profile yololo`를 실행했다. 열려 있을 수 있으므로 필요 없으면 cmux에서 닫아도 된다.
