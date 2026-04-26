# Research: 온프레미스 GitLab 코드 저장소 연동

## 결정 1: 기존 Python 기반 저장소 수집 런타임을 유지하고 provider 확장만 추가한다

**Decision**: 새 기능은 `pilot-git-repo-connection/`의 기존 Python 3.12 런타임(FastAPI, SQLAlchemy, Celery, Jinja2/HTMX)을 유지한 채, GitHub Cloud 전용 흐름을 provider 확장 구조로 일반화해 구현한다.

**Rationale**:
- 현재 저장소에는 GitHub Cloud 연동이 이미 같은 코드베이스에 구현되어 있고, API route, persistence model, worker, operator UI가 모두 이 구조를 전제로 동작한다.
- 별도 서비스나 새 스택을 도입하면 GitHub 회귀 범위가 불필요하게 커지고, spec이 요구한 "기존 GitHub Cloud 연동과의 호환성"을 해칠 가능성이 높다.
- 기존 테스트 자산과 운영 UI를 그대로 재사용하면서 provider 분기만 추가하는 편이 delivery risk가 가장 낮다.

**Alternatives considered**:
- GitLab 전용 별도 서비스 추가: 분리는 쉽지만 traceability, UI, worker, 배포 경로가 중복된다.
- Node/TypeScript 재구현: 기존 pilot 구현과 충돌하고 회귀 범위가 커진다.

## 결정 2: provider-agnostic core + provider adapter 구조로 GitHub/GitLab 호환성을 확보한다

**Decision**: 저장소 연결 생성, ref 해석, snapshot 실행, 상태 요약, traceability projection은 provider 공통 서비스로 유지하고, 아래만 provider adapter로 분리한다.

- 원격 URL 파싱/검증
- webhook 보안 검증
- webhook payload 정규화
- provider event -> domain event 매핑
- delivery id 추출 규칙

**Rationale**:
- 현재 구현은 `process_github_event`, `github_webhooks.py`, `github_event_parser`처럼 GitHub 전용 이름이 진입 경계를 장악하고 있다.
- GitLab을 같은 방식으로 추가하면 전용 분기가 늘어나 유지보수가 어려워진다.
- 반대로 모든 것을 추상화하면 GitHub 코드까지 크게 흔들리므로, 공통 core와 provider adapter를 분리하는 수준이 적절하다.

**Alternatives considered**:
- GitHub와 GitLab 각각 독립 도메인 서비스 유지: 초기 구현은 빠르지만 snapshot/job/state 규칙 중복이 생긴다.
- 모든 route/schema를 즉시 provider-neutral로 전면 개편: 최종 형태엔 가깝지만 GitHub 회귀 위험이 커진다.

## 결정 3: GitLab webhook 보안은 `X-Gitlab-Token` 기반 exact-match 검증으로 처리한다

**Decision**: GitLab self-managed webhook 수신은 raw body HMAC이 아니라 GitLab이 전송하는 `X-Gitlab-Token` 헤더와 저장된 활성 secret의 exact-match 비교로 검증한다. GitHub는 기존 `X-Hub-Signature-256` HMAC 검증을 유지한다.

**Rationale**:
- GitLab 공식 webhook 문서는 secret token을 요청 헤더로 전달하는 모델을 사용한다.
- GitHub와 GitLab의 서명 방식이 다르므로, 같은 verifier를 억지로 재사용하면 provider별 실패 원인을 분리하기 어렵다.
- spec은 공식 연결 상태와 webhook health를 분리하라고 요구하므로, provider별 보안 모델 차이를 adapter 층에서 흡수하는 편이 적절하다.

**Alternatives considered**:
- GitLab에도 자체 HMAC 래퍼 추가: GitLab 기본 계약과 어긋나고 운영 설정이 복잡해진다.
- 토큰 미검증 상태 허용: 보안 요구와 충돌한다.

## 결정 4: GitLab delivery dedupe 키는 `Idempotency-Key` 우선, `X-Gitlab-Webhook-UUID` 보조로 사용한다

**Decision**: GitLab webhook 이벤트의 `provider_delivery_id`는 아래 우선순위로 추출한다.

1. `Idempotency-Key`
2. `X-Gitlab-Webhook-UUID`
3. 위 두 값이 모두 없으면 `connection_id + event_name + object_kind + object_id + head_sha + occurred_at` 해시

**Rationale**:
- GitLab 공식 문서는 webhook 요청에 `Idempotency-Key`와 `X-Gitlab-Webhook-UUID`를 함께 제공할 수 있음을 명시한다.
- 중복 delivery 제거는 spec의 필수 요구이고, GitHub와 달리 GitLab은 헤더 체계가 다르므로 명시적인 추출 우선순위가 필요하다.
- fallback 해시는 edge deployment나 프록시 환경에서 일부 헤더가 누락된 경우에도 record-only 이력은 남길 수 있게 한다.

**Alternatives considered**:
- `X-Gitlab-Webhook-UUID`만 사용: 재시도 idempotency semantics가 약하다.
- payload body hash만 사용: 서로 다른 delivery가 같은 payload를 보낼 때 audit 구분이 어렵다.

## 결정 5: GitLab Merge Request snapshot 트리거는 `open`, `reopen`, `update` 중 code-moving update로 한정한다

**Decision**:
- GitLab Merge Request hook의 `object_attributes.action`이 `open` 또는 `reopen`이면 snapshot 후보로 인정한다.
- `update`는 다음 중 하나일 때만 snapshot 후보로 인정한다.
  - `object_attributes.oldrev`가 존재
  - `object_attributes.last_commit.id`가 직전 cursor의 `head_sha`와 다름
- reviewer, label, title, description, state change만 있는 `update`는 이력만 기록한다.

**Rationale**:
- spec은 `opened`, `reopened`, `updated/pushed` 계열만 snapshot 트리거로 인정한다고 고정했다.
- GitLab의 `update` action은 코드 변경 없는 메타데이터 수정도 포함하므로 추가 필터가 없으면 snapshot noise가 커진다.
- `oldrev` 또는 `last_commit.id` 차이를 기준으로 code-moving update만 가려내면 GitHub의 `synchronize` 대응 의미와도 맞는다.

**Alternatives considered**:
- 모든 `update`를 snapshot 트리거로 사용: reviewer 변경, label 변경에도 snapshot이 발생한다.
- `open`/`reopen`만 허용: source branch force-push 이후 최신화가 누락된다.

## 결정 6: GitLab HTTPS credential은 `read_repository` 범위 토큰만 허용하고, SSH는 deploy key/readonly key만 허용한다

**Decision**:
- HTTPS는 `read_repository` 범위를 가진 access token 계열만 허용한다.
- SSH는 저장소 읽기 전용 검증을 통과한 key만 허용한다.
- 연결 검증은 기존 `git ls-remote` 기반 validator를 재사용하되, provider별 URL 규칙과 인증 실패 메시지 매핑만 분기한다.
- 런타임 credential binding은 secret을 remote URL, Git config, process argv에 남기지 않는 방식을 사용한다.

**Rationale**:
- spec은 GitHub와 동일하게 연결 단위 공유 읽기 전용 credential만 허용하라고 고정했다.
- GitLab은 self-managed 환경에서 토큰 종류가 다양할 수 있으므로, 토큰 종류가 아니라 scope(`read_repository`)를 기준으로 허용하는 편이 안정적이다.
- SSH key도 실제 Git CLI 검증 결과로 read-only 여부를 확인하는 편이 운영적으로 안전하다.

**Alternatives considered**:
- token 종류를 Personal Access Token으로만 제한: self-managed 운영 유연성이 떨어진다.
- credential type별 별도 검증 로직 작성: 구현이 중복된다.

## 결정 7: canonical connection 상태는 그대로 유지하고, provider reachability 문제는 health로 분리한다

**Decision**:
- `reauth_required`는 인증 실패 또는 credential 무효/만료일 때만 사용한다.
- `ref_missing`은 기본 ref 조회 실패가 확정됐을 때만 사용한다.
- GitLab 서버 도달 불가, DNS 실패, TLS 오류, webhook token mismatch, delivery validation failure는 canonical 상태를 바꾸지 않고 `ConnectionHealthSummary`로 분리한다.

**Rationale**:
- clarify에서 공식 상태 모델을 `active`, `reauth_required`, `ref_missing`으로 고정했다.
- self-managed GitLab은 네트워크 경로, 방화벽, 사설 인증서 문제로 일시 unreachable이 될 수 있는데, 이를 재인증 필요로 해석하면 운영자가 잘못 대응하게 된다.
- health 분리 모델은 기존 GitHub 연결과의 contract 호환성도 유지한다.

**Alternatives considered**:
- `server_unreachable`를 canonical 상태에 추가: 기존 GitHub 계약과 어긋난다.
- 모든 오류를 `reauth_required`로 통합: 문제 분류가 부정확하다.

## 결정 8: snapshot과 sync pipeline은 기존 공통 흐름을 유지하되 provider parser 출력만 바꾼다

**Decision**: GitLab에서도 기존 `RepositorySyncRun -> CodeSnapshot -> CodeSnapshotFile` 흐름과 mirror/snapshot archive 저장 방식을 그대로 유지한다. provider adapter는 공통 `NormalizedRepositoryEvent`를 출력하고, 이후 cursor 판단과 snapshot job enqueue는 공통 서비스가 처리한다.

**Rationale**:
- snapshot 저장 방식은 provider와 무관한 공통 기능이다.
- spec은 GitHub/GitLab 간 결과 해석과 traceability 호환성을 요구하므로 snapshot provenance 필드도 같은 구조를 유지해야 한다.
- provider별로 sync pipeline을 나누면 dedupe, stale head, traceability 구현이 중복된다.

**Alternatives considered**:
- GitLab 전용 snapshot pipeline 생성: 테스트와 운영 복잡도가 커진다.
- webhook route에서 직접 snapshot 생성: API 응답 경로가 길어지고 retry 설계가 약해진다.

## 결정 9: 공용 API 계약은 유지하고 GitLab webhook endpoint를 추가한다

**Decision**:
- `POST /api/repository-connections`, `PATCH /api/repository-connections/{id}`, `POST /api/repository-connections/{id}/verify`, `POST /api/repository-connections/{id}/snapshots`, `GET /api/repository-connections/{id}/events` 등 기존 공용 API는 유지한다.
- `provider` enum에 `gitlab_self_managed`를 추가한다.
- provider-specific webhook route로 `POST /api/webhooks/gitlab/{connectionId}`를 추가한다.
- GitHub route `/api/webhooks/github/{connectionId}`는 그대로 유지한다.

**Rationale**:
- 연결 관리 API는 이미 provider-neutral shape를 갖고 있다.
- webhook은 provider별 헤더와 보안 검증 방식이 달라 route 분리가 더 단순하다.
- 기존 GitHub contract test를 깨지 않고 GitLab contract를 병행 추가할 수 있다.

**Alternatives considered**:
- 단일 `/api/webhooks/{provider}/{connectionId}` route로 통합: 최종 형태는 깔끔하지만 기존 GitHub route 회귀가 커진다.
- GitLab도 GitHub route 재사용: 헤더/보안 모델 차이 때문에 부적절하다.

## 결정 10: GitLab compatibility regression은 설계 산출물과 테스트 계획에서 GitHub 회귀를 first-class로 다룬다

**Decision**: 모든 설계 문서와 후속 tasks는 GitLab 신규 시나리오와 같은 수의 GitHub 회귀 검증을 포함해야 한다. 최소 회귀 범위는 아래다.

- GitHub 연결 생성/검증
- GitHub Push webhook
- GitHub PR webhook
- GitHub connection detail / event timeline / snapshot traceability

**Rationale**:
- user 요청의 핵심 제약이 "기존 GitHub Cloud 연동 기능과의 호환성"이다.
- provider abstraction refactor는 GitHub 경계를 건드릴 가능성이 높다.
- plan 단계에서 회귀 범위를 명시해야 후속 tasks와 evidence가 실제로 그 범위를 커버한다.

**Alternatives considered**:
- GitLab 신규 시나리오만 검증: 가장 큰 리스크인 기존 기능 파손을 놓치게 된다.

## 결정 11: GitLab instance는 `remoteUrl`에서 파생하고 outbound host는 allowlist로 제한한다

**Decision**:
- 사용자가 별도 `providerInstanceUrl`을 입력하지 않는다.
- `provider_instance_url`은 `remoteUrl`에서 파생한 저장 메타데이터다.
- `/gitlab` 같은 path prefix는 instance subpath로 추정하지 않고 project namespace로 취급한다.
- localhost, private IPv4, 비표준 HTTPS/SSH 포트는 지원하되 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS` exact-origin allowlist가 필요하다.
- IPv6, GitHub host, trailing-dot host, userinfo, query/fragment, whitespace/control chars, dot path segment, malformed port는 거부한다.

**Rationale**:
- 별도 instance URL 입력은 operator 입력 부담과 `remoteUrl`/instance mismatch 위험을 늘린다.
- self-managed GitLab의 subpath 배포 여부는 `remoteUrl`만으로 안정적으로 판별하기 어렵다.
- 온프레미스 환경에서는 localhost/private network 접근이 필요할 수 있지만, SSRF와 내부망 오용을 막기 위해 outbound git 접근 전 allowlist가 필요하다.
- 비표준 포트는 운영상 필요하지만, host-only allowlist로 포트까지 암묵 허용하면 노출 범위가 넓어진다.

**Alternatives considered**:
- 사용자가 instance URL을 직접 입력: 명시성은 높지만 mismatch 검증과 UX 복잡도가 커진다.
- `/gitlab`을 instance subpath로 자동 추정: 실제 namespace가 `gitlab/...`인 저장소와 충돌한다.
- localhost/private IP를 일괄 차단: 보안은 단순하지만 온프레미스 검증과 사설 GitLab 운영을 지원하기 어렵다.

## 결정 12: Credentialed Git subprocess는 격리된 Git 환경에서 실행한다

**Decision**:
- Git subprocess는 service-user `HOME`, `XDG_CONFIG_HOME`, ambient `GIT_CONFIG_*`, ambient `GIT_SSH_COMMAND`, ambient `SSH_AUTH_SOCK`을 상속하지 않는다.
- `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`을 강제한다.
- HTTPS PAT는 remote URL에 삽입하지 않고, `GIT_ASKPASS` helper가 per-session token으로 인증된 local request에만 PAT를 제공한다.
- SSH private key는 temporary key file에 쓰지 않고 isolated `ssh-agent`에 stdin으로 등록한다. Git child에는 `SSH_AUTH_SOCK`/`SSH_AGENT_PID`를 노출하지 않고 `GIT_SSH_COMMAND`의 explicit `IdentityAgent`만 전달한다.
- SSH agent cleanup 실패는 본 Git 작업의 성공/실패 결과를 덮어쓰지 않고 best-effort warning으로 처리한다.

**Rationale**:
- Credentialed Git 명령이 host-level `.gitconfig`, credential helper, `url.*.insteadOf`, ambient SSH agent를 신뢰하면 secret exfiltration 또는 의도하지 않은 remote redirect가 가능하다.
- PAT를 remote URL에 넣으면 command, config, log, mirror metadata에 노출될 수 있다.
- SSH private key temp file은 cleanup 실패나 filesystem inspection 리스크를 키운다.
- Cleanup failure가 본 작업 오류를 덮어쓰면 운영자가 auth/ref/mirror 문제를 잘못 해석한다.

**Alternatives considered**:
- 기존 환경을 그대로 상속: 구현은 단순하지만 credentialed Git 경계에서 신뢰 범위가 과도하게 넓다.
- PAT를 HTTPS URL userinfo로 전달: Git 표준 동작은 쉽지만 secret이 URL 형태로 퍼질 수 있다.
- SSH key temp file 유지: 호환성은 좋지만 local disk secret exposure가 남는다.

## Sources Used

- GitLab Docs, Webhooks: https://docs.gitlab.com/ee/user/project/integrations/webhooks.html
- GitLab Docs, Merge request events: https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#merge-request-events
- GitLab Docs, Push events: https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#push-events
- GitLab Docs, Personal access tokens: https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html
- GitLab Docs, Deploy keys: https://docs.gitlab.com/ee/user/project/deploy_keys/
- Local implementation reference: `pilot-git-repo-connection/src/tci/`
