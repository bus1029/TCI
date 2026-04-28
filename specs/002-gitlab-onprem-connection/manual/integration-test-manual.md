# 온프레미스 GitLab 연동 통합 테스트 매뉴얼

## 목적

이 문서는 `002-gitlab-onprem-connection` 기능을 로컬과 실환경형 구성에서
어떻게 통합 테스트할지 정리한 사용 매뉴얼이다. 자동화된 빠른 회귀 확인,
전체 회귀 확인, 실제 PostgreSQL/Redis/FastAPI/Celery/GitLab self-managed
프로젝트를 사용하는 수동 검증, PostgreSQL migration smoke까지 한 번에
따라갈 수 있게 정리한다.

## 먼저 알아둘 것

- 가장 빠른 검증은 GitLab quickstart/latency helper와 focused integration
  테스트다.
- 실제 런타임 통합 테스트는 PostgreSQL 16, Redis 7, FastAPI app, Celery
  worker, GitLab self-managed 테스트 프로젝트가 필요하다.
- GitLab self-managed 원격 저장소는 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`에
  등록된 host 또는 `host:port`만 접근할 수 있다.
- `http://` GitLab remote는 폐쇄망 파일럿 전용이며,
  `TCI_ALLOW_INSECURE_GITLAB_HTTP=true`일 때만 허용된다.
- webhook secret은 GitHub 기능과 달리 회전 유예 없이 단일 활성 secret만
  검증한다.
- 실제 destructive migration 경로는 전용 DB에서만 실행해야 한다.

## 디렉터리 기준

모든 명령은 기본적으로 아래 디렉터리에서 실행한다.

```bash
cd /Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/pilot-git-repo-connection
```

## 1. 가장 빠른 통합 확인

GitLab primary flow와 GitHub compatibility를 가장 빨리 확인하는 경로다.
구현이 대체로 정상인지 보려면 먼저 이 단계부터 돌리면 된다.

```bash
python -m pytest \
  tests/integration/repository_connections/test_gitlab_quickstart_validation.py \
  tests/integration/repository_connections/test_gitlab_webhook_status_latency.py \
  tests/integration/repository_connections/test_gitlab_connection_lifecycle.py \
  tests/integration/repository_connections/test_gitlab_scoped_snapshot.py \
  tests/integration/repository_connections/test_gitlab_provider_flows.py \
  tests/integration/repository_connections/test_github_gitlab_compatibility.py \
  -q
```

기대 결과:

- `test_gitlab_quickstart_validation.py`
  - GitLab 연결 생성
  - scope 저장
  - 첫 snapshot 생성
  - Push/MR webhook 처리
  - traceability 확인
  - GitHub compatibility 확인
- `test_gitlab_webhook_status_latency.py`
  - Push/MR webhook status projection이 detail/events에 1분 SLA 안에 반영되는지 확인
- `test_gitlab_connection_lifecycle.py`
  - verify 성공
  - `reauth_required`
  - `ref_missing`
  - 조치 필요 상태에서 manual collection 차단
  - 초기 snapshot 생성
- `test_gitlab_scoped_snapshot.py`
  - default ref 변경 후 기존 이력 보존
  - scope version stamping
  - empty-result snapshot의 `NO_INCLUDED_FILES` 실패 처리
- `test_gitlab_provider_flows.py`
  - Push/MR webhook
  - duplicate delivery
  - stale head
  - token mismatch health
  - state-based webhook snapshot blocking
- `test_github_gitlab_compatibility.py`
  - GitHub Cloud 기존 connection/snapshot/webhook 흐름이 깨지지 않는지 확인

## 2. helper 스크립트로 빠르게 재현하기

설계 검증 결과를 숫자와 상태값으로 빨리 보고 싶으면 helper를 직접
실행한다.

```bash
python tests/support/run_gitlab_quickstart_validation.py
python tests/support/measure_gitlab_webhook_status_latency.py
```

기대 확인 포인트:

- `run_gitlab_quickstart_validation.py`
  - `SC001_GITLAB_FIRST_SNAPSHOT_SECONDS`
  - Push event processing completed
  - MR event processing completed
  - GitHub compatibility `True`
- `measure_gitlab_webhook_status_latency.py`
  - sample count
  - completed sample count
  - max seconds
  - p95 seconds

주의:

- 두 helper는 실제 GitLab 서버가 아니라 deterministic TestClient/in-memory
  backend와 inline worker path 기준으로 빠르게 검증한다.
- helper 결과는 `specs/002-gitlab-onprem-connection/delivery-evidence.md`
  기준선과 비교하면 된다.

## 3. 전체 회귀 테스트

기능 전체가 깨지지 않았는지 보려면 아래를 실행한다.

```bash
python -m pytest -q
```

참고:

- `delivery-evidence.md` 기준 최신 전체 Python suite는 `498 passed`다.
- 전체 suite warning 중 `TestRepositoryEvent` dataclass collection warning은
  기능 실패가 아니다.

## 4. 실환경형 통합 테스트

실제 PostgreSQL, Redis, FastAPI, Celery, GitLab self-managed 테스트
프로젝트를 함께 검증하는 절차다.

### 4-1. 의존성 설치

```bash
python -m pip install -e '.[dev]'
```

### 4-2. 환경 변수 준비

```bash
export PYTHONPATH=src
export TCI_PROJECT_ROOT="$PWD"
export TCI_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME'
export TCI_REDIS_URL='redis://localhost:6379/0'
export TCI_CREDENTIAL_ENCRYPTION_KEY="$(python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
)"
export TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS='gitlab.example.com'
export TCI_ALLOW_INSECURE_GITLAB_HTTP='false'
```

비표준 HTTPS/SSH 포트나 private IPv4를 쓰면 `host:port`까지 등록한다.

```bash
export TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS='gitlab.example.com:8443,192.168.10.20:2222'
```

필수 변수:

- `TCI_PROJECT_ROOT`
- `TCI_DATABASE_URL`
- `TCI_REDIS_URL`
- `TCI_CREDENTIAL_ENCRYPTION_KEY`
- `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`
- `TCI_ALLOW_INSECURE_GITLAB_HTTP`
  - 기본값은 `false`다.
  - 폐쇄망 파일럿에서 `http://` GitLab remote를 써야 할 때만 `true`로 둔다.

### 4-3. DB 마이그레이션 적용

```bash
python -m alembic upgrade head
```

### 4-4. FastAPI app 실행

```bash
python -m uvicorn tci.app:create_app --factory --reload
```

### 4-5. Celery worker 실행

다른 터미널에서 같은 환경 변수를 설정한 뒤 실행한다.

```bash
celery -A tci.workers.celery_app:celery_app worker -l info
```

## 5. 실환경에서 수동으로 확인할 순서

아래 순서는 `specs/002-gitlab-onprem-connection/quickstart.md`를 실제 운영
흐름처럼 밟는 방법이다.

1. `POST /api/planning-input-references`
2. `POST /api/repository-connections`
   - `provider=gitlab_self_managed`
   - `remoteUrl`
   - `transport=ssh`, `https`, 또는 opt-in된 `http`
   - `defaultRefType=branch` 또는 `tag`
   - `defaultRefName`
   - read-only credential
3. allowlist에 없는 host 또는 `host:port`가 git 접근 전에 400으로 차단되는지 확인
4. `POST /api/repository-connections/{id}/verify`
5. `GET /api/repository-connections/{id}`
6. `POST /api/repository-connections/{id}/scope-rules`
7. `POST /api/repository-connections/{id}/snapshots`
8. GitLab Push webhook을 `POST /api/webhooks/gitlab/{id}`로 발송
9. GitLab Merge Request webhook을 `POST /api/webhooks/gitlab/{id}`로 발송
10. `GET /api/repository-connections/{id}/events`
11. `GET /api/repository-connections/{id}/snapshots/{snapshotId}`
12. 운영 화면 확인
13. `/connections/{id}`
14. `/connections/{id}/scope`
15. `/connections/{id}/events`

수동 확인 포인트:

- 연결 생성 직후 `status=active`와 `provider=gitlab_self_managed`가 보이는지
- `providerInstanceUrl`, `providerProjectPath`가 remote URL에서 파생되어 보이는지
- `/gitlab/group/repo.git` 같은 path prefix가 instance subpath가 아니라 project
  namespace로 취급되는지
- Operator detail page에 GitLab instance URL, project path, active scope
  traceability가 보이는지
- Operator detail page와 API 응답에 `shared_token`, `webhookAuthMode`, raw
  operator token이 노출되지 않는지
- 잘못된 token 또는 SSH key로 재검증하면 `reauth_required`로 전환되는지
- 선택된 ref가 사라진 경우 `ref_missing`으로 전환되고 새 수집이 차단되는지
- scope 저장 후 `latestScopeRule`, `excludeBinary`, `maxFileSizeBytes`,
  `warningState`가 일관되게 보이는지
- scope rule 변경 후 manual snapshot에 새 scope version이 찍히는지
- Push webhook이 `202 Accepted` 이후 worker를 통해 후속 snapshot으로 이어지는지
- MR `opened`, `reopened`, code-moving `update`만 snapshot 후보가 되는지
- reviewer/label 변경만 있는 MR update는 `record_only`인지
- duplicate delivery는 중복 처리되지 않는지
- stale event가 최신 snapshot 상태를 덮어쓰지 않는지
- 잘못된 `X-Gitlab-Token`은 canonical connection status를 바꾸지 않고
  `webhookHealth.webhookStatus=secret_mismatch_detected`만 반영하는지
- 올바른 token으로 다시 보내면 webhook health가 `healthy`로 유지 또는 회복되는지
- GitHub와 GitLab 연결이 동시에 있을 때 provider별 event/snapshot이 섞이지 않는지

## 6. GitLab 특화 보안/격리 확인

아래 항목은 자동화 테스트에도 포함되어 있지만, 실환경 점검 때 별도 확인하면
좋다.

- allowlist는 credential decrypt와 outbound git access 전에 적용된다.
- `http://` remote는 `TCI_ALLOW_INSECURE_GITLAB_HTTP=true`가 아니면
  credential decrypt와 outbound git access 전에 차단된다.
- GitHub host, trailing-dot host, IPv6, userinfo, query/fragment, whitespace,
  malformed port는 GitLab self-managed remote로 거부된다.
- HTTPS PAT는 `remoteUrl`, mirror `origin`, Git command argv/config에 포함되지 않는다.
- HTTP/HTTPS PAT는 `remoteUrl`, mirror `origin`, Git command argv/config에 포함되지 않는다.
- HTTP/HTTPS askpass helper는 per-session token 없는 local socket request에 PAT를 제공하지 않는다.
- HTTP PAT는 네트워크 구간에서 평문으로 노출될 수 있으므로 폐쇄망 파일럿에서만 사용한다.
- SSH private key는 temporary file로 쓰이지 않고 isolated `ssh-agent`에 등록된다.
- Git child env에 ambient `SSH_AUTH_SOCK`, `GIT_SSH_COMMAND`, service-user Git
  config가 상속되지 않는다.
- SSH agent cleanup 실패가 성공한 Git 작업 또는 원래 Git 오류를 덮어쓰지 않는다.
- scope filtering 전 raw Git tree entry cap이 적용된다.
- blob read 전에 scope prefiltering이 적용된다.

## 7. PostgreSQL destructive migration smoke

이 항목은 실제 PostgreSQL에 대해 Alembic round-trip과 migration guard를
확인하는 별도 smoke다. 이 테스트만은 파괴적일 수 있으므로 전용 DB로만
실행해야 한다.

```bash
export TCI_TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/TEST_DB'
export TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1
export TCI_MIGRATION_TEST_DATABASE_URL="$TCI_TEST_DATABASE_URL"
export TCI_MIGRATION_TEST_DATABASE_URL_ACK="$TCI_MIGRATION_TEST_DATABASE_URL"
export TCI_MIGRATION_TEST_DATABASE_NAME='TEST_DB'
python -m pytest tests/integration/repository_connections/test_phase2_migration_smoke.py -q
```

주의:

- `TCI_TEST_DATABASE_URL`이 없으면 skip 된다.
- `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1`이 없으면 skip 된다.
- `TCI_MIGRATION_TEST_DATABASE_URL`이 없으면 실DB bootstrap 테스트도 skip 된다.
- `TCI_MIGRATION_TEST_DATABASE_URL_ACK`는 full DSN과 정확히 같아야 한다.
- `TCI_MIGRATION_TEST_DATABASE_NAME`은 DSN에서 파싱한 raw DB 이름과 정확히 같아야 한다.
- SQLite in-memory로는 이 테스트를 대체할 수 없다.

## 8. 실패했을 때 먼저 볼 것

### GitLab 연결 생성 또는 verify가 깨질 때

- `src/tci/domain/services/create_repository_connection.py`
- `src/tci/domain/services/verify_repository_connection.py`
- `src/tci/infrastructure/git/remote_parsers.py`
- `src/tci/infrastructure/git/gitlab_readonly_validator.py`

### allowlist가 예상과 다르게 동작할 때

- `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`
- `src/tci/infrastructure/git/remote_parsers.py`
- `tests/unit/repository_connections/test_gitlab_provider_parsing.py`

### scope 또는 snapshot이 깨질 때

- `src/tci/domain/services/default_scope_policy.py`
- `src/tci/domain/services/scope_filter_engine.py`
- `src/tci/domain/services/build_code_snapshot.py`
- `src/tci/domain/services/create_initial_snapshot.py`
- `tests/integration/repository_connections/test_gitlab_scoped_snapshot.py`

### webhook enqueue 또는 status projection이 깨질 때

- `src/tci/api/routes/gitlab_webhooks.py`
- `src/tci/domain/services/process_gitlab_event.py`
- `src/tci/infrastructure/queue/repository_ingestion_tasks.py`
- `src/tci/workers/celery_app.py`
- `tests/integration/repository_connections/test_gitlab_provider_flows.py`

### GitHub 회귀가 의심될 때

- `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- `tests/contract/repository_ingestion/test_github_webhook_contract.py`
- `tests/integration/repository_connections/test_github_webhook_refresh.py`
