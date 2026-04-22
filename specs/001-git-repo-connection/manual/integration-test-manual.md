# 코드 저장소 연동 통합 테스트 매뉴얼

## 목적

이 문서는 `001-git-repo-connection` 기능을 로컬에서 어떻게 통합
테스트할지 정리한 사용 매뉴얼이다. 빠른 회귀 확인, 전체 회귀 확인,
실제 PostgreSQL/Redis/FastAPI/Celery를 띄운 실환경형 검증,
Alembic migration smoke까지 한 번에 따라갈 수 있게 정리한다.

## 먼저 알아둘 것

- 가장 빠른 검증은 `pytest` 기반 integration/helper 경로다.
- 실제 런타임 통합 테스트는 PostgreSQL 16, Redis 7, FastAPI app,
  Celery worker가 필요하다.
- `/docs`만으로 수동 흐름을 시작하려면 먼저
  `POST /api/planning-input-references`로
  `planningInputReferenceId`를 발급받아야 한다.
- 실제 destructive migration 경로는 전용 DB에서만 실행해야 한다.

## 디렉터리 기준

모든 명령은 기본적으로 아래 디렉터리에서 실행한다.

```bash
cd /Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/pilot-git-repo-connection
```

## 1. 가장 빠른 통합 확인

핵심 사용자 흐름과 edge-state를 가장 빨리 확인하는 경로다. 구현이
대체로 정상인지 보려면 먼저 이 단계부터 돌리면 된다.

```bash
python -m pytest \
  tests/integration/repository_connections/test_edge_state_regression.py \
  tests/integration/repository_connections/test_webhook_status_latency.py \
  tests/integration/repository_connections/test_quickstart_validation.py \
  tests/integration/repository_connections/test_operator_event_pages.py \
  -q
```

기대 결과:

- `test_edge_state_regression.py`
  - `reauth_required`
  - `ref_missing`
  - grace expiry 후 이전 secret 거부
  - bad replay 이후 health/detail 보존
- `test_webhook_status_latency.py`
  - `public route -> queue task -> completed projection` 반영 시간 확인
- `test_quickstart_validation.py`
  - planning input bootstrap
  - 연결 생성
  - scope 저장
  - manual snapshot
  - webhook push/PR 처리
  - traceability 확인
  - grace 기간/만료 후 secret 처리 확인

## 2. helper 스크립트로 빠르게 재현하기

설계 검증 결과를 숫자와 상태값으로 빨리 보고 싶으면 helper를 직접
실행한다.

```bash
python tests/support/run_quickstart_validation.py
python tests/support/measure_webhook_status_latency.py
```

기대 확인 포인트:

- `run_quickstart_validation.py`
  - `SC001_FIRST_SNAPSHOT_SECONDS`
  - `PUSH_EVENT_PROCESSING_STATUS=completed`
  - `PR_EVENT_PROCESSING_STATUS=completed`
  - `GRACE_ACCEPTED=True`
  - `EXPIRED_REJECTION_CODE=WEBHOOK_SECRET_MISMATCH`
- `measure_webhook_status_latency.py`
  - `SC002_SAMPLE_COUNT`
  - `SC002_COMPLETED_SAMPLE_COUNT`
  - `SC002_MAX_SECONDS`
  - `SC002_P95_SECONDS`

주의:

- 이 helper 둘은 단순 service 직호출이 아니라 실제
  `route + queued task path`를 타도록 맞춰져 있다.
- helper 결과는 `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`
  기준선과 비교하면 된다.

## 3. 전체 회귀 테스트

기능 전체가 깨지지 않았는지 보려면 아래를 실행한다.

```bash
python -m pytest -q
```

참고:

- 이전에는 로컬 `~/.gitconfig`의 `gpg.format` 오염 때문에 Git
  subprocess 테스트가 깨졌지만,
  `tests/unit/repository_connections/test_git_foundation.py`,
  `tests/unit/repository_connections/test_git_mirror_manager.py`에서
  테스트 전용 Git 환경을 분리해 지금은 전체 회귀가 통과한다.

## 4. 실환경형 통합 테스트

실제 PostgreSQL, Redis, FastAPI, Celery를 띄워서 API와 worker를 함께
검증하는 절차다.

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
```

필수 변수:

- `TCI_PROJECT_ROOT`
- `TCI_DATABASE_URL`
- `TCI_REDIS_URL`
- `TCI_CREDENTIAL_ENCRYPTION_KEY`

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

아래 순서는 `specs/001-git-repo-connection/quickstart.md`를 실제 운영
흐름처럼 밟는 방법이다.

1. `POST /api/planning-input-references`
2. `POST /api/repository-connections`
3. 필요하면 `POST /api/repository-connections/{id}/verify`
4. `POST /api/repository-connections/{id}/scope-rules`
5. `POST /api/repository-connections/{id}/webhook-secret`
6. `POST /api/repository-connections/{id}/snapshots`
7. 이후 추가 수동 snapshot은
   `POST /api/repository-connections/{id}/snapshots`
   with `{"reason": "manual_refresh"}`
8. GitHub webhook을 `POST /api/webhooks/github/{id}`로 발송
9. `GET /api/repository-connections/{id}`
10. `GET /api/repository-connections/{id}/events`
11. `GET /api/repository-connections/{id}/snapshots/{snapshotId}`
12. 운영 화면 확인
13. `/connections/{id}`
14. `/connections/{id}/scope`
15. `/connections/{id}/events`

수동 확인 포인트:

- planning input reference 응답의 `id`를 그대로
  `planningInputReferenceId`에 이어서 쓸 수 있는지
- 연결 생성 직후 `active` 상태와 기본 ref 정보가 응답에 보이는지
- 잘못된 credential일 때 `reauth_required`가 보이는지
- scope 저장 후 warning이 일관되게 보이는지
- scope rule 변경 후 `manual_refresh` snapshot에 새 규칙이 반영되는지
- webhook secret 발급 응답의 평문 secret을 GitHub 설정에 복사할 수 있는지
- snapshot 생성 후 traceability 체인이 응답에 담기는지
- push/PR webhook이 `202 Accepted` 이후 worker를 통해 반영되는지
- duplicate/stale/stale_head/event timeline이 설계대로 보이는지
- secret rotation grace 동안 이전 secret이 수용되고,
  grace 만료 후에는 `WEBHOOK_SECRET_MISMATCH`로 거부되는지

## 6. PostgreSQL destructive migration smoke

이 항목은 실제 PostgreSQL에 대해 Alembic round-trip을 확인하는
별도 smoke다. 이 테스트만은 파괴적일 수 있으므로 전용 DB로만
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
- `TCI_MIGRATION_TEST_DATABASE_NAME`은 DSN에서 파싱한 raw DB 이름과
  정확히 같아야 한다.
- SQLite in-memory로는 이 테스트를 대체할 수 없다.

## 7. 실패했을 때 먼저 볼 것

### Git 관련 테스트가 깨질 때

- `tests/unit/repository_connections/test_git_foundation.py`
- `tests/unit/repository_connections/test_git_mirror_manager.py`
- 현재는 테스트 전용 `HOME`과 빈 `.gitconfig`를 fixture로 주입한다.
- 로컬 `~/.gitconfig`를 고치기보다 테스트 격리 로직이 깨졌는지 먼저 본다.

### worker enqueue가 안 될 때

- `src/tci/api/routes/github_webhooks.py`
- `src/tci/api/routes/repository_snapshots.py`
- `src/tci/workers/celery_app.py`
- `src/tci/infrastructure/queue/repository_ingestion_tasks.py`

### 설정 로딩이 실패할 때

- `src/tci/settings.py`
- 특히 아래 환경 변수를 확인한다.
  - `TCI_PROJECT_ROOT`
  - `TCI_DATABASE_URL`
  - `TCI_REDIS_URL`
  - `TCI_CREDENTIAL_ENCRYPTION_KEY`

## 8. 권장 실행 순서

개발 완료 후 통합 테스트를 직접 해보려면 아래 순서를 권장한다.

1. `test_edge_state_regression.py`, `test_webhook_status_latency.py`,
   `test_quickstart_validation.py`, `test_operator_event_pages.py`
2. `python tests/support/run_quickstart_validation.py`
3. `python tests/support/measure_webhook_status_latency.py`
4. `python -m pytest -q`
5. 필요하면 PostgreSQL/Redis/FastAPI/Celery를 띄워
   `planning-input-references -> repository-connections -> scope-rules ->
   webhook-secret -> snapshots -> webhook` 순서로 수동 quickstart 수행
6. 전용 destructive DB가 준비됐을 때만 `test_phase2_migration_smoke.py`

## 9. 문서와 결과 비교 기준

실행 결과를 비교할 때는 아래 문서를 기준으로 본다.

- 설계 검증 순서: `specs/001-git-repo-connection/quickstart.md`
- 구현 근거와 최신 기준선:
  `pilot-git-repo-connection/specs/001-git-repo-connection/delivery-evidence.md`
- 다음 세션 상태 요약:
  `specs/001-git-repo-connection/next-session-handoff.md`
