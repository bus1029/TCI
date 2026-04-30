# 짧은 요약

- 이번 세션은 `$plan`으로 다음 개발 순서를 정한 뒤 `$tdd`로 `T037/T038`와 `US3` candidate API foundation을 구현했다.
- `get_repository_connection_detail`와 `list_repository_connections`가 이제 service-level `origin` projection을 붙인다.
- `GET /api/repository-candidates`가 추가됐다. 설정된 candidate source가 없으면 manual URL fallback empty state를 반환한다.
- candidate projection은 `workspace_id`로 scope를 강제하고, `remoteUrl`은 안전한 `http`/`https` URL만 응답한다. userinfo/query/fragment/invalid port/unsafe scheme/공백/control 문자는 `null`로 suppress한다.
- reviewer loop를 반복했다. 최종 Security no findings, Python approve. General reviewer는 초반 `Too many open files`로 incomplete였고, Security/Python final re-review와 full verification으로 closure 처리했다.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 브랜치: `003-repository-first-connections`
- `git status -sb` 기준 branch ahead/behind 표시는 없다.
- 현재 worktree는 uncommitted 변경과 untracked 신규 파일이 있다.
- 변경 파일:
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
  - `pilot-git-repo-connection/src/tci/app.py`
  - `pilot-git-repo-connection/src/tci/domain/services/get_repository_connection_detail.py`
  - `pilot-git-repo-connection/src/tci/domain/services/list_repository_connections.py`
  - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_legacy_compatibility.py`
  - `specs/003-repository-first-connections/delivery-evidence.md`
  - `specs/003-repository-first-connections/tasks.md`
- 신규 untracked 파일:
  - `pilot-git-repo-connection/src/tci/api/routes/repository_candidates.py`
  - `pilot-git-repo-connection/src/tci/api/schemas/repository_candidate.py`
  - `pilot-git-repo-connection/src/tci/domain/services/list_repository_candidates.py`
  - `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_candidate_contract.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_candidates.py`
- `tasks.md` 주요 상태:
  - 완료: `T017-T029`, `T031-T046`, `T055-T058`
  - 아직 미완료: `T030`, `T047-T054`, `T059-T067`, Final phase
  - `T030`은 `SC-001` 실제 운영자 리허설이 없어 완료 처리하지 않았다.

# 이번 세션에서 바뀐 것

- `repository_connection_support.py`
  - `build_connection_origin`와 `matching_workspace_planning_input_reference`를 추가했다.
  - `origin.kind`는 `workspace_repository`, `legacy_planning`, `legacy_unassigned`를 유지한다.
  - same-workspace planning reference만 legacy trace로 인정한다.
- `get_repository_connection_detail.py`
  - detail service가 반환 connection에 `origin` projection을 붙인다.
- `list_repository_connections.py`
  - list service가 workspace connection 목록마다 `origin` projection을 붙인다.
- `repository_connection.py`
  - serializer의 origin 계산 중복을 domain helper 사용으로 정리했다.
  - serializer는 service가 넣은 `connection.origin`이 있으면 우선 사용하고, 없으면 fallback으로 계산한다.
- `repository_candidate.py`
  - candidate API response schema를 추가했다.
- `list_repository_candidates.py`
  - `RepositoryCandidateProjection`, `RepositoryCandidateSource`, `RepositoryCandidateDependencies`, repository projection Protocol들을 추가했다.
  - candidate source가 없으면 `provider_not_configured` empty state와 manual URL guidance를 반환한다.
  - candidate source가 있어도 requested `workspace_id`와 다른 candidate는 serialization 전에 제거한다.
  - existing connection과 provider/project path/provider instance가 일치하면 `alreadyConnected=true`, `selectable=false`로 표시한다.
  - `remoteUrl`은 안전하지 않거나 malformed이면 `null`로 반환한다.
- `repository_candidates.py`
  - `GET /api/repository-candidates` route를 추가했다.
  - 기존 operator auth dependency와 `X-TCI-Workspace-Id` validation을 사용한다.
- `app.py`
  - `repository_candidates_router`를 등록했다.
  - `AppDependencies.repository_candidate_source`를 `RepositoryCandidateSource | None`으로 추가했다.
- `test_repository_first_legacy_compatibility.py`
  - detail/list service가 `legacy_unassigned` origin을 직접 projection하는 regression을 추가했다.
- `test_repository_candidate_contract.py`
  - candidate empty manual-url state와 configured provider-scope candidate response contract를 추가했다.
- `test_repository_candidates.py`
  - existing repository candidate 표시, cross-workspace filtering, secret-bearing URL suppression, malformed/unsafe URL suppression을 검증한다.
- `tasks.md`
  - `T037`, `T038`, `T045`, `T046`, `T055-T058`를 완료 처리했다.
- `delivery-evidence.md`
  - RED/GREEN, reviewer loop, final verification 결과를 기록했다.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md`
  - 현재 완료/미완료 task 기준선.
- `specs/003-repository-first-connections/delivery-evidence.md`
  - 이번 세션 RED/GREEN, reviewer remediation, 최종 검증 근거.
- `pilot-git-repo-connection/src/tci/domain/services/list_repository_candidates.py`
  - candidate source Protocol, workspace filtering, existing connection match, safe `remoteUrl` 핵심.
- `pilot-git-repo-connection/src/tci/api/routes/repository_candidates.py`
  - 새 `GET /api/repository-candidates` route.
- `pilot-git-repo-connection/src/tci/api/schemas/repository_candidate.py`
  - candidate response schema.
- `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_candidates.py`
  - candidate service behavior와 보안 regression.
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_candidate_contract.py`
  - candidate API contract.
- `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - origin projection helper와 다음 `T059` identity helper를 추가할 가능성이 높은 파일.
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - 다음 `T060` duplicate prevention 적용 지점.

# 꼭 유지해야 할 기준

- 새 repository connection create는 `planningInputReferenceId` 또는 planning/spec/plan 출처 필드를 받지 않아야 한다.
- obsolete planning/spec/plan field는 compatibility로 수용하지 말고 `400 INVALID_INPUT`으로 거부해야 한다.
- 새 workspace 기반 connection은 `planning_input_reference_id=None`이어야 한다.
- 새 workspace 기반 연결에서 `traceability.planningInputReference = null`은 정상 상태다.
- legacy planning trace는 같은 workspace에 속할 때만 보존/노출해야 한다.
- missing 또는 cross-workspace legacy planning reference는 `legacy_unassigned`로 표시해야 한다.
- cross-workspace planning reference의 `sourceReference`, `approvedSpecPath`, `approvedPlanPath`는 connection detail과 snapshot detail에서 노출하지 말아야 한다.
- candidate source가 반환한 항목도 반드시 requested `workspace_id`와 일치해야 serialization한다.
- candidate `remoteUrl`은 credential, token, query, fragment, unsafe scheme, malformed host/port/path를 echo하지 않아야 한다.
- candidate discovery 개인 grant는 operation credential로 저장하거나 승격하지 않아야 한다.
- API validation error와 web form error는 credential secret을 echo하지 않아야 한다.
- rejected create는 connection/credential/event/sync side effect를 만들지 않아야 한다.
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

# 이번 세션에서 얻은 중요한 메모

- `T037/T038`는 완료됐다. 이전 handoff의 “service-level로 옮길지 판단 필요”는 더 이상 현재 상태가 아니다.
- `T045/T046/T055-T058`도 완료됐다. 다음 시작점은 `T047/T059` canonical identity helper다.
- `T030`은 아직 미완료다. `SC-001` 6회 운영자 timing rehearsal이 없으면 완료 처리하면 안 된다.
- `SC-004`도 아직 미완료다. 60개 mixed-provider 식별 과제와 57/60 성공 계산이 필요하다.
- Security reviewer가 candidate API에서 중요한 gap을 잡았다.
  - 첫 번째: candidate source 반환값을 그대로 믿으면 cross-workspace repository metadata가 누출될 수 있었다.
  - 두 번째: `remoteUrl`이 secret-bearing URL을 echo할 수 있었다.
  - 세 번째 re-review: malformed/unsafe scheme URL도 suppress해야 한다고 지적했다.
  - 모두 수정됐고 final security re-review는 no remaining findings였다.
- Python reviewer가 candidate source dependency typing을 block했다.
  - `RepositoryCandidateDependencies`, `RepositoryCandidateConnectionRepository`, `RepositoryCandidateConnection` Protocol로 해결했다.
  - final Python re-review는 approve였다.
- General reviewer는 초반 `Too many open files`로 incomplete였다. 이후 메인 세션에서 checks를 재실행했고 Security/Python 최종 re-review로 closure 처리했다.
- dependency/lockfile 변경은 없다. `pip-audit`/`safety`는 설치되어 있지 않아 dependency audit는 실행하지 못했다.
- `basedpyright`, `bandit`도 현재 env에서 unavailable로 보고됐다.

# 테스트와 검증 상태

- 최종 검증 통과.
- 주요 RED/GREEN:
  - `rtk pytest tests/integration/repository_connections/test_repository_first_legacy_compatibility.py::test_detail_and_list_services_project_legacy_origin_state -q`
    - RED: `RepositoryConnection`에 service-level `origin` attribute가 없어 실패.
    - GREEN: detail/list service origin projection 추가 후 `1 passed`.
  - `rtk proxy pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py -q`
    - RED: `tci.domain.services.list_repository_candidates` 모듈이 없어 collection 실패.
    - GREEN: candidate schema/service/route/app registration 후 통과.
  - `rtk pytest tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_filters_candidates_from_other_workspaces tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_removes_secret_bearing_remote_urls -q`
    - RED: projection에 `workspace_id`가 없고 unsafe `remoteUrl`을 그대로 반환.
    - GREEN: workspace filtering과 URL suppression 후 `2 passed`.
  - `rtk pytest tests/unit/repository_connections/test_repository_candidates.py::test_candidate_service_removes_malformed_or_unsafe_remote_urls -q`
    - RED: malformed/unsafe scheme URL을 반환.
    - GREEN: `http`/`https` allowlist, hostname/port/control text 검증 후 통과.
- Reviewer loop:
  - Security reviewer: final no remaining security findings.
  - Python reviewer: final approve.
  - General reviewer: no confirmed findings였지만 incomplete. Security/Python final review와 full checks로 보완.
- 최종 focused regression:
  - `rtk pytest tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/unit/repository_connections/test_repository_candidates.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_repository_connection_origin.py -q`
  - 결과: `15 passed`.
- 최종 broad regression:
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - 결과: `571 passed`.
- 최종 static checks:
  - `rtk black --check .`
    - 결과: `158 files would be left unchanged`.
  - `rtk ruff check .`
    - 결과: no issues found.
  - focused `rtk mypy src/tci/api/schemas/repository_candidate.py src/tci/domain/services/list_repository_candidates.py src/tci/api/routes/repository_candidates.py src/tci/app.py src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_connections.py src/tci/domain/services/repository_connection_support.py src/tci/api/schemas/repository_connection.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_repository_first_legacy_compatibility.py tests/unit/repository_connections/test_repository_candidates.py`
    - 결과: no issues found.
  - `rtk alembic heads`
    - 결과: `009_repository_first_connections (head)`.
  - `rtk proxy git diff --check`
    - 결과: 통과.

# 다음 세션의 시작 순서

1. `rtk proxy git status -sb`와 `rtk proxy git diff --stat`로 현재 변경 파일을 확인한다.
2. 커밋 요청이 있으면 이번 변경을 하나의 `feat:` 또는 `test:` 성격 커밋으로 묶을지 먼저 결정한다.
3. 계속 개발하면 `T047`과 `T059`를 먼저 TDD로 시작한다.
   - 목표: candidate path와 manual URL path가 같은 canonical repository identity를 계산하도록 helper를 만든다.
   - 예상 파일: `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_identity.py`, `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`.
4. 그 다음 `T049/T060`으로 candidate-selected/manual URL duplicate prevention integration을 붙인다.
   - 예상 파일: `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`, `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`.
5. 이후 `T050-T052/T061-T063` credential boundary와 permission failure mapping으로 진행한다.
6. Operator UI는 candidate API와 duplicate/credential 흐름이 안정된 뒤 `T048/T064-T066`에서 처리한다.
7. 새 작업 전 `delivery-evidence.md`에 RED/GREEN/검증 명령을 이어서 기록한다.

# 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - `handoff.md`를 현재 상태로 갱신했다.
  - 직전 최종 검증은 모두 통과했다.
- 바로 다음 액션:
  - 커밋 여부를 결정한다.
  - 커밋하지 않고 계속 개발하면 `T047/T059` canonical repository identity helper부터 시작한다.

# 병렬 작업과 소유권

- 이번 세션에서 subagent reviewer를 사용했다. 모두 read-only였고 파일 수정은 메인 세션에서만 수행했다.
- 사용한 reviewer:
  - Security reviewer: candidate workspace isolation, URL echo, malformed URL finding을 냈고 모두 수정 후 final no findings.
  - Python reviewer: candidate dependency typing finding을 냈고 Protocol 보강 후 final approve.
  - General reviewer: 초반 도구 문제로 incomplete. 확정 finding은 없었다.
- 리뷰 중 `Too many open files (os error 24)`와 backend stream disconnect가 있었지만 메인 세션 검증과 재리뷰로 마무리했다.
