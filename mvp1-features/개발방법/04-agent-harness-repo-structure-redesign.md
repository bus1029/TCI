# Agent Harness 저장소 구조 설계

## 문서 목적

이 문서는 TCI에서 Agent Harness를 어디에 두고, 어떤 최소 디렉터리부터 시작하며, 언제 구조를 확장할지를 정한다.

Harness는 제품 기능 자체가 아니라 Agent 작업 기준과 PR Gate를 연결하는 레이어다. 핵심은 완성형 디렉터리 트리를 한 번에 만드는 것이 아니라, Feature ID를 기준으로 작업 범위와 완료 기준을 추적할 수 있게 만드는 것이다.

## 핵심 용어

| 용어 | 의미 |
| --- | --- |
| Agent Harness | Agent 작업 기준, 검증 규칙, 완료 근거, PR Gate를 연결하는 운영 레이어 |
| Feature ID | `specs/`, `evidence/`, `feature-registry/`를 연결하는 기능 고유 이름 |
| SpecKit 산출물 | `spec.md`, `plan.md`, `tasks.md`처럼 Feature 요구와 구현 계획을 담는 문서 |
| 코드 쓰기 범위 | 해당 Feature에서 수정할 수 있는 제품 코드 경로 |
| 필수 문서 범위 | 해당 Feature에서 영향 여부를 확인하고 필요하면 갱신해야 하는 문서 경로 |
| 공동 수정 영역 | migration, lockfile, 생성물처럼 여러 작업이 동시에 건드리면 충돌 위험이 큰 경로 |
| 완료 근거 | 테스트, 운영자 확인, 산출물 링크, 잔여 위험을 요약한 완료 판단 근거. 실제 파일은 `evidence/<feature-id>/verification.md`에 둔다 |
| PR Gate | main 병합 전에 자동 검사와 검토자 승인을 강제하는 장치 |

## 핵심 결정

TCI Agent Harness 저장소 구조는 “어떤 Agent를 쓰는가”보다 “같은 Feature의 완료 기준을 무엇으로 삼는가”를 고정하는 구조다. 초기 MVP에서는 Harness를 별도 저장소로 분리하지 않고 TCI 모노레포 안에 둔다. 대신 제품 코드, Feature별 운영 등록부, Harness 운영 규칙을 섞지 않도록 `specs/`, `evidence/`, `feature-registry/`, `harness/`, 필요 시 `shared-contracts/`, `docs/`의 책임을 분리한다.

## 문서 범위

### 결정 범위

이 문서의 결정 범위는 다음과 같다.

- MVP에서 먼저 만들 최소 디렉터리
- 확장 후 권장할 Harness 디렉터리 구조
- Feature ID를 기준으로 `specs/`, `evidence/`, `feature-registry/`를 연결하는 방식
- Harness 형태를 지키며 개발하는 착수, 기록, 완료 흐름
- 자동 Gate와 검토자 판단을 분리하는 기준

### 제외 범위

이 문서가 정하지 않는 것은 다음과 같다.

- 개별 Feature의 상세 요구사항
- 특정 Agent 또는 모델 선택
- CI 제품 선택
- 실제 스크립트 구현 코드
- 각 앱과 서비스 내부 코드 구조

## 모노레포 구조

### 기본 전제

TCI 초기 개발에서는 Agent Harness를 제품 코드와 같은 모노레포 안에 둔다. 이 문서는 모노레포 안에서 어떤 디렉터리가 어떤 책임을 맡는지만 정리한다.

모노레포 안에 Harness를 둔다는 뜻은 모든 파일을 자유롭게 수정해도 된다는 뜻이 아니다. Harness는 오히려 Agent가 수정할 수 있는 코드 범위, 반드시 확인해야 하는 문서 범위, 공동 수정 영역, 완료 근거 위치를 좁히기 위해 둔다.

### 전체 구조

초기 모노레포는 제품 코드, SpecKit 산출물, 완료 판단 근거, Feature별 운영 등록부, Harness 운영 기준, 필요 시 두는 공유 계약 기준을 분리해서 둔다. 이 단계에서는 `harness/` 내부를 세세하게 펼치기보다, Feature ID를 기준으로 어느 위치가 서로 연결되는지만 먼저 보여준다.

```text
tci-platform/
├─ AGENTS.md
├─ apps/
├─ services/
├─ specs/
│  └─ <feature-id>/
├─ evidence/
│  └─ <feature-id>/
├─ feature-registry/
│  └─ <feature-id>.yml
├─ harness/
│  ├─ rules/
│  ├─ templates/
│  ├─ scripts/
│  └─ config/
├─ shared-contracts/          # 승격된 공유 계약 기준. 필요할 때만 둠
└─ docs/
```

### 책임 분리

초기 모노레포의 큰 책임 분리는 다음과 같다.

| 위치 | 책임 | 경계 기준 |
| --- | --- | --- |
| `apps/` | 사용자가 직접 쓰는 애플리케이션 | 제품 기능 구현 위치 |
| `services/` | 독립 실행 성격이 강한 내부 서비스와 worker | 비동기 작업, 분석, 내부 처리 구현 위치 |
| `specs/<feature-id>/` | SpecKit이 만드는 Feature별 요구, 설계, 작업, 검증 절차 | Feature별 작업 기준 |
| `evidence/<feature-id>/` | Feature 완료 판단 요약과 산출물 링크 | 완료 판단 근거 |
| `feature-registry/` | Feature별 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역, 검토 조건 | Harness가 읽는 검사 대상 |
| `harness/` | Agent 작업 기준, 템플릿, 검사 스크립트, PR Gate 규칙 | 검사 방법과 운영 규칙 |
| `shared-contracts/` | 승격된 공유 계약 기준 | 전체 계약 저장소가 아니라 이후 Feature가 참조할 참고 기준 |
| `docs/` | Feature를 넘어 유지되는 구조 설명과 ADR | 장기 구조 설명과 결정 기록 |

제품 코드는 `apps/`와 `services/`에 둔다. Feature 설명과 검증 기준은 `specs/`와 `evidence/`에서 추적한다. Feature별 운영 데이터는 `feature-registry/`에 둔다. Harness는 이 운영 등록부를 읽고 어떤 범위와 Gate를 검사해야 하는지 판단한다.

Feature 하나에서만 쓰는 계약 예시나 검증용 데이터는 `specs/<feature-id>/contracts/`에 둔다. `shared-contracts/`는 여러 Feature에서 반복해서 확인된 기준을 별도로 정리할 때만 사용하며, 기존 Feature 전용 계약을 이동하거나 대체하지 않는다. 다만 구조에서 삭제하지는 않는다. 이 위치가 없으면 공통 기준을 정리할 공식 위치가 사라져 Feature별 계약과 코드에 같은 기준이 흩어진다.

## MVP 최소 구조

### 시작 기준

초기 MVP에서는 Harness의 모든 하위 구조를 한 번에 만들 필요가 없다. 먼저 필요한 것은 Feature별 운영 등록부, 완료 근거 형식, 민감 정보 검사, 쓰기 범위 검사, 기본 Gate 실행 기준이다. 이 기준이 있어야 Agent 작업을 PR 단위로 검토하고 main 병합 전에 누락을 차단할 수 있다.

### 디렉터리 구조

MVP 최소 구조는 다음과 같다.

```text
feature-registry/
└─ <feature-id>.yml

harness/
├─ README.md
├─ rules/
│  ├─ development-flow.md    # 착수 전 확인, 개발 중 기록, 완료 후 산출물 기준
│  ├─ evidence.md            # 완료 판단 근거와 잔여 위험 기록 기준
│  ├─ sensitive-data.md      # 민감 정보 차단과 요약 기록 기준
│  └─ repo-boundary.md       # 코드 쓰기 범위와 공동 수정 영역 기준
├─ templates/
│  ├─ evidence.md
│  └─ pr-description.md
├─ scripts/
│  ├─ check-evidence
│  ├─ check-sensitive-data
│  ├─ check-feature-id
│  └─ check-write-scope
└─ config/
   └─ harness.yml
```

### 디렉터리 책임

각 디렉터리의 MVP 책임은 다음과 같다.

| 위치 | MVP 책임 |
| --- | --- |
| `feature-registry/` | Feature ID별 `specs/`, `evidence/`, 코드 쓰기 범위, 필수 문서 범위 연결 |
| `harness/rules/` | 개발 흐름, Gate 기준, Agent 운영 규칙 |
| `harness/templates/` | 완료 근거와 PR 본문을 같은 형식으로 작성하게 하는 양식 |
| `harness/scripts/` | CI에서 실행할 최소 자동 검사 |
| `harness/config/` | Harness 전체 설정과 필수 검사 기준 |

`harness/templates/evidence.md`는 작성 양식이고, 실제 완료 근거 파일은 `evidence/<feature-id>/verification.md`에 둔다. 템플릿은 여러 Feature가 같은 형식으로 `verification.md`를 작성하게 하는 기준이다.

### Feature 운영 등록부

`feature-registry/<feature-id>.yml`은 MVP의 핵심 파일이다. Harness는 이 파일을 읽고 Feature별 산출물 위치, 수정 허용 범위, 문서 확인 범위, 공동 수정 영역, 필요한 검사를 판단한다.

```yaml
feature_id: repository-snapshot-detail
specs_path: specs/repository-snapshot-detail
evidence_path: evidence/repository-snapshot-detail
code_write_scope:
  - apps/core-api/**
  - apps/web-console/**
required_document_scope:
  - specs/repository-snapshot-detail/**
  - evidence/repository-snapshot-detail/**
  - feature-registry/repository-snapshot-detail.yml
shared_areas:
  - apps/core-api/alembic/versions/**
  - apps/web-console/src/generated/**
review_owners:
  - backend-team
  - frontend-team
required_reviews:
  - owner-approval
  - shared-area-approval
required_checks:
  - check-feature-id
  - check-evidence
  - check-sensitive-data
  - check-write-scope
```

주요 필드는 다음 의미로 쓴다.

| 필드 | 의미 |
| --- | --- |
| `specs_path` | 이 Feature의 SpecKit 산출물 위치 |
| `evidence_path` | 이 Feature의 실제 완료 근거 위치 |
| `code_write_scope` | 제품 코드에서 수정할 수 있는 경로 |
| `required_document_scope` | 영향 여부를 확인하고 필요하면 갱신해야 하는 문서 경로 |
| `shared_areas` | 충돌 위험 때문에 별도 승인이 필요한 공동 수정 영역 |
| `review_owners` | 변경 내용을 확인할 책임 팀 또는 책임자 |
| `required_reviews` | Gate 통과 전에 필요한 검토 또는 승인 조건 |
| `required_checks` | PR 전에 통과해야 하는 자동 검사 |

`shared_areas`는 쓰기 범위 안에 있더라도 충돌 위험 때문에 별도 표시가 필요한 경로다. `required_checks`는 이 Feature에 적용할 Harness 스크립트 목록을 가리킨다.

### 필수 자동 검사

MVP에서 먼저 고정할 자동 검사는 다음 네 가지다. 이 검사는 `feature-registry/<feature-id>.yml`의 경로와 검사 목록을 기준으로 실행한다.

| 검사 | 목적 | 실패 조건 |
| --- | --- | --- |
| `check-feature-id` | PR, spec, 완료 근거, Feature 운영 등록부가 같은 Feature ID를 쓰는지 확인 | Feature ID 누락 또는 경로 불일치 |
| `check-evidence` | 완료 판단에 필요한 근거가 있는지 확인 | 표준 완료 근거 누락 또는 필수 항목 누락 |
| `check-sensitive-data` | 저장소, 완료 근거, PR 본문에 민감 정보가 남지 않도록 차단 | `token`, `cookie`, `private key`, DB URL, 원본 secret 값 포함 |
| `check-write-scope` | 변경 파일이 Feature 운영 등록부의 허용 범위 안에 있는지 확인 | 허용되지 않은 경로 수정, 공동 수정 영역 변경 표시 누락 |

MVP에서는 별도 `schemas/` 없이 `rules/`와 `templates/`에 적힌 필수 항목을 `scripts/`가 직접 검사해도 된다. 단, 스크립트가 검사하는 기준은 먼저 `rules/`에 검토자가 읽을 수 있게 적어야 한다. 그래야 자동화가 실패했을 때 검토자와 Agent가 같은 기준으로 수정할 수 있다.

### 자동화와 검토자 판단

MVP Gate는 자동 차단과 검토자 판단을 분리한다. 자동 검사는 누락과 명백한 위반을 막고, 검토자는 변경 의도와 잔여 위험을 판단한다.

| 구분 | MVP 기준 |
| --- | --- |
| 자동 차단 | Feature ID 불일치, 완료 근거 누락, 민감 정보 포함, 쓰기 범위 위반 |
| 검토자 확인 | 완료 근거의 잔여 위험, 공동 수정 영역 승인, 생략한 검증의 타당성 |
| 확장 후 자동화 | 영향 범위 검증, 검토 의견 상태 검사, 스키마 기반 완료 근거 검증 |

### 완료 판단 기준

이 MVP 구조의 목표는 완전한 Harness 플랫폼을 만드는 것이 아니다. 목표는 작업 완료를 주장하기 전에 최소한 다음 질문에 답할 수 있게 만드는 것이다.

- 어떤 Feature를 끝냈는가
- 어떤 제품 코드 범위를 수정했는가
- 어떤 필수 문서와 완료 근거를 갱신했는가
- 어떤 자동 검사를 통과했는가
- 민감 정보가 저장소, PR, 완료 근거에 남지 않았는가

### 확장 기준과 구조

이 다섯 가지 질문에 안정적으로 답할 수 있으면, 그다음에 `schemas/`, `examples/`, `check-affected`, `check-review-findings`를 추가한다.

다음 항목은 기존 `harness/` 구조를 대체하지 않고, 필요한 시점에 추가한다.

```text
harness/
├─ rules/
├─ templates/
├─ scripts/
│  ├─ check-evidence
│  ├─ check-sensitive-data
│  ├─ check-feature-id
│  ├─ check-write-scope
│  ├─ check-affected
│  └─ check-review-findings
├─ config/
├─ schemas/
│  ├─ feature-record.schema.json
│  ├─ evidence.schema.json
│  └─ review-finding.schema.json
└─ examples/
   ├─ feature-record.example.yml
   ├─ evidence.example.md
   └─ review-finding.example.md
```

확장 디렉터리는 다음 역할을 맡는다.

| 위치 | 역할 | 사용 대상 |
| --- | --- | --- |
| `harness/schemas/` | Feature 운영 등록부, 완료 근거, 검토 의견의 필수 필드와 상태값 정의 | 자동 검사와 형식 검증 |
| `harness/examples/` | 실제 값이 채워진 Feature 운영 등록부, 완료 근거, 검토 의견 작성 예시 | Agent 작업 맥락과 작성 기준 |

확장 스크립트는 다음 입력을 검사한다.

| 위치 | 검사 대상 | 목적 |
| --- | --- | --- |
| `harness/scripts/check-affected` | 변경 파일 목록, 의존성 지도, 앱/서비스/테스트 매핑, 필수 검사 매핑 | 영향 범위 검증 |
| `harness/scripts/check-review-findings` | PR 검토와 댓글 상태, `required_reviews`, 검토 의견 상태값 | 검토 의견 상태 검사 |

`harness/templates/`가 작성자가 채워야 할 빈 양식이라면, `harness/examples/`는 실제 값이 들어간 작성 예시다. 이 예시는 Harness 산출물 작성 기준이지, `specs/<feature-id>/contracts/examples/`나 `shared-contracts/examples/`에 두는 검증용 계약 예제 데이터와 다르다.
