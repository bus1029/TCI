# 코드 저장소 연동 Docker 설치 가이드

## 목적

이 문서는 `001-git-repo-connection` 통합 테스트를 위해 어떤 제품을
Docker로 준비해야 하는지 정리한 조사 문서다. 코드베이스 요구사항과
공식 문서를 기준으로, 필수 컨테이너와 선택 컨테이너를 나누고 실제
로컬 설치 순서를 제안한다.

## 결론 먼저

이 기능의 통합 테스트를 위해 Docker로 반드시 띄워야 하는 것은
아래 두 가지다.

1. `PostgreSQL 16`
2. `Redis 7`

선택적으로 있으면 편한 것은 아래다.

1. `Adminer` 또는 `pgAdmin`
2. webhook 외부 유입 확인용 프록시 도구

반대로 아래는 Docker 설치 대상이 아니다.

1. GitHub Cloud 테스트 저장소
2. GitHub PAT 또는 SSH credential
3. GitHub webhook secret
4. FastAPI app과 Celery worker 자체

FastAPI app과 Celery worker는 우선 호스트에서 직접 실행하는 편이
디버깅이 쉽다. Docker는 먼저 상태 저장 인프라인 PostgreSQL, Redis를
안정적으로 띄우는 데 집중하는 것이 좋다.

## 왜 이 두 제품이 필수인가

### PostgreSQL 16

프로젝트 스펙이 `PostgreSQL 16`을 전제로 한다. 코드도
`TCI_DATABASE_URL`이 있어야 실제 영속 계층과 Alembic migration을
탈 수 있게 되어 있다.

이 제품이 필요한 이유:

- repository connection metadata 저장
- scope rule 저장
- sync run 저장
- repository event 저장
- snapshot metadata 저장
- Alembic migration round-trip 검증

### Redis 7

프로젝트 스펙이 `Redis 7`을 전제로 한다. 코드도
`TCI_REDIS_URL`이 있어야 Celery broker/backend를 만들 수 있다.

이 제품이 필요한 이유:

- snapshot enqueue
- webhook sync enqueue
- Celery broker/backend
- queue 기반 처리 흐름 검증

## Docker 관점에서 준비해야 할 제품 목록

### 필수

- `Docker Desktop` 또는 `Docker Engine + Docker Compose plugin`
- `postgres:16`
- `redis:7`

### 선택

- `adminer`
  - PostgreSQL 상태를 브라우저로 빠르게 보려면 유용하다.
- webhook 프록시
  - 실제 GitHub webhook을 로컬 FastAPI로 보내려면 공인 URL 또는
    프록시가 필요하다.
  - GitHub 공식 문서는 로컬 테스트 시 webhook proxy URL과
    `smee-client` 사용을 안내한다.

## 공식 문서 기준으로 확인한 핵심 사항

### Docker Compose 설치

Docker 공식 문서는 `Docker Desktop` 설치를 가장 쉬운 권장 경로로
설명한다. `Docker Desktop`에는 `Docker Engine`, `Docker CLI`,
`Docker Compose`가 함께 포함된다.

Linux에서는 이미 `Docker Engine`과 `Docker CLI`가 있다면
`Docker Compose plugin`을 따로 설치할 수 있다.

### PostgreSQL 공식 이미지

PostgreSQL 공식 Docker 이미지에서 핵심은 아래다.

- `POSTGRES_PASSWORD`는 필수다.
- `POSTGRES_USER`, `POSTGRES_DB`는 선택이다.
- Docker Compose 예시도 공식 문서에 있다.
- 초기화 관련 환경 변수는 비어 있는 데이터 디렉터리에서만 적용된다.

이 말은, 한번 볼륨이 만들어진 뒤에는 환경 변수를 바꿔도 이미 생성된
DB에는 반영되지 않을 수 있다는 뜻이다. 테스트 DB를 다시 만들고 싶으면
볼륨을 지우는 절차까지 같이 생각해야 한다.

### Redis 공식 이미지

Redis 공식 Docker 이미지는 기본적으로 쉽게 띄울 수 있지만,
컨테이너 밖으로 포트를 열면 보안상 주의가 필요하다.

이번 로컬 통합 테스트에서는 아래 원칙으로 쓰는 것이 안전하다.

- `127.0.0.1:6379:6379`처럼 localhost에만 바인딩
- 외부 공개 없음
- 필요 이상으로 password/auth를 얹지 않음

## 권장 아키텍처

로컬에서는 아래 구성이 가장 단순하다.

- Docker
  - `postgres:16`
  - `redis:7`
  - 선택: `adminer`
- 호스트 실행
  - `uvicorn tci.app:create_app --factory --reload`
  - `celery -A tci.workers.celery_app:celery_app worker -l info`

이 구성이 좋은 이유:

- Python 코드 수정 시 이미지 rebuild가 필요 없다.
- 테스트와 디버깅이 빠르다.
- 인프라만 컨테이너화하므로 장애 원인 분리가 쉽다.

## 추천 Docker Compose 구성

아래는 이 프로젝트 기준의 최소 권장 예시다. 아직 레포에 공식
`compose.yaml`이 들어간 것은 아니므로, 필요하면 별도 파일로 만들어
써야 한다.

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

Mac 또는 Windows면 `Docker Desktop`을 설치하는 것이 가장 간단하다.
Linux면 `Docker Engine + Docker CLI + Docker Compose plugin` 조합으로
준비한다.

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

다른 터미널에서 같은 환경 변수를 맞춘 뒤 실행한다.

```bash
celery -A tci.workers.celery_app:celery_app worker -l info
```

## 선택 제품 판단 기준

### Adminer

권장 상황:

- DB 테이블이 실제로 생성됐는지 보고 싶을 때
- webhook event row, snapshot row를 눈으로 확인하고 싶을 때
- Alembic 후 schema 상태를 빠르게 보고 싶을 때

불필요한 상황:

- pytest/helper만 돌릴 때
- SQLAlchemy 테스트 결과만 보면 충분할 때

### webhook 프록시 도구

권장 상황:

- 실제 GitHub Cloud 저장소에서 webhook을 쏴서 로컬 서버로 받고 싶을 때
- GitHub UI의 delivery/redelivery까지 확인하고 싶을 때

주의:

- 이건 PostgreSQL/Redis처럼 “반드시 Docker로 설치해야 하는 제품”은 아니다.
- GitHub 공식 문서는 로컬 테스트 시 webhook proxy URL과
  `smee-client`를 사용해 포워딩하는 흐름을 안내한다.
- 즉, webhook 실수신 테스트가 필요하면 Docker 인프라 외에
  프록시 도구도 별도로 준비해야 한다.

## Docker로 먼저 하지 말아야 할 것

아래는 초기에 굳이 Docker로 감싸지 않는 편이 낫다.

- FastAPI app
- Celery worker
- test runner

이유:

- 코드 수정 후 재기동이 느려진다.
- 로그 확인이 불편해진다.
- 현재 목적은 “통합 테스트에 필요한 제품 설치”이지
  “전체 개발 환경 컨테이너화”가 아니다.

## 이 프로젝트 기준 최종 추천안

지금 단계에서는 아래 구성이 가장 합리적이다.

1. Docker Desktop 또는 Docker Engine + Compose plugin 설치
2. `postgres:16` 컨테이너 설치
3. `redis:7` 컨테이너 설치
4. 필요하면 `adminer` 추가
5. FastAPI와 Celery는 호스트에서 실행
6. 실제 GitHub webhook까지 볼 때만 `smee-client` 같은 프록시 추가

## 문서로 남겨둘 결정

- 필수 Docker 대상은 `PostgreSQL 16`, `Redis 7`이다.
- `Adminer`는 선택이다.
- webhook 프록시는 선택이며, 실제 GitHub Cloud webhook 실험 때만 필요하다.
- FastAPI app과 Celery worker는 우선 호스트 실행을 유지한다.
- 실제 PostgreSQL destructive migration smoke를 닫으려면
  테스트 전용 PostgreSQL DB를 따로 둬야 한다.

## 참고한 공식 문서

- Docker Compose 설치 개요:
  `https://docs.docker.com/compose/install/`
- PostgreSQL Docker Official Image:
  `https://hub.docker.com/_/postgres`
- Redis Docker Official Image:
  `https://hub.docker.com/_/redis`
- GitHub webhook 로컬 테스트:
  `https://docs.github.com/en/webhooks/testing-and-troubleshooting-webhooks/testing-webhooks`
