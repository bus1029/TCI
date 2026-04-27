# Feature Specification: 온프레미스 GitLab 코드 저장소 연동

**Feature Branch**: `[002-gitlab-onprem-connection]`  
**Created**: 2026-04-23  
**Status**: In Progress
**Input**: User description: "TCI의 데이터 수집 영역에서 Git 기반 형상 관리 시스템과 연동하여 코드베이스와 변경 이력을 수집하고 분석 가능한 코드 스냅샷을 생성한다. 기존 GitHub Cloud 연동 기능에 추가로 On-premise GitLab 연동 기능을 추가로 개발해야 하며, 기존 GitHub Cloud 연동 기능 관련 코드와의 호환성을 고려해야 한다. Git 기반 레포지토리 연결(SSH/HTTPS), 분석 대상 브랜치/태그 선택, 제외/포함 경로 및 파일 타입 설정, 코드 변경 이벤트 감지(Commit, Push, MR), Webhook 기반 실시간 이벤트 수신."

## Implementation Status

- Phase 2 foundation, US1 연결/초기 snapshot/operator detail, US2 scope/ref 관리, US3 webhook 최신화 경로가 구현됐다.
- 구현된 범위:
  - GitLab self-managed remote 파싱과 provider metadata 저장
  - host allowlist 기반 fail-closed 검증
  - create/verify/default-ref/scope-preview/snapshot build 경로의 공통 allowlist 적용
  - 기본 ref 변경의 allowlist-before-decrypt 순서
  - SSH custom-port allowlist control
  - snapshot allowlist rejection의 `MIRROR_SYNC_FAILED` 분류
  - GitHub/GitLab coexistence 회귀 검증
  - 실제 PostgreSQL migration smoke, 실DB bootstrap, live constraint name regression
  - GitLab operator detail의 instance URL, project path, active scope traceability 표시
  - webhook health 렌더링 상태에서 `shared_token` / `webhookAuthMode` 비노출 회귀 검증
  - GitLab scope rule 저장/detail projection, `excludeBinary`, `preview_failed`, auto-default scope provenance
  - GitLab scoped snapshot의 active scope version stamping, default-ref carry-forward, prior history preservation
  - empty-result snapshot의 `NO_INCLUDED_FILES` 실패 처리와 connection status 보존
  - HTTPS PAT URL embedding 제거, askpass token handshake, isolated SSH agent, ambient Git config/agent 상속 차단
  - scope filtering 전 raw Git tree entry cap과 blob read 전 prefiltering
  - GitLab push/MR webhook token 검증, delivery-id extraction, event normalization, queued/record-only/dedupe/stale handling
  - GitHub/GitLab public webhook response uniform `202 accepted` hardening
  - same-ref active sync uniqueness, blocked follow-up handoff, `dispatch_enqueued_at` 기반 replay/crash recovery
  - operator token guard와 signed HttpOnly operator session cookie
- 아직 pending인 범위:
  - Phase 6 quickstart/latency harness와 final evidence refresh
- 최종 reviewer loop는 `python-reviewer`, `security-reviewer`, `database-reviewer`, `pr-test-analyzer` 기준 clean으로 완료됐다. 일반 `reviewer`는 사용자 결정에 따라 제외한다.
- 상세 증적은 `specs/002-gitlab-onprem-connection/delivery-evidence.md`를 기준으로 한다.

## Design Input Traceability *(mandatory)*

- **Planning Source**: 2026-04-23 사용자 요청 "TCI 데이터 수집 영역의 온프레미스 GitLab 코드 저장소 연동", 기존 기준선 [specs/001-git-repo-connection/spec.md](../001-git-repo-connection/spec.md)
- **Why now**: GitHub Cloud만으로는 온프레미스 환경 고객의 코드 수집 수요를 충족할 수 없으므로, 기존 운영 모델을 유지한 채 GitLab 배포 환경까지 수집 범위를 확장해야 한다.
- **Scope baseline**: 온프레미스 GitLab 저장소 연결, SSH/HTTPS 접근, 분석 대상 브랜치 또는 태그 선택, 포함/제외 경로 및 파일 타입 규칙, Commit/Push/Merge Request 이벤트 감지, webhook 기반 실시간 이벤트 수신, 분석 가능한 코드 스냅샷 생성, 기존 GitHub Cloud 흐름과의 호환성 유지
- **Out of scope**: Git 이외 형상 관리 시스템 지원, 저장소 쓰기 작업, CI/CD 파이프라인 실행, 코드 품질 평가 로직 자체, GitHub Cloud 기능 재설계, 다른 GitLab 배포 형태에 대한 신규 범위 확장, 저장소 주소와 별도로 GitLab 인스턴스 URL 입력 필드 추가, webhook secret 이중 허용 또는 회전 유예 기간 운영

## Closed Clarifications

- Q: GitLab 연결 자격 증명은 어떤 운영 모델로 관리할 것인가? → A: GitHub Cloud와 동일하게 저장소 연결 단위 공유 자격 증명을 사용하고, 읽기 전용 권한만 허용한다.
- Q: GitLab 연결의 기본 수집 제외 정책은 무엇으로 둘 것인가? → A: GitHub Cloud와 동일하게 텍스트 기반 소스 파일만 기본 수집하고, 바이너리·생성 산출물·5 MiB 초과 파일은 기본 제외한다.
- Q: Commit 이벤트는 어떤 방식으로 처리할 것인가? → A: GitHub Cloud와 동일하게 Push/Merge Request payload에서 추출한 기록 전용 이벤트로 저장하고, 독립적인 스냅샷 트리거로는 사용하지 않는다.
- Q: 어떤 Merge Request action만 스냅샷 최신화 트리거로 인정할 것인가? → A: `opened`, `reopened`, `updated/pushed` 계열만 스냅샷 최신화 후보로 인정하고, 그 외 action은 이력만 기록한다.
- Q: 공식 연결 상태 모델은 어떻게 둘 것인가? → A: GitHub Cloud와 동일하게 공식 연결 상태는 `active`, `reauth_required`, `ref_missing`만 사용하고, webhook 이상은 별도 health로 분리한다.
- Q: GitLab 연결 식별을 위해 저장소 주소 외 별도 인스턴스 URL 입력 필드를 추가할 것인가? → A: 아니다. 이번 범위에서는 저장소 주소와 기존 연결 메타데이터만 사용하고, 별도 사용자 입력 필드는 추가하지 않는다.
- Q: webhook secret 회전 유예 기간이나 이전 secret 동시 허용을 이번 범위에 포함할 것인가? → A: 아니다. 이번 범위는 단일 활성 secret 검증과 health 신호 제공까지만 포함한다.
- Q: GitLab instance subpath를 `remoteUrl`에서 추정할 것인가? → A: 아니다. `https://gitlab.example.com/gitlab/group/repo.git`의 `/gitlab`도 project namespace 일부로 취급한다.
- Q: 사용자가 별도 GitLab instance URL을 입력하게 할 것인가? → A: 아니다. `provider_instance_url`은 `remoteUrl`에서 파생된 저장 메타데이터이며 API 입력 필드가 아니다.
- Q: localhost, private IPv4, 비표준 SSH/HTTPS 포트를 지원할 것인가? → A: 지원한다. 단, outbound git 접근 전 `TCI_GITLAB_SELF_MANAGED_ALLOWED_HOSTS`에 exact origin이 등록되어 있어야 한다.
- Q: 어떤 GitLab remote URL을 거부할 것인가? → A: GitHub host, trailing-dot host, IPv6, userinfo, query/fragment, whitespace/control chars, dot path segment, malformed port는 거부한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 온프레미스 GitLab 저장소 연결과 초기 스냅샷 생성 (Priority: P1)

수집 담당자는 온프레미스 GitLab 저장소를 SSH 또는 HTTPS로 연결하고, 분석 대상 브랜치 또는 태그를 선택한 뒤 첫 코드 스냅샷을 생성할 수 있어야 한다.

**Why this priority**: 저장소 연결과 초기 스냅샷이 성립해야 이후 이벤트 수집과 분석 파이프라인이 모두 시작될 수 있다.

**Independent Test**: 유효한 온프레미스 GitLab 저장소 주소와 연결 단위 공유 읽기 전용 접근 정보를 등록하고 기본 분석 대상 ref를 1개 선택한 뒤, 첫 코드 스냅샷이 생성되는지 확인하면 독립 검증이 가능하다.

**Acceptance Scenarios**:

1. **Given** 수집 담당자가 접근 가능한 온프레미스 GitLab 저장소 주소와 SSH 또는 HTTPS 기반의 연결 단위 공유 읽기 전용 자격 증명을 제공한 상태에서, **When** 저장소 연결을 등록하면, **Then** 시스템은 연결 가능 여부를 검증하고 분석 가능한 저장소 연결을 생성해야 한다.
2. **Given** 활성화된 온프레미스 GitLab 저장소 연결과 기본 분석 대상 브랜치 또는 태그가 설정된 상태에서, **When** 초기 수집을 실행하면, **Then** 시스템은 해당 ref 기준의 분석 가능한 코드 스냅샷을 생성하고 수집 결과를 보여줘야 한다.
3. **Given** 온프레미스 GitLab 저장소 연결이 `reauth_required` 또는 `ref_missing` 상태로 전환된 상태에서, **When** 사용자가 수동 수집 또는 후속 최신화를 시도하면, **Then** 시스템은 새 수집을 차단하고 수정이 필요한 원인을 명확히 보여줘야 한다.
4. **Given** 기존 GitHub Cloud 저장소 연결이 이미 운영 중인 상태에서, **When** 새로운 온프레미스 GitLab 저장소 연결을 추가하더라도, **Then** 시스템은 기존 GitHub Cloud 연결의 수집 흐름과 이력을 그대로 유지해야 한다.

---

### User Story 2 - 수집 범위와 분석 대상 ref 관리 (Priority: P2)

수집 담당자는 온프레미스 GitLab 저장소 연결마다 분석 대상 브랜치 또는 태그, 포함 경로, 제외 경로, 파일 타입 조건을 관리해 필요한 코드 범위만 안정적으로 수집할 수 있어야 한다. 기본 정책은 GitHub Cloud와 동일하게 텍스트 기반 소스 파일만 수집하고, 바이너리·생성 산출물·5 MiB 초과 파일은 제외해야 한다.

**Why this priority**: 저장소 전체를 무차별 수집하면 분석 비용과 노이즈가 커지므로, 실제로 의미 있는 코드만 대상으로 제한할 수 있어야 한다.

**Independent Test**: 연결된 온프레미스 GitLab 저장소에서 분석 대상 ref와 범위 규칙을 설정한 뒤 새 스냅샷을 생성하여, 결과 파일 집합이 설정과 일치하고 기본 제외 대상이 포함되지 않는지 확인하면 독립 검증이 가능하다.

**Acceptance Scenarios**:

1. **Given** 활성화된 온프레미스 GitLab 저장소 연결이 있을 때, **When** 사용자가 분석 대상 브랜치 또는 태그를 선택하고 저장하면, **Then** 이후 생성되는 수집과 스냅샷은 해당 ref를 기준으로 처리되어야 한다.
2. **Given** 저장소 연결에 포함 경로, 제외 경로, 파일 타입 규칙이 설정된 상태에서, **When** 새 스냅샷을 생성하면, **Then** 시스템은 해당 규칙에 맞는 분석 가능한 파일만 스냅샷에 포함해야 한다.
3. **Given** 범위 규칙이 지나치게 좁아 실제 수집 대상 파일이 남지 않을 가능성이 있는 상태에서, **When** 사용자가 규칙을 저장하거나 스냅샷을 실행하면, **Then** 시스템은 빈 수집 위험 또는 실패를 명확히 알려 사용자가 설정을 수정할 수 있게 해야 한다.
4. **Given** 저장소에 바이너리, 생성 산출물, 5 MiB 초과 파일이 포함된 상태에서, **When** 사용자가 이를 포함하는 규칙으로 스냅샷을 실행하더라도, **Then** 시스템은 해당 파일을 기본 제외 대상으로 유지해야 한다.

---

### User Story 3 - 실시간 변경 이벤트 수신과 호환 운영 (Priority: P3)

시스템 운영자는 온프레미스 GitLab 저장소에서 발생하는 Commit, Push, Merge Request 이벤트를 webhook으로 실시간 수신해 변경 이력을 기록하고, Push 및 Merge Request를 기준으로 후속 코드 스냅샷을 최신 상태로 유지할 수 있어야 한다. Commit 이벤트는 Push 또는 Merge Request payload에서 추출한 기록 전용 이력으로 다뤄야 한다. Merge Request 기반 최신화는 `opened`, `reopened`, `updated/pushed` 계열 action에만 반응해야 한다. 이때 GitHub Cloud와 GitLab 간 운영 모델은 호환되어야 하며, 서로의 이벤트와 스냅샷이 혼합되면 안 된다.

**Why this priority**: 초기 스냅샷만으로는 최신 상태 분석이 불가능하므로, 변경 이벤트를 안정적으로 처리해 코드 수집을 지속적으로 최신화해야 한다.

**Independent Test**: 연결된 온프레미스 GitLab 저장소에서 Push와 Merge Request 이벤트를 전송하고, 해당 payload에서 추출된 Commit 이력이 기록되며 Push/Merge Request 기준 스냅샷만 최신화되는지 확인하면 독립 검증이 가능하다.

**Acceptance Scenarios**:

1. **Given** webhook이 정상 등록된 온프레미스 GitLab 저장소 연결이 있을 때, **When** 유효한 Push 이벤트가 수신되면, **Then** 시스템은 이벤트를 기록하고 해당 변경 상태를 반영하는 후속 스냅샷 최신화를 시작해야 한다.
2. **Given** webhook이 정상 등록된 온프레미스 GitLab 저장소 연결이 있을 때, **When** `opened`, `reopened`, `updated/pushed` 계열의 유효한 Merge Request 이벤트가 수신되면, **Then** 시스템은 이벤트를 기록하고 Merge Request source branch 최신 상태 기준의 스냅샷 최신화를 시작해야 한다.
3. **Given** 동일 워크스페이스에 GitHub Cloud 연결과 온프레미스 GitLab 연결이 함께 존재할 때, **When** 각 저장소에서 이벤트가 들어오면, **Then** 시스템은 provider별 연결과 이력을 분리해 처리하고 기존 GitHub Cloud 흐름을 손상시키지 않아야 한다.
4. **Given** 유효한 Push 또는 Merge Request payload에 commit 메타데이터가 포함된 상태에서, **When** 시스템이 이벤트를 기록하면, **Then** 시스템은 commit 이력을 기록하되 해당 commit 기록만으로는 독립적인 스냅샷 최신화를 시작하지 않아야 한다.
5. **Given** Merge Request의 비코드성 상태 변경이나 그 외 action 이벤트가 수신된 상태에서, **When** 시스템이 이벤트를 처리하면, **Then** 시스템은 이력만 기록하고 별도의 스냅샷 최신화를 시작하지 않아야 한다.

---

### Edge Cases

- 온프레미스 GitLab 서버가 일시적으로 도달 불가하거나 접근 정보가 만료되면 `reauth_required` 전환과 별도 health 신호를 어떤 기준으로 구분해 보여줄 것인가?
- 선택된 브랜치 또는 태그가 삭제되거나 Merge Request source branch가 더 이상 조회되지 않으면 `ref_missing` 전환과 수집 차단을 어떻게 보여줄 것인가?
- 동일한 webhook 이벤트가 중복 전달되거나 늦게 도착한 오래된 이벤트가 더 최신 변경 상태를 덮어쓰려 할 때 어떻게 중복 반영을 막을 것인가?
- Commit 메타데이터가 Push와 Merge Request 양쪽에서 중복 관측될 때 어떤 기준으로 기록 중복을 막을 것인가?
- Merge Request의 비코드성 상태 변경, reviewer 변경, 라벨 변경처럼 source branch HEAD를 바꾸지 않는 action은 어떤 기준으로 이력만 남기고 스냅샷은 건너뛸 것인가?
- 포함 규칙과 제외 규칙이 충돌해 분석 가능한 파일이 남지 않는 경우 어떤 경고와 실패 상태를 보여줄 것인가?
- 기본 제외 대상인 바이너리, 생성 산출물, 5 MiB 초과 파일을 사용자가 명시적으로 포함하려 할 때 어떤 안내와 차단 규칙을 보여줄 것인가?
- GitHub Cloud와 온프레미스 GitLab 연결이 같은 저장소 이름이나 유사한 경로 체계를 가져도 provider 식별이 뒤섞이지 않도록 어떻게 추적 관계를 보장할 것인가?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 기존 GitHub Cloud 지원을 유지하면서 온프레미스 GitLab 저장소를 추가 연결 대상으로 지원해야 한다.
- **FR-002**: 시스템은 각 저장소 연결에 대해 저장소 provider, 저장소 주소, 연결 방식(SSH 또는 HTTPS), 연결 단위 공유 자격 증명, 운영 상태를 등록하고 식별할 수 있어야 한다.
- **FR-002a**: 시스템은 온프레미스 GitLab 연결에서도 GitHub Cloud와 동일하게 읽기 전용 자격 증명만 허용하고, 쓰기 권한이 포함된 자격 증명은 승인하지 않아야 한다.
- **FR-003**: 시스템은 저장소 연결 등록 시 접근 가능 여부를 확인하고, 연결 실패 시 사용자가 수정 가능한 원인을 이해할 수 있게 해야 한다.
- **FR-004**: 시스템은 온프레미스 GitLab 지원 추가 이후에도 기존 GitHub Cloud 연결 생성, 수집, 이벤트 처리, 이력 조회 흐름을 변경 없이 유지해야 한다.
- **FR-004a**: 시스템은 GitHub Cloud와 동일하게 공식 저장소 연결 상태로 `active`, `reauth_required`, `ref_missing`만 사용해야 한다.
- **FR-005**: 시스템은 저장소 연결 1건당 분석 대상 브랜치 또는 태그 1개를 선택하고 이후 변경할 수 있게 해야 한다.
- **FR-006**: 시스템은 분석 대상 ref가 변경되더라도 기존 스냅샷과 이벤트 이력을 보존하고, 변경 이후 새로 시작되는 수집부터 새 ref를 적용해야 한다.
- **FR-007**: 시스템은 저장된 접근 정보가 더 이상 유효하지 않거나 선택된 ref를 조회할 수 없으면 연결을 조치 필요 상태로 전환하고, 사용자가 수정하기 전까지 수동 실행과 webhook 기반 최신화를 포함한 모든 새 수집을 차단해야 한다.
- **FR-007a**: 시스템은 접근 정보 무효 또는 만료 시 연결 상태를 `reauth_required`로 전환해야 한다.
- **FR-007b**: 시스템은 기본 분석 대상 ref를 더 이상 조회할 수 없으면 연결 상태를 `ref_missing`으로 전환해야 한다.
- **FR-008**: 시스템은 저장소 연결마다 포함 경로, 제외 경로, 파일 타입 조건을 설정하고 수정할 수 있게 해야 한다.
- **FR-009**: 시스템은 동일한 범위 규칙 의미와 검증 기준을 GitHub Cloud와 온프레미스 GitLab 연결 모두에 일관되게 적용해야 한다.
- **FR-009a**: 시스템은 GitHub Cloud와 동일하게 텍스트 기반 소스 파일만 기본 수집 대상으로 삼고, 바이너리·생성 산출물·5 MiB 초과 파일은 기본 제외해야 한다.
- **FR-010**: 시스템은 각 성공적인 수집 시점마다 저장소 식별 정보, provider, 기준 ref, 수집 시각, 적용된 범위 규칙을 포함한 분석 가능한 코드 스냅샷을 생성해야 한다.
- **FR-011**: 시스템은 각 성공적인 수집 결과를 이후 분석과 재검토에 사용할 수 있는 완전한 파일 집합 스냅샷으로 보존해야 한다.
- **FR-012**: 시스템은 Commit, Push, Merge Request 이벤트를 webhook 기반으로 실시간에 가깝게 수신하고 저장소 연결 이력으로 기록해야 한다.
- **FR-012a**: 시스템은 GitHub Cloud와 동일하게 Push 또는 Merge Request payload에서 추출한 commit 메타데이터를 기록 전용 commit 이벤트로 저장해야 한다.
- **FR-013**: 시스템은 Push 및 Merge Request 이벤트를 후속 스냅샷 최신화의 기준 이벤트로 사용하고, Commit 이벤트는 변경 이력 기록용으로 저장하되 독립적인 스냅샷 생성을 강제하지 않아야 한다.
- **FR-014**: 시스템은 Merge Request 기반 스냅샷을 해당 Merge Request의 source branch 최신 상태 기준으로 생성해야 한다.
- **FR-014a**: 시스템은 `opened`, `reopened`, `updated/pushed` 계열의 Merge Request action에 대해서만 스냅샷 최신화 후보를 생성하고, 그 외 action은 이력 기록만 수행해야 한다.
- **FR-015**: 시스템은 저장소 연결별 webhook secret을 등록하고, 검증에 실패한 이벤트는 처리하지 않으며 거부 사유를 구분해 기록해야 한다.
- **FR-015a**: 시스템은 webhook secret 미설정, secret 불일치, 최근 검증 실패, 서버 도달 불가 같은 운영 이상을 공식 연결 상태와 분리된 health 신호로 제공해야 한다.
- **FR-016**: 시스템은 중복 전달된 webhook 이벤트를 식별해 중복 처리하지 않아야 하며, 늦게 도착한 오래된 이벤트가 더 최신 스냅샷 상태를 덮어쓰지 못하게 해야 한다.
- **FR-017**: 시스템은 각 저장소 연결에 대해 최신 성공 수집 시각, 마지막 실패 시각, 마지막 처리 이벤트를 확인할 수 있는 요약 상태를 제공해야 한다.
- **FR-018**: 시스템은 저장소 연결, 범위 규칙, 이벤트 기록, 코드 스냅샷 사이의 추적 관계를 유지해 변경 이력 재구성과 감사가 가능해야 한다.
- **FR-019**: 시스템은 범위 규칙 저장 시 빈 수집 가능성을 경고하고, 실제 스냅샷 실행 결과 분석 가능한 파일이 없으면 성공으로 처리하지 말아야 한다.
- **FR-020**: 시스템은 동일 워크스페이스에서 GitHub Cloud 연결과 온프레미스 GitLab 연결을 동시에 운영할 수 있게 해야 하며, provider 간 이벤트, 상태, 스냅샷, 이력이 서로 섞이지 않도록 보장해야 한다.
- **FR-021**: 시스템은 저장소 쓰기 권한 없이도 수집 기능을 수행할 수 있도록 연결 단위 공유 읽기 전용 자격 증명 기반의 운영 모델을 유지해야 한다.
- **FR-022**: 시스템은 사용자가 온프레미스 GitLab 연결을 등록하거나 운영할 때도 기존 GitHub Cloud 연결과 유사한 작업 순서와 상태 해석 방식을 제공해야 한다.
- **FR-023**: 시스템은 승인된 계획 입력과 연결된 저장소 연결 및 스냅샷 사이의 추적성을 유지해, 어떤 수집 결과가 어떤 기획 범위와 연결되는지 확인할 수 있게 해야 한다.

### Key Entities *(include if feature involves data)*

- **Repository Connection**: 분석 대상으로 등록된 Git 저장소 연결 정보. provider 종류, 저장소 주소, 연결 방식, 접근 정보 상태, 기본 분석 대상 ref, 운영 상태를 포함한다.
- **Connection Health Summary**: 공식 연결 상태와 분리된 운영 이상 요약 정보. webhook secret 이상, 최근 검증 실패, 서버 도달 불가, 마지막 처리 이벤트와 같은 운영 신호를 포함한다.
- **Collection Scope Rule**: 저장소에서 어떤 파일을 분석 대상으로 포함하거나 제외할지 정의하는 규칙. 포함 경로, 제외 경로, 파일 타입 조건을 포함한다.
- **Repository Event**: Commit, Push, Merge Request 등 저장소에서 발생한 변경 이벤트 기록. 이벤트 유형, 발생 시각, 관련 ref, 처리 결과, 연결된 후속 최신화 결과를 포함한다.
- **Code Snapshot**: 특정 시점의 분석 가능한 코드 수집 결과. provider, 저장소, 기준 ref, 수집 시각, 적용된 범위 규칙, 포함된 파일 집합을 포함한다.
- **Connection Status**: 외부 계약에서 사용하는 공식 연결 상태 집합. `active`, `reauth_required`, `ref_missing`만 포함한다.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 권한이 유효한 운영자는 표준 운영 경로(온프레미스 GitLab 저장소 주소 입력, 기본 분석 대상 ref 1개 선택, 연결 검증 통과, 첫 코드 스냅샷 완료 확인)를 15분 이내에 끝낼 수 있다.
- **SC-002**: 유효한 Push 또는 Merge Request 이벤트의 95% 이상은 수신 후 1분 이내에 처리 상태가 확인 가능해야 한다.
- **SC-003**: 성공적으로 생성된 코드 스냅샷의 100%는 어떤 provider, 어떤 저장소, 어떤 ref, 어떤 범위 규칙, 어떤 시점의 수집 결과인지 추적 가능해야 한다.
- **SC-004**: 기존 승인된 GitHub Cloud 기준선 시나리오는 GitLab 지원 추가 후에도 모두 추가 수동 우회 없이 성공해야 한다.
- **SC-005**: 감사 표본으로 확인한 스냅샷의 100%는 저장된 포함/제외 경로 및 파일 타입 규칙과 일치해야 한다.

## Assumptions

- 기존 GitHub Cloud 연동 기능과 운영 모델은 신규 GitLab 지원의 기준선으로 유지된다.
- 초기 사용자는 저장소 접근 정보와 webhook 설정 권한을 가진 내부 운영자 또는 수집 담당자다.
- 온프레미스 GitLab 인스턴스는 TCI가 접근 가능한 네트워크 경로에 존재한다고 가정한다.
- 저장소 연결 1건은 기본 분석 대상 ref 1개를 갖고, 추가 상시 분석이 필요하면 별도 연결 또는 후속 범위 확장으로 처리한다.
- GitLab 연결 자격 증명도 사용자 개인 세션이 아니라 저장소 연결 단위의 공유 비밀정보로 관리된다고 가정한다.
- GitLab 연결의 기본 수집 제외 정책도 GitHub Cloud 기준선과 동일하게 유지된다고 가정한다.
- Commit 이벤트는 별도 독립 webhook이 아니라 Push 또는 Merge Request payload에서 추출 가능한 commit 메타데이터로 기록된다고 가정한다.
- Merge Request action 명칭은 provider별 표현 차이가 있더라도, 의미상 `opened`, `reopened`, `updated/pushed` 계열만 스냅샷 최신화 대상으로 매핑된다고 가정한다.
- 공식 연결 상태는 `active`, `reauth_required`, `ref_missing`만 사용하고, webhook 및 운영 이상은 별도 health 신호로 노출한다고 가정한다.
- TCI는 이 기능에서 저장소 데이터를 읽고 스냅샷을 생성하지만, 원격 저장소 코드 수정이나 배포는 수행하지 않는다.
- 온프레미스 GitLab host allowlist는 운영자가 환경 변수로 관리한다. 기본 포트는 host만 허용하고, 비표준 포트는 `host:port`로 허용한다.
- IPv6 GitLab remote는 이번 범위에서 지원하지 않는다.

## Approval Gate

- Implementation MUST NOT begin until this spec is reviewed and accepted as the active scope baseline.
- During the initial pilot, generation of this spec does NOT authorize automatic execution of the implement phase.
