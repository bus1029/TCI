# Data Model: 코드 저장소 연동

## Overview

승인된 spec 범위를 유지하기 위해 데이터 모델은 `저장소 연결 1건 = 기본 ref 1개`를 전제로 한다. PR source branch는 영속 연결 설정이 아니라 이벤트성 분석 타깃으로 표현한다.

## Core Entities

### 0. PlanningInputReference

**Purpose**: 저장소 연결 기능이 어떤 계획 입력과 승인된 spec/plan에서 출발했는지 런타임에서 식별한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `workspace_id` | UUID | 워크스페이스 범위 |
| `source_type` | enum | `user_request`, `planning_brief`, `imported_note` |
| `source_title` | string | 운영자용 계획 입력 제목 |
| `source_reference` | string | 문서 경로, ticket, URL, 또는 식별자 |
| `approved_spec_path` | string | `spec.md` 경로 |
| `approved_plan_path` | string | `plan.md` 경로 |
| `created_at` | timestamptz | 생성 시각 |

**Validation Rules**:
- `approved_spec_path`와 `approved_plan_path`는 같은 feature 디렉터리를 가리켜야 한다.
- 런타임 traceability가 필요한 연결은 반드시 planning input reference를 가져야 한다.

### 1. RepositoryConnection

**Purpose**: 분석 대상으로 등록된 GitHub Cloud 저장소 연결의 기준 메타데이터와 운영 상태를 보관한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `workspace_id` | UUID | 워크스페이스 범위 |
| `planning_input_reference_id` | UUID | FK -> PlanningInputReference |
| `provider` | enum | `github_cloud` 고정 |
| `remote_url` | string | SSH 또는 HTTPS URL |
| `transport` | enum | `ssh`, `https` |
| `repository_owner` | string | URL 파싱 결과 |
| `repository_name` | string | URL 파싱 결과 |
| `default_ref_type` | enum | `branch`, `tag` |
| `default_ref_name` | string | 기본 분석 ref 이름 |
| `status` | enum | `pending_verification`, `active`, `reauth_required`, `ref_missing`, `webhook_unconfigured`, `disabled` |
| `mirror_path` | string | `.runtime/git-mirrors/{connectionId}.git` |
| `active_scope_rule_version_id` | UUID | 현재 적용 규칙 |
| `active_credential_revision_id` | UUID | 현재 연결 credential |
| `active_webhook_secret_revision_id` | UUID | 현재 webhook secret |
| `webhook_health_state` | enum | `healthy`, `missing_secret`, `secret_mismatch_detected`, `signature_invalid_recently` |
| `last_webhook_rejection_reason` | enum nullable | `secret_missing`, `secret_mismatch`, `signature_invalid` |
| `last_webhook_rejected_at` | timestamptz nullable | 최근 webhook 거부 시각 |
| `last_verified_at` | timestamptz | 최근 연결 검증 시각 |
| `last_successful_snapshot_at` | timestamptz | 최근 성공 스냅샷 시각 |
| `last_failed_sync_at` | timestamptz | 최근 실패 시각 |
| `last_processed_event_id` | UUID nullable | FK -> RepositoryEvent, connection detail 요약용 마지막 처리 이벤트 |
| `last_processed_event_at` | timestamptz | 최근 이벤트 반영 시각 |
| `created_at` | timestamptz | 생성 시각 |
| `updated_at` | timestamptz | 수정 시각 |

**Validation Rules**:
- `planning_input_reference_id`는 null일 수 없다.
- `provider`는 v1에서 `github_cloud`만 허용
- `remote_url`은 GitHub Cloud SSH/HTTPS 패턴만 허용
- `default_ref_type`은 `branch` 또는 `tag`만 허용
- 읽기 전용 credential 검증 통과 전 `active` 전환 금지
- `last_processed_event_id`가 존재하면 같은 `RepositoryConnection`에 속한 `RepositoryEvent`를 가리켜야 한다.
- `webhook_unconfigured`는 secret 누락 상태에만 사용하고, secret mismatch는 `status = active` + `webhook_health_state = secret_mismatch_detected`로 표현

**State Transitions**:

```text
pending_verification -> active
pending_verification -> reauth_required
active -> reauth_required
active -> ref_missing
active -> webhook_unconfigured
reauth_required -> active
ref_missing -> active
webhook_unconfigured -> active
active -> disabled
disabled -> pending_verification
```

### 2. RepositoryCredentialRevision

**Purpose**: 저장소 연결 단위의 읽기 전용 SSH/HTTPS 자격 증명을 revision 단위로 저장한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `credential_type` | enum | `ssh_private_key`, `https_pat` |
| `encrypted_secret` | bytes/text | KMS 또는 애플리케이션 암호화 대상 |
| `display_fingerprint` | string | 운영자 확인용 fingerprint |
| `read_only_validated` | boolean | 쓰기 권한 거부 검증 결과 |
| `status` | enum | `active`, `previous_grace`, `revoked` |
| `grace_until` | timestamptz nullable | 회전 grace 종료 시각 |
| `created_at` | timestamptz | 생성 시각 |

**Validation Rules**:
- credential 저장 전 반드시 read-only 검증 수행
- active revision은 연결당 1건만 허용

### 3. WebhookSecretRevision

**Purpose**: webhook 서명 검증용 secret 이력과 상태를 관리한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `encrypted_secret` | bytes/text | HMAC secret |
| `status` | enum | `active`, `previous_grace`, `revoked` |
| `grace_until` | timestamptz nullable | rotation grace 종료 |
| `created_at` | timestamptz | 생성 시각 |

**Validation Rules**:
- active secret는 연결당 1건만 허용
- 검증은 active와 grace 상태 secret만 사용

### 4. CollectionScopeRuleVersion

**Purpose**: 수집 범위 규칙의 버전 이력을 유지하고, 각 스냅샷이 어느 규칙을 사용했는지 추적한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `planning_input_reference_id` | UUID | FK -> PlanningInputReference |
| `include_paths` | jsonb | glob 배열 |
| `exclude_paths` | jsonb | glob 배열 |
| `allowed_file_types` | jsonb | 확장자/언어 식별자 배열 |
| `blocked_file_types` | jsonb | 확장자/언어 식별자 배열 |
| `max_file_size_bytes` | integer | 기본 5 MiB |
| `exclude_binary` | boolean | 기본 `true` |
| `warning_state` | enum | `ok`, `empty_result_risk`, `over_broad_include` |
| `created_at` | timestamptz | 생성 시각 |
| `created_by` | UUID | 사용자 ID 또는 시스템 |

**Validation Rules**:
- `planning_input_reference_id`는 connection의 planning input reference와 일치해야 한다.
- glob 구문은 저장 시 검증
- include/exclude 충돌 시 warning 계산
- 결과 0건 예상이면 `empty_result_risk`

### 5. RepositoryEvent

**Purpose**: GitHub webhook delivery와 내부 도메인 이벤트 해석 결과를 기록한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `provider_delivery_id` | string | `X-GitHub-Delivery`, unique |
| `provider_event_type` | enum | `push`, `pull_request`, `ping`, `unknown` |
| `provider_action` | string nullable | PR action 등 |
| `domain_event_type` | enum | `commit_recorded`, `push_received`, `pr_received`, `signature_rejected`, `secret_missing`, `secret_mismatch` |
| `target_kind` | enum | `default_ref`, `pull_request_source`, `none` |
| `target_key` | string | `default_ref` 또는 `pr:{number}` |
| `target_ref_name` | string nullable | branch/tag/source branch |
| `target_head_sha` | string nullable | 최신 HEAD SHA |
| `occurred_at` | timestamptz | payload 기준 시각 |
| `received_at` | timestamptz | 수신 시각 |
| `signature_status` | enum | `verified`, `secret_missing`, `secret_mismatch`, `signature_invalid` |
| `verified_secret_revision_status` | enum nullable | `active`, `previous_grace` |
| `rejection_reason` | enum nullable | `secret_missing`, `secret_mismatch`, `signature_invalid` |
| `processing_decision` | enum | `record_only`, `queued`, `duplicate_delivery`, `duplicate_head`, `stale_head`, `rejected` |
| `processing_status` | enum | `received`, `validated`, `queued`, `completed`, `failed`, `rejected` |
| `payload_hash` | string | raw body sha256 |
| `sync_run_id` | UUID nullable | FK -> RepositorySyncRun |
| `snapshot_id` | UUID nullable | FK -> CodeSnapshot |

**Validation Rules**:
- `provider_delivery_id` unique
- `target_head_sha`는 queued/completed 상태에서 필수
- `signature_status = verified`이고 grace 대상 secret이 사용된 경우 `verified_secret_revision_status`는 필수
- `signature_status != verified`이면 `processing_status = rejected`
- `processing_status = rejected`이면 `rejection_reason` 필수

### 6. RepositoryEventCursor

**Purpose**: 기본 ref 또는 PR source branch 단위의 최신 accepted HEAD SHA를 저장해 stale event를 거른다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `target_key` | string | `default_ref` 또는 `pr:{number}` |
| `latest_head_sha` | string | 최신 accepted SHA |
| `latest_event_id` | UUID | FK -> RepositoryEvent |
| `updated_at` | timestamptz | 갱신 시각 |

**Validation Rules**:
- `(connection_id, target_key)` unique

### 7. RepositorySyncRun

**Purpose**: 수동 초기 수집 또는 이벤트 기반 최신화 시도의 실행 단위를 표현한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `trigger_type` | enum | `manual_initial`, `manual_refresh`, `webhook_push`, `webhook_pull_request` |
| `trigger_event_id` | UUID nullable | FK -> RepositoryEvent |
| `requested_ref_type` | enum | `branch`, `tag`, `pull_request_branch` |
| `requested_ref_name` | string | 기본 ref 또는 PR source branch |
| `resolved_commit_sha` | string nullable | ref 해석 결과 |
| `status` | enum | `pending`, `running`, `succeeded`, `failed`, `blocked` |
| `failure_code` | enum nullable | `AUTH_FAILED`, `REF_NOT_FOUND`, `NO_INCLUDED_FILES`, `MIRROR_SYNC_FAILED`, `SNAPSHOT_WRITE_FAILED` |
| `failure_message` | text nullable | 운영 표시용 메시지 |
| `started_at` | timestamptz | 시작 시각 |
| `completed_at` | timestamptz nullable | 종료 시각 |

**State Transitions**:

```text
pending -> running
running -> succeeded
running -> failed
running -> blocked
blocked -> pending
```

### 8. CodeSnapshot

**Purpose**: 특정 수집 성공 시점의 완전한 코드 스냅샷을 나타낸다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `sync_run_id` | UUID | FK -> RepositorySyncRun |
| `scope_rule_version_id` | UUID | FK -> CollectionScopeRuleVersion |
| `requested_ref_type` | enum | `branch`, `tag`, `pull_request_branch` |
| `requested_ref_name` | string | 요청 기준 ref |
| `resolved_commit_sha` | string | 실제 고정 SHA |
| `tree_sha` | string | Git tree SHA |
| `archive_path` | string | `.runtime/code-snapshots/{snapshotId}` |
| `file_count` | integer | 포함 파일 수 |
| `total_bytes` | bigint | 포함 파일 총 크기 |
| `created_at` | timestamptz | 생성 시각 |

**Validation Rules**:
- `resolved_commit_sha`와 `archive_path`는 성공 스냅샷에서 필수
- 한 sync run은 성공 시 최대 1 snapshot만 생성

### 9. CodeSnapshotFile

**Purpose**: 스냅샷에 포함된 각 파일의 manifest와 무결성 정보를 저장한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `snapshot_id` | UUID | FK -> CodeSnapshot |
| `path` | string | 저장소 상대 경로 |
| `extension` | string nullable | 확장자 |
| `language_hint` | string nullable | 추론 언어 |
| `size_bytes` | integer | 파일 크기 |
| `content_sha256` | string | 본문 해시 |
| `archive_blob_path` | string | snapshot archive 내부 경로 |
| `included_by` | enum | `default_policy`, `user_include`, `pr_source_snapshot` |

**Validation Rules**:
- `(snapshot_id, path)` unique
- `archive_blob_path`는 snapshot archive 하위 경로여야 함

## Relationships

```text
PlanningInputReference 1 --- n RepositoryConnection
PlanningInputReference 1 --- n CollectionScopeRuleVersion
RepositoryConnection 1 --- n RepositoryCredentialRevision
RepositoryConnection 1 --- n WebhookSecretRevision
RepositoryConnection 1 --- n CollectionScopeRuleVersion
RepositoryConnection 1 --- n RepositoryEvent
RepositoryConnection 1 --- n RepositoryEventCursor
RepositoryConnection 1 --- n RepositorySyncRun
RepositoryConnection 1 --- n CodeSnapshot

RepositoryEvent 0..1 --- 1 RepositorySyncRun
RepositorySyncRun 0..1 --- 1 CodeSnapshot
CodeSnapshot 1 --- n CodeSnapshotFile
CollectionScopeRuleVersion 1 --- n CodeSnapshot
```

## Derived Views

### Connection Health View

운영 화면은 아래 파생 필드를 사용한다.

- `last_successful_snapshot_at`
- `last_failed_sync_at`
- `last_processed_event_id`
- `last_processed_event_at`
- `last_processed_event_summary` (`id`, `provider_event_type`, `provider_action`, `target_key`, `processing_decision`, `processed_at`)
- `current_status`
- `webhook_health_state`
- `last_webhook_rejection_reason`
- `webhook_secret_rotation_state`
- `webhook_secret_grace_until`
- `previous_secret_deliveries_during_grace`
- `active_scope_rule_warning_state`
- `latest_event_decision`

### Event Timeline View

상세 이벤트 이력 조회는 아래 필드를 중심으로 제공한다.

- `RepositoryEvent.id`
- `provider_event_type`
- `provider_action`
- `target_key`
- `target_head_sha`
- `signature_status`
- `verified_secret_revision_status`
- `rejection_reason`
- `processing_decision`
- `processing_status`
- `sync_run_id`
- `snapshot_id`
- `received_at`
- `processed_at`

### Traceability View

`FR-014` 충족을 위해 다음 연결 경로를 유지한다.

```text
planning input reference -> repository connection -> scope rule version
repository connection + trigger event -> sync run
scope rule version + sync run + trigger event -> code snapshot
code snapshot -> snapshot manifest (CodeSnapshotFile)
```

## Notes

- 멀티 ref 영속 설정은 이번 범위에 포함하지 않는다.
- PR source branch snapshot은 `requested_ref_type = pull_request_branch`로만 나타내고, 연결의 기본 ref 설정은 바꾸지 않는다.
- v1에서는 snapshot retention 정책보다 완전 보존과 추적성을 우선한다.
- secret mismatch는 연결 전체를 `webhook_unconfigured`로 바꾸지 않고, 운영자가 secret 재설정을 판단할 수 있는 degraded health 신호로만 노출한다.
