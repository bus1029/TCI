# Feature Specification: 워크스페이스 기반 저장소 연결 시작점 전환

**Feature Branch**: `003-repository-first-connections`  
**Created**: 2026-04-29  
**Status**: Accepted as active scope baseline for planning and task generation
**Input**: User description: "저장소 연결 기능이 어떤 계획 입력과 승인된 spec/plan에서 출발했는지에서 시작하는게 아니라, 기존에 개발한 GitHub이나 GitLab 연동처럼 Repository 연결에서 시작하도록 수정하고 싶다. 기존 GitHub, GitLab 연동 기능의 경우엔 항상 '어떤 계획 입력과 승인된 spec/plan에서 출발'했는지 확인하기 위한 DB 테이블 및 관련 데이터 구조가 존재함. 이젠 spec/plan에서 시작하는게 아니라 사용자가 워크스페이스를 생성하고, 생성된 워크스페이스에서 어떤 Repository(GitHub, GitLab)에 연결하면 좋을지 결정하는 구조로 변경하면 좋겠음. 기존에 개발한 GitHub 및 GitLab 연동 기능과의 호환성을 모두 고려해야 함"

## Design Input Traceability *(mandatory)*

- **Planning Source**: 2026-04-29 사용자 요청 "저장소 연결 시작점을 승인된 spec/plan 기준에서 워크스페이스의 Repository 선택 기준으로 전환", 기존 기준선 [specs/001-git-repo-connection/spec.md](../001-git-repo-connection/spec.md), [specs/002-gitlab-onprem-connection/spec.md](../002-gitlab-onprem-connection/spec.md)
- **Why now**: 저장소 연결의 실제 사용자 흐름은 먼저 워크스페이스를 만들고 그 안에서 연결할 GitHub 또는 GitLab 저장소를 고르는 방식이어야 하며, 승인된 spec/plan 존재 여부가 새 저장소 연결의 선행 조건이 되면 초기 설정 흐름과 기존 GitHub/GitLab 운영 모델이 어긋난다.
- **Scope baseline**: 워크스페이스 생성 이후 Repository 연결을 시작하는 흐름, GitHub/GitLab 저장소 선택과 연결 생성, 새 연결에서 계획 입력 및 승인된 spec/plan 참조를 필수값에서 선택적 이력으로 전환, 기존 GitHub Cloud 및 온프레미스 GitLab 연결과 이력의 호환성 유지
- **Out of scope**: 신규 저장소 provider 추가, 저장소 코드 수집/스냅샷 생성 규칙 재설계, provider별 webhook 의미 변경, 기존 GitHub/GitLab 연결 이력 삭제, 계획/spec/plan 산출물 작성 기능 자체 변경, 자동 저장소 추천 알고리즘 도입
- **Approval note**: 2026-04-29 세션에서 이 문서는 `003-repository-first-connections`의 현재 scope baseline으로 채택되었다. 구현 실행은 spec/plan/tasks 검토 후 별도 명시 승인 전까지 보류한다.

## Clarifications

### Session 2026-04-29

- Q: 새 워크스페이스 기반 Repository 연결에서 planning/spec/plan trace를 어떻게 저장할 것인가? → A: 새 연결은 planning trace 없이 생성하고, 기존 trace만 보존한다.
- Q: 워크스페이스에서 저장소를 어떤 방식으로 선택하게 할 것인가? → A: 후보 목록 선택과 수동 저장소 URL 입력을 모두 지원한다.
- Q: 저장소 후보 조회와 실제 연결 운영은 어떤 권한 모델을 사용할 것인가? → A: 개인 provider 권한은 후보 조회에만 사용하고, 연결 운영은 워크스페이스 공유 읽기 전용 권한을 사용한다.
- Q: 기존 planning 기반 연결은 워크스페이스 모델에 어떻게 귀속할 것인가? → A: 기존 연결의 기존 workspace_id를 그대로 사용하고, 귀속이 불명확한 연결만 호환성 상태로 표시한다.
- Q: 저장소 후보 목록은 어떤 범위에서 제공할 것인가? → A: 설정된 provider 계정 또는 인스턴스에서만 후보 목록을 제공하고, 나머지는 수동 URL 입력을 사용한다.
- Q: 구 클라이언트가 새 저장소 연결 생성 요청에 `planningInputReferenceId`를 포함하면 어떻게 처리할 것인가? → A: 요청을 거부하고 저장하지 않는다.
- Q: 개인 provider 권한만 있고 워크스페이스 공유 읽기 전용 권한이 준비되지 않은 경우 연결 생성을 어떻게 처리할 것인가? → A: 후보 조회만 허용하고 생성은 차단한다.
- Q: SC-001의 표본/분모를 어떻게 고정할 것인가? → A: 대표 운영자 3명이 GitHub 1회와 GitLab 1회씩 총 6회 수행하고, 6회 중 5회 이상 10분 이내 성공해야 한다.
- Q: SC-004의 사용자 구분 성공률은 어떻게 측정할 것인가? → A: 대표 운영자 3명이 mixed-provider 화면에서 20개 식별 과제를 수행하고, 총 60개 중 57개 이상 정답이어야 한다.
- Q: FR-003b의 workspace shared read-only credential 경계는 어디까지 검증해야 하는가? → A: 생성, 검증, 수집, 이벤트 처리, 상태 조회, 재검증 모두 shared read-only credential만 허용해야 한다.
- Q: 기존 GitHub/GitLab 생성 흐름 호환성은 구 planning 기반 create payload 수락까지 포함하는가? → A: 아니다. 기존 provider 의미와 기존 연결 운영만 유지하고, 새 create payload의 planning 참조는 거부한다.
- Q: 새 create 요청에서 거부할 planning/spec/plan 참조 필드는 무엇인가? → A: `planningInputReferenceId`, `planningInputReference`, `planningTrace`, `traceability.planningInputReference`, `approvedSpecPath`, `approvedPlanPath`, `specPath`, `planPath`를 포함해 planning/spec/plan 출처를 전달하는 동등 필드를 거부한다.
- Q: planning trace가 없는 새 연결에서 snapshot 범위는 어디까지 보장해야 하는가? → A: 연결 검증, 수집 시작, snapshot 생성, snapshot 상세 traceability, 상태 조회가 모두 정상 동작해야 한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 워크스페이스에서 저장소 연결 시작 (Priority: P1)

워크스페이스 소유자는 새 워크스페이스를 만든 뒤 승인된 spec/plan을 먼저 고르지 않고, 해당 워크스페이스에서 연결할 GitHub 또는 GitLab 저장소를 선택해 워크스페이스 공유 읽기 전용 권한으로 저장소 연결을 만들 수 있어야 한다. 후보 목록 조회에는 사용자 개인 provider 권한을 사용할 수 있지만, 생성된 연결의 생성, 검증, 수집, 이벤트 처리, 상태 조회, 재검증은 개인 권한에 의존하지 않아야 한다. 후보 목록은 워크스페이스에 설정된 provider 계정 또는 GitLab 인스턴스 접근 정보에서만 제공하며, 후보 목록을 제공할 수 없는 provider 또는 인스턴스는 수동 URL 입력으로 연결해야 한다.

**Why this priority**: 이번 변경의 핵심 가치가 저장소 연결의 시작점을 spec/plan에서 워크스페이스와 Repository 선택으로 옮기는 것이므로, 이 흐름이 독립적으로 동작해야 MVP가 성립한다.

**Independent Test**: 새 워크스페이스를 생성하고 GitHub 또는 GitLab 저장소를 선택해 연결을 완료했을 때, 계획 입력이나 승인된 spec/plan 참조 없이도 연결이 생성되고 운영 가능한 상태로 표시되는지 확인한다.

**MVP Boundary**: 이 스토리의 독립 검증은 수동 URL 입력 경로와 기존 provider 검증 흐름을 통해 완료할 수 있어야 한다. 설정된 provider 계정 또는 GitLab 인스턴스에서 후보 목록을 조회하고 이미 연결된 저장소와 구분하는 판단 지원은 User Story 3에서 완성한다.

**Acceptance Scenarios**:

1. **Given** 사용자가 새 워크스페이스를 생성한 상태에서, **When** 저장소 연결 시작을 선택하면, **Then** 시스템은 승인된 spec/plan 선택을 요구하지 않고 GitHub 또는 GitLab 저장소 연결 선택지와 수동 URL 입력 경로를 보여줘야 한다.
2. **Given** 사용자가 워크스페이스 안에서 접근 가능한 GitHub 저장소를 후보 목록에서 선택하거나 저장소 URL로 입력한 상태에서, **When** 워크스페이스 공유 읽기 전용 권한으로 연결 정보를 제출하면, **Then** 시스템은 해당 워크스페이스에 GitHub 저장소 연결을 생성하고 연결 상태를 보여줘야 한다.
3. **Given** 사용자가 워크스페이스 안에서 접근 가능한 GitLab 저장소를 후보 목록에서 선택하거나 저장소 URL로 입력한 상태에서, **When** 워크스페이스 공유 읽기 전용 권한으로 연결 정보를 제출하면, **Then** 시스템은 해당 워크스페이스에 GitLab 저장소 연결을 생성하고 연결 상태를 보여줘야 한다.
4. **Given** 새 저장소 연결에 연결된 계획 입력이나 승인된 spec/plan 참조가 저장되지 않은 상태에서, **When** 사용자가 연결 상세를 확인하면, **Then** 시스템은 이를 오류가 아닌 정상적인 워크스페이스 기반 연결로 표시해야 한다.

---

### User Story 2 - 기존 GitHub/GitLab 연결 호환성 유지 (Priority: P2)

기존에 계획 입력과 승인된 spec/plan 추적 구조를 포함해 만들어진 GitHub Cloud 및 온프레미스 GitLab 연결은 새 워크스페이스 기반 흐름이 도입된 뒤에도 연결, 이벤트, 스냅샷, 이력 조회가 깨지지 않아야 한다.

**Why this priority**: 시작점 전환이 기존 저장소 연결 자산을 손상시키면 사용자는 새 흐름을 채택할 수 없고, GitHub/GitLab 연동의 신뢰성이 낮아진다.

**Independent Test**: 기존 방식으로 생성된 GitHub 및 GitLab 연결을 각각 열어 연결 상태, 이력, 스냅샷, provider별 이벤트가 기존과 동일하게 조회되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 계획 입력과 승인된 spec/plan 참조를 가진 기존 GitHub 연결이 있을 때, **When** 사용자가 새 흐름 도입 후 해당 연결 상세를 열면, **Then** 시스템은 기존 추적 이력을 보존한 채 연결을 정상 표시해야 한다.
2. **Given** 계획 입력과 승인된 spec/plan 참조를 가진 기존 GitLab 연결이 있을 때, **When** 사용자가 새 흐름 도입 후 해당 연결 상세를 열면, **Then** 시스템은 기존 추적 이력을 보존한 채 연결을 정상 표시해야 한다.
3. **Given** 같은 워크스페이스에 새 워크스페이스 기반 연결과 기존 계획 기반 연결이 함께 있을 때, **When** 사용자가 연결 목록과 상세를 조회하면, **Then** 시스템은 두 연결의 출처 차이를 명확히 보여주되 동일한 운영 행동을 제공해야 한다.
4. **Given** 기존 연결에 저장된 계획/spec/plan 이력이 있을 때, **When** 새 저장소 연결 시작 흐름을 사용하더라도, **Then** 시스템은 해당 이력을 새 연결 생성의 필수 조건으로 재사용하거나 요구하지 않아야 한다.
5. **Given** 기존 planning 기반 연결이 기존 `workspace_id`를 가지고 있을 때, **When** 새 워크스페이스 기반 목록과 상세에서 조회되면, **Then** 시스템은 해당 `workspace_id`를 canonical 귀속으로 사용해야 한다.

---

### User Story 3 - 워크스페이스 기준 연결 관리와 판단 지원 (Priority: P3)

워크스페이스 관리자는 한 워크스페이스 안에서 연결 가능한 GitHub/GitLab 저장소와 이미 연결된 저장소를 구분해 보고, 어떤 Repository를 연결할지 판단할 수 있어야 한다.

**Why this priority**: 사용자가 워크스페이스 생성 후 저장소를 결정하는 구조에서는 연결 후보와 기존 연결 상태를 워크스페이스 기준으로 이해할 수 있어야 중복 연결과 provider 혼동을 줄일 수 있다.

**Independent Test**: GitHub와 GitLab 연결 후보가 함께 있는 워크스페이스에서 후보 목록, 기존 연결 여부, provider 식별, 중복 방지 동작을 확인하고, 대표 운영자 3명의 mixed-provider 식별 과제 결과를 SC-004 증거로 기록한다.

**Acceptance Scenarios**:

1. **Given** 워크스페이스에 아직 연결된 저장소가 없을 때, **When** 사용자가 저장소 연결 화면을 열면, **Then** 시스템은 설정된 provider 계정 또는 인스턴스에서 가져온 후보 목록과 수동 URL 입력 경로를 워크스페이스 기준으로 보여줘야 한다.
2. **Given** 워크스페이스에 이미 연결된 저장소가 있을 때, **When** 사용자가 저장소 연결 후보를 확인하면, **Then** 시스템은 이미 연결된 저장소와 새로 연결 가능한 저장소를 구분해 보여주고 수동 URL 입력에서도 같은 중복 기준을 적용해야 한다.
3. **Given** GitHub 저장소와 GitLab 저장소가 같은 이름이나 유사한 경로를 가질 때, **When** 사용자가 후보 목록 또는 수동 URL 입력 결과를 기존 연결과 비교하면, **Then** 시스템은 provider와 저장소 식별 정보를 구분해 혼동 없이 선택할 수 있게 해야 한다.
4. **Given** 사용자가 이미 같은 워크스페이스에 연결된 동일 provider의 동일 저장소를 다시 연결하려 할 때, **When** 연결을 제출하면, **Then** 시스템은 중복 연결을 막고 기존 연결로 이동할 수 있는 안내를 제공해야 한다.

### Edge Cases

- 워크스페이스가 생성되었지만 설정된 provider 계정 또는 인스턴스에서 가져올 수 있는 GitHub/GitLab 후보가 없으면, 시스템은 후보 목록이 비어 있다는 상태와 수동 URL 입력 경로를 안내해야 한다.
- provider 계정 또는 GitLab 인스턴스 접근 정보가 설정되지 않은 경우, 시스템은 후보 목록을 비워 두고 수동 URL 입력으로 연결할 수 있게 해야 한다.
- 저장소 접근 권한이 만료되거나 회수된 경우, 시스템은 새 연결 생성을 중단하고 기존 provider별 재인증 또는 권한 수정 흐름으로 안내해야 한다.
- 기존 계획 기반 연결의 워크스페이스 귀속이 불명확하면, 시스템은 해당 연결을 숨기거나 삭제하지 않고 운영자가 호환성 처리를 완료할 수 있는 상태로 보여줘야 한다.
- 같은 저장소가 여러 워크스페이스에 연결될 수 있는 운영 정책이 있더라도, 한 워크스페이스 안에서는 동일 provider와 동일 저장소의 중복 연결을 허용하지 않아야 한다.
- 계획/spec/plan 이력이 있는 기존 연결과 이력이 저장되지 않은 새 연결이 같은 목록에 표시될 때, 이력 없음은 오류나 미완성 상태로 표시되면 안 된다.
- GitHub와 GitLab의 provider별 상태, 이벤트, 스냅샷은 같은 워크스페이스 안에서도 서로 섞이지 않아야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 워크스페이스 생성 이후 해당 워크스페이스에서 저장소 연결을 시작할 수 있게 해야 한다.
- **FR-002**: 시스템은 새 저장소 연결 생성 시 계획 입력, 승인된 spec, 승인된 plan 참조를 요구하거나 저장하지 않아야 한다.
- **FR-002a**: 시스템은 새 저장소 연결 생성 요청에 `planningInputReferenceId`, `planningInputReference`, `planningTrace`, `traceability.planningInputReference`, `approvedSpecPath`, `approvedPlanPath`, `specPath`, `planPath` 또는 동등한 planning/spec/plan 출처 참조 필드가 포함되면 해당 요청을 거부하고, 해당 값을 새 연결에 저장하지 않아야 한다.
- **FR-003**: 시스템은 GitHub 저장소 연결과 GitLab 저장소 연결을 모두 워크스페이스 기반 시작 흐름에서 선택 가능한 대상으로 제공해야 한다.
- **FR-003a**: 시스템은 저장소 연결 대상 선택 시 접근 가능한 후보 목록 선택과 수동 저장소 URL 입력을 모두 지원해야 한다.
- **FR-003b**: 시스템은 후보 목록 조회에 사용자 개인 provider 권한을 사용할 수 있지만, 생성된 저장소 연결의 생성, 검증, 수집, 이벤트 처리, 상태 조회, 재검증은 워크스페이스 공유 읽기 전용 권한만으로 운영해야 한다.
- **FR-003c**: 시스템은 워크스페이스에 설정된 provider 계정 또는 GitLab 인스턴스 접근 정보가 있는 경우에만 해당 범위의 저장소 후보 목록을 제공해야 한다.
- **FR-003d**: 시스템은 provider 계정 또는 인스턴스 접근 정보가 없어 후보 목록을 제공할 수 없는 경우에도 수동 저장소 URL 입력 경로를 제공해야 한다.
- **FR-004**: 시스템은 새 저장소 연결을 워크스페이스에 귀속된 연결로 표시하고, 사용자가 연결 목록과 상세에서 워크스페이스 맥락을 확인할 수 있게 해야 한다.
- **FR-005**: 시스템은 기존 계획/spec/plan 참조가 있는 GitHub 및 GitLab 연결의 이력과 운영 상태를 보존해야 한다.
- **FR-006**: 시스템은 기존 계획/spec/plan 참조를 기존 연결에만 남는 선택적 legacy 이력 정보로 취급해야 하며, 새 워크스페이스 기반 연결에는 새 planning trace를 생성하지 않아야 한다.
- **FR-007**: 시스템은 연결 상세에서 연결 출처가 워크스페이스 기반인지, 기존 계획 기반 이력을 포함하는지 사용자가 이해할 수 있게 표시해야 한다.
- **FR-008**: 시스템은 기존 GitHub Cloud 연결의 provider별 remote 검증, credential 검증, 상태 조회, 이벤트 조회, 스냅샷 조회, webhook 처리 의미를 새 시작점 전환 이후에도 유지해야 한다. 단, 새 저장소 연결 생성 요청의 planning/spec/plan 참조 필드 수락은 호환성 범위에 포함하지 않는다.
- **FR-009**: 시스템은 기존 온프레미스 GitLab 연결의 provider별 remote 검증, credential 검증, 상태 조회, 이벤트 조회, 스냅샷 조회, webhook 처리 의미를 새 시작점 전환 이후에도 유지해야 한다. 단, 새 저장소 연결 생성 요청의 planning/spec/plan 참조 필드 수락은 호환성 범위에 포함하지 않는다.
- **FR-010**: 시스템은 한 워크스페이스 안에서 동일 provider와 동일 저장소가 후보 목록 또는 수동 URL 입력 중 어떤 경로로 제출되더라도 중복 연결되지 않도록 해야 한다.
- **FR-011**: 시스템은 GitHub와 GitLab 저장소가 같은 이름이나 유사한 경로를 가져도 provider별 연결, 상태, 이벤트, 스냅샷, 이력을 분리해 보여줘야 한다.
- **FR-012**: 시스템은 사용자가 접근 권한이 없는 저장소를 연결하려 할 때 연결 생성을 완료하지 않고 권한 문제와 해결 방법을 알려줘야 한다.
- **FR-012a**: 시스템은 개인 provider 권한만 있고 워크스페이스 공유 읽기 전용 권한이 준비되지 않은 경우 저장소 후보 확인은 허용할 수 있으나 연결 생성을 완료하지 않아야 한다.
- **FR-012b**: 시스템은 저장소 접근 권한 만료, 권한 회수, shared read-only credential 검증 실패를 연결 생성 실패로 처리하고 기존 provider별 재인증 또는 권한 수정 흐름으로 이동할 수 있는 안내를 제공해야 한다.
- **FR-013**: 시스템은 워크스페이스에 연결 가능한 저장소가 없을 때 빈 상태를 오류로 처리하지 않고, 사용자가 다음 조치를 이해할 수 있게 해야 한다.
- **FR-014**: 시스템은 기존 계획 기반 연결이 워크스페이스 기반 목록과 상세 화면에서 사라지지 않도록 호환성 상태를 제공해야 한다.
- **FR-014a**: 시스템은 기존 planning 기반 연결의 기존 `workspace_id`를 워크스페이스 기반 모델의 canonical 귀속으로 사용해야 한다.
- **FR-014b**: 시스템은 기존 `workspace_id`가 없거나 일관되지 않아 귀속이 불명확한 기존 연결을 삭제하거나 숨기지 않고 별도 호환성 상태로 표시해야 한다.
- **FR-015**: 시스템은 새 워크스페이스 기반 연결과 기존 계획 기반 연결이 함께 있는 경우에도 동일한 provider별 운영 행동을 제공해야 한다.
- **FR-016**: 시스템은 새 연결에 계획/spec/plan 참조가 저장되지 않아도 연결 검증, 수집 시작, snapshot 생성, snapshot 상세 traceability, 상태 조회가 정상 흐름으로 처리되게 해야 한다.

### Key Entities

- **Workspace**: 사용자가 저장소 연결을 관리하는 작업 공간. 저장소 연결 목록, 연결 가능한 provider 선택, 워크스페이스 공유 읽기 전용 연결 권한 맥락을 포함한다.
- **Repository Connection**: 워크스페이스에 등록된 GitHub 또는 GitLab 저장소 연결. provider, 저장소 식별 정보, 연결 상태, 워크스페이스 공유 읽기 전용 권한 상태, 운영 이력을 포함한다.
- **Repository Candidate**: 사용자가 워크스페이스에서 후보 목록으로 검토할 수 있거나 수동 URL 입력으로 지정할 수 있는 GitHub 또는 GitLab 저장소. provider, 저장소 이름/경로, 이미 연결되었는지 여부, 접근 가능 여부, 후보 조회에 사용된 provider 계정 또는 인스턴스 범위, 입력 경로를 포함한다.
- **Connection Origin**: 연결이 워크스페이스 기반 흐름으로 생성되었는지, 기존 계획/spec/plan 이력을 가진 연결인지, 기존 연결의 워크스페이스 귀속이 명확한지 나타내는 사용자 이해용 출처 정보.
- **Legacy Planning Trace**: 기존 GitHub/GitLab 연결에 남아 있는 계획 입력, 승인된 spec, 승인된 plan 관련 이력. 새 워크스페이스 기반 연결에는 생성하거나 저장하지 않으며, 기존 연결에서는 보존되어야 한다.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 대표 운영자 3명이 각각 GitHub 1회와 GitLab 1회씩 총 6회의 연결 리허설을 수행했을 때, 6회 중 5회 이상이 계획 입력이나 승인된 spec/plan 선택 없이 10분 이내에 저장소 연결을 완료해야 하며, 각 시도는 시작/완료 타임스탬프와 성공/실패 결과를 실행 증거로 남겨야 한다.
- **SC-002**: 새 저장소 연결 수락 테스트의 100%에서 계획 입력, 승인된 spec, 승인된 plan 참조를 저장하지 않아도 연결 생성과 상세 조회가 성공한다.
- **SC-003**: 기존 GitHub Cloud 및 온프레미스 GitLab 기준선 시나리오의 100%가 시작점 전환 이후에도 추가 수동 우회 없이 성공한다.
- **SC-004**: 대표 운영자 3명이 mixed-provider 워크스페이스 화면에서 provider와 저장소 식별 정보를 기준으로 총 60개 식별 과제를 수행했을 때, 57개 이상을 올바르게 구분해야 하며, 과제별 정답/오답 결과를 실행 증거로 남겨야 한다.
- **SC-005**: 동일 워크스페이스 안에서 동일 provider와 동일 저장소의 중복 연결 시도는 100% 기존 연결 안내 또는 중복 방지 결과로 이어진다.
- **SC-006**: 기존 계획/spec/plan 이력이 있는 연결의 100%가 새 흐름 도입 후에도 목록과 상세에서 접근 가능하며, 해당 이력은 삭제되거나 필수값으로 재해석되지 않는다.
- **SC-007**: 개인 provider 권한만 있거나 shared read-only credential 검증에 실패한 연결 생성 시도의 100%가 연결을 생성하지 않고 권한 문제와 해결 안내를 반환한다.

## Assumptions

- 워크스페이스를 생성하고 저장소를 연결하는 사용자는 해당 워크스페이스에서 연결 관리 권한을 가진다고 가정한다.
- 사용자 개인 provider 권한은 저장소 후보를 찾는 데만 사용되며, 저장소 연결 생성 이후 운영은 워크스페이스 공유 읽기 전용 권한으로 수행된다고 가정한다.
- 1차 변경 범위의 provider는 기존에 개발된 GitHub Cloud와 온프레미스 GitLab로 한정한다.
- GitHub/GitLab별 저장소 접근 검증, 이벤트 수신, 스냅샷 생성의 세부 의미는 기존 승인된 기준선을 유지한다.
- 기존 계획/spec/plan 추적 정보는 감사 및 과거 맥락 확인을 위한 선택적 legacy 이력으로 남기되, 새 연결의 선행 조건으로 사용하거나 새로 생성하지 않는다.
- 저장소 자동 추천이나 우선순위 산정은 이번 범위가 아니며, 사용자가 설정된 provider 계정/인스턴스에서 제공되는 후보를 보거나 저장소 URL을 직접 입력해 결정하는 흐름을 기준으로 한다.
- 기존 planning 기반 연결은 기존 `workspace_id`를 canonical 귀속으로 사용하며, 귀속 관계가 불명확한 예외에만 연결을 숨기거나 삭제하지 않는 호환성 상태가 필요하다고 가정한다.

## Approval Gate

- This spec is accepted as the active scope baseline for planning and task generation in the 2026-04-29 session.
- Implementation MUST NOT begin until the updated spec, plan, and task set are reviewed together and a human explicitly approves implementation.
- During the initial pilot, generation or update of this spec does NOT authorize automatic execution of the implement phase.
