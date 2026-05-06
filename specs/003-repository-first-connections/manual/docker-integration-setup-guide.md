# 워크스페이스 기반 저장소 연결 Docker 설치 가이드

## 목적

이 문서는 `003-repository-first-connections` 통합 테스트를 위해 Docker로 준비해야 하는 로컬 인프라를 정리한다. 현재 Docker Compose 기준은 `specs/001-git-repo-connection/docker-compose`이며, 애플리케이션은 호스트에서 실행하고 PostgreSQL/Redis만 Docker로 띄우는 구성을 기본으로 한다.

## 결론 먼저

기본 통합 테스트에 필요한 Docker 제품은 아래와 같다.

- `postgres:18.3`
- `redis:8.6.2`

destructive migration smoke나 분리된 테스트 DB가 필요할 때는 test compose를 함께 사용한다.

- `postgres:18.3`
- host port `5433`
- database `tci_test`

Docker로 띄우지 않는 항목은 아래와 같다.

- FastAPI app
- Celery worker
- GitHub Cloud
- GitLab self-managed 운영 인스턴스
- read-only credential, PAT, deploy key, SSH key
- webhook secret

FastAPI app과 Celery worker는 호스트에서 직접 실행하는 편이 빠르다. 코드 수정 뒤 이미지 rebuild가 필요 없고, 로그와 디버깅도 단순하다.

## Compose 파일 위치

현재 기준 Compose 파일은 아래에 있다.

```text
specs/001-git-repo-connection/docker-compose/docker-compose.yaml
specs/001-git-repo-connection/docker-compose/docker-compose-test.yaml
```

서비스 구성:

| 파일 | 서비스 | 포트 | 용도 |
|------|--------|------|------|
| `docker-compose.yaml` | `postgres` | `127.0.0.1:5432` | 로컬 개발 및 수동 통합 테스트 DB |
| `docker-compose.yaml` | `redis` | `127.0.0.1:6379` | Celery broker/backend, webhook queue |
| `docker-compose-test.yaml` | `postgres` | `127.0.0.1:5433` | migration smoke와 분리된 테스트 DB |

## 데이터 디렉터리 준비

Compose 파일은 `${TCI_DOCKER_DATA_ROOT}`를 사용한다. 먼저 로컬 데이터 루트를 정한다.

```bash
export TCI_DOCKER_DATA_ROOT="$PWD/.runtime/docker"
mkdir -p "$TCI_DOCKER_DATA_ROOT"
```

권장 실행 위치:

```bash
cd /Users/seokhyunbae_1/Desktop/기획_스프린트/TCI
```

## 기본 인프라 실행

PostgreSQL과 Redis를 실행한다.

```bash
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

로그 확인:

```bash
docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose.yaml \
  logs postgres

docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose.yaml \
  logs redis
```

## 테스트 DB 실행

destructive migration smoke나 별도 DB 검증이 필요하면 test compose를 실행한다.

```bash
docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose-test.yaml \
  up -d
```

상태 확인:

```bash
docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose-test.yaml \
  ps
```

## 애플리케이션 환경 변수

아래 값은 `pilot-git-repo-connection`에서 FastAPI app, Celery worker, Alembic을 호스트 실행할 때 사용한다.

```bash
cd /Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/pilot-git-repo-connection

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

GitLab self-managed가 비표준 포트나 private IPv4를 쓰면 host 또는 `host:port`까지 등록한다.

```bash
export TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS='gitlab.example.com:8443,192.168.10.20:2222'
```

폐쇄망 파일럿에서 `http://` GitLab remote를 검증해야 할 때만 아래 값을 켠다.

```bash
export TCI_ALLOW_INSECURE_GITLAB_HTTP='true'
```

주의:

- `TCI_OPERATOR_API_TOKEN`은 실제 토큰을 문서나 evidence에 기록하지 않는다
- `TCI_CREDENTIAL_ENCRYPTION_KEY`는 매 세션 생성 가능하지만, 이미 암호화된 credential row를 재사용해야 하면 같은 키가 필요하다
- `TCI_ALLOW_INSECURE_GITLAB_HTTP=true`는 폐쇄망 파일럿 전용이다

## Alembic 적용

```bash
python -m alembic upgrade head
python -m alembic heads
```

기대 결과:

```text
009_repository_first_connections (head)
```

## FastAPI app 실행

```bash
python -m uvicorn tci.app:create_app --factory --reload
```

## Celery worker 실행

다른 터미널에서 같은 환경 변수를 설정한 뒤 실행한다.

```bash
celery -A tci.workers.celery_app:celery_app worker -l info
```

## destructive migration smoke용 환경 변수

test compose를 띄운 뒤 아래 값을 사용한다. 이 검증은 테스트 DB에서만 실행한다.

```bash
export TCI_TEST_DATABASE_URL='postgresql+psycopg://tci:tci@127.0.0.1:5433/tci_test'
export TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1
export TCI_MIGRATION_TEST_DATABASE_URL="$TCI_TEST_DATABASE_URL"
export TCI_MIGRATION_TEST_DATABASE_URL_ACK="$TCI_MIGRATION_TEST_DATABASE_URL"
export TCI_MIGRATION_TEST_DATABASE_NAME='tci_test'
```

주의:

- `TCI_MIGRATION_TEST_DATABASE_URL_ACK`는 full DSN과 정확히 같아야 함
- `TCI_MIGRATION_TEST_DATABASE_NAME`은 DSN의 DB 이름과 정확히 같아야 함
- 운영 DB나 공유 개발 DB로 destructive migration smoke를 실행하지 않음

## 종료

기본 인프라 종료:

```bash
docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose.yaml \
  down
```

테스트 DB 종료:

```bash
docker compose \
  -f specs/001-git-repo-connection/docker-compose/docker-compose-test.yaml \
  down
```

데이터까지 삭제해야 할 때만 `${TCI_DOCKER_DATA_ROOT}` 아래 데이터를 직접 지운다.

