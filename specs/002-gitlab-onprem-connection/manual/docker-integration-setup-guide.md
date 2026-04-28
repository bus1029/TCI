# 온프레미스 GitLab 연동 Docker 설치 가이드

## 목적

이 문서는 `002-gitlab-onprem-connection` 통합 테스트를 위해 어떤 제품을
Docker로 준비해야 하는지 정리한 조사 문서다. 코드베이스 요구사항과
GitLab self-managed 검증 특성을 기준으로, 필수 컨테이너와 선택 컨테이너를
나누고 실제 로컬 설치 순서를 제안한다.

## 결론 먼저

이 기능의 통합 테스트를 위해 Docker로 반드시 띄워야 하는 것은 아래 두 가지다.

1. `PostgreSQL 16`
2. `Redis 7`

선택적으로 있으면 편한 것은 아래다.

1. `Adminer` 또는 `pgAdmin`
2. webhook 외부 유입 확인용 프록시 도구
3. 격리된 GitLab CE 테스트 인스턴스

반대로 아래는 Docker 설치 대상이 아니다.

1. 사내 또는 고객사 GitLab self-managed 운영 인스턴스
2. GitLab read-only PAT, deploy key, SSH key
3. GitLab webhook secret
4. FastAPI app과 Celery worker 자체

FastAPI app과 Celery worker는 우선 호스트에서 직접 실행하는 편이 디버깅이
쉽다. Docker는 먼저 상태 저장 인프라인 PostgreSQL, Redis를 안정적으로
띄우는 데 집중하는 것이 좋다.

## 왜 PostgreSQL과 Redis가 필수인가

### PostgreSQL 16

프로젝트 스펙이 `PostgreSQL 16`을 전제로 한다. 코드도 `TCI_DATABASE_URL`이
있어야 실제 영속 계층과 Alembic migration을 탈 수 있게 되어 있다.

이 제품이 필요한 이유:

- repository connection metadata 저장
- GitLab provider instance/project metadata 저장
- encrypted credential metadata 저장
- scope rule 저장
- repository event 저장
- webhook health projection 저장
- sync run 저장
- snapshot metadata 저장
- Alembic migration round-trip 검증

### Redis 7

프로젝트 스펙이 `Redis 7`을 전제로 한다. 코드도 `TCI_REDIS_URL`이 있어야
Celery broker/backend와 webhook limiter 경로를 검증할 수 있다.

이 제품이 필요한 이유:

- snapshot enqueue
- webhook sync enqueue
- Celery broker/backend
- webhook limiter
- queue 기반 처리 흐름 검증

## GitLab CE 컨테이너는 필수인가

필수는 아니다. 이 기능은 "온프레미스 GitLab"과 연동하는 기능이므로, 가장
의미 있는 수동 검증은 실제 접근 가능한 GitLab self-managed 테스트 프로젝트를
사용하는 것이다.

GitLab CE 컨테이너가 유용한 경우:

- 사내 GitLab 테스트 프로젝트를 쓰기 어렵다.
- webhook, token, SSH key 설정을 완전히 격리해서 실험해야 한다.
- GitLab 버전별 동작 차이를 별도로 확인해야 한다.

GitLab CE 컨테이너를 기본 경로로 두지 않는 이유:

- 이미지가 크고 초기 기동 시간이 길다.
- 메모리 요구량이 PostgreSQL/Redis보다 훨씬 크다.
- SSH, HTTPS, webhook callback URL, root password, project seed 설정이 추가로 필요하다.
- 이번 코드의 핵심 회귀는 이미 TestClient/in-memory backend 자동화로 빠르게 확인된다.

따라서 기본 통합 테스트는 PostgreSQL/Redis만 Docker로 띄우고, GitLab은
별도 self-managed 테스트 프로젝트를 사용하는 구성을 권장한다.

## Docker 관점에서 준비해야 할 제품 목록

### 필수

- `Docker Desktop` 또는 `Docker Engine + Docker Compose plugin`
- `postgres:16`
- `redis:7`

### 선택

- `adminer`
  - PostgreSQL 상태를 브라우저로 빠르게 보려면 유용하다.
- webhook 프록시
  - 실제 GitLab webhook을 로컬 FastAPI로 보내려면 공인 URL 또는 프록시가 필요하다.
- `gitlab/gitlab-ce`
  - 격리된 GitLab self-managed 테스트 인스턴스가 필요할 때만 사용한다.

## 권장 아키텍처

로컬에서는 아래 구성이 가장 단순하다.

- Docker
  - `postgres:16`
  - `redis:7`
  - 선택: `adminer`
- 별도 GitLab self-managed 테스트 프로젝트
  - 사내 테스트 인스턴스 또는 격리된 GitLab CE
  - read-only PAT 또는 deploy key
  - webhook secret
- 호스트 실행
  - `uvicorn tci.app:create_app --factory --reload`
  - `celery -A tci.workers.celery_app:celery_app worker -l info`

이 구성이 좋은 이유:

- Python 코드 수정 시 이미지 rebuild가 필요 없다.
- 테스트와 디버깅이 빠르다.
- PostgreSQL/Redis 장애와 애플리케이션 장애를 분리해서 볼 수 있다.
- 실제 GitLab self-managed 네트워크/credential/webhook 설정을 검증할 수 있다.

## 추천 Docker Compose 구성

아래는 이 프로젝트 기준의 최소 권장 예시다. 아직 레포에 공식
`compose.yaml`이 들어간 것은 아니므로, 필요하면 별도 파일로 만들어 쓴다.

```yaml
services:
  postgres:
    image: postgres:16
    container_name: tci-postgres
    restart: unless-stopped
    shm_size: 256mb
    environment:
      POSTGRES_USER: tci
      POSTGRES_PASSWORD: tci
      POSTGRES_DB: tci
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - tci-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tci -d tci"]
      interval: 10s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    container_name: tci-redis
    restart: unless-stopped
    command: ["redis-server", "--save", "60", "1", "--loglevel", "warning"]
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - tci-redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  adminer:
    image: adminer
    container_name: tci-adminer
    restart: unless-stopped
    profiles: ["tools"]
    ports:
      - "127.0.0.1:8080:8080"

volumes:
  tci-postgres-data:
  tci-redis-data:
```

## 실제 설치 순서

### 1. Docker 준비

Mac 또는 Windows면 `Docker Desktop`을 설치하는 것이 가장 간단하다. Linux면
`Docker Engine + Docker CLI + Docker Compose plugin` 조합으로 준비한다.

확인 명령:

```bash
docker --version
docker compose version
```

### 2. Compose 파일 준비

예시를 바탕으로 `compose.integration.yml` 같은 파일을 만든다.

### 3. 컨테이너 기동

```bash
docker compose -f compose.integration.yml up -d
```

### 4. 상태 확인

```bash
docker compose -f compose.integration.yml ps
docker compose -f compose.integration.yml logs postgres
docker compose -f compose.integration.yml logs redis
```

### 5. 애플리케이션 환경 변수 연결

호스트에서 FastAPI app과 Celery worker를 실행할 때 아래 값을 맞춘다.

```bash
export PYTHONPATH=src
export TCI_PROJECT_ROOT="$PWD"
export TCI_DATABASE_URL='postgresql+psycopg://tci:tci@127.0.0.1:5432/tci'
export TCI_REDIS_URL='redis://127.0.0.1:6379/0'
export TCI_CREDENTIAL_ENCRYPTION_KEY='여기에 Fernet 키'
export TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS='gitlab.example.com'
export TCI_ALLOW_INSECURE_GITLAB_HTTP='false'
```

GitLab self-managed가 비표준 포트나 private IPv4에 있으면 아래처럼 지정한다.

```bash
export TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS='gitlab.example.com:8443,192.168.10.20:2222'
```

GitLab self-managed가 폐쇄망 파일럿 환경에서 `http://`만 제공되면 아래 값을
명시적으로 켠다. 이 경우 PAT가 평문 HTTP 구간에 노출될 수 있으므로 운영
환경에서는 사용하지 않는다.

```bash
export TCI_ALLOW_INSECURE_GITLAB_HTTP='true'
```

### 6. Alembic 적용

```bash
python -m alembic upgrade head
```

### 7. FastAPI app 실행

```bash
python -m uvicorn tci.app:create_app --factory --reload
```

### 8. Celery worker 실행

다른 터미널에서 같은 환경 변수를 설정한 뒤 실행한다.

```bash
celery -A tci.workers.celery_app:celery_app worker -l info
```

### 9. GitLab webhook callback 준비

GitLab self-managed 서버가 로컬 FastAPI에 접근할 수 있어야 한다.

선택지:

- 같은 네트워크에서 접근 가능한 개발 장비 IP를 사용한다.
- 사내 reverse proxy 또는 tunnel을 사용한다.
- webhook 프록시 도구를 사용한다.

GitLab webhook URL 예시:

```text
https://example-tunnel.test/api/webhooks/gitlab/{connectionId}
```

GitLab webhook 설정:

- Secret token: 테스트용 webhook secret
- Push events: enabled
- Merge request events: enabled
- SSL verification: 테스트 환경의 인증서 상태에 맞춰 설정

## 선택: GitLab CE 컨테이너

격리된 GitLab 인스턴스가 꼭 필요하면 별도 compose 파일로 운영하는 편이 좋다.
PostgreSQL/Redis 통합 테스트 compose와 섞으면 기동/초기화 시간이 길어지고
장애 원인도 흐려진다.

예시 뼈대:

```yaml
services:
  gitlab:
    image: gitlab/gitlab-ce:latest
    container_name: tci-gitlab-ce
    restart: unless-stopped
    hostname: gitlab.local.test
    ports:
      - "127.0.0.1:8929:80"
      - "127.0.0.1:2222:22"
    shm_size: 256m
    environment:
      GITLAB_OMNIBUS_CONFIG: |
        external_url 'http://gitlab.local.test:8929'
        gitlab_rails['gitlab_shell_ssh_port'] = 2222
    volumes:
      - tci-gitlab-config:/etc/gitlab
      - tci-gitlab-logs:/var/log/gitlab
      - tci-gitlab-data:/var/opt/gitlab

volumes:
  tci-gitlab-config:
  tci-gitlab-logs:
  tci-gitlab-data:
```

주의:

- `gitlab/gitlab-ce`는 무겁다. 충분한 CPU/메모리 여유가 필요하다.
- hostname, callback URL, SSH clone URL, allowlist 값이 서로 맞아야 한다.
- 예시의 `gitlab.local.test`는 로컬 DNS 또는 `/etc/hosts` 설정이 필요할 수 있다.
- 로컬 GitLab CE를 쓰면 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`에
  `gitlab.local.test:8929` 또는 SSH용 `gitlab.local.test:2222`를 등록한다.

## 종료와 초기화

일반 종료:

```bash
docker compose -f compose.integration.yml down
```

데이터까지 삭제:

```bash
docker compose -f compose.integration.yml down -v
```

주의:

- `down -v`는 PostgreSQL/Redis 볼륨을 삭제한다.
- migration smoke나 반복 수동 테스트에서 깨끗한 DB가 필요할 때만 사용한다.

## 흔한 문제

### PostgreSQL 연결 실패

- `docker compose ps`로 health 상태를 먼저 본다.
- `TCI_DATABASE_URL`의 user/password/host/port/db name을 확인한다.
- 기존 볼륨이 남아 있으면 `POSTGRES_*` 환경 변수 변경이 반영되지 않았을 수 있다.

### Redis 연결 실패

- `redis-cli -h 127.0.0.1 ping`으로 확인한다.
- `TCI_REDIS_URL`이 `redis://127.0.0.1:6379/0`인지 확인한다.
- 포트가 이미 다른 Redis에 잡혀 있으면 compose port를 바꾼다.

### GitLab remote 접근 차단

- `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`에 정확한 host 또는 `host:port`가 있는지 확인한다.
- HTTP/HTTPS 비표준 포트와 SSH 비표준 포트는 각각 `host:port`로 등록한다.
- IPv6, trailing-dot host, userinfo, query/fragment가 들어간 remote URL은 거부된다.
- `http://` remote는 `TCI_ALLOW_INSECURE_GITLAB_HTTP=true`가 아니면 거부된다.

### webhook이 앱에 도달하지 않음

- GitLab 서버에서 FastAPI callback URL로 네트워크 접근이 가능한지 확인한다.
- 로컬 `localhost`는 GitLab 서버 입장에서는 GitLab 서버 자신을 뜻할 수 있다.
- tunnel 또는 접근 가능한 개발 장비 IP를 사용한다.

### webhook token mismatch

- GitLab webhook Secret token과 TCI connection의 활성 webhook secret이 같은지 확인한다.
- 이 기능은 이전 secret grace period를 제공하지 않는다.
- 잘못된 token은 canonical connection status가 아니라 webhook health로 반영된다.
