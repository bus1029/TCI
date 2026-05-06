# 워크스페이스 기반 저장소 연결 통합 테스트 매뉴얼

## 목적

이 문서는 `003-repository-first-connections` 기능을 통합 테스트하는 절차를 정리한다. 자동 회귀 테스트, Docker 기반 PostgreSQL/Redis 실행, FastAPI/Celery 실환경형 확인, 워크스페이스 기반 GitHub/GitLab 연결 리허설, mixed-provider 식별 리허설을 한 흐름으로 따라갈 수 있게 구성한다.

## 먼저 알아둘 것

- 가장 빠른 검증은 repository-first focused regression이다
- Docker 인프라는 `specs/001-git-repo-connection/docker-compose` 구성을 사용한다
- 기본 Docker 서비스는 PostgreSQL과 Redis다
- FastAPI app과 Celery worker는 호스트에서 직접 실행한다
- 새 저장소 연결은 planning/spec/plan 참조 없이 생성되어야 한다
- 기존 planning 기반 GitHub/GitLab 연결은 목록과 상세에서 계속 보여야 한다
- 후보 조회는 개인 provider 권한을 사용할 수 있지만, 생성 이후 운영은 workspace shared read-only credential만 사용해야 한다
- 실제 운영자 리허설 evidence에는 실명, 토큰, full remote URL, raw log, screenshot을 기록하지 않는다

## 디렉터리 기준

레포 루트:

```bash
cd /Users/seokhyunbae_1/Desktop/기획_스프린트/TCI
```

애플리케이션 루트:

```bash
cd /Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/pilot-git-repo-connection
```

## 1. Docker 인프라 준비

레포 루트에서 실행한다.

```bash
export TCI_DOCKER_DATA_ROOT="$PWD/.runtime/docker"
mkdir -p "$TCI_DOCKER_DATA_ROOT"

docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose.yaml \
  up -d
```

상태 확인:

```bash
docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose.yaml \
  ps
```

기대 상태:

- `tci-postgres` healthy
- `tci-redis` healthy
- PostgreSQL host port `127.0.0.1:5432`
- Redis host port `127.0.0.1:6379`

## 2. 애플리케이션 환경 변수 준비

애플리케이션 루트에서 실행한다.

```bash
export PYTHONPATH=src
export TCI_PROJECT_ROOT="$PWD"
export TCI_DATABASE_URL='postgresql+psycopg://tci:tci@127.0.0.1:5432/tci'
export TCI_REDIS_URL='redis://127.0.0.1:6379/0'
export TCI_CREDENTIAL_ENCRYPTION_KEY="$(python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
)"
export TCI_OPERATOR_API_TOKEN='replace-with-32-byte-random-operator-token'
export TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS='gitlab.example.com'
export TCI_ALLOW_INSECURE_GITLAB_HTTP='false'
```

GitLab self-managed가 비표준 포트나 private IPv4를 쓰면 아래처럼 지정한다.

```bash
export TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS='gitlab.example.com:8443,192.168.10.20:2222'
```

## 3. DB migration 확인

```bash
python -m alembic upgrade head
python -m alembic heads
```

기대 결과:

```text
009_repository_first_connections (head)
```

## 4. 가장 빠른 자동 통합 확인

워크스페이스 기반 저장소 연결 흐름이 대체로 정상인지 먼저 확인한다.

```bash
rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q
```

기대 결과:

```text
Pytest: 140 passed
```

확인 범위:

- planning/spec/plan 참조 없이 connection create
- obsolete planning field rejection matrix
- GitHub/GitLab manual URL flow
- candidate list와 manual fallback
- candidate/manual duplicate prevention
- shared read-only credential boundary
- operation credential boundary
- operator page create/list/detail
- mixed-provider provider/repository 구분
- SC-004 60문항 fixture 생성

## 5. GitHub/GitLab 회귀 확인

기존 GitHub Cloud와 GitLab self-managed 동작이 유지되는지 확인한다.

```bash
rtk pytest tests/integration/repository_connections/test_github_gitlab_compatibility.py tests/integration/repository_connections/test_gitlab_connection_lifecycle.py tests/integration/repository_connections/test_github_webhook_refresh.py tests/integration/repository_connections/test_gitlab_provider_flows.py tests/integration/repository_connections/test_operator_event_pages.py tests/contract/repository_ingestion/test_github_webhook_contract.py tests/contract/repository_ingestion/test_gitlab_webhook_contract.py tests/contract/repository_ingestion/test_gitlab_connection_contract.py tests/contract/repository_ingestion/test_gitlab_scope_contract.py -q
```

기대 결과:

```text
Pytest: 113 passed
```

확인 범위:

- legacy planning trace 보존
- GitHub webhook refresh
- GitLab lifecycle
- GitLab Push/MR webhook
- GitLab scope contract
- provider별 event page
- GitHub/GitLab mixed compatibility

## 6. 전체 repository ingestion 회귀

기능 전체가 깨지지 않았는지 확인한다.

```bash
rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q
```

기대 결과:

```text
Pytest: 615 passed
```

## 7. 정적 검증

```bash
rtk black --check .
rtk ruff check .
rtk mypy src/tci/api/schemas/repository_candidate.py src/tci/api/schemas/repository_connection.py src/tci/api/routes/repository_candidates.py src/tci/api/routes/repository_connections.py src/tci/api/routes/repository_events.py src/tci/app.py src/tci/domain/services/create_repository_connection.py src/tci/domain/services/get_repository_connection_detail.py src/tci/domain/services/list_repository_candidates.py src/tci/domain/services/list_repository_connections.py src/tci/domain/services/list_repository_events.py src/tci/domain/services/process_github_event.py src/tci/domain/services/process_gitlab_event.py src/tci/domain/services/repository_connection_support.py src/tci/domain/services/verify_repository_connection.py src/tci/domain/services/build_code_snapshot.py src/tci/domain/services/update_default_ref.py src/tci/web/routes/repository_connections.py src/tci/web/routes/repository_events.py tests/support/operator_identification_rehearsal.py tests/unit/repository_connections/test_repository_candidates.py tests/unit/repository_connections/test_repository_connection_credentials.py tests/unit/repository_connections/test_repository_connection_identity.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py
rtk alembic heads
rtk proxy git diff --check
```

기대 결과:

- `black`: files would be left unchanged
- `ruff`: no issues found
- `mypy`: no issues found
- `alembic heads`: `009_repository_first_connections (head)`
- `git diff --check`: passed

## 8. FastAPI와 Celery 실환경형 실행

자동 테스트가 통과하면 호스트에서 app과 worker를 실행한다.

FastAPI app:

```bash
python -m uvicorn tci.app:create_app --factory --reload
```

Celery worker:

```bash
celery -A tci.workers.celery_app:celery_app worker -l info
```

확인 포인트:

- app boot 성공
- DB 연결 성공
- Redis 연결 성공
- Alembic head와 DB schema 일치
- worker가 Redis broker/backend에 연결

## 9. 수동 API 통합 확인

수동 API 확인은 synthetic workspace와 throwaway repository를 사용한다.

### 9-1. GitHub workspace-first 연결

1. workspace ID 준비
2. `POST /api/repository-connections`
3. `provider=github_cloud`
4. GitHub remote URL 또는 candidate 선택
5. workspace shared read-only credential 제출
6. default ref 제출
7. 응답 확인
   - `status=active`
   - `origin.kind=workspace_repository`
   - `traceability.planningInputReference=null`
   - planning/spec/plan field 저장 없음
8. `POST /api/repository-connections/{id}/verify`
9. snapshot 생성 또는 초기 snapshot 상태 확인
10. `GET /api/repository-connections/{id}`
11. `GET /api/repository-connections/{id}/snapshots/{snapshotId}`

### 9-2. GitLab workspace-first 연결

1. workspace ID 준비
2. GitLab instance allowlist 확인
3. `POST /api/repository-connections`
4. `provider=gitlab_self_managed`
5. GitLab remote URL 또는 candidate 선택
6. workspace shared read-only credential 제출
7. default ref 제출
8. 응답 확인
   - `status=active`, `reauth_required`, 또는 `ref_missing`
   - `origin.kind=workspace_repository`
   - `providerInstanceUrl` 표시
   - `providerProjectPath` 표시
   - `traceability.planningInputReference=null`
9. verify, snapshot, detail, event 조회 확인

### 9-3. obsolete planning field 거부

아래 필드를 하나씩 create payload에 추가해 모두 거부되는지 확인한다.

- `planningInputReferenceId`
- `planningInputReference`
- `planningTrace`
- `traceability.planningInputReference`
- `approvedSpecPath`
- `approvedPlanPath`
- `specPath`
- `planPath`

기대 결과:

- `400 INVALID_INPUT`
- `code=obsolete_planning_reference`
- connection row 생성 없음
- mirror sync 없음
- snapshot job 없음

### 9-4. credential boundary 확인

1. 개인 provider grant로 candidate list 표시
2. workspace shared read-only credential 없이 create 시도
3. `shared_credential_required` 확인
4. expired, revoked, invalid credential로 create 시도
5. `shared_credential_invalid`, `repository_not_authorized`, `provider_reauth_required` 확인
6. active connection 생성 없음 확인
7. 성공한 connection에서 verify, collect, event, status, reverify 실행
8. 개인 provider grant 제거 또는 회수 뒤에도 operation path가 workspace shared read-only credential만 사용하는지 확인

### 9-5. duplicate prevention 확인

1. candidate 선택으로 connection 생성
2. 같은 provider/repository를 manual URL로 다시 생성 시도
3. duplicate response 확인
4. 순서를 반대로 반복
5. git ref resolve, credential probe, mirror sync 전에 실패하는지 확인

### 9-6. legacy planning compatibility 확인

1. planning trace가 있는 기존 GitHub connection 준비
2. planning trace가 있는 기존 GitLab connection 준비
3. workspace connection list 조회
4. detail 조회
5. 확인 항목
   - `origin.kind=legacy_planning`
   - legacy planning trace 표시
   - 기존 `workspace_id` 기준으로 조회
   - missing 또는 cross-workspace planning reference는 `legacy_unassigned`
   - GitHub/GitLab event와 snapshot history 분리

## 10. 운영자 화면 확인

브라우저에서 operator 화면을 확인한다. 이 확인은 자동 회귀 테스트가 아니라 실제 운영 화면 smoke 확인이다. 자동 회귀는 아래 명령으로 먼저 돌릴 수 있다.

```bash
rtk pytest tests/integration/repository_connections/test_operator_connection_pages.py -q
```

브라우저 확인 전 FastAPI app이 실행 중이어야 한다.

```bash
python -m uvicorn tci.app:create_app --factory --reload
```

테스트용 workspace ID와 connection ID를 준비한다. workspace ID는 UUID 형식이면 되고, 9장에서 생성한 connection을 확인하려면 같은 workspace ID를 계속 사용한다.

확인 경로:

- `/connections?workspaceId={workspaceId}`
- `/connections/{id}?workspaceId={workspaceId}`
- `/connections/{id}/events?workspaceId={workspaceId}`
- `/connections/{id}/scope?workspaceId={workspaceId}`

브라우저 화면은 `X-TCI-Operator-Token` header를 직접 넣기 어렵기 때문에 operator session cookie를 먼저 만든다. 브라우저에서 `http://127.0.0.1:8000/connections?workspaceId={workspaceId}`를 연 뒤 DevTools console에서 아래 코드를 실행한다.

```js
await fetch('/operator/session', {
  method: 'POST',
  headers: {'Content-Type': 'application/x-www-form-urlencoded'},
  body: new URLSearchParams({
    operatorToken: '<TCI_OPERATOR_API_TOKEN 값>',
    next: '/connections?workspaceId={workspaceId}'
  }),
  credentials: 'include'
})
```

그다음 `/connections?workspaceId={workspaceId}`를 새로고침한다. 성공하면 운영자 화면이 열리고, connection 상세와 event/scope 화면으로 이동할 수 있다.

확인 포인트:

- planning input 선택 UI 없음
- candidate list 표시
- candidate empty state가 오류가 아니라 manual URL fallback으로 표시
- GitHub/GitLab provider 구분 가능
- GitLab instance와 project path 표시
- workspace context 표시
- origin 표시
- legacy planning trace 표시
- credential failure remediation 표시
- secret-bearing `remoteUrl`이 validation error 화면에 다시 노출되지 않음
- personal grant가 operation credential처럼 표시되지 않음

증거를 남길 때는 operator token, credential, cookie, credential-bearing URL, raw log, private repo path, 민감정보가 보이는 screenshot을 기록하지 않는다. 필요한 경우 workspace ID, connection ID, provider, 상태값, 민감정보를 제거한 관찰 결과만 남긴다.

## 11. SC-001 운영자 리허설

`SC-001`은 자동 테스트로 대체할 수 없다. 대표 운영자 3명이 실제 화면에서 GitHub 1회, GitLab 1회씩 총 6회 연결 리허설을 수행해야 한다.

사전 자동 확인:

```bash
rtk pytest tests/contract/repository_ingestion/test_repository_connection_contract.py tests/contract/repository_ingestion/test_repository_candidate_contract.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py tests/integration/repository_connections/test_operator_connection_pages.py tests/integration/repository_connections/test_mixed_provider_workspace.py tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q
```

기록 필드:

| 필드 | 설명 |
|------|------|
| `operator_id` | `operator-01` 같은 가명 |
| `provider` | `github_cloud` 또는 `gitlab_self_managed` |
| `repository_label` | `repo-a` 같은 비식별 label |
| `start_timestamp` | 시작 시각 |
| `end_timestamp` | 완료 시각 |
| `elapsed_minutes` | 소요 시간 |
| `result` | `pass` 또는 `fail` |

통과 기준:

- 총 6회 attempt
- 5회 이상 10분 이내 성공
- 모든 attempt에 시작/완료 timestamp와 성공/실패 결과 기록

기록 금지:

- 실명
- 이메일
- username
- token
- cookie
- session ID
- auth header
- full remote URL
- credential-bearing URL
- screenshot
- terminal raw log
- private repository path
- provider account secret

## 12. SC-004 mixed-provider 식별 리허설

`SC-004`도 자동 테스트로 대체할 수 없다. fixture는 60문항 준비 상태만 확인한다.

사전 fixture 확인:

```bash
rtk pytest tests/integration/repository_connections/test_operator_mixed_provider_identification.py -q
```

기록 필드:

| 필드 | 설명 |
|------|------|
| `operator_id` | `operator-01` 같은 가명 |
| `task_id` | `SC-004-01` 같은 비식별 task ID |
| `expected_provider` | 기대 provider |
| `expected_repository_label` | 기대 저장소 label |
| `answer_provider` | 운영자 답변 provider |
| `answer_repository_label` | 운영자 답변 저장소 label |
| `correct` | `true` 또는 `false` |

통과 기준:

- 대표 운영자 3명
- 각 20문항
- 총 60문항
- 57개 이상 정답

기록 금지:

- screenshot
- full remote URL
- private repository path
- operator name
- cookie
- token
- raw browser log
- provider account secret

## 13. evidence 반영 기준

리허설 결과는 아래 파일에 기록한다.

```text
specs/003-repository-first-connections/delivery-evidence.md
```

반영 규칙:

- `SC-001`은 6회 attempt와 5-of-6 계산이 있어야 `Verified`
- `SC-004`는 60개 answer와 57-of-60 계산이 있어야 `Verified`
- `T071`은 `SC-001` 실제 evidence가 있어야 완료
- `T072`는 `SC-004` 실제 evidence가 있어야 완료
- `T030`은 `SC-001` 실제 evidence가 충족된 뒤에만 완료
- `T073`은 coverage map과 evidence 본문이 일치한 뒤에만 완료
- `FR-003c`는 실제 provider account/instance integration evidence가 없으면 `Partial` 유지

## 14. PostgreSQL destructive migration smoke

분리된 테스트 DB에서만 실행한다. 레포 루트에서 test compose를 먼저 띄운다.

```bash
export TCI_DOCKER_DATA_ROOT="$PWD/.runtime/docker"

docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose-test.yaml \
  up -d
```

애플리케이션 루트에서 환경 변수를 설정한 뒤 실행한다.

```bash
export TCI_TEST_DATABASE_URL='postgresql+psycopg://tci:tci@127.0.0.1:5433/tci_test'
export TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1
export TCI_MIGRATION_TEST_DATABASE_URL="$TCI_TEST_DATABASE_URL"
export TCI_MIGRATION_TEST_DATABASE_URL_ACK="$TCI_MIGRATION_TEST_DATABASE_URL"
export TCI_MIGRATION_TEST_DATABASE_NAME='tci_test'

rtk pytest tests/integration/repository_connections/test_phase2_migration_smoke.py -q
```

주의:

- 운영 DB로 실행하지 않음
- 공유 개발 DB로 실행하지 않음
- `TCI_MIGRATION_TEST_DATABASE_URL_ACK`는 full DSN과 정확히 같아야 함
- `TCI_MIGRATION_TEST_DATABASE_NAME`은 DSN의 DB 이름과 정확히 같아야 함

## 15. 실패했을 때 먼저 볼 것

### create 또는 obsolete field rejection 실패

- `src/tci/api/schemas/repository_connection.py`
- `src/tci/api/routes/repository_connections.py`
- `src/tci/domain/services/create_repository_connection.py`
- `tests/contract/repository_ingestion/test_repository_connection_contract.py`

### candidate 또는 duplicate prevention 실패

- `src/tci/domain/services/list_repository_candidates.py`
- `src/tci/domain/services/repository_connection_support.py`
- `src/tci/domain/services/create_repository_connection.py`
- `tests/contract/repository_ingestion/test_repository_candidate_contract.py`
- `tests/unit/repository_connections/test_repository_connection_identity.py`

### credential boundary 실패

- `src/tci/domain/services/repository_connection_support.py`
- `src/tci/domain/services/verify_repository_connection.py`
- `src/tci/domain/services/build_code_snapshot.py`
- `src/tci/domain/services/process_github_event.py`
- `src/tci/domain/services/process_gitlab_event.py`
- `tests/integration/repository_connections/test_repository_operation_credential_boundary.py`

### GitHub/GitLab compatibility 실패

- `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
- `tests/integration/repository_connections/test_gitlab_connection_lifecycle.py`
- `tests/integration/repository_connections/test_github_webhook_refresh.py`
- `tests/integration/repository_connections/test_gitlab_provider_flows.py`

### operator UI 실패

- `src/tci/web/routes/repository_connections.py`
- `src/tci/web/routes/repository_events.py`
- `src/tci/web/templates/connections/index.html`
- `src/tci/web/templates/connections/detail.html`
- `src/tci/web/templates/connections/events.html`
- `tests/integration/repository_connections/test_operator_connection_pages.py`
- `tests/integration/repository_connections/test_mixed_provider_workspace.py`
