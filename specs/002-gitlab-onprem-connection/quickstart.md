# Quickstart: 온프레미스 GitLab 코드 저장소 연동 설계 검증

## 목적

이 문서는 GitLab self-managed 연동이 기존 GitHub Cloud 기능을 깨지 않고 추가되었는지 빠르게 검증하는 실행 순서를 정의한다. 설계 검증, QA, task 분해, delivery evidence의 공통 기준으로 사용한다.

## Current Readiness

- 구현된 자동화 기준선:
  - GitLab self-managed 연결 생성
  - remote metadata 파싱
  - host allowlist
  - verify/default-ref/scope-preview/snapshot fail-closed 경로
  - 실제 PostgreSQL migration smoke와 실DB bootstrap
  - GitLab SSH custom-port allowlist
  - GitHub/GitLab coexistence
  - snapshot allowlist rejection 분류 회귀 검증
  - GitLab operator detail의 instance URL, project path, active scope traceability 표시
  - webhook health 렌더링 상태에서 `shared_token` / `webhookAuthMode` 비노출 검증
- GitLab 연결부터 초기 snapshot 및 operator detail까지는 자동화 검증 기준선이 준비됐다.
- scope/ref 전체 흐름과 webhook quickstart는 아직 실행 가능한 제품 동작이 아니라, 이후 구현과 검증이 따라야 할 기준선이다.
- 현재 준비된 자동화 표면:
  - `tests/contract/repository_ingestion/test_gitlab_connection_contract.py`
  - `tests/contract/repository_ingestion/test_gitlab_webhook_contract.py`
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `tests/contract/repository_ingestion/test_repository_scope_contract.py`
  - `tests/integration/repository_connections/test_gitlab_provider_flows.py`
  - `tests/integration/repository_connections/test_gitlab_connection_lifecycle.py`
  - `tests/integration/repository_connections/test_operator_connection_pages.py`
  - `tests/unit/repository_connections/test_gitlab_provider_parsing.py`
  - `tests/unit/repository_connections/test_process_gitlab_event.py`
  - `tests/unit/repository_connections/test_update_default_ref.py`
  - `tests/integration/repository_connections/test_github_gitlab_compatibility.py`
  - `tests/integration/repository_connections/test_phase2_migration_smoke.py`
- 전체 quickstart 검증은 US2/US3 이후 실제 구현 상태에 맞춰 채워진다.
- 최신 실행 결과는 `delivery-evidence.md`를 기준으로 확인한다.

## 사전 조건

1. `pilot-git-repo-connection/` 런타임이 실행 중이어야 한다.
2. PostgreSQL 16, Redis 7, Git CLI, API app, Celery worker가 모두 떠 있어야 한다.
3. GitLab self-managed 테스트 프로젝트 1개 준비
4. GitLab webhook 설정 권한과 secret token 준비
5. GitLab 읽기 전용 credential 준비
   - SSH deploy key 또는 read-only SSH key
   - 또는 `read_repository` scope를 가진 HTTPS access token
6. 회귀 검증용 GitHub Cloud 테스트 저장소 1개 준비
7. 런타임 디렉터리 `pilot-git-repo-connection/.runtime/git-mirrors`, `pilot-git-repo-connection/.runtime/code-snapshots`가 생성되어 있어야 한다.
8. GitLab self-managed host allowlist 설정
   - 환경 변수: `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`
   - 기본 HTTPS/SSH origin은 host만 등록한다. 예: `gitlab.example.com`
   - 비표준 포트는 `host:port`로 등록한다. 예: `gitlab.example.com:8443`, `192.168.10.20:2222`
   - `localhost`와 private IPv4는 지원하지만 allowlist 등록이 필요하다.

## 검증 시나리오

### 1. GitLab 연결 생성 및 검증

1. `POST /api/repository-connections`로 `provider=gitlab_self_managed`, `remoteUrl`, `transport`, `defaultRefType`, `defaultRefName`, `credential`를 등록한다.
2. `remoteUrl` host 또는 `host:port`가 allowlist에 없으면 git 접근 전에 400으로 차단되는지 확인한다.
3. `/gitlab` 같은 path prefix가 instance subpath가 아니라 project namespace로 저장되는지 확인한다.
4. `POST /api/repository-connections/{id}/verify`를 호출해 연결 검증이 성공하는지 확인한다.
5. 상세 조회에서 `status=active`, `provider=gitlab_self_managed`, `providerInstanceUrl`, `providerProjectPath`, `lastProcessedEvent=null`인지 확인한다.
6. Operator detail page에서 GitLab instance URL, project path, active scope traceability가 보이고 `shared_token` / `webhookAuthMode`가 보이지 않는지 확인한다.
7. 잘못된 token 또는 SSH key로 재검증하면 `reauth_required`로 전환되는지 확인한다.

### 2. Scope rule 및 초기 snapshot

1. `POST /api/repository-connections/{id}/scope-rules`에 include/exclude/file type 규칙을 저장한다.
2. 바이너리, 생성 산출물, `5 MiB` 초과 파일이 기본 제외되는지 확인한다.
3. `POST /api/repository-connections/{id}/snapshots`로 초기 snapshot을 실행한다.
4. `RepositorySyncRun`이 `succeeded`, `CodeSnapshot`이 생성되고 traceability block이 채워지는지 확인한다.

### 3. GitLab Push webhook

1. 기본 ref에 commit을 push한다.
2. GitLab webhook이 `POST /api/webhooks/gitlab/{connectionId}`로 전송되게 한다.
3. 응답이 `202 Accepted`인지 확인한다.
4. event list에서 `providerEventType=push`, `processingDecision=queued`를 확인한다.
5. 동일 delivery를 재전송했을 때 `duplicate_delivery`가 기록되는지 확인한다.

### 4. GitLab Merge Request webhook

1. source branch에서 Merge Request를 생성한다.
2. `open` action으로 snapshot sync가 enqueue되는지 확인한다.
3. source branch를 다시 push한 뒤 `update` action이 code-moving update로 분류되어 새 snapshot이 enqueue되는지 확인한다.
4. reviewer/label 변경만 발생한 `update`는 `record_only`인지 확인한다.
5. Merge Request source branch HEAD 기준 snapshot이 생성되는지 확인한다.

### 5. GitLab webhook 보안과 health

1. 올바른 `X-Gitlab-Token`으로 webhook을 보내면 검증 성공하는지 확인한다.
2. 잘못된 token으로 보내면 canonical status는 유지되고 `webhookHealth.webhookStatus=secret_mismatch_detected`가 노출되는지 확인한다.
3. 올바른 token으로 다시 보내면 `webhookHealth.webhookStatus=healthy`로 회복되는지 확인한다.

### 6. Provider compatibility regression

1. 기존 GitHub connection 생성 시나리오를 그대로 다시 실행한다.
2. `POST /api/webhooks/github/{connectionId}` Push webhook이 여전히 성공하는지 확인한다.
3. GitHub PR webhook snapshot 최신화가 계속 동작하는지 확인한다.
4. GitHub detail/event/snapshot response shape가 기존 contract와 동일한지 확인한다.

## 필요한 테스트 세트

- Unit
  - GitLab remote URL parser
  - GitLab host allowlist and custom port enforcement
  - GitLab token verifier
  - GitLab MR `update` -> snapshot/record-only 분기
  - provider delivery id 추출
  - GitHub/GitLab 공통 stale SHA 판정
- Integration
  - GitLab connection verify
  - GitLab push webhook -> sync run -> snapshot
  - GitLab MR open/update webhook -> source branch snapshot
  - `reauth_required` / `ref_missing` 상태에서 새 수집 차단
  - GitLab unreachable vs `reauth_required` 구분
  - GitHub regression flows
- Contract
  - provider enum 확장
  - GitLab webhook endpoint headers/body
  - connection detail health projection
  - GitHub contract no-break regression
- End-to-End
  - GitLab connection -> scope rules -> initial snapshot -> push -> MR -> detail timeline
  - GitHub connection -> push -> PR regression flow

## 완료 기준

- 운영자는 15분 이내 GitLab 연결부터 첫 snapshot 완료까지 확인할 수 있다.
- 유효한 GitLab Push/Merge Request webhook의 95% 이상이 1분 이내 처리 상태에 반영된다.
- GitHub Cloud 기존 quickstart 핵심 흐름이 추가 수동 우회 없이 그대로 성공한다.
- detail, event, snapshot 조회만으로 provider/connection/ref/scope/trigger provenance를 역추적할 수 있다.
