# SpecKit 기반 TCI 프로젝트 산출물 구조

## 문서 목적

이 문서는 SpecKit 기반 TCI 프로젝트에서 주요 산출물을 어디에 두고, 각 위치가 어떤 책임을 갖는지 정리한다.

SpecKit은 Feature 단위로 요구사항, 계획, 작업 목록을 만드는 흐름이다. 이 문서는 그 산출물과 TCI가 추가로 관리하는 완료 근거, Feature 등록부, 공유 계약 기준을 저장소 어디에 둘지 정한다.

Feature 하나는 기본적으로 `specs/`, `evidence/`, `feature-registry/` 세 경로로 추적한다. `shared-contracts/`는 모든 Feature가 쓰는 필수 경로가 아니라, 여러 Feature에서 반복 확인된 기준을 따로 정리할 때만 둔다.

이 문서에서는 주요 용어를 다음 의미로 쓴다.

| 용어 | 의미 |
| --- | --- |
| Feature | SpecKit으로 관리하는 완결 기능 단위 |
| Feature ID | `specs/`, `evidence/`, `feature-registry/`를 연결하는 기능 고유 이름 |
| Feature 등록부 | Feature별 산출물 경로를 연결하는 `feature-registry/<feature-id>.yml` |
| 검증 절차 문서 | 구현자나 운영자가 따라 할 검증 절차를 담는 `specs/<feature-id>/quickstart.md` |
| 완료 근거 문서 | 실제로 실행한 검증과 판단 근거를 남기는 `evidence/<feature-id>/verification.md` |
| 공유 계약 기준 | 여러 Feature에서 반복해서 확인된 경계 기준을 별도로 정리한 참고 문서 |

Feature ID는 `NNN-kebab-case-topic` 형식으로 쓴다. 예시는 `004-zip-upload-workspace-delete`다. 공유 계약 기준은 필요할 때만 `shared-contracts/`에 둔다.

## 문서 범위

이 문서의 결정 범위는 다음과 같다.

- 대상 경로: `AGENTS.md`, `apps/`, `services/`, `specs/`, `evidence/`, `feature-registry/`, 필요 시 `shared-contracts/`, `docs/`
- SpecKit 기본 경로와 Feature ID 기준 산출물 연결 구조
- Feature 전용 계약과 공유 계약 기준의 위치
- 실행 산출물과 문서 산출물의 위치

Feature 등록부의 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역, 검토 조건, PR Gate 판단은 별도 운영 절차 문서에서 다룬다.

이 문서가 정하지 않는 것은 다음과 같다.

- 개별 Feature의 상세 요구사항
- 앱, 서비스 내부 코드 작성 규칙
- 테스트 프레임워크별 작성 방식
- CI 구현 방식
- Feature 운영 순서와 Gate 실패 처리

## 전체 산출물 구조

### 기본 구조

TCI 프로젝트의 산출물은 제품 코드, Feature별 SpecKit 산출물, 완료 근거 문서, Feature 등록부, 필요할 때만 두는 공유 계약 기준, 장기 문서로 나뉜다. Feature ID는 관련 산출물 경로의 기준이다.

SpecKit에서 주로 생성되거나 확정되는 산출물의 관계는 다음처럼 본다.

| 단계 | 주요 산출물 |
| --- | --- |
| `specify`, `clarify` | `spec.md`, 필요한 `checklists/` |
| `plan` | `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, 필요한 `contracts/` |
| `tasks` | `tasks.md` |

저장소 루트 기준 예시는 다음과 같다.

```text
<repo-root>/
├─ AGENTS.md                     # Agent 공통 작업 지침
├─ apps/                         # 사용자가 직접 쓰는 애플리케이션
│  ├─ core-api/                  # 제품 API
│  └─ web-console/               # 웹 콘솔 UI
├─ services/                     # 독립 실행 내부 서비스
│  ├─ analyzer/                  # 분석 작업
│  └─ workers/                   # 비동기 worker
├─ specs/                        # Feature별 SpecKit 산출물
│  └─ <feature-id>/              # Feature ID 단위 작업 공간
│     ├─ spec.md                 # 요구사항과 성공 기준
│     ├─ plan.md                 # 구현 전략과 위험 판단
│     ├─ research.md             # 선택지와 결정 근거
│     ├─ data-model.md           # 도메인 모델과 상태 변화
│     ├─ quickstart.md           # 검증 절차
│     ├─ tasks.md                # 작업 순서와 병렬화 기준
│     ├─ checklists/             # 요구사항 품질 검사
│     └─ contracts/              # Feature 전용 협업 경계
├─ evidence/                     # 완료 근거 문서
│  └─ <feature-id>/
│     └─ verification.md         # 실제 검증 결과
├─ feature-registry/             # Feature별 등록부
│  └─ <feature-id>.yml           # 산출물 경로 연결
├─ shared-contracts/             # 승격된 공유 계약 기준. 필요할 때만 둠
└─ docs/                         # 장기 유지 문서
   ├─ architecture/              # 구조 설명
   └─ adr/                       # 되돌리기 어려운 결정 기록
```

### 책임 분리

| 위치 | 책임 |
| --- | --- |
| `AGENTS.md` | Agent가 저장소 작업을 시작할 때 먼저 읽는 공통 작업 지침 |
| `apps/` | 사용자가 직접 쓰는 애플리케이션 |
| `services/` | 독립 실행 성격이 강한 내부 서비스와 worker |
| `specs/<feature-id>/` | Feature별 요구사항, 설계 판단, 작업 목록, 검증 절차 |
| `specs/<feature-id>/contracts/` | 해당 Feature에서 사용하는 API, 이벤트, 저장 경계, 관측 기준, 예시 데이터 기준 |
| `evidence/<feature-id>/verification.md` | 완료 근거, 실행한 검증, 증거 링크 |
| `feature-registry/<feature-id>.yml` | Feature ID와 산출물 경로 연결 |
| `shared-contracts/` | 이후 Feature가 참조할 승격된 공유 계약 기준 |
| `docs/architecture/` | Feature를 넘어 유지되는 구조 설명 |
| `docs/adr/` | 되돌리기 어려운 결정의 배경과 대안 기록 |

제품 코드는 `apps/`와 `services/`에 둔다. 요구사항, 설계 판단, 검증 절차는 `specs/`에서 추적하고, 완료 근거는 `evidence/`에 남긴다. Feature별 산출물 연결 정보는 `feature-registry/`에 둔다.

Feature 등록부의 구조 문서 기준 최소 연결 예시는 다음과 같다.

```yaml
feature_id: 004-zip-upload-workspace-delete
specs_path: specs/004-zip-upload-workspace-delete
evidence_path: evidence/004-zip-upload-workspace-delete
```

코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역, 검토 조건 같은 운영 필드는 별도 운영 절차 문서에서 다룬다.

## SpecKit 산출물 위치

### 기본 경로 유지

SpecKit 산출물의 기본 작업 공간은 `specs/<feature-id>/`다. SpecKit 경로를 그대로 쓰는 이유는 도구의 기본값을 팀 규칙의 출발점으로 삼기 위해서다.

SpecKit 기본 경로를 유지하면 다음 흐름을 지킬 수 있다.

- SpecKit 템플릿과 명령이 기대하는 상대 경로를 유지한다
- `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md` 사이의 참조 관계를 유지한다
- Agent가 어느 파일부터 읽어야 하는지 명확히 한다
- SpecKit 업그레이드나 템플릿 변경 시 팀이 임의로 바꾼 경로와 충돌할 가능성을 줄인다

### 산출물 매핑

SpecKit 기본 산출물은 `specs/<feature-id>/` 아래에 둔다. TCI가 완료 판단을 위해 추가로 관리하는 산출물은 별도 표로 구분한다.

| 산출물 | 표준 위치 | 역할 |
| --- | --- | --- |
| `spec.md` | `specs/<feature-id>/spec.md` | Feature 요구사항과 성공 기준 |
| `plan.md` | `specs/<feature-id>/plan.md` | 구현 전략과 위험 판단 |
| `research.md` | `specs/<feature-id>/research.md` | 선택지와 결정 근거 |
| `data-model.md` | `specs/<feature-id>/data-model.md` | 도메인 모델과 상태 변화 |
| `quickstart.md` | `specs/<feature-id>/quickstart.md` | 구현 전 정한 검증 절차 |
| `tasks.md` | `specs/<feature-id>/tasks.md` | 작업 순서와 병렬화 기준 |
| `checklists/requirements.md` | `specs/<feature-id>/checklists/requirements.md` | 요구사항 품질 검사 |
| 추가 `checklists/*.md` | `specs/<feature-id>/checklists/` | 보안, UX, API 등 별도 점검 |
| `contracts/` | `specs/<feature-id>/contracts/` | 외부 인터페이스나 병렬 작업 기준 |

TCI에서 추가로 관리하는 구조 산출물은 다음과 같다.

| 산출물 | 표준 위치 | 역할 |
| --- | --- | --- |
| `verification.md` | `evidence/<feature-id>/verification.md` | 실제 검증 결과와 완료 판단 근거 |
| Feature 등록부 | `feature-registry/<feature-id>.yml` | Feature ID와 산출물 경로 연결 |
| 공유 계약 기준 | `shared-contracts/` | 반복 확인된 공유 기준 보관 |

`verification.md` 파일은 구현 중 초안으로 만들 수 있다. 실제 완료 판단에 쓰는 검증 결과와 잔여 위험은 PR 준비 또는 완료 판단 시점에 확정한다.

### 완료 근거 분리 기준

완료 근거는 `specs/<feature-id>/` 아래로 넣지 않고 `evidence/<feature-id>/verification.md`에 둔다. `specs/<feature-id>/`는 요구사항, 설계 판단, 작업 목록, 예정 검증 절차처럼 구현 전에 정하는 기준을 담는다. 반면 `verification.md`는 실제로 실행한 검증, 생략한 검증, 운영자 확인, 잔여 위험처럼 구현 후 완료 판단에 쓰는 결과를 담는다.

이 둘을 같은 `specs/<feature-id>/` 아래에 넣으면 Feature 관련 문서가 한곳에 모인다는 장점은 있지만, 계획 산출물과 실행 결과의 경계가 흐려진다. 시간이 지나면 `specs/`가 SpecKit 작업 기준이 아니라 모든 Feature 기록을 보관하는 저장소처럼 커지고, Harness나 PR Gate가 완료 근거만 따로 조회하기 어려워진다.

따라서 Feature 소유권은 폴더 중첩이 아니라 Feature ID로 연결한다. `specs/<feature-id>/quickstart.md`는 예정 검증 절차를 담고, `evidence/<feature-id>/verification.md`는 실제 실행 결과를 담으며, `feature-registry/<feature-id>.yml`이 두 경로를 연결한다.

## 실행 산출물 위치

### 기본 원칙

SpecKit 산출물과 계약 기준은 제품 코드 밖에 두지만, 실행 산출물은 런타임과 배포를 맡는 앱이나 서비스에 둔다.

런타임이 직접 읽거나 배포되는 파일은 `apps/`나 `services/`에 둔다. 변경 의도와 예정 검증 기준은 `specs/`에 두고, 실제 검증 결과와 완료 근거는 `evidence/`에 둔다.

| 항목 | 기준 위치 | 설명 |
| --- | --- | --- |
| DB 마이그레이션 파일 | `apps/core-api/alembic/versions/` 또는 `services/<owner>/migrations/` | 실제 DB 변경 파일 |
| worker 작업 정의 | `services/workers/` 하위 소유 모듈 | 비동기 작업 실행 코드 |
| 스크립트·설정 파일 | 소유 앱이나 서비스의 `scripts/`, `config/` | 런타임 또는 배포에서 쓰는 파일 |

DB 마이그레이션 파일은 소유 앱이나 서비스의 마이그레이션 경로에 둔다. 여러 구현 단위가 함께 의존하는 저장 경계가 있을 때만 `specs/<feature-id>/contracts/storage-contract.md`를 둔다. 단순 테이블 변경 의도나 마이그레이션 실행 순서는 저장 계약으로 보지 않는다.

## 계약 위치

### 계약 해석 기준

이 문서에서 `contracts/`는 다른 구현 단위가 맞춰야 하는 경계 기준을 뜻한다. 내부 구현 설명이면 계약이 아니고, API, 이벤트, 저장 경계, 관측 기준처럼 다른 작업자나 검증 절차가 의존하면 계약으로 본다.

SpecKit 기본 흐름에서 `contracts/`는 주로 외부 인터페이스나 컴포넌트 경계에 해당하는 산출물이다. API 요청/응답, 엔드포인트, CLI, UI 입력처럼 다른 구현자가 맞춰야 하는 경계가 있을 때 만든다. `storage-contract.md`, `tracing-spans.md`, `contract-examples.md` 같은 파일명은 SpecKit 기본 산출물 이름이 아니라 TCI가 필요할 때 추가하는 확장 산출물이다. 커스텀 스킬, 템플릿 오버라이드, 프리셋 같은 생성 방식은 별도 운영 절차 문서에서 다룬다.

### Feature 전용 계약

Feature 하나에서만 쓰는 경계 기준의 기준 경로는 `specs/<feature-id>/contracts/`다. 프론트엔드와 백엔드가 같은 기능을 병렬 개발할 때도 이 경로를 기준으로 맞춘다.

Feature 전용 `contracts/`에는 기본적으로 하위 디렉터리를 만들지 않고 파일을 둔다. SpecKit이 만든 계약 파일명을 우선 유지하고, 추가 파일이 필요할 때도 파일명만으로 계약의 종류를 알 수 있게 한다. 한 계약 유형의 파일이 여러 개로 커지거나 하위 자료가 많아질 때만 예외적으로 하위 디렉터리를 만든다.

아래 파일은 가능한 예시이지 필수 목록이 아니다. `openapi.yaml`이나 `events.md`처럼 인터페이스 경계가 명확한 파일은 SpecKit contracts의 기본 의미와 가깝다. `storage-contract.md`, `tracing-spans.md`, `contract-examples.md`는 TCI가 병렬 개발과 검증 기준을 더 명확히 하려고 필요할 때 추가하는 확장 산출물이다.

```text
specs/<feature-id>/contracts/
├─ openapi.yaml
├─ events.md
├─ storage-contract.md
├─ tracing-spans.md
└─ contract-examples.md
```

파일명은 SpecKit이 생성한 이름을 우선한다. 팀이 직접 추가하는 계약 파일은 다음 기준을 참고하되, 이 표의 이름을 고정 규칙으로 보지 않는다.

| 계약 유형 | 의미 | 파일명 예시 | 생성 조건 |
| --- | --- | --- | --- |
| API 계약 | 요청, 응답, 오류 형식, 필수 필드 기준 | `openapi.yaml` | API 경계를 다른 구현 단위가 맞춰야 할 때 |
| 이벤트 계약 | 이벤트 본문, 메시지 구조, 라우팅 메타데이터 기준 | `events.md` | worker나 분석 서비스가 같은 이벤트를 처리할 때 |
| 저장 계약 | 여러 구현 단위가 함께 의존하는 저장 경계, 불변식, 하위 호환 기준 | `storage-contract.md` | 단순 테이블 변경이 아니라 공유 저장 경계가 있을 때 |
| 관측 기준 | trace/span 이름과 필수 속성 기준 | `tracing-spans.md` | 장애나 지연을 여러 컴포넌트 기준으로 추적해야 할 때 |
| 계약 예시 | 계약을 이해하고 검증하기 위한 대표 입력과 출력 | `contract-examples.md` | 계약 검증용 예시가 병렬 구현 기준이 될 때 |

`data-model.md`는 Feature의 도메인 엔티티, 필드, 관계, 상태 전이, 검증 규칙을 설명한다. 저장 계약은 그중 다른 컴포넌트나 병렬 작업자가 직접 의존하는 저장 경계만 따로 고정한다. 단순한 테이블 변경 이유, 마이그레이션 작성 의도, 데이터 보정이나 되돌리기 순서는 계약보다 구현 계획과 운영 절차에 가깝다.

### 공유 계약

`shared-contracts/`는 일반 Feature 작업에서 매번 만들거나 갱신하는 위치가 아니다. 새 Feature는 먼저 `specs/<feature-id>/contracts/`에 Feature 전용 계약을 둔다.

공유 계약은 다음 규칙으로 다룬다.

- 여러 Feature에서 같은 API, 이벤트, 저장, 관측 기준이 반복될 때 후보로 본다
- 기존 Feature 전용 계약은 이동하거나 대체하지 않고 당시 판단 기록으로 보존한다
- 새 Feature가 공유 기준을 따라야 하면 Feature 산출물이나 Feature 등록부에서 `shared-contracts/`를 명시적으로 참조한다
- 새 Feature가 공유 기준을 따르지 못하면 Feature 전용 계약이나 Feature 등록부에 예외를 남긴다
- `shared-contracts/`는 비워 둘 수 있지만 구조에서 제거하지 않는다

```text
shared-contracts/
├─ api/
├─ events/
├─ mcp/
├─ storage/
├─ tracing/
└─ examples/
```

공유 계약의 하위 디렉터리 역할은 다음과 같다.

| 위치 | 역할 | 대표 파일 예시 |
| --- | --- | --- |
| `api/` | 공통 오류 응답, 인증 헤더, 페이지 나누기 기준 | `error-response.md` |
| `events/` | 여러 worker와 분석 서비스가 함께 쓰는 이벤트 공통 구조와 메시지 규칙 | `event-envelope.md` |
| `mcp/` | 외부 Agent에게 공통으로 제공할 컨텍스트 묶음과 도구 입출력 기준 | `tool-contracts.md` |
| `storage/` | 여러 Feature가 공통으로 따르는 저장 경계, 산출물 저장 위치, 보존 기간 기준 | `artifact-retention.md` |
| `tracing/` | 여러 Feature가 공유하는 trace 속성과 이름 기준 | `trace-attributes.md` |
| `examples/` | 여러 Feature가 함께 쓰는 공통 검증용 예시 데이터 | `contract-examples.md` |
