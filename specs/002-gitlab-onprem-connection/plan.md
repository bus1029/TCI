# Implementation Plan: 온프레미스 GitLab 코드 저장소 연동

**Branch**: `[002-gitlab-onprem-connection]` | **Date**: 2026-04-23 | **Spec**: `/specs/002-gitlab-onprem-connection/spec.md`  
**Input**: Feature specification from `/specs/002-gitlab-onprem-connection/spec.md`

## Summary

이 계획은 기존 `pilot-git-repo-connection` Python 런타임에 GitLab Self-Managed provider를 추가해, GitHub Cloud와 동일한 canonical contract 아래에서 저장소 연결, ref 선택, scope rule, Push/Merge Request 기반 snapshot 최신화, operator traceability를 함께 제공한다. 핵심 전략은 기존 GitHub 구현을 유지한 채 provider-specific webhook/security/parser 경계만 adapter로 분리하고, connection/snapshot/event/health/read-model은 공통 core로 재사용하는 것이다.

## Implementation Progress

- 2026-04-24 기준 GitLab self-managed remote 파싱, provider metadata 저장, host allowlist, create/verify/default-ref/scope-preview/snapshot fail-closed 경로를 구현했다.
- 2026-04-24 기준 기본 ref 변경은 GitLab allowlist 통과 후에만 credential decrypt를 수행한다.
- 2026-04-24 기준 snapshot build의 GitLab allowlist rejection은 credential failure로 오분류하지 않고 `MIRROR_SYNC_FAILED`로 기록한다.
- 2026-04-24 기준 실제 PostgreSQL `tci_test`에서 Alembic migration smoke, 실DB bootstrap, live constraint name regression 검증을 완료했다.
- 아직 남은 구현 범위는 GitLab webhook event normalization, operator detail/read-model, UI 표시다.

## Change Traceability

**Planning Input**: 2026-04-23 사용자 요청 "코드 저장소 연동 기능의 기술 계획 작성", 제약 "clarify에서 추가 구체화가 필요한 사항은 plan에서 명확히 구체화", "기존 GitHub Cloud 연동 기능 관련 코드와의 호환성 고려"  
**Spec Scope Baseline**: 2026-04-23 clarify 5건이 반영된 `/specs/002-gitlab-onprem-connection/spec.md`  
**Scope Changes Since Input**: 승인된 spec 범위를 벗어나지 않는 수준에서 아래 설계 규칙을 plan 단계에서 고정했다.

- GitLab 연결 credential은 GitHub와 동일하게 연결 단위 공유 비밀정보 + 읽기 전용만 허용한다.
- 기본 수집 제외 정책은 GitHub와 동일하게 텍스트 기반 소스 파일만 포함하고 바이너리·생성 산출물·`5 MiB` 초과 파일은 제외한다.
- Commit은 Push/Merge Request payload에서 추출한 기록 전용 event이며 독립 snapshot trigger가 아니다.
- GitLab Merge Request snapshot trigger는 `open`, `reopen`, code-moving `update`만 인정한다.
- 공식 연결 상태는 `active`, `reauth_required`, `ref_missing`만 유지하고, GitLab 서버 unreachable/webhook token mismatch는 health projection으로 분리한다.
- 기존 GitHub Cloud route, schema shape, GitHub contract test는 유지하고 GitLab provider를 additive change로 도입한다.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography  
**Storage**: PostgreSQL 16 for connection/event/snapshot metadata, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `pilot-git-repo-connection/.runtime/git-mirrors`, local snapshot archive under `pilot-git-repo-connection/.runtime/code-snapshots`  
**Testing**: `pytest`, `pytest-asyncio`, `httpx`, `schemathesis`, Playwright-backed operator regression, contract fixtures for GitHub/GitLab webhook payloads  
**Target Platform**: Linux-based API/worker runtime with Git CLI access and network reachability to on-prem GitLab instances  
**Project Type**: Python web application with JSON API, async worker, and server-rendered operator UI  
**Performance Goals**: valid GitLab Push/Merge Request webhooks의 95% 이상을 1분 이내 처리 상태로 반영; GitLab 연결부터 첫 snapshot 완료까지 15분 이내; GitHub 회귀 시나리오는 기존 1분/10분 기준을 유지  
**Constraints**: pilot 단계로 implement auto-run 금지; GitHub 계약과 response shape 호환 유지; 기본 ref 1개 정책 유지; GitLab webhook 보안은 `X-Gitlab-Token` exact-match; GitHub webhook 보안은 기존 HMAC 유지; binary/large file hard-exclude 유지; provider reachability 문제는 canonical status로 승격하지 않음; traceability는 API 응답만으로 조회 가능해야 함  
**Scale/Scope**: 내부 운영자가 관리하는 low hundreds 수준의 mixed-provider connections, bursty webhook deliveries, GitHub와 GitLab이 동시에 존재하는 워크스페이스, full snapshot retention for auditability

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Planning input is linked and translated into concrete design scope.
- [x] `spec.md` is approved for the scope implemented by this plan.
- [x] This plan introduces no scope that is absent from the approved spec.
- [x] Traceability from planning input -> spec -> plan will remain intact after delivery.
- [x] Pilot rule acknowledged: implementation will not auto-run and requires explicit human approval.
- [x] Validation evidence required for completion is defined in this plan.

## Clarification Freeze

이번 계획은 spec에서 의도적으로 planning 단계로 넘긴 항목을 구현 규칙으로 닫는다.

| Topic | Plan-Level Decision |
|-------|---------------------|
| GitLab webhook 보안 방식 | GitHub와 달리 `X-Gitlab-Token` exact-match 검증을 사용한다. 검증 대상은 단일 활성 secret이며 이전 secret 동시 허용은 이번 범위에 포함하지 않는다. |
| GitLab delivery dedupe 키 | `Idempotency-Key` 우선, `X-Gitlab-Webhook-UUID` 보조, 둘 다 없으면 derived hash를 사용한다. |
| GitLab MR update 세분화 | `action=update` 중 `oldrev` 존재 또는 `last_commit.id` 변경이 감지된 경우만 snapshot 후보로 인정한다. reviewer/label/title 변경만 있는 update는 `record_only`다. |
| GitLab 서버 unreachable | canonical status는 유지하고 health projection에 `providerReachabilityStatus=unreachable_recently`로 기록한다. auth 실패일 때만 `reauth_required`로 전환한다. |
| GitLab credential 허용 범위 | HTTPS는 `read_repository` scope 토큰만, SSH는 read-only 검증을 통과한 key만 허용한다. |
| GitHub 호환 전략 | GitHub route와 contract는 유지하고, provider adapter 계층을 추가하는 additive refactor만 허용한다. |
| Event cursor 의미 | `default_ref`, `pr:{number}`, `mr:{iid}` 단위 cursor를 유지해 stale event를 provider-neutral하게 거른다. |
| Operator summary | connection detail은 provider와 무관하게 `lastSuccessfulSnapshotAt`, `lastFailedSyncAt`, `lastProcessedEvent`, `webhookHealth`, `traceability`를 동일 shape로 제공한다. |

## Project Structure

### Documentation (this feature)

```text
specs/002-gitlab-onprem-connection/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── delivery-evidence.md
├── contracts/
│   └── repository-ingestion.openapi.yaml
└── tasks.md
```

### Source Code (planned implementation structure)

```text
pilot-git-repo-connection/
├── src/
│   └── tci/
│       ├── api/
│       │   ├── routes/
│       │   │   ├── repository_connections.py
│       │   │   ├── repository_events.py
│       │   │   ├── repository_scope.py
│       │   │   ├── repository_snapshots.py
│       │   │   ├── github_webhooks.py
│       │   │   └── gitlab_webhooks.py
│       │   └── schemas/
│       ├── domain/
│       │   └── services/
│       │       ├── create_repository_connection.py
│       │       ├── process_github_event.py
│       │       ├── process_gitlab_event.py
│       │       └── repository_event_processing.py
│       ├── infrastructure/
│       │   ├── git/
│       │   ├── persistence/
│       │   ├── queue/
│       │   ├── snapshots/
│       │   └── webhooks/
│       │       ├── github_*.py
│       │       ├── gitlab_*.py
│       │       └── provider_event_types.py
│       ├── web/
│       │   ├── routes/
│       │   └── templates/connections/
│       ├── workers/
│       ├── settings.py
│       └── app.py
├── alembic/versions/
└── tests/
    ├── contract/repository_ingestion/
    ├── integration/repository_connections/
    └── unit/repository_connections/
```

**Structure Decision**: 구현은 기존 `pilot-git-repo-connection` 루트를 유지한다. GitHub-specific route와 parser는 그대로 두고, 같은 디렉터리 계층에 GitLab-specific adapter를 추가한다. 공통 connection/snapshot/state/traceability 규칙은 `domain/services`와 `infrastructure/persistence`에서 provider-neutral helper로 끌어올리고, provider 차이는 `infrastructure/webhooks`와 provider-specific route/service에서 흡수한다.

## Design Artifacts

### Research Status

- `research.md`는 provider adapter 구조, GitLab webhook token 검증, GitLab delivery id 추출 우선순위, MR update gating, reachability health 분리, credential scope 허용 기준을 고정했다.
- GitLab docs 기반으로 webhook 보안과 event semantics를 문서화했다.
- 로컬 구현 스캔으로 실제 변경 지점(`github_webhooks.py`, `process_github_event.py`, persistence enums, tests/support fixtures)을 식별했다.

### Data Model Status

- `data-model.md`는 기존 connection/event/snapshot 모델을 mixed-provider 구조로 확장했다.
- `RepositoryConnection.provider`는 `github_cloud`, `gitlab_self_managed`를 지원하도록 확장한다.
- `ConnectionHealthSummary`와 `ConnectionStatus`를 분리해 canonical state 호환성을 유지한다.
- GitLab-specific dedupe와 MR cursor를 위해 `provider_event_idempotency_source`, `mr:{iid}` target key를 추가한다.

### Contract Status

- 공용 connection/scope/snapshot/event API는 shape를 유지한다.
- `provider` enum에 `gitlab_self_managed`를 추가한다.
- provider-specific webhook route로 `POST /api/webhooks/gitlab/{connectionId}`를 새로 정의한다.
- GitHub route는 그대로 유지해 기존 contract test와 operator flow를 깨지 않는다.

## Implementation Strategy

### Slice 1. Provider-Compatible Connection Lifecycle

- `RepositoryProvider` enum과 remote parser를 확장한다.
- GitLab self-managed 식별은 기존 저장소 주소와 provider metadata를 사용하며, 별도 `providerInstanceUrl` 사용자 입력 필드는 추가하지 않는다.
- `provider_instance_url`은 `remoteUrl`에서 파생한다. `/gitlab` 같은 path prefix는 instance subpath로 추정하지 않고 project namespace로 취급한다.
- localhost, private IPv4, 비표준 SSH/HTTPS 포트는 지원하되, outbound git 접근 전 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS` exact-origin allowlist를 통과해야 한다.
- GitLab remote parser는 GitHub host, trailing-dot host, IPv6, userinfo, query/fragment, whitespace/control chars, dot path segment, malformed port를 거부한다.
- GitHub/GitLab 모두 같은 canonical status와 detail response shape를 유지한다.
- credential validator는 기존 `git ls-remote` 흐름을 재사용하되, GitLab remote URL parser와 read-only token scope validation을 추가한다.

### Slice 2. Provider-Neutral Snapshot and Scope Pipeline

- scope rule, file filtering, snapshot archive, traceability block은 기존 공통 구현을 유지한다.
- GitLab 연결도 동일한 scope precedence와 hard exclude를 적용한다.
- `RepositorySyncRun`과 `CodeSnapshot`은 provider-neutral로 유지하고, trigger type에 `webhook_merge_request`만 추가한다.
- snapshot detail과 operator UI는 provider 값만 추가하고 structure는 바꾸지 않는다.

### Slice 3. GitLab Webhook Intake and Event Normalization

- `/api/webhooks/gitlab/{connectionId}` route를 추가한다.
- `X-Gitlab-Token` 검증, delivery id 추출, payload parsing, event normalization을 GitLab adapter로 분리한다.
- GitLab Push hook은 기본 ref 일치 시 queued, 아니면 record-only로 처리한다.
- GitLab Merge Request hook은 `open`, `reopen`, code-moving `update`만 queued로 처리하고 나머지는 record-only로 남긴다.
- Commit metadata는 Push/MR payload에서 추출해 `commit_recorded` domain event로 저장한다.

### Slice 4. Health, Reachability, and Operator Read Models

- canonical status는 auth/ref 문제에만 반응하게 유지한다.
- GitLab 서버 unreachable, TLS 실패, DNS 실패, token mismatch는 `ConnectionHealthSummary`에 누적한다.
- connection detail read model은 mixed-provider health를 같은 UI section에서 렌더링한다.
- event timeline은 provider-specific raw fields를 보여주되 processing decision vocabulary는 공통으로 맞춘다.

### Slice 5. GitHub Compatibility Regression

- 기존 GitHub routes, fixtures, contract tests, integration tests를 유지한다.
- provider abstraction refactor 후에도 GitHub `push`, `pull_request`, secret rotation, detail summary, snapshot traceability가 그대로 통과해야 한다.
- GitHub-specific file names를 즉시 전면 rename하지 않는다. additive file introduction 후 공통 helper로만 이동한다.

## Validation Strategy

- Unit
  - GitLab remote URL parsing
  - GitLab self-managed host allowlist and custom port handling
  - GitLab token verification
  - GitLab delivery id extraction priority
  - MR `update` gating (`oldrev` / `last_commit.id` 비교)
  - provider-neutral stale cursor logic
  - health vs canonical status separation
- Contract
  - create/update connection provider enum expansion
  - GitLab webhook endpoint headers and accepted response
  - connection detail health projection shape
  - GitHub existing contract no-break regression
- Integration
  - GitLab standard operator path completes within 15 minutes for SC-001
  - GitLab verify success / auth failure / unreachable failure
  - `reauth_required` / `ref_missing` 상태에서 manual snapshot과 webhook-driven snapshot 차단
  - GitLab push webhook -> sync run -> snapshot
  - GitLab MR open/update -> source branch snapshot
  - GitHub push/PR regression
  - mixed-provider workspace listing/detail flows
- End-to-End
  - GitLab connection -> scope rules -> initial snapshot -> push -> MR -> detail timeline
  - GitHub connection -> push -> PR regression path
- Delivery evidence
  - provider별 story/FR/SC 검증 링크를 feature evidence 문서에 남긴다.

## Complexity Tracking

현재 헌법 위반은 없다. scope 추가는 모두 승인된 spec의 clarify를 구현 가능한 기술 규칙으로 닫은 수준이다. 다만 mixed-provider compatibility 때문에 provider abstraction refactor가 필요하므로, task 분해 시 아래 순서를 강제한다.

1. 공통 contract/data model 확장
2. GitLab adapter 추가
3. GitHub regression 통과
4. operator read model 통합

이 순서를 어기면 기존 GitHub 흐름 파손 위험이 커진다.
