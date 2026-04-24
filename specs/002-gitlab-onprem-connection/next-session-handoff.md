# Next Session Handoff: GitLab Self-Managed Connection

## 1. 짧은 요약

GitLab self-managed 저장소 연결의 US1 backend 경로를 완료했다.

현재 완료 범위는 Phase 2의 US1 필요분(`T009`, `T010`, `T012`)과 US1 backend task `T017`~`T021`, evidence `T023`이다. `T008`은 US3 webhook event normalization 선행 작업으로 defer했다. `T022` operator detail/read-model/UI polish는 아직 미구현이다.

## 2. 현재 상태

- 코드 변경은 아직 커밋되지 않았다.
- `tasks.md`는 `T009`, `T010`, `T012`, `T017`~`T021`, `T023` 완료로 갱신됐다.
- `delivery-evidence.md`는 RED/GREEN, 정적 검증, reviewer loop 결과까지 갱신됐다.
- 최종 `reviewer`, `python-reviewer`, `security-reviewer` 재리뷰는 모두 findings 없음이다.
- `python -m pip check`는 통과했다.
- `pip-audit` / `python -m pip_audit`는 로컬 도구 미설치로 미실행이다.

현재 `git status --short` 기준 주요 변경:

- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- `pilot-git-repo-connection/src/tci/app.py`
- `pilot-git-repo-connection/src/tci/domain/services/update_default_ref.py`
- `pilot-git-repo-connection/src/tci/infrastructure/git/git_readonly_validator.py`
- `pilot-git-repo-connection/src/tci/infrastructure/git/gitlab_readonly_validator.py` 신규
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_app.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_update_default_ref.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_readonly_validator.py` 신규
- `specs/002-gitlab-onprem-connection/delivery-evidence.md`
- `specs/002-gitlab-onprem-connection/tasks.md`
- `specs/002-gitlab-onprem-connection/next-session-handoff.md`

## 3. 이번 세션에서 바뀐 것

- `GitLabReadonlyValidator`를 추가해 GitLab-specific dry-run push stderr를 read-only/auth failure 신호로 처리한다.
- `GitReadonlyValidator`의 auth/read-only token 목록을 subclass가 확장 가능하도록 `ClassVar[tuple[str, ...]]`로 정리했다.
- `build_app_dependencies()`가 production dependency로 `GitLabReadonlyValidator`를 사용하게 했다.
- GitLab connection create/patch/detail response에 `providerInstanceUrl`, `providerProjectPath`를 포함한다.
- 보안 리뷰에 따라 `webhookAuthMode`는 일반 connection response에서 노출하지 않는다.
- `update_default_ref.py`가 remote auth/ref failure를 `reauth_required` / `ref_missing`으로 persisted transition한다.
- `update_default_ref.py`는 local decrypt/config failure에서는 connection status를 변경하지 않는다.
- active credential revision이 없으면 default-ref update에서 `reauth_required`로 전환한다.
- API cross-request regression을 추가했다: `PATCH`가 missing ref로 실패하면 detail status가 `ref_missing`이고 이후 snapshot 요청이 `409 DEFAULT_REF_NOT_FOUND`로 차단된다.
- Phase 2 gate를 현실 기준으로 정리했다. US1 gate는 `T005`, `T006`, `T007`, `T009`, `T010`, `T011`, `T012` 완료로 충족한다.

## 4. 다음 에이전트가 먼저 봐야 할 파일

- `specs/002-gitlab-onprem-connection/tasks.md`
- `specs/002-gitlab-onprem-connection/delivery-evidence.md`
- `specs/002-gitlab-onprem-connection/spec.md`
- `specs/002-gitlab-onprem-connection/plan.md`
- `pilot-git-repo-connection/src/tci/infrastructure/git/gitlab_readonly_validator.py`
- `pilot-git-repo-connection/src/tci/infrastructure/git/git_readonly_validator.py`
- `pilot-git-repo-connection/src/tci/domain/services/update_default_ref.py`
- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_readonly_validator.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_update_default_ref.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`

## 5. 꼭 유지해야 할 기준

- GitLab self-managed outbound git 접근 전에는 반드시 allowlist 검사를 통과해야 한다.
- Stored credential은 GitLab allowlist 통과 전에 decrypt하지 않는다.
- Allowlist는 port-sensitive origin 정책이다. 기본 포트는 host만 허용하고, 비표준 포트는 `host:port`가 필요하다.
- SSH custom port는 `provider_instance_url`에 저장하지 않는다. 저장된 `remote_url`에서 port를 다시 파싱해야 한다.
- Snapshot allowlist rejection은 credential failure나 `reauth_required`로 오분류하면 안 된다. `MIRROR_SYNC_FAILED`로 기록해야 한다.
- Scope preview의 allowlist rejection은 preview 실패로 삼키면 안 된다.
- GitHub 기존 흐름은 GitLab validator 추가 때문에 깨지면 안 된다.
- Generic `401 unauthorized` / `403 forbidden`을 auth failure로 분류하지 않는다. GitLab-specific `HTTP Basic: Access denied` 같은 명확한 메시지만 auth failure로 본다.
- `webhookAuthMode`는 일반 connection create/patch/detail response에 노출하지 않는다.
- local decrypt/config failure는 사용자 credential 문제로 persisted transition하지 않는다.

## 6. 다시 논의하지 말아야 할 결정

- `T008`은 US3 webhook event normalization 선행 작업으로 defer한다.
- `T022`는 아직 미구현이며 다음 UI/detail polish 후보로 남긴다.
- 사용자가 GitLab instance URL을 직접 입력하는 방식은 이번 범위에서 제외한다.
- GitLab instance subpath는 heuristic으로 추정하지 않는다.
- `/gitlab` path segment도 namespace/project path로 취급한다.
- `localhost`, private IPv4, 비표준 SSH/HTTPS 포트는 지원한다. 단, 해당 origin은 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`에 명시되어야 한다.
- IPv6는 이번 범위에서 거부한다.
- `github.com`과 trailing-dot host는 GitLab self-managed provider로 받지 않는다.
- 공식 connection status는 `active`, `reauth_required`, `ref_missing`만 유지한다. Reachability/webhook 문제는 health로 분리한다.

## 7. 이번 세션에서 얻은 중요한 메모

- `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS` 예시:
  - `gitlab.example.com`
  - `gitlab.example.com:8443`
  - `localhost:2222`
  - `192.168.10.20:2222`
- 비표준 HTTPS 포트는 `provider_instance_url`에 보존한다.
- 비표준 SSH 포트는 instance URL에는 보존하지 않고 `remote_url`에서 allowlist origin을 재계산한다.
- GitLab create/patch/detail response는 `providerInstanceUrl`, `providerProjectPath`를 노출한다.
- `webhookAuthMode`는 response에서 제외한다. 보안 리뷰에서 recon risk로 지적됐고 제거 완료됐다.
- `specs/001-git-repo-connection/docker-compose/docker-compose-test.yaml`는 현재 tracked file이다. 이전 handoff의 untracked 메모는 stale이다.
- Repo에는 tracked `.pyc` 파일이 일부 있다. 테스트 실행으로 변경될 수 있으나 소스 변경이 아니면 임의 삭제하지 말고 `git restore -- <tracked .pyc>`로 오염만 제거한다.

## 8. 테스트와 검증 상태

- RED/GREEN 핵심:
  - `tests/unit/repository_connections/test_gitlab_readonly_validator.py`
    - 처음에는 `ModuleNotFoundError: No module named 'tci.infrastructure.git.gitlab_readonly_validator'`로 실패
    - 구현 후 pass
  - `tests/unit/repository_connections/test_app.py::test_build_app_dependencies_uses_gitlab_aware_readonly_validator`
    - 처음에는 generic `GitReadonlyValidator` wiring으로 실패
    - 구현 후 `GitLabReadonlyValidator` wiring과 behavior sample pass
  - `tests/unit/repository_connections/test_update_default_ref.py`
    - missing ref/auth/missing credential transition, local decrypt non-transition regression 추가
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py`
    - GitLab create/patch/detail metadata, `webhookAuthMode` 비노출, cross-request snapshot block regression 추가

- 전체 변경 범위:
  - `pytest tests/unit/repository_connections tests/contract/repository_ingestion tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_gitlab_compatibility.py -q`
  - 결과: `264 passed, 12 skipped in 7.21s`

- 정적 검증:
  - `mypy src/tci/app.py src/tci/infrastructure/git/git_readonly_validator.py src/tci/infrastructure/git/gitlab_readonly_validator.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/update_default_ref.py tests/unit/repository_connections/test_gitlab_readonly_validator.py tests/unit/repository_connections/test_app.py tests/unit/repository_connections/test_update_default_ref.py`
  - 결과: `Success: no issues found in 8 source files`
  - `ruff check src/tci/app.py src/tci/infrastructure/git/git_readonly_validator.py src/tci/infrastructure/git/gitlab_readonly_validator.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/update_default_ref.py tests/unit/repository_connections/test_gitlab_readonly_validator.py tests/unit/repository_connections/test_app.py tests/unit/repository_connections/test_update_default_ref.py tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - 결과: `All checks passed!`
  - `black --check src/tci/app.py src/tci/infrastructure/git/git_readonly_validator.py src/tci/infrastructure/git/gitlab_readonly_validator.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/update_default_ref.py tests/unit/repository_connections/test_gitlab_readonly_validator.py tests/unit/repository_connections/test_app.py tests/unit/repository_connections/test_update_default_ref.py tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - 결과: `9 files would be left unchanged`
  - `git diff --check`
  - 결과: 통과

- Package sanity:
  - `python -m pip check`
  - 결과: `No broken requirements found.`
  - `python -m pip_audit`
  - 결과: `/opt/anaconda3/bin/python: No module named pip_audit`
  - `command -v pip-audit && pip-audit || true`
  - 결과: executable 없음
  - 남은 gap: package vulnerability scanner는 로컬 설치 도구 부재로 미실행

- Reviewer loop:
  - 1차 `reviewer`: coverage gap 2건. 수정 완료.
  - 1차 `python-reviewer`: missing credential transition 등 3건. 수정 완료.
  - 1차 `security-reviewer`: generic `401/403`, `webhookAuthMode` 노출, decrypt fault misclassification. 수정 완료.
  - 최종 `reviewer`: findings 없음, approve.
  - 최종 `python-reviewer`: findings 없음, approve.
  - 최종 `security-reviewer`: findings 없음.

## 9. 다음 세션의 시작 순서

1. `git status --short`로 diff를 확인한다.
2. 이 handoff와 `tasks.md`, `delivery-evidence.md`가 서로 맞는지 빠르게 확인한다.
3. 다음 scope를 고른다:
   - UI/detail polish 우선이면 `T022`
   - webhook foundation 우선이면 `T008` 후 `T032`~`T043`
   - scope/ref 관리 우선이면 `T024`~`T031`
4. 다음 개발도 TDD로 진행한다. RED/GREEN 증거를 `delivery-evidence.md`에 남긴다.
5. 변경 후 `pytest`, `mypy`, `ruff`, `black --check`, `git diff --check`, `python -m pip check`를 실행한다.
6. 구현 후 `reviewer`, `python-reviewer`, 보안 민감 변경이면 `security-reviewer`를 다시 돌린다.

## 10. 마지막 액션과 바로 다음 액션

마지막 액션은 이 handoff를 현재 diff, 테스트, reviewer 결과 기준으로 교체한 것이다.

바로 다음 액션은 `git status --short` 확인 후 다음 scope를 선택하는 것이다. 추천 순서는 `T022`로 operator detail/read-model/UI를 마감하거나, US3로 가려면 먼저 `T008` provider event normalization을 시작하는 것이다.

## 병렬 작업과 소유권

- 구현 소유권은 parent session이 가졌다.
- `tdd-guide`는 read-only 테스트 분해에 사용했다.
- `reviewer`, `python-reviewer`, `security-reviewer`는 read-only 검증에 사용했다.
- 1차 reviewer findings는 parent session에서 수정했다.
- 최종 reviewer loop는 모두 findings 없음이다.
