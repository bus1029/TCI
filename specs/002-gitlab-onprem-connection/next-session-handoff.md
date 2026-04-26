# Next Session Handoff: GitLab Self-Managed Connection

## 1. 짧은 요약

GitLab self-managed 저장소 연결의 `US1`과 `US2`는 완료됐다.

- 완료: `T013`~`T023` GitLab 연결/verify/초기 snapshot
- 완료: `T024`~`T031` scope/ref 관리와 filtered snapshot
- 완료: reviewer loop findings 전부 해소
- 아직 미구현: `T008`, `T032`~`T043` US3 webhook 수신/처리

다음 세션은 US3 시작 전 `T008` provider event normalization부터 TDD로 진행하면 된다.

## 2. 현재 상태

- 코드 변경은 아직 커밋되지 않았다.
- `git status --short` 기준 다수의 수정 파일과 신규 파일이 있다.
- `tasks.md`는 `T024`~`T031` 완료, 다음 우선순위 `T008`/US3로 갱신됐다.
- `delivery-evidence.md`는 US2 RED/GREEN, reviewer loop, security hardening, 전체 Python suite 결과까지 갱신됐다.
- `reviewer`, `python-reviewer`, `security-reviewer`는 모두 blocking findings 없음으로 종료됐다.
- 실행 중인 subagent는 없다.

중요 신규 파일:

- `pilot-git-repo-connection/src/tci/infrastructure/git/git_command_env.py`
- `pilot-git-repo-connection/alembic/versions/005_scope_rule_preview_failed_warning.py`
- `pilot-git-repo-connection/alembic/versions/006_scope_rule_auto_default_flag.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_gitlab_scope_contract.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_scope_rules.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_scoped_snapshot.py`

## 3. 이번 세션에서 바뀐 것

- Scope rule API/HTML이 `excludeBinary`를 request, response, detail projection, operator form에 포함한다.
- GitLab scope save/detail contract와 scoped snapshot integration 테스트가 추가됐다.
- Scope rule persistence에 `preview_failed` 경고 상태와 auto-default provenance가 추가됐다.
- Snapshot build는 active/default scope version을 확정한 뒤 materialize하고, scope 변경 race를 retry한다.
- Empty-result snapshot은 `NO_INCLUDED_FILES`로 실패하되 connection status를 잘못 전환하지 않는다.
- Git mirror materialization은 scope/hard-exclude/file-type 필터를 blob read 전에 적용한다.
- Snapshot tree walk는 raw tree entry count도 제한한다.
- HTTPS PAT는 remote URL에 넣지 않고 askpass Unix socket + per-session token + request budget으로 처리한다.
- SSH private key는 temp file에 쓰지 않고 isolated `ssh-agent`에 stdin으로 등록한다.
- Git subprocess env는 ambient Git config, service-user home config, ambient SSH agent, ambient `GIT_SSH_COMMAND`를 상속하지 않는다.
- Operator scope page가 GitLab instance URL, project path, binary policy warning을 표시한다.
- `webhookAuthMode`, `shared_token`, secret 값은 general API/detail/operator HTML에 노출하지 않는다.

## 4. 다음 에이전트가 먼저 봐야 할 파일

현재 상태 확인:

- `specs/002-gitlab-onprem-connection/tasks.md`
- `specs/002-gitlab-onprem-connection/delivery-evidence.md`
- `specs/002-gitlab-onprem-connection/spec.md`
- `specs/002-gitlab-onprem-connection/plan.md`

US2 구현/회귀 맥락:

- `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
- `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
- `pilot-git-repo-connection/src/tci/infrastructure/git/git_command_env.py`
- `pilot-git-repo-connection/src/tci/infrastructure/git/git_mirror_manager.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_git_foundation.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_git_mirror_manager.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_gitlab_scope_contract.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_scope_rules.py`
- `pilot-git-repo-connection/tests/integration/repository_connections/test_gitlab_scoped_snapshot.py`

US3 시작 파일:

- `pilot-git-repo-connection/src/tci/infrastructure/webhooks/provider_event_types.py`
- `pilot-git-repo-connection/src/tci/domain/services/repository_event_processing.py`
- `pilot-git-repo-connection/src/tci/infrastructure/webhooks/gitlab_token_verifier.py`
- `pilot-git-repo-connection/src/tci/infrastructure/webhooks/gitlab_delivery_id.py`
- `pilot-git-repo-connection/src/tci/infrastructure/webhooks/gitlab_event_parser.py`
- `pilot-git-repo-connection/src/tci/domain/services/process_gitlab_event.py`
- `pilot-git-repo-connection/src/tci/api/routes/gitlab_webhooks.py`
- `pilot-git-repo-connection/src/tci/infrastructure/queue/repository_ingestion_tasks.py`

## 5. 꼭 유지해야 할 기준

- GitLab self-managed outbound git 접근 전에는 반드시 allowlist 검사를 통과해야 한다.
- Stored credential은 GitLab allowlist 통과 전에 decrypt하지 않는다.
- Allowlist는 port-sensitive origin 정책이다. 비표준 포트는 `host:port`가 필요하다.
- SSH custom port는 `provider_instance_url`에 저장하지 않는다. 저장된 `remote_url`에서 다시 파싱해야 한다.
- Snapshot allowlist rejection은 credential failure나 `reauth_required`로 오분류하면 안 된다. `MIRROR_SYNC_FAILED`로 기록해야 한다.
- Scope preview의 allowlist rejection은 preview failure로 삼키면 안 된다.
- Generic `401 unauthorized` / `403 forbidden`은 auth failure로 분류하지 않는다.
- `webhookAuthMode`, `shared_token`, webhook secret 값은 general response/operator HTML에 노출하지 않는다.
- Local decrypt/config failure는 사용자 credential 문제로 persisted transition하지 않는다.
- GitHub 기존 흐름은 GitLab 변경 때문에 깨지면 안 된다.
- Credentialed Git subprocess는 ambient Git config, ambient `GIT_SSH_COMMAND`, ambient `SSH_AUTH_SOCK`을 상속하면 안 된다.
- HTTPS askpass socket은 token 없는 local client에 PAT를 제공하면 안 된다.
- SSH agent cleanup 실패는 본 작업의 성공/실패 결과를 덮어쓰면 안 된다.
- 대형 저장소는 scope filter 이전 raw tree entry cap으로 worker 점유를 제한해야 한다.

## 6. 다시 논의하지 말아야 할 결정

- `T008`은 US3 webhook event normalization 선행 작업으로 defer한다.
- `T022`는 완료됐다.
- `T024`~`T031`은 완료됐다.
- 다음 기본 후보는 US3 webhook 수신/처리(`T008`, `T032`~`T043`)다.
- 사용자가 GitLab instance URL을 직접 입력하는 방식은 이번 범위에서 제외한다.
- GitLab instance subpath는 heuristic으로 추정하지 않는다.
- `/gitlab` path segment도 namespace/project path로 취급한다.
- `localhost`, private IPv4, 비표준 SSH/HTTPS 포트는 지원한다. 해당 origin은 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`에 명시되어야 한다.
- IPv6는 이번 범위에서 거부한다.
- `github.com`과 trailing-dot host는 GitLab self-managed provider로 받지 않는다.
- 공식 connection status는 `active`, `reauth_required`, `ref_missing`만 유지한다. Reachability/webhook 문제는 health로 분리한다.

## 7. 이번 세션에서 얻은 중요한 메모

- 기존 scope engine/snapshot pipeline은 이미 provider-neutral이었다.
- `excludeBinary=false`일 때 binary file은 포함 가능하지만, hard excluded path와 `5 MiB` 초과 파일은 계속 제외된다.
- Operator scope form에서 checkbox가 누락된 직접 POST는 기존 기본값 유지를 위해 `excludeBinary=true`로 처리한다.
- GitLab allowlist rejection은 scope preview helper에서 `RepositoryConnectionProblem`으로 전파되어야 한다.
- Repo에는 tracked `.pyc` 파일이 일부 있다. 테스트 실행으로 변경되면 소스 변경이 아니므로 `git restore -- <tracked .pyc>`로 오염만 제거한다.
- `pip_audit`는 현재 workspace에 설치되어 있지 않다. `python -m pip check`는 통과했다.

## 8. 테스트와 검증 상태

TDD 주요 RED:

- 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/contract/repository_ingestion/test_gitlab_scope_contract.py tests/unit/repository_connections/test_gitlab_scope_rules.py tests/integration/repository_connections/test_gitlab_scoped_snapshot.py -q`
- 결과: `2 failed, 6 passed`
- 의도한 실패: scope projection에 `excludeBinary`가 없고, `excludeBinary=false`가 snapshot filter path에 전달되지 않음

TDD GREEN:

- 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/contract/repository_ingestion/test_gitlab_scope_contract.py tests/unit/repository_connections/test_gitlab_scope_rules.py tests/integration/repository_connections/test_gitlab_scoped_snapshot.py -q`
- 결과: `8 passed in 0.93s`

Reviewer finding hardening:

- 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections/test_git_foundation.py -q`
- 결과: `32 passed in 2.28s`
- 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections/test_git_mirror_manager.py -q`
- 결과: `19 passed in 9.66s`

관련 범위 회귀:

- 명령: `PYTHONDONTWRITEBYTECODE=1 pytest tests/contract/repository_ingestion/test_gitlab_scope_contract.py tests/unit/repository_connections/test_gitlab_scope_rules.py tests/unit/repository_connections/test_git_mirror_manager.py tests/unit/repository_connections/test_git_foundation.py tests/unit/repository_connections/test_phase2_foundation.py tests/unit/repository_connections/test_update_default_ref.py tests/unit/repository_connections/test_verify_repository_connection.py tests/integration/repository_connections/test_gitlab_scoped_snapshot.py tests/contract/repository_ingestion/test_repository_connection_contract.py tests/contract/repository_ingestion/test_repository_scope_contract.py tests/integration/repository_connections/test_scoped_snapshot.py tests/integration/repository_connections/test_operator_scope_pages.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_phase2_migration_smoke.py -q`
- 결과: `174 passed, 5 skipped in 15.03s`

전체 Python suite:

- 명령: `PYTHONDONTWRITEBYTECODE=1 pytest -q`
- 결과: `354 passed, 17 skipped in 16.43s`

정적/패키지 검증:

- focused `mypy`: `Success: no issues found in 22 source files`
- focused `ruff check`: `All checks passed!`
- focused `black --check`: `5 files would be left unchanged`
- `git diff --check`: 통과
- `python -m pip check`: `No broken requirements found.`
- `python -m pip_audit`: `/opt/anaconda3/bin/python: No module named pip_audit`

최종 reviewer 결과:

- `reviewer`: blocking findings 없음
- `python-reviewer`: blocking findings 없음, approve
- `security-reviewer`: blocking findings 없음, prior security findings addressed

## 9. 다음 세션의 시작 순서

1. `git status --short`로 현재 diff와 tracked `.pyc` 오염 여부를 확인한다.
2. `specs/002-gitlab-onprem-connection/tasks.md`에서 `T008`과 US3 작업 순서를 확인한다.
3. `T008` provider event normalization의 RED 테스트를 먼저 작성한다.
4. 이어서 `T032`~`T035` webhook contract/unit/integration/GitHub regression 테스트를 작성한다.
5. RED 확인 후 `T036`~`T042` 구현으로 넘어간다.
6. 구현 후 `reviewer`, `python-reviewer`, `security-reviewer` loop를 다시 돌린다.

## 10. 마지막 액션과 바로 다음 액션

마지막 액션은 US2 reviewer loop findings 해소, 전체 Python suite 검증, evidence/handoff 갱신이다.

바로 다음 액션은 US3 선행 `T008`의 RED 테스트 작성이다.

## 병렬 작업과 소유권

- 구현 소유권은 parent session이 가졌다.
- 계획 단계에서 `planner`가 read-only 단계 분해를 보조했다.
- reviewer loop에서 `reviewer`, `python-reviewer`, `security-reviewer`가 재검토했다.
- reviewer loop는 no blocking findings로 종료됐다.
