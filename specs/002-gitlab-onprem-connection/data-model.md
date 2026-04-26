# Data Model: 온프레미스 GitLab 코드 저장소 연동

## Overview

이 설계는 기존 `pilot-git-repo-connection` 데이터 모델을 유지하면서 `github_cloud`와 `gitlab_self_managed`를 같은 canonical contract 아래에서 다룬다. 핵심 원칙은 다음과 같다.

- 저장소 연결 1건은 기본 분석 ref 1개만 가진다.
- Push/Merge Request만 snapshot trigger가 된다.
- Commit은 기록 전용 domain event다.
- canonical connection 상태는 `active`, `reauth_required`, `ref_missing`만 사용한다.
- provider별 webhook 보안/헤더 차이는 health 및 event metadata로 분리한다.

## Current Implementation Alignment

- 현재 구현된 항목:
  - `RepositoryConnection.provider`
  - `provider_instance_url`
  - `provider_project_path`
  - `provider_event_idempotency_source`
  - `webhook_merge_request` trigger support
  - health projection persistence fields
  - GitLab allowlist-before-credential-decrypt ordering
  - create/verify/default-ref/scope-preview/snapshot build 공통 allowlist 정책
  - SSH custom-port allowlist positive/negative control
  - snapshot allowlist rejection의 `MIRROR_SYNC_FAILED` 분류
  - live PostgreSQL check constraint name과 SQLAlchemy metadata naming 일치 검증
  - operator detail/read-model/UI의 GitLab instance/project/traceability 표시
  - webhook health 렌더링 상태에서 `shared_token` / `webhookAuthMode` 비노출 검증
- 아직 pending인 항목은 US2 scope/ref 관리와 GitLab webhook event normalization/수신/처리다.
- 따라서 이 문서는 “구현된 US1 baseline + 남은 목표 모델”로 해석한다.

## Core Entities

### 1. PlanningInputReference

기존과 동일. GitHub/GitLab 모두 같은 planning input provenance 체인을 사용한다.

### 2. RepositoryConnection

**Purpose**: GitHub Cloud 또는 GitLab Self-Managed 저장소 연결의 공통 메타데이터와 canonical 상태를 관리한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `workspace_id` | UUID | 워크스페이스 범위 |
| `planning_input_reference_id` | UUID | FK -> PlanningInputReference |
| `provider` | enum | `github_cloud`, `gitlab_self_managed` |
| `provider_instance_url` | string nullable | GitLab self-managed base URL metadata derived from `remote_url`. GitHub는 `null` |
| `remote_url` | string | SSH 또는 HTTPS remote |
| `transport` | enum | `ssh`, `https` |
| `repository_namespace` | string | `owner` 또는 `group/subgroup` |
| `repository_name` | string | project/repo name |
| `provider_project_path` | string | `namespace/name` canonical path |
| `default_ref_type` | enum | `branch`, `tag` |
| `default_ref_name` | string | 기본 분석 ref |
| `status` | enum | `active`, `reauth_required`, `ref_missing` |
| `mirror_path` | string | `.runtime/git-mirrors/{connectionId}.git` |
| `active_scope_rule_version_id` | UUID | 현재 scope rule |
| `active_credential_revision_id` | UUID | 현재 credential revision |
| `active_webhook_secret_revision_id` | UUID nullable | 현재 webhook secret revision |
| `webhook_auth_mode` | enum | `hmac_sha256`, `shared_token` |
| `webhook_health_state` | enum | provider-neutral health state |
| `last_webhook_rejection_reason` | enum nullable | 최근 webhook 거부 사유 |
| `last_webhook_rejected_at` | timestamptz nullable | 최근 webhook 거부 시각 |
| `last_verified_at` | timestamptz nullable | 최근 verify 완료 시각 |
| `last_successful_snapshot_at` | timestamptz nullable | 최근 성공 snapshot |
| `last_failed_sync_at` | timestamptz nullable | 최근 sync 실패 |
| `last_processed_event_id` | UUID nullable | 마지막 처리 event |
| `last_processed_event_at` | timestamptz nullable | 마지막 처리 시각 |
| `created_at` | timestamptz | 생성 시각 |
| `updated_at` | timestamptz | 수정 시각 |

**Validation Rules**:

- `provider = github_cloud`면 `provider_instance_url`은 `null`, `webhook_auth_mode = hmac_sha256`
- `provider = gitlab_self_managed`면 `provider_instance_url`이 저장되더라도 `remote_url`에서 파생된 값이어야 하며 별도 사용자 입력 필드는 아니다. `webhook_auth_mode = shared_token`
- GitLab self-managed의 `provider_instance_url`은 `https://host` 또는 비표준 HTTPS 포트가 포함된 `https://host:port` 형식이다.
- SSH custom port는 `provider_instance_url`에 저장하지 않고, outbound 검증 시 저장된 `remote_url`에서 다시 파싱한다.
- GitLab self-managed의 `provider_project_path`는 `/gitlab` 같은 path prefix도 namespace로 포함한다. instance subpath는 추정하지 않는다.
- `status`는 `active`, `reauth_required`, `ref_missing`만 허용
- `provider_project_path`는 `repository_namespace + "/" + repository_name`과 일치해야 한다
- canonical status는 webhook mismatch나 서버 일시 장애로 변경되지 않는다

### 3. RepositoryCredentialRevision

**Purpose**: 저장소 연결 단위의 읽기 전용 credential revision을 관리한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `credential_type` | enum | `ssh_private_key`, `https_access_token` |
| `encrypted_secret` | bytes/text | 암호화 저장 |
| `display_fingerprint` | string | 운영자 표시용 |
| `read_only_validated` | boolean | 읽기 전용 검증 결과 |
| `provider_scope_summary` | string nullable | 예: `read_repository` |
| `status` | enum | `active`, `previous_grace`, `revoked` |
| `created_at` | timestamptz | 생성 시각 |

**Validation Rules**:

- GitLab HTTPS credential은 `read_repository` scope가 확인돼야 한다
- SSH credential은 쓰기 시도가 차단되는 검증을 통과해야 한다
- active revision은 연결당 1건만 허용

### 4. WebhookSecretRevision

**Purpose**: provider별 webhook secret/token 이력을 revision으로 관리한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `encrypted_secret` | bytes/text | GitHub HMAC secret 또는 GitLab token |
| `status` | enum | `active`, `revoked` |
| `created_at` | timestamptz | 생성 시각 |

**Validation Rules**:

- active revision은 연결당 1건만 허용
- webhook 검증은 활성 revision 1건만 대상으로 사용한다

### 5. CollectionScopeRuleVersion

기존과 동일하되 GitLab에서도 같은 의미를 유지한다.

**Additional Rules**:

- 기본 정책은 텍스트 기반 소스 파일만 수집
- 바이너리, 생성 산출물, `5 MiB` 초과 파일은 provider와 무관하게 기본 제외
- `empty_result_risk` 계산 로직은 provider와 무관해야 한다

### 6. RepositoryEvent

**Purpose**: provider delivery와 내부 domain event 해석 결과를 기록한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `provider_delivery_id` | string | GitHub delivery ID 또는 GitLab idempotency key |
| `provider_event_type` | enum | `push`, `pull_request`, `merge_request`, `ping`, `unknown` |
| `provider_action` | string nullable | action/status |
| `provider_event_idempotency_source` | enum | `delivery_header`, `uuid_header`, `derived_hash` |
| `domain_event_type` | enum | `commit_recorded`, `push_received`, `pr_received`, `mr_received`, `signature_rejected`, `secret_missing`, `secret_mismatch` |
| `target_kind` | enum | `default_ref`, `pull_request_source`, `merge_request_source`, `none` |
| `target_key` | string | `default_ref`, `pr:{number}`, `mr:{iid}` |
| `target_ref_name` | string nullable | branch/tag/source branch |
| `target_head_sha` | string nullable | 최신 HEAD SHA |
| `occurred_at` | timestamptz | payload 기준 시각 |
| `received_at` | timestamptz | 수신 시각 |
| `signature_status` | enum | `verified`, `secret_missing`, `secret_mismatch`, `signature_invalid` |
| `verified_secret_revision_status` | enum nullable | `active` |
| `rejection_reason` | enum nullable | 거부 사유 |
| `processing_decision` | enum | `record_only`, `queued`, `duplicate_delivery`, `duplicate_head`, `stale_head`, `rejected` |
| `processing_status` | enum | `received`, `validated`, `queued`, `completed`, `failed`, `rejected` |
| `payload_hash` | string | raw body hash |
| `sync_run_id` | UUID nullable | FK -> RepositorySyncRun |
| `snapshot_id` | UUID nullable | FK -> CodeSnapshot |

**Validation Rules**:

- `(connection_id, provider_delivery_id)` unique
- GitHub `push`/`pull_request`, GitLab `push`/`merge_request`를 공통 domain event로 정규화해야 한다
- GitLab `update` action은 code-moving update가 아니면 `processing_decision = record_only`

### 7. RepositoryEventCursor

**Purpose**: target별 최신 accepted HEAD SHA를 유지한다.

**Additional Rules**:

- `target_key = mr:{iid}`는 GitLab Merge Request source branch cursor를 뜻한다
- `target_key = pr:{number}`는 GitHub PR cursor를 뜻한다
- provider가 달라도 stale 판단 규칙은 동일하다

### 8. RepositorySyncRun

**Purpose**: 수동/이벤트 기반 snapshot 시도를 표현한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> RepositoryConnection |
| `trigger_type` | enum | `manual_initial`, `manual_refresh`, `webhook_push`, `webhook_pull_request`, `webhook_merge_request` |
| `trigger_event_id` | UUID nullable | FK -> RepositoryEvent |
| `requested_ref_type` | enum | `branch`, `tag`, `pull_request_branch` |
| `requested_ref_name` | string | ref/source branch |
| `resolved_commit_sha` | string nullable | ref 해석 결과 |
| `status` | enum | `pending`, `running`, `succeeded`, `failed`, `blocked` |
| `failure_code` | enum nullable | `AUTH_FAILED`, `REF_NOT_FOUND`, `NO_INCLUDED_FILES`, `MIRROR_SYNC_FAILED`, `SNAPSHOT_WRITE_FAILED`, `QUEUE_DISPATCH_FAILED` |
| `failure_message` | text nullable | 운영자 메시지 |
| `started_at` | timestamptz | 시작 시각 |
| `completed_at` | timestamptz nullable | 종료 시각 |

**State Rules**:

- GitLab 서버 unreachable은 `MIRROR_SYNC_FAILED` 또는 `AUTH_FAILED`로 구분한다
- `reauth_required`는 auth failure 때만 canonical 상태를 갱신한다

### 9. CodeSnapshot

기존과 동일하되 provider-neutral provenance를 유지한다.

**Additional Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `provider_event_family` | enum | `manual`, `push`, `pull_request`, `merge_request` |

**Validation Rules**:

- `trigger_event_id`가 GitLab Merge Request라면 `requested_ref_name`은 source branch여야 한다
- snapshot manifest는 provider와 무관하게 동일 schema를 사용한다

### 10. ConnectionHealthSummary

**Purpose**: canonical status와 분리된 운영 health projection을 제공한다.

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `connection_id` | UUID | 1:1 with RepositoryConnection |
| `webhook_status` | enum | `healthy`, `missing_secret`, `secret_mismatch_detected`, `signature_invalid_recently` |
| `provider_reachability_status` | enum | `reachable`, `unreachable_recently`, `tls_failed_recently`, `dns_failed_recently` |
| `last_rejection_reason` | enum nullable | 최근 webhook 거부 |
| `last_reachability_failure_code` | enum nullable | 최근 연결 실패 유형 |
| `last_processed_event_id` | UUID nullable | 마지막 이벤트 |
| `last_successful_snapshot_at` | timestamptz nullable | 최근 성공 snapshot |
| `last_failed_sync_at` | timestamptz nullable | 최근 실패 sync |

**Validation Rules**:

- canonical status와 독립적으로 계산한다
- GitLab 서버 unreachable은 여기서만 드러나고 `RepositoryConnection.status`는 유지한다

## State Transitions

### RepositoryConnection.status

```text
active -> reauth_required
active -> ref_missing
reauth_required -> active
ref_missing -> active
```

### Webhook / Reachability Handling

```text
active + reachable -> active + unreachable_recently
active + unreachable_recently -> active + reachable
active + healthy -> active + secret_mismatch_detected
active + secret_mismatch_detected -> active + healthy
```

## Compatibility Notes

- 기존 GitHub rows는 migration 후에도 유효해야 하므로 `provider_instance_url`은 nullable add-column 또는 derived persistence field로 도입한다.
- 기존 GitHub webhook events는 `provider_event_type = pull_request`를 계속 유지하고, GitLab은 `merge_request`를 새 값으로 추가한다.
- `provider_project_path` DB column은 rollout-safe하게 nullable로 유지하되, GitLab row는 provider-scoped check로 non-null을 요구한다.
- GitLab remote URL은 GitHub host, trailing-dot host, IPv6, userinfo, query/fragment, whitespace/control chars, dot path segment, malformed port를 거부한다.
- 기존 API summary fields(`lastProcessedEvent`, `lastSuccessfulSnapshotAt`, `lastFailedSyncAt`)는 shape 변경 없이 provider 값과 health 정보만 확장한다.
