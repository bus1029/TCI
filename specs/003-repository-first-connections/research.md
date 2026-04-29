# Research: 워크스페이스 기반 저장소 연결 시작점 전환

## 결정 1: 새 RepositoryConnection은 planning trace 없이 생성한다

**Decision**: 새 워크스페이스 기반 저장소 연결은 `planning_input_reference_id`를 저장하지 않는다. 기존 연결에 이미 저장된 planning reference만 legacy provenance로 보존한다.

**Rationale**:
- clarify에서 "planning trace를 저장 안 하는" 방향이 확정됐다.
- 새 연결마다 synthetic planning reference를 만들면 사용자 흐름은 Repository-first로 보이더라도 데이터 모델은 여전히 plan-first가 된다.
- 기존 trace는 감사 이력이므로 삭제하지 않고 legacy provenance로만 둔다.

**Alternatives considered**:
- Synthetic planning reference 자동 생성: 데이터 모델 왜곡과 불필요한 row 증가.
- Workspace default planning reference 공유: 여러 연결의 실제 출처가 한 reference로 섞인다.

## 결정 2: planning reference FK는 nullable legacy 관계로 전환한다

**Decision**: `RepositoryConnection.planning_input_reference_id`는 nullable FK가 된다. legacy rows는 값을 유지하고, 신규 rows는 null을 정상 상태로 사용한다.

**Rationale**:
- 현재 create service, serializer, snapshot traceability가 planning reference를 필수로 가정한다.
- null 허용을 명시하지 않으면 새 Repository-first 연결의 create/detail/snapshot이 모두 기존 trace 구조에 막힌다.
- 기존 `workspace_id`는 이미 connection에 있으므로 새 연결의 workspace 귀속에는 planning reference가 필요하지 않다.

**Alternatives considered**:
- 별도 `LegacyRepositoryConnection` 모델 분리: list/detail/snapshot 로직 중복.
- planning reference row 유지하고 nullable만 피하기: spec 결정과 충돌.

## 결정 3: traceability는 planning reference 중심에서 connection origin 중심으로 재구성한다

**Decision**: detail/snapshot traceability는 `origin`과 connection/scope/event/snapshot identifiers를 중심으로 구성한다. `planningInputReference`는 nullable legacy enrichment로 남긴다.

**Rationale**:
- constitution의 change traceability는 spec/plan/tasks/evidence 산출물에서 유지된다.
- runtime RepositoryConnection의 traceability는 사용자가 연결 상태와 수집 결과를 이해하기 위한 도메인 trace다.
- 새 연결에서 planning reference가 null이어도 active scope, latest event, latest snapshot은 여전히 추적 가능해야 한다.

**Alternatives considered**:
- traceability block 제거: 기존 API/UI 계약과 GitHub/GitLab 회귀가 깨진다.
- planningInputReference만 null로 두고 origin 추가 안 함: 사용자가 legacy/new 차이를 이해하기 어렵다.

## 결정 4: create API는 planningInputReferenceId를 제거하고 workspace header를 기준으로 생성한다

**Decision**: `POST /api/repository-connections`는 `X-TCI-Workspace-Id`와 provider/remote/credential/default ref 입력만으로 connection을 생성한다. `planningInputReferenceId`는 신규 contract에서 제거하며, 구 클라이언트가 이 필드 또는 동등한 planning/spec/plan 참조 필드를 보내면 요청을 거부하고 저장하지 않는다.

**Rationale**:
- 현 route는 이미 workspace header를 요구한다.
- create service가 planning reference를 조회해 workspace를 재확인하는 역할을 하고 있으나, 새 모델에서는 connection 자체의 `workspace_id`가 canonical이다.
- obsolete field를 무시하면 클라이언트가 planning trace가 저장된다고 오해할 수 있으므로 validation error로 빠르게 드러내는 편이 안전하다.
- 새 happy path는 field 없이 성공해야 한다.

**Alternatives considered**:
- `planningInputReferenceId` optional 유지: client가 계속 보낼 유인이 남고 시작점 전환이 흐려진다.
- `planningInputReferenceId`를 조용히 ignore: 데이터 손상은 피하지만 client migration 실패를 숨긴다.
- 새 endpoint 추가: 같은 기능의 create endpoint가 둘로 갈라져 호환성 테스트가 복잡해진다.

## 결정 5: 후보 목록은 configured provider scope에서만 제공하고 수동 URL 입력을 항상 유지한다

**Decision**: `GET /api/repository-candidates`는 워크스페이스에 설정된 provider 계정 또는 GitLab 인스턴스 접근 정보가 있는 경우에만 후보 목록을 반환한다. 정보가 없으면 empty candidates와 manual URL guidance를 반환한다.

**Rationale**:
- GitHub는 계정 권한으로 후보를 찾을 수 있지만, GitLab Self-Managed는 인스턴스 범위 없이는 후보 탐색 기준이 없다.
- 수동 URL 입력은 기존 GitHub/GitLab 연결 생성 방식과 호환되는 안정적인 fallback이다.
- 후보 목록을 필수로 만들면 온프레미스 GitLab과 폐쇄망 환경의 초기 연결이 막힌다.

**Alternatives considered**:
- GitHub만 candidates 제공: UX 일관성이 낮다.
- 모든 provider candidates 필수: GitLab 인스턴스 미설정 상태에서 불가능하다.

## 결정 6: 개인 provider 권한과 워크스페이스 연결 credential을 분리한다

**Decision**: 개인 provider 권한은 candidate discovery에만 사용한다. connection creation, connection verification, mirror sync, snapshot collection, webhook/event handling, status lookup that requires repository access, and reverify all use only the workspace shared read-only credential.

**Rationale**:
- 기존 GitHub/GitLab 연결은 연결 단위 공유 읽기 전용 credential을 사용한다.
- 개인 권한을 운영 credential로 사용하면 사용자가 퇴사하거나 권한이 회수될 때 workspace connection이 깨진다.
- 보안상 candidate discovery grant와 long-lived repository ingestion credential의 목적과 보관 정책을 분리해야 한다.
- shared read-only credential이 없거나 검증에 실패하면 connection row를 active로 만들지 않고 provider별 재인증 또는 권한 수정 안내를 반환한다.
- 이벤트 처리와 상태 조회/재검증까지 같은 경계를 적용해야 개인 provider grant가 운영 경로로 재도입되는 회귀를 막을 수 있다.

**Alternatives considered**:
- 개인 권한으로 운영까지 수행: 운영 안정성과 감사성이 약하다.
- 개인 권한 없이 공유 credential만 사용: candidate listing UX가 제한된다.

## 결정 6a: 권한 실패는 연결 생성 실패로 고정한다

**Decision**: 저장소 접근 권한 만료, 권한 회수, shared read-only credential 검증 실패, 개인 provider grant만 있는 create 시도는 연결 생성을 완료하지 않는다. 동일한 credential boundary 위반이 검증, 수집, 이벤트 처리, 상태 조회, 재검증에서 발견되면 해당 operation을 실패시키고 API는 권한 문제와 해결 안내를 담은 problem response를 반환하며, operator UI는 provider별 재인증 또는 credential 수정 흐름으로 안내한다.

**Rationale**:
- 후보 조회와 연결 운영 credential의 경계를 테스트 가능하게 만든다.
- half-created active connection이나 snapshot enqueue가 발생하면 이후 sync/event 처리에서 실패 원인이 흐려진다.
- spec의 "후보 조회는 가능하지만 생성 완료는 금지" 요구를 구현 가능한 실패 계약으로 고정한다.

**Alternatives considered**:
- `reauth_required` connection을 생성하고 나중에 복구: 생성 완료 금지 요구와 충돌한다.
- 개인 provider grant를 임시 운영 credential로 승격: credential boundary와 감사 요구를 깨뜨린다.

## 결정 7: 기존 GitHub/GitLab provider semantics는 변경하지 않는다

**Decision**: GitHub HMAC webhook, GitLab shared-token webhook, provider별 event normalization, snapshot trigger rules, scope filtering, mirror/snapshot storage는 기존 의미를 유지한다.

**Rationale**:
- 이번 기능은 시작점과 provenance 모델 전환이다.
- provider semantics를 같이 바꾸면 기존 GitHub/GitLab 호환성 검증 범위가 과도하게 커진다.
- 기존 테스트 자산은 provider behavior regression을 그대로 검증할 수 있다.

**Alternatives considered**:
- 이 기회에 provider abstraction 전면 재설계: scope 초과 및 회귀 위험 증가.

## 결정 8: 기존 planning 기반 연결은 기존 workspace_id를 canonical 귀속으로 유지한다

**Decision**: 기존 rows는 `repository_connections.workspace_id`를 워크스페이스 기반 모델의 canonical workspace로 사용한다. 값이 없거나 불일치하는 예외만 compatibility state로 표시한다.

**Rationale**:
- 현 DB 모델은 connection 자체에 `workspace_id`를 이미 저장한다.
- 전체 재귀속 migration은 데이터 손상 위험이 크고 spec이 요구하지 않는다.
- 불명확한 예외를 숨기면 운영자가 복구할 수 없다.

**Alternatives considered**:
- 전체 legacy row 재귀속: 필요 이상으로 위험하다.
- legacy 영역에서만 조회: 새 workspace list에서 기존 연결이 사라져 호환성 요구와 충돌한다.

## Sources Used

- Local implementation reference: `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py`
- Local implementation reference: `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
- Local implementation reference: `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
- Local contract baseline: `specs/002-gitlab-onprem-connection/contracts/repository-ingestion.openapi.yaml`
