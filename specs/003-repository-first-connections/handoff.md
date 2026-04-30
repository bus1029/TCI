# 짧은 요약

- 이번 세션은 `$tdd`로 `T052`, `T062`, `T063`의 event/status operation credential boundary를 완료했다.
- GitHub/GitLab webhook 처리와 event status 조회가 active + read-only validated workspace operation credential만 사용하도록 막았다.
- 중복 delivery, 비활성 connection, 정적 `record_only` PR/MR 이벤트는 operation credential/ref resolve를 건너뛴다.
- auth/decrypt/bind 실패는 fail-closed로 `CONNECTION_AUTH_FAILED`를 반환하고 `REAUTH_REQUIRED` 상태를 별도 성공 세션에 남긴다.
- 일반 reviewer, security reviewer, Python reviewer 최종 결과는 모두 no findings였다.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 브랜치: `003-repository-first-connections`
- 현재 브랜치는 `origin/003-repository-first-connections`보다 `ahead 1` 상태다.
- staged 변경은 없다.
- 작업트리 변경 파일:
  - `pilot-git-repo-connection/src/tci/api/routes/repository_events.py`
  - `pilot-git-repo-connection/src/tci/domain/services/list_repository_events.py`
  - `pilot-git-repo-connection/src/tci/domain/services/process_github_event.py`
  - `pilot-git-repo-connection/src/tci/domain/services/process_gitlab_event.py`
  - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
  - `pilot-git-repo-connection/src/tci/web/routes/repository_events.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`
  - `specs/003-repository-first-connections/delivery-evidence.md`
  - `specs/003-repository-first-connections/tasks.md`
  - `specs/003-repository-first-connections/handoff.md`
- `tasks.md`에서 `T052`, `T062`, `T063`은 완료 상태다.
- 아직 남은 주요 task:
  - `T030`
  - `T048`
  - `T053`, `T054`
  - `T064-T073`
- `SC-001`, `SC-004`는 실제 운영자 리허설 전까지 완료 처리하지 말아야 한다.

# 이번 세션에서 바뀐 것

- `list_repository_events.py`
  - event status/list 조회 전에 `require_active_operation_credential_for_connection()`을 호출한다.
  - credential boundary 실패 시 `mark_connection_reauth_required()`로 상태를 `REAUTH_REQUIRED`로 남긴 뒤 예외를 다시 올린다.
- `repository_connection_support.py`
  - connection id 기반 operation credential helper를 추가했다.
  - `mark_connection_reauth_required()`를 추가해 실패 중인 outer session rollback과 분리된 상태 갱신을 제공한다.
- `repository_connection_repository.py`
  - `update_status()`를 추가했다.
- `process_github_event.py`
  - webhook head resolution이 active workspace read-only operation credential을 통해서만 동작한다.
  - provider auth 실패, decrypt 실패, credential bind 실패는 fail-closed로 `CONNECTION_AUTH_FAILED`가 된다.
  - non-retryable duplicate delivery는 기존 `duplicate_delivery` 결정을 보존한다.
  - 비활성 connection은 새/retryable delivery를 `record_only`로 기록하고 sync queue를 만들지 않는다.
  - `closed` 같은 정적 `record_only` PR action은 credential/ref resolve를 하지 않는다.
- `process_gitlab_event.py`
  - GitHub와 같은 operation credential boundary를 적용했다.
  - reviewer-only MR update, unsupported fork MR, duplicate delivery, 비활성 connection은 credential/ref resolve를 건너뛴다.
- `repository_events.py` API route
  - event status/list credential failure를 problem response로 매핑한다.
- `web/routes/repository_events.py`
  - operator event page에서 credential failure를 `400` plain text로 반환한다.
- `tests/support/repository_connection_testkit.py`
  - fake repository에 `update_status()`를 추가했다.
- `test_repository_operation_credential_boundary.py`
  - rollbacking session factory를 추가해 실패 outer session에서 상태 갱신이 보존되는지 검증한다.
  - GitHub/GitLab event processing, corrupted credential, provider auth failure, duplicate replay, non-active connection, static record-only 이벤트, status lookup을 포함해 총 17개 boundary regression을 검증한다.
- `tasks.md`
  - `T052`, `T062`, `T063`을 완료 처리했다.
- `delivery-evidence.md`
  - event/status boundary RED/GREEN, reviewer remediation, broad verification 결과를 기록했다.
  - `FR-003b`, `FR-012b`를 verified로 갱신했다.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md`
  - 현재 완료/미완료 task 기준선.
- `specs/003-repository-first-connections/delivery-evidence.md`
  - 이번 RED/GREEN, reviewer loop, broad verification 기록.
- `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - operation credential helper와 `mark_connection_reauth_required()` 계약.
- `pilot-git-repo-connection/src/tci/domain/services/process_github_event.py`
  - GitHub webhook two-phase decision과 credential resolve 경계.
- `pilot-git-repo-connection/src/tci/domain/services/process_gitlab_event.py`
  - GitLab webhook two-phase decision과 credential resolve 경계.
- `pilot-git-repo-connection/src/tci/domain/services/list_repository_events.py`
  - event status/list 조회 boundary.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - 현재 credential boundary의 핵심 regression suite.

# 꼭 유지해야 할 기준

- candidate personal grant는 operation credential로 저장하거나 승격하지 않아야 한다.
- operation credential은 active + read-only validated workspace credential이어야 한다.
- event/status/verify/collect/reverify 경로는 personal provider grant로 fallback하면 안 된다.
- credential boundary 실패는 사용자에게 remediation 가능한 `CONNECTION_AUTH_FAILED` 계열 응답으로 보여야 한다.
- auth/decrypt/bind 실패는 sync queue를 만들지 말고 fail-closed 처리해야 한다.
- `REAUTH_REQUIRED` 상태 기록은 실패 중인 outer transaction rollback에 같이 사라지면 안 된다.
- non-retryable duplicate delivery는 connection 상태가 나중에 바뀌어도 `duplicate_delivery` 결정을 보존해야 한다.
- 정적 `record_only` 이벤트는 operation credential이나 외부 `git ls-remote`를 사용하지 않아야 한다.
- 비활성 connection의 webhook은 새 sync를 만들지 말고 기록만 해야 한다.
- `connections/index.html`이 create/list 통합 템플릿이다. 없는 `connections/create.html`, `connections/list.html`을 다시 만들지 말아야 한다.
- `SC-001`, `SC-004`는 실제 운영자 리허설 없이 완료 처리하지 말아야 한다.

# 다시 논의하지 말아야 할 결정

- repository-first create에서 planning/spec/plan reference를 요구하지 않는다.
- obsolete planning/spec/plan create field는 호환 수용하지 않고 `400 INVALID_INPUT`으로 거부한다.
- `candidateId`만으로 active connection을 만들지 않는다.
- candidate source 결과와 submitted remote의 canonical repository identity가 다르면 create 전에 거부한다.
- candidate source가 반환한 개인 grant material은 operation credential material이 아니다.
- GitHub/GitLab webhook provider semantics는 이번 범위에서 재설계하지 않는다.
- duplicate precheck는 git ref resolve, credential probe, mirror sync 전에 실패해야 한다.
- GitLab SSH remote의 명시적 포트는 allowlist에서 포트까지 요구한다. `:443`도 SSH에서는 default HTTPS port로 취급하지 않는다.
- legacy planning trace는 같은 workspace에 속할 때만 보존/노출한다.

# 이번 세션에서 얻은 중요한 메모

- `RepositoryConnectionProblem`은 `RuntimeError` 계열이라 broad `except RuntimeError`보다 먼저 잡아야 한다.
- corrupted encrypted credential은 decrypt 단계에서 `RepositoryConnectionProblem`으로 올라오며, 이 경로도 `REAUTH_REQUIRED`를 남겨야 한다.
- provider `GitConnectionAuthError`를 `None`으로 삼키면 stale-head 판단을 우회해 sync가 queued될 수 있다.
- duplicate delivery 판단 뒤에 non-active status override를 무조건 적용하면 기존 event의 `duplicate_delivery`가 `record_only`로 덮인다.
- 정적 `record_only` 이벤트도 parser가 `target_head_sha`, `requested_ref_name`을 채우므로 pre-decision 없이 resolve하면 credential을 불필요하게 사용한다.
- `$git-commit pilot-git-repo-connection`은 staged diff가 없어 working tree diff 기준으로 작성했다.
- 이 커밋 메시지는 `pilot-git-repo-connection` 하위 변경만 반영한다. `specs/...` 문서 변경은 범위 밖이다.

# 테스트와 검증 상태

- RED:
  - `rtk proxy pytest tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - 결과: event/status 경로가 revoked credential을 허용해 실패.
- Reviewer remediation RED:
  - `rtk proxy pytest tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - 결과: rollback 중 `REAUTH_REQUIRED` 유실, provider auth fail-open, duplicate delivery credential 요구가 드러남.
- 최종 focused boundary:
  - `rtk pytest tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - 결과: `17 passed`.
- 관련 webhook/operator:
  - `rtk pytest tests/integration/repository_connections/test_github_webhook_refresh.py tests/integration/repository_connections/test_gitlab_provider_flows.py tests/integration/repository_connections/test_operator_event_pages.py -q`
  - 결과: `23 passed`.
- broad repository regression:
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - 결과: `605 passed`.
- focused typing:
  - `rtk mypy src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py src/tci/domain/services/list_repository_events.py src/tci/domain/services/repository_connection_support.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/api/routes/repository_events.py src/tci/web/routes/repository_events.py tests/support/repository_connection_testkit.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - 결과: no issues found.
- lint/format:
  - `rtk ruff check .`
  - 결과: no issues found.
  - `rtk black --check .`
  - 결과: `162 files would be left unchanged`.
- migration head:
  - `rtk alembic heads`
  - 결과: `009_repository_first_connections (head)`.
- whitespace:
  - `rtk proxy git diff --check`
  - 결과: passed.
- 최종 reviewer loop:
  - General reviewer: no findings.
  - Security reviewer: no findings.
  - Python reviewer: no findings.
- 보안 도구:
  - `pip-audit`, `safety`, `bandit`는 로컬에 없어 실행하지 못했다.
  - dependency/lockfile 변경은 없다.

# 다음 세션의 시작 순서

1. `git status -sb`로 현재 변경과 staged 상태를 확인한다.
2. 커밋할 경우, 아래 `$git-commit pilot-git-repo-connection` 메시지는 `pilot-git-repo-connection` 하위 변경만 설명한다.
3. 문서 변경까지 같은 커밋에 넣을지, 별도 docs 커밋으로 나눌지 결정한다.
4. 계속 개발하면 `T048`, `T064-T066` operator candidate UI와 credential failure state부터 시작한다.
5. 그 다음 `T053`, `T054` mixed-provider separation/identification evidence를 진행한다.
6. `T030`, `SC-001`, `SC-004`는 실제 운영자 리허설 evidence가 준비될 때까지 완료 처리하지 않는다.

# 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - `cmux` 새 terminal pane을 `workspace:1`에 열었다. 생성 결과는 `surface:3`, `pane:3`이다.
  - `$git-commit pilot-git-repo-connection` 범위의 커밋 메시지를 작성했다.
  - 이 `handoff.md`를 현재 세션 상태로 교체했다.
- 바로 다음 액션:
  - 커밋을 실제로 만들지 여부를 사용자가 결정한다.
  - 커밋한다면 `pilot-git-repo-connection` scoped 변경과 `specs/...` 문서 변경의 커밋 범위를 먼저 정한다.

# 병렬 작업과 소유권

- 이번 세션에서 reviewer subagent를 사용했다. 모두 read-only였고 파일 수정은 메인 세션에서만 수행했다.
- 최종 reviewer:
  - General reviewer: no findings, 추가 계약/통합 테스트 114개 통과 확인.
  - Security reviewer: no findings, credential fallback/use/fail-closed/static search 확인.
  - Python reviewer: no findings, focused mypy/ruff/black/py_compile 확인.
- `cmux`:
  - `workspace:1`에 새 terminal pane `pane:3`, `surface:3`을 생성했다.
  - 이 pane은 작업 표시용으로 열었고, 실제 파일 수정은 메인 세션에서 수행했다.
