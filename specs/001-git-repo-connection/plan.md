# Implementation Plan: 코드 저장소 연동

**Branch**: `[006-git-repo-connection]` | **Date**: 2026-04-16 | **Spec**: `/specs/001-git-repo-connection/spec.md`  
**Input**: Feature specification from `/specs/001-git-repo-connection/spec.md`

## Summary

이 계획은 TCI 데이터 수집 영역에 GitHub Cloud 기반 Git 저장소 연결 기능을 추가해 읽기 전용 SSH/HTTPS 연결, 기본 분석 ref 1개(branch/tag), 경로 및 파일 타입 기반 수집 범위 제어, Push/PR 이벤트 기반 실시간 최신화, 완전한 코드 스냅샷 보존까지를 설계한다. 구현 상세보다 설계 입력 문서 품질을 우선하며, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`에서 운영 규칙과 경계 조건을 먼저 고정한 뒤에만 구현 단계로 넘어간다.

## Change Traceability

**Planning Input**: 2026-04-16 사용자 요청 "코드 저장소 연동 기능의 기술 계획 작성"  
**Spec Scope Baseline**: 2026-04-16 작성된 `/specs/001-git-repo-connection/spec.md` 초안. 문서 디렉터리는 `001`을 유지하지만 활성 feature branch는 `006-git-repo-connection`이다.  
**Scope Changes Since Input**: 승인된 spec의 Clarifications를 바탕으로 아래 설계 규칙을 명시적으로 고정했다.

- v1 공식 지원 범위는 GitHub Cloud만이며 저장소 접근은 읽기 전용 SSH/HTTPS credential만 허용한다.
- 저장소 연결 1건은 기본 분석 ref 1개만 유지하고, PR source branch는 이벤트성 예외 타깃으로만 처리한다.
- Commit은 기록 전용 도메인 이벤트이며 Push/PR만 스냅샷 갱신 트리거가 된다.
- 각 수집 성공 시점은 필터가 적용된 전체 파일 집합을 완전 스냅샷으로 고정 저장한다.
- 사용자의 include 규칙이 있더라도 바이너리와 5 MiB 초과 파일은 v1에서 수집하지 않는다.
- webhook 거부 사유는 `secret_missing`, `secret_mismatch`, `signature_invalid`로 분리해 운영자가 재설정 필요 상태를 명확히 본다.

## Technical Context

**Language/Version**: TypeScript 5.6 on Node.js 22 LTS  
**Primary Dependencies**: Fastify 5, Zod 3.24, Prisma 6, BullMQ 5, ioredis, pino, React 19, Next.js 15 App Router  
**Storage**: PostgreSQL 16 for connection/event/snapshot metadata, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `.runtime/git-mirrors`, local snapshot archive under `.runtime/code-snapshots`  
**Testing**: contract, integration, unit, and quickstart-regression suites aligned to the generated OpenAPI contract and operator validation flows  
**Target Platform**: Linux-based API/worker runtime with Git CLI available; operator UI served as a web application  
**Project Type**: web application with API, async worker, and operator-facing UI  
**Performance Goals**: valid webhook deliveries acknowledged quickly and reflected in processing status within 1 minute for at least 95% of Push/PR events; repository connection to first successful snapshot remains achievable within 10 minutes  
**Constraints**: design-input quality takes precedence over implementation speed; pilot forbids auto-implement; GitHub Cloud only in v1; default ref 1개 정책; read-only credential only; raw-body HMAC verification required; binary and large files excluded by default  
**Scale/Scope**: pilot release for internal operators managing low hundreds of repository connections, single default ref per connection, bursty webhook deliveries, and full snapshot retention for auditability

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Planning input is linked and translated into concrete design scope.
- [x] `spec.md` is approved for the scope implemented by this plan.
- [x] This plan introduces no scope that is absent from the approved spec.
- [x] Traceability from planning input -> spec -> plan will remain intact after delivery.
- [x] Pilot rule acknowledged: implementation will not auto-run and requires explicit human approval.
- [x] Validation evidence required for completion is defined in this plan.

## Clarification Freeze

이번 계획에서는 spec의 clarify/edge case를 구현 전 운영 규칙으로 닫아 더 이상 `NEEDS CLARIFICATION`이 남지 않도록 고정한다.

| Topic | Plan-Level Decision |
|-------|---------------------|
| 기본 ref 삭제/이름 변경 | 다음 검증 또는 수집 시 연결 상태를 `ref_missing`으로 바꾸고, 운영자가 새 기본 ref를 고르기 전까지 신규 sync run을 차단한다. |
| 추가 브랜치/태그 상시 분석 | 현재 연결이 기본 ref 1개만 지원함을 UI/API에서 명시하고, `새 연결 생성` 또는 `기본 ref 교체` 중 하나를 선택하게 한다. |
| secret 누락 | 연결 상태를 `webhook_unconfigured`로 두고, delivery는 `secret_missing` 거부 사유로 기록한다. |
| secret 불일치 | 연결은 `active`를 유지하되 `webhookHealth.status = secret_mismatch_detected`로 노출하고, 운영자에게 저장된 secret과 GitHub 설정을 함께 재설정하라고 안내한다. |
| 기타 서명 실패 | delivery는 `signature_invalid`로 기록하고 최근 실패 상태를 `webhookHealth.status = signature_invalid_recently`로 노출한다. |
| Commit 이벤트 의미 | GitHub의 별도 commit webhook을 전제하지 않고 Push/PR payload 안의 commit 메타데이터를 `commit_recorded` 도메인 이벤트로 분리 저장한다. |
| 빈 수집 결과 | 규칙 저장 시 `empty_result_risk` 경고를 반환하고, 실제 스냅샷 실행에서는 `NO_INCLUDED_FILES`로 실패 처리한다. |
| 바이너리/대용량 예외 포함 | 사용자 예외 규칙이 있어도 v1에서는 수집하지 않는다. 후속 범위로 남긴다. |
| PR force push / out-of-order event | PR 번호 또는 기본 ref 기준 cursor를 유지하고 최신 accepted HEAD SHA보다 오래된 이벤트는 `stale_head`로 종료한다. |

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

현재 저장소는 기획/설계 문서 중심이다. 구현 승인 후 아래 구조를 생성해 이 계획을 코드로 옮긴다.

```text
src/
├── server/
│   ├── lib/
│   │   ├── config/
│   │   └── http/
│   └── modules/
│       ├── repository-connections/
│       │   ├── api/
│       │   ├── infrastructure/
│       │   │   ├── git/
│       │   │   ├── persistence/
│       │   │   └── snapshots/
│       │   ├── services/
│       │   └── workers/
│       └── webhooks/
│           └── github/
├── shared/
│   └── contracts/
└── web/
    └── app/
        └── connections/

prisma/
└── migrations/

tests/
├── contract/
│   └── repository-ingestion/
├── integration/
│   └── repository-connections/
└── unit/
    └── repository-connections/

.runtime/
├── git-mirrors/
└── code-snapshots/
```

**Structure Decision**: API, worker, operator UI를 하나의 TypeScript codebase에서 분리된 모듈 경계로 관리한다. 저장소 연결/스냅샷/웹훅은 `src/server/modules` 아래 도메인 모듈로, 운영자 화면은 `src/web/app/connections` 아래로, 계약과 테스트는 각각 `src/shared/contracts`와 `tests/`로 고정해 traceability를 유지한다.

## Implementation Strategy

### Slice 1. Connection Lifecycle

- 저장소 연결 생성, read-only credential 검증, 기본 ref 검증, 연결 상태 전이를 먼저 고정한다.
- 연결 메타데이터와 credential/webhook secret revision을 분리 저장해 회전 이력과 재검증을 보장한다.
- 첫 수동 스냅샷이 설계 전체의 기준선이므로 US1을 먼저 독립 검증 가능하게 만든다.

### Slice 2. Scope-Controlled Snapshot Pipeline

- 기본 하드 제외 -> 사용자 include -> 사용자 exclude -> 파일 타입 룰 -> 텍스트/크기 가드 순으로 필터 우선순위를 고정한다.
- 필터 적용 결과는 `CodeSnapshot`과 `CodeSnapshotFile` manifest에 함께 저장해 후속 분석 입력을 재현 가능하게 만든다.
- 규칙 저장 경고와 실행 시 하드 실패를 분리해 운영자가 설계 의도를 이해하도록 한다.

### Slice 3. Webhook Intake and Event Freshness

- Fastify webhook route는 raw body 검증 후 이벤트 영속화와 enqueue까지만 수행하고, 실질 sync는 BullMQ worker가 담당한다.
- Push는 기본 ref와 일치할 때만, PR은 `opened`, `reopened`, `synchronize`, `ready_for_review`에서만 스냅샷 최신화 후보가 된다.
- dedupe는 `X-GitHub-Delivery` unique 처리와 `targetKey + headSha` cursor 처리의 2단으로 설계한다.

### Slice 4. Operator Observability and Traceability

- 상세 조회는 최근 성공/실패 수집 시각, 마지막 처리 이벤트, webhook health, 마지막 거부 사유를 함께 노출한다.
- `planning input -> spec -> plan -> contract/data-model -> tasks -> delivery evidence` 경로를 깨지 않도록 모든 상태 코드와 실패 코드를 문서에서 먼저 고정한다.

## Validation Strategy

- Unit: scope precedence, binary/size guard, stale SHA detection, secret rejection reason mapping
- Contract: repository connection, scope rules, snapshot trigger, webhook intake, event/status 조회 OpenAPI 준수
- Integration: Git mirror fetch, snapshot archive generation, credential rotation, webhook raw-body signature verification, delivery dedupe, stale event skip
- Quickstart regression: 연결 생성 -> 규칙 저장 -> 초기 스냅샷 -> Push 최신화 -> PR source snapshot -> webhook failure visibility
- Delivery evidence: 구현 이후 `/specs/001-git-repo-connection/delivery-evidence.md`에서 story별 검증 근거를 링크한다

## Complexity Tracking

현재 계획에는 헌장 위반을 정당화해야 하는 예외가 없다. 복잡도는 `Git transport + webhook + snapshot archive` 조합에서 나오지만, 이는 승인된 spec 요구사항을 직접 만족시키기 위한 최소 설계다.
