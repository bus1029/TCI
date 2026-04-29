# Implementation Plan: 워크스페이스 기반 저장소 연결 시작점 전환

**Branch**: `003-repository-first-connections` | **Date**: 2026-04-29 | **Spec**: `/specs/003-repository-first-connections/spec.md`  
**Input**: Feature specification from `/specs/003-repository-first-connections/spec.md`

## Summary

이 계획은 기존 `pilot-git-repo-connection` Python 런타임에서 저장소 연결 생성의 출발점을 `planningInputReferenceId` 필수 입력에서 워크스페이스 기반 Repository 연결로 전환한다. 핵심 전략은 `RepositoryConnection`과 downstream scope/snapshot/event trace에서 planning reference를 optional legacy 관계로 낮추고, 새 연결은 planning trace 없이 생성하되 기존 GitHub Cloud/GitLab Self-Managed 연결의 traceability와 provider별 운영 흐름을 보존하는 것이다.

## Change Traceability

**Planning Input**: 2026-04-29 사용자 요청 "저장소 연결 기능이 Repository 연결에서 시작하도록 수정하는 기술 계획", 제약 "clarify 항목은 plan에서 명확히 구체화", "기존 GitHub Cloud, GitLab 연동 기능 관련 코드와의 호환성 고려"  
**Spec Scope Baseline**: 2026-04-29 clarify 7건이 반영된 `/specs/003-repository-first-connections/spec.md`
**Scope Changes Since Input**: 승인된 spec 범위를 벗어나지 않는 수준에서 아래 설계 규칙을 plan 단계에서 고정한다.

- 새 Repository 연결 생성 payload는 `planningInputReferenceId`를 받지 않는다.
- 구 클라이언트가 `planningInputReferenceId` 또는 동등한 planning/spec/plan 참조 필드를 보내면 요청을 거부하고 저장하지 않는다.
- 기존 연결의 `planning_input_reference_id`와 traceability block은 legacy provenance로 보존한다.
- 새 연결의 detail/snapshot traceability는 `planningInputReference: null`, `origin.kind = workspace_repository` 형태로 노출한다.
- 후보 목록은 설정된 provider 계정 또는 GitLab 인스턴스 접근 범위에서만 제공하고, 항상 수동 URL 입력 경로를 유지한다.
- 후보 조회에 쓰이는 개인 provider 권한은 연결 운영 credential로 승격하지 않는다.
- 새 연결 생성은 검증된 워크스페이스 공유 읽기 전용 credential이 있어야만 완료된다.
- 기존 `workspace_id`가 있는 planning 기반 연결은 그 값을 canonical workspace 귀속으로 사용한다.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography  
**Storage**: PostgreSQL 16 for connection/event/snapshot metadata and legacy planning references, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `pilot-git-repo-connection/.runtime/git-mirrors`, local snapshot archive under `pilot-git-repo-connection/.runtime/code-snapshots`  
**Testing**: `pytest`, `pytest-asyncio`, `httpx`, `schemathesis`, operator UI integration tests, existing GitHub/GitLab webhook and connection contract fixtures  
**Target Platform**: Linux-based API/worker runtime with Git CLI access and network reachability to GitHub Cloud and configured GitLab Self-Managed instances  
**Project Type**: Python web application with JSON API, async worker, and server-rendered operator UI  
**Performance Goals**: 새 워크스페이스 기반 GitHub/GitLab 연결 생성부터 상세 조회까지 10분 이내 완료; 기존 GitHub/GitLab webhook 처리 기준은 유지; 후보 목록 조회는 설정된 provider 계정/인스턴스 범위에서 일반 운영 화면 사용자가 기다릴 수 있는 시간 안에 완료  
**Constraints**: pilot 단계로 implement auto-run 금지; `planningInputReferenceId` 필수 계약 제거는 additive compatibility가 아니라 명시적 reject로 수행; 기존 GitHub/GitLab create/detail/snapshot/event/webhook 회귀 통과; 새 연결은 planning trace를 저장하지 않음; 기존 planning trace는 삭제하지 않음; candidate 조회 credential과 연결 운영 credential 분리; 개인 provider 권한만으로 connection active 생성 금지; shared read-only credential 검증 실패 시 생성 중단과 해결 안내 제공; 한 워크스페이스 안 동일 provider+canonical repository 중복 차단; provider별 event/snapshot/history projection 분리 유지
**Scale/Scope**: 내부 운영자가 관리하는 low hundreds 수준의 mixed-provider workspace connections, 기존 planning 기반 연결과 신규 workspace 기반 연결이 함께 존재하는 전환 기간, provider별 webhook burst와 snapshot retention은 기존 기준 유지

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Planning input is linked and translated into concrete design scope.
- [x] `spec.md` is approved for the scope implemented by this plan.
- [x] This plan introduces no scope that is absent from the approved spec.
- [x] Traceability from planning input -> spec -> plan will remain intact after delivery.
- [x] Pilot rule acknowledged: implementation will not auto-run and requires explicit human approval.
- [x] Validation evidence required for completion is defined in this plan.

## Clarification Freeze

| Topic | Plan-Level Decision |
|-------|---------------------|
| 새 연결 planning trace | `RepositoryConnection.planning_input_reference_id`를 nullable legacy FK로 전환하고, 새 workspace-based create path는 planning reference row를 만들거나 연결하지 않는다. |
| obsolete planning field | `POST /api/repository-connections`에 `planningInputReferenceId` 또는 동등한 planning/spec/plan 참조 필드가 포함되면 400 계열 validation error로 거부하고 값을 저장하지 않는다. |
| 기존 trace 보존 | 기존 GitHub/GitLab 연결의 planning reference는 migration에서 유지하고, detail/snapshot traceability에 legacy provenance로 계속 노출한다. |
| 저장소 선택 방식 | provider 후보 목록 선택과 수동 URL 입력을 모두 지원한다. 수동 URL 입력은 기존 GitHub/GitLab 연결 생성 경로와 같은 validator를 사용한다. |
| 후보 목록 범위 | 후보 목록은 워크스페이스에 설정된 provider 계정 또는 GitLab 인스턴스 접근 정보가 있을 때만 제공한다. 미설정 provider는 empty candidate state와 수동 URL 입력만 제공한다. |
| 권한 모델 | 개인 provider 권한은 후보 조회에만 사용한다. 연결 검증, mirror sync, snapshot, webhook 처리, 재검증은 워크스페이스 공유 읽기 전용 credential만 사용한다. shared read-only credential이 없거나 검증 실패하면 연결 생성은 실패한다. |
| 권한 실패 UX/API | 접근 권한 만료, 권한 회수, shared read-only credential 검증 실패는 connection row를 active로 만들지 않고 provider별 재인증 또는 권한 수정 안내가 포함된 문제 응답/화면 상태로 표현한다. |
| 기존 workspace 귀속 | 기존 planning 기반 연결에 저장된 `workspace_id`를 canonical workspace 귀속으로 사용한다. 값이 없거나 일관되지 않은 예외만 compatibility state로 표시한다. |
| GitHub/GitLab 호환성 | provider별 remote parser, webhook verifier, event normalizer, snapshot pipeline은 기존 의미를 유지한다. 이 기능은 시작점/traceability/UX/API 계약을 바꾸며 provider semantics를 재설계하지 않는다. |

## Project Structure

### Documentation (this feature)

```text
specs/003-repository-first-connections/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── repository-first-connections.openapi.yaml
├── checklists/
│   └── requirements.md
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
│       │   │   ├── repository_candidates.py
│       │   │   ├── repository_snapshots.py
│       │   │   ├── repository_events.py
│       │   │   ├── github_webhooks.py
│       │   │   └── gitlab_webhooks.py
│       │   └── schemas/
│       │       ├── repository_connection.py
│       │       └── repository_candidate.py
│       ├── domain/
│       │   └── services/
│       │       ├── create_repository_connection.py
│       │       ├── get_repository_connection_detail.py
│       │       ├── list_repository_candidates.py
│       │       ├── build_traceability_reference.py
│       │       └── repository_connection_support.py
│       ├── infrastructure/
│       │   ├── git/
│       │   │   └── remote_parsers.py
│       │   ├── persistence/
│       │   │   ├── models.py
│       │   │   └── repository_connection_repository.py
│       │   ├── queue/
│       │   ├── snapshots/
│       │   └── webhooks/
│       ├── web/
│       │   ├── routes/
│       │   │   ├── repository_connections.py
│       │   │   └── repository_connection_detail.py
│       │   └── templates/connections/
│       └── workers/
├── alembic/versions/
└── tests/
    ├── contract/repository_ingestion/
    ├── integration/repository_connections/
    └── unit/repository_connections/
```

**Structure Decision**: 기존 `pilot-git-repo-connection` 루트를 유지한다. 새 기능은 저장소 연결 시작점과 provenance 계약을 바꾸므로 `repository_connections.py`, `RepositoryConnection` persistence, detail serialization, snapshot traceability builder, operator connection create UI가 주 변경 지점이다. `github_webhooks.py`, `gitlab_webhooks.py`, provider event parser, snapshot builder는 compatibility regression 대상으로 두고 의미 변경을 피한다.

## Design Artifacts

### Research Status

- `research.md`는 planning trace nullable 전환, obsolete planning field reject, legacy provenance 보존, candidate listing scope, credential ownership, migration compatibility, contract versioning 결정을 고정한다.
- plan 단계에서 추가 clarification이 필요한 항목은 모두 `Clarification Freeze`에 implementation rule로 닫았다.
- 로컬 구현 스캔으로 실제 변경 지점(`CreateRepositoryConnectionRequest`, `RepositoryConnection.planning_input_reference_id`, `serialize_repository_connection_detail`, `serialize_code_snapshot_detail`, `create_repository_connection`)을 식별했다.

### Data Model Status

- `data-model.md`는 `PlanningInputReference`를 legacy-only provenance로 재정의한다.
- `RepositoryConnection.planning_input_reference_id`는 nullable FK로 전환하고, `origin_kind`/compatibility 상태를 추가한다.
- `RepositoryCredentialRevision`은 workspace shared read-only operation credential만 저장하며 candidate discovery personal grant는 저장하지 않는다.
- `CollectionScopeRuleVersion`과 `CodeSnapshot` traceability는 connection을 기준으로 구성하고 planning reference는 optional legacy enrichment가 된다.
- `RepositoryCandidate`는 persisted entity가 아니라 provider/account/instance-scoped projection이다.

### Contract Status

- `POST /api/repository-connections` request에서 `planningInputReferenceId`를 제거하고, 포함된 요청은 validation error로 거부한다.
- `RepositoryConnectionDetailResponse.traceability.planningInputReference`는 nullable이 된다.
- `origin` block을 추가해 `workspace_repository`, `legacy_planning`, `legacy_unassigned`를 구분한다.
- `GET /api/repository-candidates`를 추가해 설정된 provider 계정/인스턴스 범위의 후보 목록을 반환한다.
- 개인 provider grant로 조회된 candidate는 operation credential이 아니며, connection create는 workspace shared read-only credential 검증을 요구한다.
- 기존 GitHub/GitLab webhook endpoint 계약은 변경하지 않는다.

## Implementation Strategy

### Slice 1. Repository Connection Provenance Model

- Alembic migration으로 `repository_connections.planning_input_reference_id`를 nullable로 전환한다.
- `repository_connections`의 `(id, planning_input_reference_id)` unique/FK 의존 관계를 검토해 nullable-safe constraint로 바꾼다.
- `collection_scope_rule_versions.planning_input_reference_id`와 snapshot traceability 경로가 connection planning reference를 필수로 가정하는 부분을 optional legacy reference로 낮춘다.
- `origin_kind` 또는 equivalent read-model field를 추가해 `workspace_repository`, `legacy_planning`, `legacy_unassigned`를 구분한다.
- 기존 rows는 기존 `workspace_id`를 canonical 귀속으로 유지하고, planning reference가 있으면 `legacy_planning`으로 표시한다.

### Slice 2. Workspace-Based Create Contract

- `CreateRepositoryConnectionRequest`에서 `planningInputReferenceId`를 제거한다.
- obsolete `planningInputReferenceId`가 포함된 요청은 validation error로 거부하고 connection row를 만들지 않는다.
- `CreateRepositoryConnectionCommand`와 service는 `workspace_id`를 직접 사용해 connection을 생성한다.
- planning reference lookup을 create path에서 제거한다.
- connection 생성 후 `connection.planning_input_reference`가 없어도 serializer와 detail read model이 동작하게 만든다.
- 수동 URL 입력은 기존 provider별 remote parser, allowlist, read-only validator, mirror sync 흐름을 그대로 사용한다.

### Slice 3. Credential Boundary and Permission Failure Handling

- candidate discovery personal grant는 후보 목록 조회 service 안에서만 사용하고 connection credential/revision으로 저장하지 않는다.
- create command는 workspace shared read-only credential 입력과 검증 결과 없이는 connection 생성을 완료하지 않는다.
- shared read-only credential 검증 실패, 저장소 접근 권한 만료, 권한 회수는 provider별 재인증 또는 권한 수정 안내가 있는 problem response와 operator UI 상태로 매핑한다.
- 실패 케이스는 active connection, initial sync, snapshot enqueue가 발생하지 않도록 한다.

### Slice 4. Traceability Projection Compatibility

- connection detail의 `traceability`는 `planningInputReference: null`을 허용한다.
- 새 `origin` block은 connection source와 compatibility state를 명시한다.
- `serialize_code_snapshot_detail`과 `build_snapshot_traceability_reference`는 snapshot -> connection -> optional planning reference 경로로 구성한다.
- legacy trace가 있는 기존 GitHub/GitLab 연결은 기존 planning reference 값을 동일하게 반환한다.
- trace가 없는 새 연결은 오류 없이 active scope, latest event, latest snapshot 중심 trace를 반환한다.

### Slice 5. Repository Candidate Flow

- `GET /api/repository-candidates` route와 schema를 추가한다.
- 후보 목록은 provider, configured account/instance scope, repository owner/path/name, alreadyConnected, selectable, accessStatus를 반환한다.
- provider 계정 또는 GitLab 인스턴스 접근 정보가 없으면 `items: []`와 manual URL guidance를 반환한다.
- candidate 조회에 사용한 개인 provider grant는 connection credential로 저장하지 않는다.
- 수동 URL create path와 candidate-selected create path 모두 canonical provider+repository identity를 계산해 같은 dedupe rule을 사용한다.

### Slice 6. Operator UI Flow

- repository connection create 화면을 workspace-first로 재구성한다.
- 화면은 provider 선택, 후보 목록, 수동 URL 입력, 워크스페이스 공유 읽기 전용 credential 입력을 같은 흐름에서 제공한다.
- planning trace absence를 오류 또는 미완성 상태로 표시하지 않는다.
- 개인 provider 권한만 있는 상태는 후보 조회 가능하지만 연결 생성 불가 상태로 표시한다.
- shared read-only credential 검증 실패는 provider별 재인증 또는 권한 수정 안내를 표시한다.
- 기존 legacy planning 연결은 목록/detail에서 `legacy planning trace`가 있는 연결로 이해 가능하게 표시한다.
- `legacy_unassigned` 연결은 숨기지 않고 운영자 compatibility action 안내를 보여준다.

### Slice 7. GitHub/GitLab Regression Guard

- GitHub Cloud create/detail/scope/snapshot/webhook regression을 기존 tests로 유지한다.
- GitLab Self-Managed create/detail/scope/snapshot/webhook regression을 기존 tests로 유지한다.
- mixed-provider workspace에서 list/detail/event/snapshot/history projection이 provider 및 canonical repository identity별로 분리되는지 검증한다.
- 기존 tests에서 planning reference fixture를 강제하는 helper를 workspace-first helper로 확장하고, legacy-path helper도 별도로 유지한다.
- provider semantics, webhook auth mode, event processing decision, snapshot trigger rules는 변경하지 않는다.

## Validation Strategy

- Unit
  - create command accepts no `planning_input_reference_id`
  - create command rejects obsolete planning reference fields
  - candidate discovery personal grant is not persisted as operation credential
  - shared read-only credential validation failure prevents active connection creation
  - detail serializer returns nullable planning trace and non-null origin
  - snapshot traceability builder works with and without legacy planning reference
  - canonical provider+repository identity dedupe handles candidate and manual URL paths
  - candidate listing returns empty state when provider account/instance is not configured
- Contract
  - `POST /api/repository-connections` rejects obsolete `planningInputReferenceId` and succeeds without it
  - `POST /api/repository-connections` returns an actionable permission problem when shared read-only credential is missing or invalid
  - `GET /api/repository-connections/{id}` returns `traceability.planningInputReference = null` for new connections
  - legacy GitHub/GitLab detail responses still expose planning reference
  - `GET /api/repository-candidates` returns scoped candidates and manual URL guidance
  - existing GitHub/GitLab webhook contracts unchanged
- Integration
  - workspace-first GitHub manual URL connection -> detail -> initial snapshot
  - workspace-first GitLab manual URL connection -> detail -> initial snapshot
  - candidate-selected connection and manual URL connection share duplicate prevention
  - personal provider grant can list candidates but cannot complete connection create without shared read-only credential
  - unauthorized/expired/revoked repository access does not create an active connection and returns remediation guidance
  - existing planning-based GitHub row remains visible and operational under its existing `workspace_id`
  - existing planning-based GitLab row remains visible and operational under its existing `workspace_id`
  - `legacy_unassigned` fixture is visible with compatibility state
- End-to-End
  - new workspace -> provider candidate/manual URL -> shared read-only credential -> connection active -> snapshot -> detail timeline with no planning trace
  - mixed workspace with legacy and new connections -> list/detail/snapshot/event/history flows remain separated by provider and origin
- Delivery evidence
  - story/FR/SC trace coverage must include workspace-first path, credential boundary path, legacy compatibility path, mixed-provider separation path, and GitHub/GitLab provider regression evidence.

## Post-Design Constitution Check

- [x] Planning input remains linked in this plan and spec artifacts even though runtime RepositoryConnection no longer stores planning trace for new rows.
- [x] Plan scope stays inside approved spec: workspace-first connection, optional legacy trace, candidate/manual selection, credential boundary, compatibility.
- [x] End-to-end traceability for the change itself remains via spec/plan/tasks/evidence; runtime planning trace removal applies only to RepositoryConnection domain rows.
- [x] Pilot implementation gate remains manual; `/speckit.implement` must not auto-run.
- [x] Validation evidence is defined for new workspace-first behavior, credential failure behavior, mixed-provider separation, and existing GitHub/GitLab regressions.

## Complexity Tracking

현재 헌법 위반은 없다. 다만 runtime 도메인의 `planningInputReference` 필수 FK 제거는 기존 데이터 모델 전제를 건드리므로 후속 tasks는 아래 순서를 지켜야 한다.

1. DB/model nullable provenance migration
2. API create contract removal and obsolete field rejection
3. shared read-only credential boundary and permission failure handling
4. detail/snapshot traceability optionalization
5. candidate/manual URL UX path
6. mixed-provider separation regression
7. GitHub/GitLab full regression

이 순서를 어기면 trace serializer나 snapshot builder가 null planning reference에서 먼저 실패하거나, 개인 provider 권한이 운영 credential로 잘못 승격될 위험이 크다.
