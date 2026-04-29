# Data Model: 워크스페이스 기반 저장소 연결 시작점 전환

## Overview

이 설계는 기존 GitHub Cloud/GitLab Self-Managed 저장소 연결 모델을 유지하되, 새 연결 생성의 시작점을 planning reference에서 workspace repository로 옮긴다.

핵심 원칙:

- 새 `RepositoryConnection`은 `planning_input_reference_id = null`이 정상이다.
- 기존 planning 기반 연결은 planning reference를 legacy provenance로 보존한다.
- `workspace_id`가 connection의 canonical workspace 귀속이다.
- provider별 webhook/snapshot/event semantics는 기존 GitHub/GitLab 기준선을 유지한다.

## Core Entities

### 1. Workspace

**Purpose**: Repository 연결을 생성하고 운영하는 최상위 사용자 작업 공간.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | canonical workspace identifier |
| `repository_connection_count` | derived integer | 목록/운영 UI 표시용 |
| `configured_provider_accounts` | derived array | 후보 목록을 제공할 수 있는 GitHub 계정 또는 GitLab 인스턴스 범위 |

**Validation Rules**:

- 모든 connection create/list/detail/snapshot/event API는 workspace scope를 먼저 확정해야 한다.
- workspace scope는 planning reference에서 파생하지 않는다.

### 2. PlanningInputReference

**Purpose**: 기존 GitHub/GitLab 연결에 남아 있는 legacy provenance.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `workspace_id` | UUID | 기존 reference가 속한 workspace |
| `source_type` | enum | 기존 값 유지 |
| `source_title` | string | 기존 값 유지 |
| `source_reference` | string | 기존 값 유지 |
| `approved_spec_path` | string | 기존 값 유지 |
| `approved_plan_path` | string | 기존 값 유지 |
| `created_at` | timestamptz | 기존 값 유지 |

**Validation Rules**:

- 신규 Repository-first connection 생성 시 새 `PlanningInputReference`를 생성하지 않는다.
- 기존 rows는 삭제하지 않는다.
- legacy connection에서만 optional provenance로 조인된다.

### 3. RepositoryConnection

**Purpose**: 워크스페이스에 등록된 GitHub Cloud 또는 GitLab Self-Managed 저장소 연결.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `workspace_id` | UUID | canonical workspace scope |
| `planning_input_reference_id` | UUID nullable | legacy FK -> PlanningInputReference. 신규 연결은 null |
| `origin_kind` | enum or derived field | `workspace_repository`, `legacy_planning`, `legacy_unassigned` |
| `provider` | enum | `github_cloud`, `gitlab_self_managed` |
| `remote_url` | string | SSH/HTTPS/HTTP support follows existing provider rules |
| `transport` | enum | existing values |
| `repository_owner` | string | canonical owner/namespace component |
| `repository_name` | string | canonical repo/project name |
| `provider_instance_url` | string nullable | GitLab metadata derived from remote URL |
| `provider_project_path` | string nullable | canonical provider path |
| `canonical_repository_key` | derived string | `provider + normalized host/path` for duplicate prevention |
| `default_ref_type` | enum | `branch`, `tag` |
| `default_ref_name` | string | default analysis ref |
| `status` | enum | `active`, `reauth_required`, `ref_missing` |
| `active_scope_rule_version_id` | UUID nullable | current scope rule |
| `active_credential_revision_id` | UUID nullable | workspace shared read-only credential |
| `active_webhook_secret_revision_id` | UUID nullable | provider webhook secret/token |
| `last_verified_at` | timestamptz nullable | existing meaning |
| `last_successful_snapshot_at` | timestamptz nullable | existing meaning |
| `last_failed_sync_at` | timestamptz nullable | existing meaning |
| `last_processed_event_id` | UUID nullable | existing meaning |
| `created_at` | timestamptz | created time |
| `updated_at` | timestamptz | updated time |

**Validation Rules**:

- New workspace-based connections MUST store `planning_input_reference_id = null`.
- Existing rows with non-null `planning_input_reference_id` remain valid.
- `(workspace_id, provider, canonical_repository_key)` must be unique for active/non-deleted connections.
- Candidate-selected and manual URL create paths must compute the same `canonical_repository_key`.
- `origin_kind = legacy_unassigned` is only for rows where workspace provenance cannot be trusted; these rows stay visible.

**State Transitions**:

Canonical status remains unchanged:

```text
active -> reauth_required
active -> ref_missing
reauth_required -> active
ref_missing -> active
```

`origin_kind` is not a connection health state:

```text
workspace_repository
legacy_planning
legacy_unassigned -> legacy_planning or workspace_repository after operator repair
```

### 4. RepositoryCandidate

**Purpose**: 워크스페이스에서 연결할 수 있는 저장소 후보 projection. Persisted entity가 아니다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `provider` | enum | `github_cloud`, `gitlab_self_managed` |
| `provider_scope` | string | configured provider account or GitLab instance scope |
| `remote_url` | string nullable | candidate-derived URL if available |
| `repository_owner` | string | owner/group namespace |
| `repository_name` | string | repo/project name |
| `provider_project_path` | string | canonical path |
| `canonical_repository_key` | string | duplicate prevention key |
| `already_connected` | boolean | true if same workspace/provider/repo already connected |
| `existing_connection_id` | UUID nullable | current connection when already connected |
| `selectable` | boolean | false if already connected or access unavailable |
| `access_status` | enum | `available`, `not_authorized`, `provider_not_configured`, `unknown` |
| `input_path` | enum | `candidate_list`, `manual_url` |

**Validation Rules**:

- Candidate list is empty when provider account/instance scope is not configured.
- Empty candidate list is not an error if manual URL input is available.
- Candidate discovery credentials must not be stored as repository operation credentials.

### 5. RepositoryCredentialRevision

**Purpose**: 워크스페이스 공유 읽기 전용 repository operation credential.

**Rules Added By This Feature**:

- Candidate discovery personal grants are not persisted here.
- A connection cannot become `active` from candidate selection alone; shared read-only credential validation is still required.
- Existing GitHub/GitLab credential validation rules remain unchanged.

### 6. CollectionScopeRuleVersion

**Purpose**: 수집 범위 규칙 버전.

**Changes**:

- `planning_input_reference_id` becomes nullable if present in the implementation.
- Scope rule traceability is derived from `connection_id`; planning reference is optional legacy enrichment.
- Existing scope rule rows keep legacy planning reference values.

### 7. RepositoryEvent

**Purpose**: provider webhook/domain event record.

**Changes**:

- No provider event schema changes are required.
- Event traceability links to `connection_id`; planning reference is resolved optionally through the connection.
- GitHub/GitLab event semantics and dedupe rules remain unchanged.

### 8. RepositorySyncRun

**Purpose**: snapshot job execution record.

**Changes**:

- No trigger-type changes are required.
- Sync run traceability links to `connection_id`; planning reference is optional.
- Manual initial and manual refresh runs must work when connection has no planning reference.

### 9. CodeSnapshot

**Purpose**: successful collected code snapshot.

**Changes**:

- Snapshot detail traceability must allow `planningInputReference = null`.
- Snapshot lineage remains reconstructable through `connectionId`, `scopeRuleVersionId`, `syncRunId`, and `triggerEventId`.

### 10. ConnectionOrigin

**Purpose**: Read-model object that tells users why a connection appears in a workspace list/detail.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `kind` | enum | `workspace_repository`, `legacy_planning`, `legacy_unassigned` |
| `has_legacy_planning_trace` | boolean | true if planning reference exists |
| `compatibility_state` | enum | `normal`, `legacy_trace_preserved`, `workspace_assignment_unclear` |
| `message` | string | operator-facing explanation |

**Validation Rules**:

- New connections return `kind = workspace_repository`.
- Existing connections with valid planning reference return `kind = legacy_planning`.
- Unclear legacy workspace assignment returns `kind = legacy_unassigned` and remains visible.

## Migration Rules

- Make `repository_connections.planning_input_reference_id` nullable.
- Preserve all non-null existing values.
- Preserve `planning_input_references` rows.
- Rework composite FK/unique constraints that require non-null planning reference.
- Add nullable-safe uniqueness for workspace/provider/canonical repository identity.
- Ensure rollback does not silently discard legacy references; rollback should fail or require explicit remediation if null planning references exist.
