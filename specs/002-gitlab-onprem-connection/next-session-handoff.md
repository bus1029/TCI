# Next Session Handoff: GitLab Self-Managed Connection

## 1. 짧은 요약

GitLab self-managed 저장소 연결의 핵심 기반을 이어서 구현했다. 이번 세션의 중심은 `remoteUrl` 기반 GitLab provider 파싱, 온프레미스 host allowlist, localhost/private-IP/비표준 포트 지원, 그리고 outbound git/credential-bound 경로의 fail-closed 검증이었다.

현재 구현은 GitLab self-managed 연결 생성, 검증, 기본 ref 변경, scope preview, snapshot build 경로에서 동일한 allowlist 정책을 공유한다. 최종 reviewer 루프는 `reviewer`, `python-reviewer`, `security-reviewer` 모두 finding 없음으로 끝났다.

## 2. 현재 상태

- 코드 변경은 아직 커밋되지 않았다.
- `tasks.md`와 `delivery-evidence.md`는 2026-04-24 구현 상태 기준으로 1차 정합화됐다.
- `pilot-git-repo-connection/src/tci/infrastructure/git/remote_parsers.py`는 새 파일이며, GitLab/GitHub remote 파싱 진입점으로 사용된다.
- GitLab self-managed는 explicit instance URL 입력 없이 `remoteUrl`에서 heuristic으로 instance와 project path를 계산한다.
- `/gitlab` subpath는 instance path로 추정하지 않는다. 예: `https://gitlab.example.com/gitlab/group/repo.git`은 `provider_instance_url=https://gitlab.example.com`, `provider_project_path=gitlab/group/repo`로 저장한다.
- `localhost`, private IPv4, 비표준 HTTPS/SSH 포트는 지원하되 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS` allowlist에 exact origin이 있어야 한다.
- GitHub host, trailing-dot host, IPv6, query/fragment/userinfo, whitespace/control chars, dot path segment, malformed port는 GitLab provider에서 거부된다.

## 3. 이번 세션에서 바뀐 것

- GitLab remote parser를 추가하고 connection creation 서비스가 공통 parser를 사용하도록 변경했다.
- `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS` 설정을 추가했다.
- `ensure_gitlab_self_managed_host_allowed`를 추가하고 create/verify/update default ref/snapshot build/scope preview 경로에 연결했다.
- Scope preview가 GitLab allowlist 거부를 fail-open하지 않도록 `RepositoryConnectionProblem`을 전파하게 했다.
- DB 모델과 migration에 GitLab provider 제약, `provider_instance_url`, `provider_project_path` 관련 검증을 보강했다.
- Repository persistence validation에서 GitLab remote URL, instance URL, project path consistency를 검증하게 했다.
- `provider_project_path` DB column은 rollout 안전성을 위해 nullable 유지하되, GitLab row는 provider-scoped check로 non-null을 요구한다.
- Korean problem detail의 unsupported provider 메시지를 GitHub 고정 표현에서 provider-neutral 표현으로 바꿨다.
- 테스트 생성물이 커밋되지 않도록 `.gitignore`의 `__pycache__/`, `*.pyc` 규칙을 유지했다.

## 4. 다음 에이전트가 먼저 봐야 할 파일

- `specs/002-gitlab-onprem-connection/tasks.md`
- `specs/002-gitlab-onprem-connection/delivery-evidence.md`
- `pilot-git-repo-connection/src/tci/infrastructure/git/remote_parsers.py`
- `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
- `pilot-git-repo-connection/src/tci/domain/services/verify_repository_connection.py`
- `pilot-git-repo-connection/src/tci/domain/services/update_default_ref.py`
- `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
- `pilot-git-repo-connection/src/tci/domain/services/evaluate_scope_rule_warning.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- `pilot-git-repo-connection/src/tci/settings.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_provider_parsing.py`
- `pilot-git-repo-connection/tests/unit/repository_connections/test_gitlab_foundation.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py`
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_scope_contract.py`

## 5. 꼭 유지해야 할 기준

- GitLab self-managed outbound git 접근 전에는 반드시 allowlist 검사를 통과해야 한다.
- Allowlist는 host-only가 아니라 port-sensitive origin 정책이다. 기본 포트는 host만 허용하고, 비표준 포트는 `host:port`가 필요하다.
- SSH custom port는 `provider_instance_url`에 저장하지 않는다. 이후 검증은 저장된 `remote_url`에서 port를 다시 파싱한다.
- Scope preview의 allowlist rejection은 preview 실패로 삼키면 안 된다.
- GitHub 기존 흐름은 provider-specific GitLab validation 때문에 깨지면 안 된다.
- Rollout 안전성을 위해 GitHub/기존 row에 GitLab-only non-null 제약을 강제하면 안 된다.
- `__pycache__`와 `*.pyc`는 커밋 대상이 아니다.

## 6. 다시 논의하지 말아야 할 결정

- 사용자가 GitLab instance URL을 직접 올리는 방식은 이번 방향에서 제외했다.
- GitLab instance subpath는 heuristic으로 추정하지 않는다.
- `/gitlab`이라는 path segment도 우선 namespace/project path로 취급한다.
- localhost/private-IP/비표준 SSH/HTTPS 포트는 지원한다.
- 단, 해당 origin은 operator allowlist에 명시되어야 한다.
- IPv6는 이번 범위에서 거부한다.
- `github.com`과 trailing-dot 변형은 GitLab self-managed provider로 받지 않는다.

## 7. 이번 세션에서 얻은 중요한 메모

- `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS` 예시:
  - `gitlab.example.com`
  - `gitlab.example.com:8443`
  - `localhost:2222`
  - `192.168.10.20:2222`
- 비표준 HTTPS 포트는 `provider_instance_url`에 보존한다.
- 비표준 SSH 포트는 instance URL에는 보존하지 않고 remote URL로부터 allowlist origin을 재계산한다.
- `update_default_ref.py`는 현재 context load 과정에서 credential decrypt가 allowlist check보다 먼저 발생한다. 네트워크 접근 전에는 차단되므로 최종 security-reviewer는 finding으로 보지 않았지만, least-exposure 개선 여지는 남아 있다.
- 실제 PostgreSQL에 Alembic migration을 적용한 검증은 아직 수행하지 않았다.
- 현재 sandbox에서 `git restore -- '*.pyc' '*/__pycache__/*'`가 `.git/index.lock` 생성 권한 문제로 실패했다. 다음 세션에서 Git 권한 또는 index lock 문제를 먼저 확인해야 한다.

## 8. 테스트와 검증 상태

- `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/repository_connections tests/contract/repository_ingestion`
  - 결과: `244 passed, 9 skipped in 7.52s`
- `PYTHONDONTWRITEBYTECODE=1 mypy ...`
  - 변경된 source/test 중심 12개 파일 검사 결과: `Success: no issues found in 12 source files`
- `ruff check ...`
  - 결과: `All checks passed!`
- `black --check ...`
  - 결과: `17 files would be left unchanged`
- `git diff --check`
  - 결과: 통과
- 최종 `reviewer`
  - findings 없음
  - residual risk: 실제 PostgreSQL Alembic migration 미검증
- 최종 `python-reviewer`
  - findings 없음
  - residual risk: subagent 환경에서는 mypy/basedpyright 실행 불가였으나, 로컬 focused mypy는 통과
- 최종 `security-reviewer`
  - findings 없음
  - residuals: `update_default_ref.py` decrypt-before-allowlist 순서 개선 여지, stored SSH custom-port가 scope preview와 snapshot build를 모두 통과하는 직접 E2E 부족

## 9. 다음 세션의 시작 순서

1. `git status --short`로 작업트리를 확인한다.
2. `.pyc` 변경이 남아 있으면 Git 권한/index lock 문제를 해결한 뒤 tracked pyc를 HEAD로 되돌린다.
3. 실제 PostgreSQL 환경에서 Alembic upgrade/downgrade 또는 migration constraint 검증을 수행한다.
4. 남은 webhook/detail/UI task를 진행한다.
5. 변경 전체에 대해 `pytest`, `mypy`, `ruff`, `black --check`, `git diff --check`를 다시 실행한다.
6. 최종 reviewer 루프를 다시 한 번 돌리고, finding이 없으면 커밋 준비를 한다.

## 10. 마지막 액션과 바로 다음 액션

마지막 액션은 `specs/002-gitlab-onprem-connection/` 하위 문서를 현재 구현 상태에 맞춰 정합화한 것이다.

바로 다음 액션은 Git 작업트리에서 pyc 노이즈와 `.git/index.lock` 생성 권한 문제를 정리하는 것이다. 그 다음 실제 PostgreSQL migration 검증과 남은 webhook/detail/UI task를 이어가면 된다.

## 병렬 작업과 소유권

- 구현 소유권은 현재 parent session이 가진다.
- `reviewer`, `python-reviewer`, `security-reviewer`는 최종 read-only 검증에 사용했다.
- 다음 세션에서 다시 agent를 호출한다면 같은 diff를 대상으로 병렬 reviewer 3종을 먼저 돌리는 것보다, migration 검증과 남은 webhook/detail/UI 구현을 완료한 뒤 최종 reviewer loop를 돌리는 편이 효율적이다.
