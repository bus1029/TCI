# Agent Harness 저장소 구조 설계

## 문서 목적

이 문서는 TCI에서 Agent Harness를 어디에 두고, 어떤 최소 디렉터리부터 시작하며, 언제 구조를 확장할지를 정한다. Harness는 제품 기능 자체가 아니라 Agent 개발 방식과 PR Gate를 운영하는 레이어다. 핵심은 완성형 디렉터리 트리를 한 번에 만드는 것이 아니라 Feature ID를 기준으로 개발 착수 전 확인물, 코드 쓰기 범위, 필수 문서 범위, 완료 후 산출물, PR Gate를 추적할 수 있게 만드는 것이다.

## 핵심 용어

| 용어 | 의미 |
| --- | --- |
| Agent Harness | Agent 작업 기준, 검증 규칙, evidence, PR Gate를 연결하는 운영 레이어 |
| Feature ID | `specs/`, `evidence/`, `feature-registry/`를 연결하는 기능 고유 이름 |
| SpecKit 산출물 | `spec.md`, `plan.md`, `tasks.md`처럼 Feature 요구와 구현 계획을 담는 문서 |
| 코드 쓰기 범위 | 해당 Feature에서 수정할 수 있는 제품 코드 경로 |
| 필수 문서 범위 | 해당 Feature에서 영향 여부를 확인하고 필요하면 갱신해야 하는 문서 경로 |
| 공동 수정 영역 | migration, lockfile, 생성물처럼 여러 작업이 동시에 건드리면 충돌 위험이 큰 경로 |
| evidence | 테스트, 운영자 확인, artifact 링크, 잔여 위험을 요약한 완료 판단 근거 |
| PR Gate | main 병합 전에 자동 검사와 검토자 승인을 강제하는 장치 |

## 핵심 결정

TCI Agent Harness 저장소 구조는 “어떤 Agent를 쓰는가”보다 “같은 Feature를 어떤 산출물, 코드 범위, 검증 기준, evidence로 완료 처리하는가”를 고정하는 구조여야 한다. 초기 MVP에서는 Harness를 별도 저장소로 분리하지 않고 TCI 모노레포 안에 둔다. 대신 제품 코드, Feature별 운영 등록부, Harness 운영 규칙을 섞지 않도록 `specs/`, `evidence/`, `feature-registry/`, `harness/`, `boundary-contracts/`, `docs/`의 책임을 분리한다.

# 문서 범위

## 결정 범위

이 문서의 결정 범위는 다음과 같다.

- MVP에서 먼저 만들 최소 디렉터리
- 확장 후 권장할 Harness 디렉터리 구조
- Feature ID를 기준으로 `specs/`, `evidence/`, `feature-registry/`를 연결하는 방식
- Harness 형태를 지키며 개발하는 착수, 기록, 완료 흐름
- 자동 Gate와 검토자 판단을 분리하는 기준

## 제외 범위

이 문서가 정하지 않는 것은 다음과 같다.

- 개별 Feature의 상세 요구사항
- 특정 Agent 또는 모델 선택
- CI 제품 선택
- 실제 스크립트 구현 코드
- 각 app, service 내부 코드 구조

# 모노레포 구조

## 기본 전제

TCI 초기 개발에서는 Agent Harness를 제품 코드와 같은 모노레포 안에 둔다. 이 문서는 모노레포 안에서 어떤 디렉터리를 어떤 책임으로 나눌지만 정리한다.

모노레포 안에 Harness를 둔다는 뜻은 모든 파일을 자유롭게 수정해도 된다는 뜻이 아니다. Harness는 오히려 Agent가 수정할 수 있는 코드 범위, 반드시 확인해야 하는 문서 범위, 공동 수정 영역, evidence 위치를 좁히기 위해 둔다.

## 전체 구조

초기 모노레포는 제품 코드, SpecKit 산출물, 완료 판단 근거, Feature별 운영 등록부, Harness 운영 기준, 공유 경계 기준을 분리해서 둔다. 이 단계에서는 `harness/` 내부를 세세하게 펼치기보다, Feature ID를 기준으로 어느 위치가 서로 연결되는지만 먼저 보여준다.

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
├─ boundary-contracts/
│  └─ shared/
└─ docs/
```

## 책임 분리

초기 모노레포의 큰 책임 분리는 다음과 같다.

| 위치 | 책임 | 경계 기준 |
| --- | --- | --- |
| `apps/` | 사용자와 직접 맞닿는 애플리케이션 | 제품 기능 구현 위치 |
| `services/` | 독립 실행 성격이 강한 내부 서비스와 worker | 비동기 작업, 분석, 내부 처리 구현 위치 |
| `specs/<feature-id>/` | SpecKit이 만드는 Feature별 요구, 설계, 작업, 검증 절차 | Feature별 작업 기준 |
| `evidence/<feature-id>/` | Feature 완료 판단 요약과 artifact 링크 | 완료 판단 근거 |
| `feature-registry/` | Feature별 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역, 검토 조건 | Harness가 읽는 검사 대상 |
| `harness/` | Agent 작업 기준, 템플릿, 검사 스크립트, PR Gate 규칙 | 검사 방법과 운영 규칙 |
| `boundary-contracts/` | 여러 Feature가 공유하는 장기 경계 기준 | 공통 API, event, storage, tracing 기준 |
| `docs/` | Feature를 넘어 유지되는 구조 설명과 ADR | 장기 구조 설명과 결정 기록 |

제품 코드는 `apps/`와 `services/`에 둔다. Feature 설명과 검증 기준은 `specs/`와 `evidence/`에서 추적한다. Feature별 운영 데이터는 `feature-registry/`에 둔다. Harness는 이 운영 등록부를 읽고 어떤 범위와 Gate를 검사해야 하는지 판단한다.

# MVP 최소 구조

## 시작 기준

초기 MVP에서는 Harness의 모든 하위 구조를 한 번에 만들 필요가 없다. 먼저 필요한 것은 Feature별 운영 등록부, evidence 형식, 민감 정보 검사, 쓰기 범위 검사, 기본 Gate 실행 기준이다. 이 기준이 있어야 Agent 작업을 PR 단위로 검토하고 main 병합 전에 누락을 차단할 수 있다.

## 디렉터리 구조

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

## 디렉터리 책임

각 디렉터리의 MVP 책임은 다음과 같다.

| 위치 | MVP 책임 |
| --- | --- |
| `feature-registry/` | Feature ID별 `specs/`, `evidence/`, 코드 쓰기 범위, 필수 문서 범위 연결 |
| `rules/` | 사람이 읽는 개발 흐름, Gate 기준, Agent 운영 규칙 |
| `templates/` | evidence와 PR 본문을 같은 형식으로 작성하게 하는 양식 |
| `scripts/` | CI에서 실행할 최소 자동 검사 |
| `config/` | Harness 전체 설정과 필수 검사 기준 |

## 필수 자동 검사

MVP에서 먼저 고정할 자동 검사는 다음 네 가지다.

| 검사 | 목적 | 실패 조건 |
| --- | --- | --- |
| `check-feature-id` | PR, spec, evidence, Feature 운영 등록부가 같은 Feature ID를 쓰는지 확인 | Feature ID 누락 또는 경로 불일치 |
| `check-evidence` | 완료 판단에 필요한 evidence가 있는지 확인 | 표준 evidence 누락 또는 필수 항목 누락 |
| `check-sensitive-data` | 저장소, evidence, PR 본문에 민감 정보가 남지 않도록 차단 | `token`, `cookie`, `private key`, DB URL, 원본 secret 값 포함 |
| `check-write-scope` | 변경 파일이 Feature 운영 등록부의 허용 범위 안에 있는지 확인 | 허용되지 않은 경로 수정, 공동 수정 영역 승인 누락 |

MVP에서는 별도 `schemas/` 없이 `rules/`와 `templates/`에 적힌 필수 항목을 `scripts/`가 직접 검사해도 된다. 단, 스크립트가 검사하는 기준은 먼저 `rules/`에 사람이 읽을 수 있는 형태로 적어야 한다. 그래야 자동화가 실패했을 때 검토자와 Agent가 같은 기준으로 수정할 수 있다.

## 자동화와 검토자 판단

MVP Gate는 자동 차단과 검토자 판단을 분리한다. 자동 검사는 누락과 명백한 위반을 막고, 검토자는 변경 의도와 잔여 위험을 판단한다.

| 구분 | MVP 기준 |
| --- | --- |
| 자동 차단 | Feature ID 불일치, evidence 누락, 민감 정보 포함, 쓰기 범위 위반 |
| 검토자 확인 | evidence의 잔여 위험, 공동 수정 영역 승인, 생략한 검증의 타당성 |
| 확장 후 자동화 | 영향 범위 검증, 검토 의견 상태 검사, 스키마 기반 evidence 검증 |

## Feature 운영 등록부

`feature-registry/<feature-id>.yml`은 MVP의 핵심 파일이다. 이 파일이 있어야 Harness가 Feature별로 어떤 산출물과 변경 범위를 확인해야 하는지 알 수 있다.

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

주요 필드는 다음처럼 해석한다.

| 필드 | 의미 |
| --- | --- |
| `code_write_scope` | 제품 코드에서 수정할 수 있는 경로 |
| `required_document_scope` | 영향 여부를 확인하고 필요하면 갱신해야 하는 문서 경로 |
| `shared_areas` | 충돌 위험 때문에 별도 승인이 필요한 공동 수정 영역 |
| `review_owners` | 변경 내용을 확인할 책임 팀 또는 책임자 |
| `required_reviews` | Gate 통과 전에 필요한 검토 또는 승인 조건 |
| `required_checks` | PR 전에 통과해야 하는 자동 검사 |

## 완료 판단 기준

이 MVP 구조의 목표는 완전한 Harness 플랫폼을 만드는 것이 아니다. 목표는 작업 완료를 주장하기 전에 최소한 다음 질문에 답할 수 있게 만드는 것이다.

- 어떤 Feature를 끝냈는가
- 어떤 제품 코드 범위를 수정했는가
- 어떤 필수 문서와 evidence를 갱신했는가
- 어떤 자동 검사를 통과했는가
- 민감 정보가 저장소, PR, evidence에 남지 않았는가

## 확장 시점

이 다섯 가지 질문에 안정적으로 답할 수 있으면, 그다음에 `schemas/`, `examples/`, `check-affected`, `check-review-findings`를 추가한다.

# Harness 개발 흐름

## 기본 원칙

Harness는 산출물의 세부 작성법을 정의하지 않는다. 대신 어떤 산출물이 있어야 하고, 어느 Feature ID에 연결되어야 하며, Gate 전에 어떤 상태여야 하는지를 정의한다. Feature별 운영 데이터는 `feature-registry/`에 두고, `harness/`는 그 데이터를 읽어 Gate를 수행하는 규칙과 도구를 담는다.

Harness를 지키며 개발한다는 것은 다음 흐름을 유지한다는 뜻이다.

```text
착수 전 확인
→ 작업 식별
→ 개발 중 기록
→ Gate 전 인덱스 정리
→ 완료 후 산출물 정리
→ PR 준비
→ Gate 통과
```

## 단계별 기준

| 단계 | Harness 기준 |
| --- | --- |
| 착수 전 확인 | `specs/<feature-id>/`의 SpecKit 산출물과 기존 `evidence/<feature-id>/verification.md`를 확인. 기존 `feature-registry/<feature-id>.yml`이 있으면 함께 확인 |
| 작업 식별 | `tasks.md`에서 이번에 진행할 task와 목표를 확인 |
| 개발 중 기록 | Gate 판단에 영향을 주는 변경, 공동 수정 영역 가능성, 생략한 검증과 사유, 민감 정보 처리 판단 기록 |
| Gate 전 인덱스 정리 | 실제 수정한 코드 범위, 갱신한 문서 범위, 공동 수정 영역 여부, 필요한 자동 검사 기준으로 `feature-registry/<feature-id>.yml` 작성 또는 갱신 |
| 완료 후 산출물 | evidence 작성 또는 갱신, 완료된 task 상태 정리 |
| PR 준비 | PR 본문에 Feature ID, 작업 요약, 검증 결과, 공동 수정 영역 승인 근거 기재 |
| Gate 통과 | Harness가 `feature-registry/<feature-id>.yml`과 PR 본문을 기준으로 자동 검사와 검토자 확인 수행 |

## 완료 처리

Harness에서 개발 완료는 Gate 통과 전까지 최종 완료로 보지 않는다. Gate를 통과한 뒤에만 해당 Feature 작업을 완료로 처리한다.

## 실패 처리

Gate 실패는 개발 흐름의 끝이 아니라 수정 루프의 시작이다. 자동 실패와 검토자 보류는 처리 방식이 다르므로 구분해서 다룬다.

| 실패 유형 | 처리 기준 |
| --- | --- |
| 자동 검사 실패 | 실패한 검사 기준에 맞춰 Feature ID, evidence, 민감 정보, 쓰기 범위, 공동 수정 영역 승인 상태를 수정하고 검사를 다시 실행 |
| 검토자 보류 | 잔여 위험, 생략한 검증, 공동 수정 영역 변경 사유를 보강하고 검토자에게 다시 확인 요청 |
| 범위 변경 필요 | `feature-registry/<feature-id>.yml`의 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역을 갱신하고 관련 검사를 다시 실행 |
