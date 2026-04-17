# Implementation Plan: 코드 저장소 연동

**Branch**: `[001-git-repo-connection]` | **Date**: 2026-04-17 | **Spec**: `/specs/001-git-repo-connection/spec.md`  
**Input**: Feature specification from `/specs/001-git-repo-connection/spec.md`

## Summary

이 계획은 TCI 데이터 수집 영역에 GitHub Cloud 기반 Git 저장소 연결 기능을 Python 중심으로 추가한다. 읽기 전용 SSH/HTTPS 연결, 기본 분석 ref 1개(branch/tag), 경로 및 파일 타입 기반 수집 범위 제어, Push/PR 이벤트 기반 최신화, webhook secret grace rotation, 그리고 계획 입력에서 코드 스냅샷까지 이어지는 추적 관계를 FastAPI API, Celery worker, SQLAlchemy/Alembic persistence, Jinja2/HTMX 운영 UI 조합으로 설계한다. 구현 속도보다 설계 입력 문서의 품질을 우선하며, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`에 운영 규칙과 검증 기준을 먼저 고정한 뒤에만 후속 task 분해로 이어진다.

## Change Traceability

**Planning Input**: 2026-04-16 사용자 요청 "코드 저장소 연동 기능의 기술 계획 작성"과 후속 보강 요청 "webhook secret grace rotation을 고려" 및 "`FR-014` 설계를 명확히 해줘"  
**Spec Scope Baseline**: 2026-04-17 clarifications가 반영된 `/specs/001-git-repo-connection/spec.md`  
**Scope Changes Since Input**: 승인된 spec의 clarifications를 기준으로 아래 설계 규칙을 고정했다.

- v1 공식 지원 범위는 GitHub Cloud만이며 저장소 접근은 읽기 전용 SSH/HTTPS credential만 허용한다.
- 저장소 연결 1건은 기본 분석 ref 1개만 유지하고, PR source branch는 이벤트성 예외 타깃으로만 처리한다.
- GitHub Cloud에서는 Push/PR payload에서 추출한 commit 메타데이터를 기록 전용 도메인 이벤트로 저장하며, Push/PR만 스냅샷 갱신 트리거가 된다.
- 각 수집 성공 시점은 필터가 적용된 전체 파일 집합을 완전 스냅샷으로 고정 저장한다.
- 바이너리와 5 MiB 초과 파일은 기본 제외하며 v1에서는 사용자 예외 규칙으로도 포함하지 않는다.
- 저장소 자격 증명이 만료되거나 취소되면 연결 상태를 `reauth_required`로 전환하고, 재인증 전까지 신규 검증과 수집을 차단한다.
- 저장된 기본 분석 대상 ref가 더 이상 유효하지 않으면 연결 상태를 `ref_missing`으로 전환하고, 새 기본 ref 선택 전까지 신규 수집을 차단한다.
- `FR-012`를 위해 connection detail은 최신 성공/실패 시각과 마지막 처리 이벤트 요약을 제공하고, 상세 이력은 event timeline 조회로 분리한다.
- webhook secret은 revision 모델로 관리하고, 회전 시 24시간 grace window 동안 current와 previous secret을 모두 허용한다.
- `FR-014`를 위해 planning input reference -> repository connection -> scope rule version -> event/sync run -> code snapshot의 추적 체인을 런타임 데이터와 조회 계약으로 노출한다.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, HTMX  
**Storage**: PostgreSQL 16 for connection/event/snapshot metadata and trace references, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `.runtime/git-mirrors`, local snapshot archive under `.runtime/code-snapshots`  
**Testing**: `pytest`, `pytest-asyncio`, `httpx`, `schemathesis`, Playwright for operator flow regression  
**Target Platform**: Linux-based API/worker runtime with Git CLI available; operator UI served from the Python application as server-rendered HTML  
**Project Type**: Python web application with JSON API, async worker, and operator-facing server-rendered UI  
**Performance Goals**: valid webhook deliveries acknowledged quickly and reflected in processing status within 1 minute for at least 95% of Push/PR events; repository connection to first successful snapshot remains achievable within 10 minutes; planned webhook secret rotation must not interrupt valid event processing during the grace window  
**Constraints**: design-input quality takes precedence over implementation speed; pilot forbids auto-implement; GitHub Cloud only in v1; default ref 1개 정책; read-only credential only; raw-body HMAC verification required; binary and large files remain hard-excluded in v1; `reauth_required`/`ref_missing` 상태는 신규 검증 또는 수집 차단을 동반해야 한다; traceability must be queryable without external log correlation  
**Scale/Scope**: pilot release for internal operators managing low hundreds of repository connections, single default ref per connection, bursty webhook deliveries, revision-based secret rotation, and full snapshot retention for auditability

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Planning input is linked and translated into concrete design scope.
- [x] `spec.md` is approved for the scope implemented by this plan.
- [x] This plan introduces no scope that is absent from the approved spec.
- [x] Traceability from planning input -> spec -> plan will remain intact after delivery.
- [x] Pilot rule acknowledged: implementation will not auto-run and requires explicit human approval.
- [x] Validation evidence required for completion is defined in this plan.

## Clarification Freeze

이번 계획은 spec의 clarify/edge case를 구현 전 운영 규칙으로 닫아, task 분해에서 다시 해석하지 않도록 기준을 고정한다.

| Topic | Plan-Level Decision |
|-------|---------------------|
| credential 만료/취소 | 연결 상태를 `reauth_required`로 바꾸고, 운영자가 자격 증명을 다시 등록하기 전까지 신규 검증과 수집을 차단한다. |
| 기본 ref 삭제/이름 변경 | 다음 검증 또는 수집 시 연결 상태를 `ref_missing`으로 바꾸고, 운영자가 새 기본 ref를 고르기 전까지 신규 sync run을 차단한다. |
| 추가 브랜치/태그 상시 분석 | 현재 연결이 기본 ref 1개만 지원함을 UI/API에서 명시하고, `새 연결 생성` 또는 `기본 ref 교체` 중 하나를 선택하게 한다. |
| secret 누락 | 연결 상태를 `webhook_unconfigured`로 두고, delivery는 `secret_missing` 거부 사유로 기록한다. |
| secret 불일치 | 연결은 `active`를 유지하되 `webhookHealth.status = secret_mismatch_detected`로 노출하고, 운영자에게 저장된 secret과 GitHub 설정을 함께 재설정하라고 안내한다. |
| 기타 서명 실패 | delivery는 `signature_invalid`로 기록하고 최근 실패 상태를 `webhookHealth.status = signature_invalid_recently`로 노출한다. |
| webhook secret 회전 | 새 secret을 활성화할 때 직전 secret은 `previous_grace` 상태로 24시간 유지한다. grace 기간에는 current/previous 둘 다 서명 검증에 사용할 수 있으며, 어떤 secret이 검증에 쓰였는지 이벤트에 남긴다. grace 종료 후 previous secret은 자동 거부 대상으로 전환한다. |
| Commit 이벤트 의미 | GitHub의 별도 commit webhook을 전제하지 않고 Push/PR payload 안의 commit 메타데이터를 `commit_recorded` 도메인 이벤트로 분리 저장한다. |
| 빈 수집 결과 | 규칙 저장 시 `empty_result_risk` 경고를 반환하고, 실제 스냅샷 실행에서는 `NO_INCLUDED_FILES`로 실패 처리한다. |
| 바이너리/대용량 예외 포함 | 사용자 예외 규칙이 있어도 v1에서는 수집하지 않는다. 후속 범위로 남긴다. |
| PR force push / out-of-order event | PR 번호 또는 기본 ref 기준 cursor를 유지하고 최신 accepted HEAD SHA보다 오래된 이벤트는 `stale_head`로 종료한다. |
| FR-012 operator summary | connection detail은 US1 시점에 최근 성공/실패 수집 요약과 최신 snapshot 정보를 제공하고, webhook/event 저장소가 추가되는 US3 이후 `lastProcessedEvent` 요약과 event timeline 상세를 함께 제공한다. |
| FR-014 traceability | planning input reference를 연결에 귀속시키고, 활성 scope rule version, trigger event, sync run, snapshot manifest까지 역추적 가능한 조회 계약을 제공한다. |

## Project Structure

### Documentation (this feature)

```text
specs/001-git-repo-connection/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── repository-ingestion.openapi.yaml
└── tasks.md
```

### Source Code (planned implementation structure)

```text
src/
└── tci/
    ├── api/
    │   ├── dependencies/
    │   ├── routes/
    │   └── schemas/
    ├── domain/
    │   ├── models/
    │   └── services/
    ├── infrastructure/
    │   ├── git/
    │   ├── persistence/
    │   ├── queue/
    │   └── snapshots/
    ├── web/
    │   ├── routes/
    │   ├── templates/
    │   │   └── connections/
    │   └── static/
    ├── workers/
    ├── settings.py
    └── app.py

alembic/
└── versions/

tests/
├── contract/
│   └── repository_ingestion/
├── integration/
│   └── repository_connections/
└── unit/
    └── repository_connections/

.runtime/
├── git-mirrors/
└── code-snapshots/
```

**Structure Decision**: API, worker, operator UI를 하나의 Python codebase에서 분리된 모듈 경계로 관리한다. 저장소 연결/스냅샷/웹훅은 `src/tci/domain`과 `src/tci/infrastructure` 아래 도메인 모듈로, JSON API는 `src/tci/api/routes`, 운영자 화면은 `src/tci/web/routes`와 `src/tci/web/templates/connections` 아래로 고정한다. 데이터베이스 스키마 이력은 `alembic/versions`, 계약 검증은 `tests/contract`, traceability projection은 connection detail, event list, snapshot detail 조회에 공통으로 노출한다.

## Design Artifacts

### Research Status

- `research.md`는 provider 범위, mirror 전략, snapshot 보존, 필터 우선순위, FastAPI raw-body HMAC 검증, Celery 비동기 처리, dedupe 규칙, 상태 코드, revision/grace 모델을 고정한다.
- 이번 보강으로 `reauth_required`, `ref_missing`, connection detail 요약 vs event timeline 상세 역할이 승인된 spec 기준으로 고정되었다.
- 이번 보강으로 `webhook secret grace rotation`은 설계 범위에 포함되며, current/previous secret 동시 허용 기간과 가시성 요구가 승인된 상태다.

### Data Model Status

- `data-model.md`는 connection, credential revision, webhook secret revision, scope rule version, event, event cursor, sync run, snapshot, snapshot file을 정의한다.
- 이번 보강으로 `RepositoryConnection`은 `reauth_required`/`ref_missing` 상태와 `lastProcessedEvent` 요약 projection을 위한 참조를 포함한다.
- 이번 보강으로 `PlanningInputReference`와 traceability projection을 명시해 `FR-014`를 문서 추적이 아니라 런타임 조회 가능성으로 닫는다.

### Contract Status

- OpenAPI 계약은 connection create/get/patch/verify, scope rules, snapshots, event list, GitHub webhook 수신 흐름을 정의한다.
- 이번 보강으로 connection detail의 webhook rotation 상태, 마지막 처리 이벤트 요약, snapshot/event traceability, previous secret acceptance 여부를 응답 모델에 포함한다.

## Implementation Strategy

### Slice 1. Connection Lifecycle and Provenance Baseline

- 저장소 연결 생성, read-only credential 검증, 기본 ref 검증, 연결 상태 전이를 먼저 고정한다.
- 연결 상태 전이는 `pending_verification`, `active`, `reauth_required`, `ref_missing`, `webhook_unconfigured`, `disabled` 집합으로 고정하고, 자격 증명 만료/취소 및 기본 ref 소실 시 차단 규칙을 함께 설계한다.
- `PlanningInputReference`를 연결과 scope rule version에 연결해, 어떤 계획 입력에서 어떤 연결 설정이 생성됐는지 조회 가능하게 만든다.
- 첫 수동 스냅샷이 설계 전체의 기준선이므로 US1은 traceability projection과 최신 성공/실패 수집 요약을 포함한 독립 검증 가능 상태로 만든다.
- 이벤트 저장소가 아직 없는 US1 단계에서는 `lastProcessedEvent` 요약을 강제하지 않고, 해당 필드는 Slice 3 이후 authoritative source가 생긴 뒤 connection detail에 확장한다.

### Slice 2. Scope-Controlled Snapshot Pipeline

- 기본 하드 제외 -> 사용자 include -> 사용자 exclude -> 파일 타입 룰 -> 텍스트/크기 가드 순으로 필터 우선순위를 고정한다.
- 필터 적용 결과는 `CodeSnapshot`과 `CodeSnapshotFile` manifest에 함께 저장하고, snapshot detail에서 사용된 scope rule version과 trigger source를 역추적할 수 있게 노출한다.
- 규칙 저장 경고와 실행 시 하드 실패를 분리해 운영자가 설계 의도를 이해하도록 한다.

### Slice 3. Webhook Intake, Rotation Grace, and Event Freshness

- FastAPI webhook route는 raw body 검증 후 이벤트 영속화와 Celery enqueue까지만 수행하고, 실질 sync는 worker가 담당한다.
- Push는 기본 ref와 일치할 때만, PR은 `opened`, `reopened`, `synchronize`, `ready_for_review`에서만 스냅샷 최신화 후보가 된다.
- secret rotation은 active revision과 previous grace revision을 함께 검증하고, grace 종료 시점과 previous-secret acceptance를 operator UI/API에서 보여준다.
- dedupe는 `X-GitHub-Delivery` unique 처리와 `targetKey + headSha` cursor 처리의 2단으로 설계한다.

### Slice 4. Operator Observability and Traceability

- connection detail은 최근 성공/실패 수집 시각, 마지막 처리 이벤트 요약, webhook health, secret rotation grace 상태, 마지막 거부 사유를 함께 노출한다.
- 마지막 처리 이벤트의 상세 이력과 상태 전이 맥락은 event timeline 조회가 담당한다.
- snapshot detail은 `planningInputReference`, `connectionId`, `scopeRuleVersionId`, `syncRunId`, `triggerEventId`를 포함한 traceability block을 제공한다.
- `planning input -> spec -> plan -> connection settings -> event/sync -> snapshot -> delivery evidence` 경로를 문서와 런타임 응답 둘 다에서 재구성 가능하게 한다.

## Validation Strategy

- Unit: scope precedence, binary/size guard, stale SHA detection, secret rejection reason mapping, previous-grace secret acceptance 분기
- Contract: repository connection, scope rules, snapshot trigger, webhook intake, connection detail summary, event/status 조회, traceability block, rotation health projection OpenAPI 준수
- Integration: Git mirror fetch, snapshot archive generation, connection provenance persistence, `reauth_required`/`ref_missing` 상태 전이, FastAPI raw-body signature verification, delivery dedupe, stale event skip, grace-period secret rollover
- Quickstart regression: MVP review 전에 연결 생성 -> 초기 스냅샷 완료까지의 소요 시간을 측정해 `SC-001` 근거를 남기고, 전체 릴리스 회귀에서는 연결 생성 -> 규칙 저장 -> 초기 스냅샷 -> Push 최신화 -> PR source snapshot -> connection detail summary 확인 -> secret rotation grace -> traceability 조회를 반복 검증한다.
- Delivery evidence: 구현 이후 `/specs/001-git-repo-connection/delivery-evidence.md`에서 story별 검증 근거와 FR/SC trace coverage를 링크한다.

## Complexity Tracking

현재 헌법 위반은 없다. scope 확장은 모두 승인된 spec(`FR-002a`, `FR-003b`, `FR-012a`, `FR-016a`, `FR-017a`, `SC-005`) 또는 기존 요구(`FR-014`)를 구체화한 수준에 머문다.
