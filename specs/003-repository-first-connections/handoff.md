# 짧은 요약

- 이번 세션은 `$tdd` 계획대로 candidate 선택 기반 repository-first 연결 생성 흐름을 개발하고 리뷰 루프까지 돌렸다.
- 운영자 화면에서 선택한 candidate의 provider/remote URL을 서버가 신뢰 가능한 candidate projection에서 다시 가져오도록 보강했다.
- 선택 불가 candidate는 HTML disabled에만 의존하지 않고 web route와 domain create service 양쪽에서 거부한다.
- credential-bearing `remoteUrl`이 validation failure 화면에 다시 노출되지 않도록 form 재렌더 데이터를 sanitize했다.
- GitHub/GitLab 혼합 workspace 식별과 이벤트/스냅샷 분리 회귀 테스트, SC-004 리허설 fixture를 추가했다.
- 일반 reviewer, security reviewer, Python reviewer 최종 결과는 모두 no findings였다.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 브랜치: `003-repository-first-connections`
- 현재 브랜치는 `origin/003-repository-first-connections`보다 `ahead 2` 상태다.
- staged 변경은 없다.
- 작업트리 변경 파일:
  - `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/detail.html`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/events.html`
  - `pilot-git-repo-connection/src/tci/web/templates/connections/index.html`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_permission_failures.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_mixed_provider_workspace.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_mixed_provider_identification.py`
  - `pilot-git-repo-connection/tests/support/operator_identification_rehearsal.py`
  - `specs/003-repository-first-connections/delivery-evidence.md`
  - `specs/003-repository-first-connections/tasks.md`
  - `specs/003-repository-first-connections/handoff.md`
- untracked temp file:
  - `specs/003-repository-first-connections/.tasks.md.swp`
  - 사용자 확인 없이 삭제하지 말고, 다음 세션에서 editor swap인지 먼저 확인한다.
- `tasks.md`에서 `T048`, `T053`, `T054`, `T064`, `T065`, `T066`, `T067`은 완료 상태다.
- `T045-T067`은 모두 완료 상태다.
- 아직 남은 final phase task:
  - `T068` quickstart 업데이트
  - `T069` repository-first focused check/evidence
  - `T070` 기존 GitHub/GitLab regression suite/evidence
  - `T071` 실제 SC-001 timed operator rehearsal evidence
  - `T072` 실제 SC-004 mixed-provider identification rehearsal evidence
  - `T073` 최종 FR/SC coverage map
- `T030`은 SC-001 6회 시도 timing validation까지 포함하므로 실제 운영자 리허설 전까지 완료 처리하지 않는다.

# 이번 세션에서 바뀐 것

- `create_repository_connection.py`
  - selected candidate의 `access_status`가 `available`이 아니면 create를 거부한다.
  - `candidateId`가 active connection 생성을 우회하는 경로가 되지 않도록 domain boundary를 추가했다.
- `web/routes/repository_connections.py`
  - 선택된 candidate projection에서 provider와 remote URL 기본값을 적용한다.
  - 선택 불가 candidate는 서버에서 먼저 거부한다.
  - validation failure 재렌더 전에 `_sanitize_form_data()`로 credential-bearing `remoteUrl`을 비운다.
  - userinfo/password/query/fragment가 포함된 remote URL, parse 실패 remote URL은 화면에 되돌려주지 않는다.
- `connections/index.html`
  - candidate radio 선택이 create payload와 맞물리도록 hidden create form 값을 정리했다.
  - 선택 불가 candidate는 disabled로 표시하되, 실제 보안 경계는 서버 검증에 둔다.
- `connections/detail.html`
  - 혼합 provider 식별을 위해 `workspace_id`를 명시적으로 노출한다.
- `connections/events.html`
  - 이벤트 화면의 provider/repository 식별 표시를 유지해 GitHub/GitLab 혼합 workspace에서 구분 가능하게 했다.
- `test_operator_connection_pages.py`
  - selected candidate가 provider/remote URL 생성 payload에 반영되는 regression을 추가했다.
  - credential-bearing `remoteUrl` 반사 차단 regression을 추가했다.
- `test_repository_first_permission_failures.py`
  - non-selectable candidate를 route/domain 양쪽에서 막는 regression을 추가했다.
- `test_mixed_provider_workspace.py`
  - GitHub/GitLab 혼합 workspace의 이벤트/스냅샷 분리 regression을 추가했다.
- `test_operator_mixed_provider_identification.py`
  - operator detail/list/events 화면 식별 정보 regression을 추가했다.
- `operator_identification_rehearsal.py`
  - SC-004 리허설용 60문항 fixture builder를 추가했다.
- `tasks.md`
  - `T048`, `T053`, `T054`, `T064`, `T065`, `T066`, `T067`을 완료 처리했다.
- `delivery-evidence.md`
  - FR/SC coverage map과 이번 RED/GREEN, reviewer remediation, verification 결과를 갱신했다.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md`
  - 현재 완료/미완료 task 기준선.
- `specs/003-repository-first-connections/delivery-evidence.md`
  - coverage map, RED/GREEN, reviewer loop, broad verification 기록.
- `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py`
  - candidate 선택, create payload projection, form sanitize 경계.
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - selected candidate access boundary.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_connection_pages.py`
  - operator create UI와 credential reflection regression.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_permission_failures.py`
  - permission failure와 non-selectable candidate regression.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_mixed_provider_workspace.py`
  - mixed provider event/snapshot separation regression.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_operator_mixed_provider_identification.py`
  - mixed provider operator identification regression.
- `pilot-git-repo-connection/tests/support/operator_identification_rehearsal.py`
  - SC-004 리허설 fixture 생성 도우미.

# 꼭 유지해야 할 기준

- `candidateId`만으로 active connection을 만들면 안 된다.
- candidate personal grant는 workspace shared read-only operation credential이 아니다.
- selected candidate는 `access_status == "available"`일 때만 create에 사용할 수 있다.
- 선택 불가 candidate의 HTML disabled 상태는 UX일 뿐이고, web route/domain service 검증이 실제 경계다.
- create route는 candidate projection에서 provider/remote URL을 다시 가져와야 한다. 사용자가 임의로 보낸 provider/remote를 그대로 신뢰하지 않는다.
- `credentialSecret`과 credential-bearing `remoteUrl`은 validation failure 화면에 다시 노출하면 안 된다.
- candidate 목록 표시는 `list_repository_candidates`의 sanitized projection을 사용해야 한다.
- `connections/index.html`이 create/list 통합 템플릿이다. 없는 `connections/create.html`, `connections/list.html`을 다시 만들지 않는다.
- GitHub/GitLab 혼합 workspace에서는 provider, repository owner/name, workspace id가 운영자에게 구분 가능해야 한다.
- `SC-001`, `SC-004`는 실제 운영자 리허설 없이 완료 처리하지 않는다.

# 다시 논의하지 말아야 할 결정

- repository-first create에서 planning/spec/plan reference를 요구하지 않는다.
- obsolete planning/spec/plan create field는 호환 수용하지 않고 `400 INVALID_INPUT`으로 거부한다.
- candidate source 결과와 submitted remote의 canonical repository identity가 다르면 create 전에 거부한다.
- candidate source가 반환한 개인 grant material은 operation credential material이 아니다.
- GitHub/GitLab webhook provider semantics는 이번 범위에서 재설계하지 않는다.
- duplicate precheck는 git ref resolve, credential probe, mirror sync 전에 실패해야 한다.
- GitLab SSH remote의 명시적 포트는 allowlist에서 포트까지 요구한다. `:443`도 SSH에서는 default HTTPS port로 취급하지 않는다.
- legacy planning trace는 같은 workspace에 속할 때만 보존/노출한다.
- SC-004 fixture 기반 테스트는 리허설 준비물이지 실제 SC-004 완료 evidence가 아니다.

# 이번 세션에서 얻은 중요한 메모

- Jinja에서 dict의 `items` key는 method와 충돌할 수 있다. candidate 목록은 `candidates["items"]`처럼 bracket access를 사용한다.
- `git diff --stat -- pilot-git-repo-connection`은 untracked 파일을 보여주지 않는다. 새 테스트 파일 포함 여부는 `git status -sb`로 확인한다.
- candidate radio는 기본적으로 `candidateId`만 submit한다. provider/remote URL은 서버가 candidate projection에서 도출해야 한다.
- `remoteUrl`은 userinfo, password, query, fragment로 credential을 담을 수 있다. validation error 재렌더 전에 비워야 한다.
- 전체 touched test file에 `mypy`를 걸면 기존 `client.app.state` attr-defined 문제가 남아 있다. 변경 source 중심 focused mypy는 통과했다.
- `$git-commit pilot-git-repo-connection`으로 작성한 커밋 메시지는 `pilot-git-repo-connection` 하위 변경만 설명한다. `specs/...` 문서 변경은 별도 범위다.
- `specs/003-repository-first-connections/.tasks.md.swp`가 untracked로 남아 있다. editor swap/temp 파일로 보이지만 사용자 확인 없이 삭제하지 않는다.

# 테스트와 검증 상태

- focused remediation:
  - `rtk pytest tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q`
  - 결과: `43 passed`
- broad repository regression:
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - 결과: `615 passed`
- lint/format:
  - `rtk ruff check .`
  - 결과: no issues found.
  - `rtk black --check .`
  - 결과: `165 files would be left unchanged`.
- focused typing:
  - `rtk mypy src/tci/domain/services/create_repository_connection.py src/tci/web/routes/repository_connections.py tests/support/operator_identification_rehearsal.py`
  - 결과: no issues found.
- migration head:
  - `rtk alembic heads`
  - 결과: `009_repository_first_connections (head)`.
- whitespace:
  - `rtk proxy git diff --check`
  - 결과: passed.
- security audit:
  - security reviewer가 `uvx pip-audit .` 실행.
  - 결과: no known vulnerabilities found.
- reviewer loop:
  - 첫 일반 reviewer findings:
    - candidate radio가 provider/remote URL create payload에 반영되지 않음.
    - non-selectable candidate가 HTML disabled에만 의존함.
    - evidence/task가 detail UI coverage를 과대 주장함.
  - 첫 security reviewer finding:
    - validation failure 뒤 credential-bearing `remoteUrl`이 화면에 반사될 수 있음.
  - remediation 뒤 재리뷰:
    - General reviewer: no findings.
    - Python reviewer: no findings.
    - Security reviewer: no findings.
- 아직 실제 evidence가 필요한 항목:
  - `SC-001`: 6회 operator attempt timed rehearsal.
  - `SC-004`: 실제 mixed-provider identification rehearsal.
  - `SC-007`: real provider account/instance integration까지는 partial.

# 다음 세션의 시작 순서

1. `rtk proxy git status -sb`로 staged/untracked 상태를 확인한다.
2. `specs/003-repository-first-connections/.tasks.md.swp`가 editor swap인지 확인하고, 삭제 여부는 사용자 지시를 받는다.
3. 커밋 범위를 정한다. 이전 `$git-commit pilot-git-repo-connection` 메시지는 app 하위 변경만 커버하고, `specs/...` 문서는 별도 커밋 후보다.
4. 커밋한다면 untracked test/support 파일을 의도적으로 stage한다.
5. 계속 개발한다면 `T068` quickstart 업데이트부터 시작한다.
6. 그 다음 `T069`, `T070` evidence run을 수행하고 `delivery-evidence.md`에 결과를 기록한다.
7. 실제 운영자 리허설을 수행할 준비가 되면 `T071`, `T072`를 진행한다.
8. 마지막으로 `T073`에서 FR/SC coverage map을 정리한다.
9. `T030`, `SC-001`, `SC-004`는 실제 evidence 전까지 완료 처리하지 않는다.

# 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - `$git-commit pilot-git-repo-connection` 요청에 대해 app 하위 변경 기준 커밋 메시지를 작성했다.
  - 실제 커밋은 만들지 않았다.
  - 이 `handoff.md`를 현재 구현/검증/리뷰 상태로 교체했다.
- 바로 다음 액션:
  - `rtk proxy git status -sb`로 handoff 갱신 후 변경 범위를 다시 확인한다.
  - 사용자가 커밋을 원하면 app 변경과 specs 문서 변경을 한 커밋으로 묶을지 나눌지 먼저 정한다.

# 병렬 작업과 소유권

- 이번 세션에서 reviewer subagent를 사용했다. 모두 read-only였고 파일 수정은 메인 세션에서만 수행했다.
- 첫 리뷰:
  - General reviewer: candidate payload, selectable boundary, evidence overclaim 지적.
  - Security reviewer: credential-bearing `remoteUrl` reflection 지적.
- 재리뷰:
  - General reviewer: no findings.
  - Python reviewer: no findings. 단, 전체 touched test file에는 기존 `client.app.state` attr-defined mypy noise가 남아 있다고 기록했다.
  - Security reviewer: no findings, `uvx pip-audit .` no known vulnerabilities 확인.
