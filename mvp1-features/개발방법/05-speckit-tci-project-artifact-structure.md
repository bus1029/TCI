# SpecKit 기반 TCI 프로젝트 산출물 구조

## 문서 목적

이 문서는 SpecKit 기반 TCI 프로젝트에서 주요 산출물이 어디에 위치하고, 각 위치가 어떤 책임을 갖는지 정리한다.

이 문서에서 쓰는 주요 용어는 다음처럼 해석한다.

| 용어 | 의미 |
| --- | --- |
| Feature ID | `specs/`, `evidence/`, `feature-registry/`를 연결하는 기능 고유 이름. `NNN-kebab-case-topic` 형식이며 예시는 `004-zip-upload-workspace-delete` |
| Feature 등록부 | Feature별 산출물 경로와 범위 정보를 연결하는 `feature-registry/<feature-id>.yml` |
| 검증 절차 문서 | 구현자가 실행하거나 사람이 따라 할 예정 검증 절차를 담는 `specs/<feature-id>/quickstart.md` |
| 완료 근거 문서 | 실제로 실행한 검증과 판단 근거를 남기는 `evidence/<feature-id>/verification.md` |

## 문서 범위

이 문서의 결정 범위는 다음과 같다.

- 대상 경로: `AGENTS.md`, `apps/`, `services/`, `specs/`, `evidence/`, `feature-registry/`, `boundary-contracts/`, `docs/`
- SpecKit 기본 경로와 Feature ID 기준 산출물 연결 구조
- Feature 전용 계약과 공유 계약의 위치
- 실행 산출물과 문서 산출물의 위치

이 문서가 정하지 않는 것은 다음과 같다.

- 개별 Feature의 상세 요구사항
- 앱, 서비스 내부 코드 작성 규칙
- 테스트 프레임워크별 작성 방식
- CI 구현 방식

## 전체 산출물 구조

### 기본 구조

TCI 프로젝트의 산출물은 제품 코드, Feature별 SpecKit 산출물, 완료 근거 문서, Feature 등록부, 공유 경계 기준, 장기 문서로 나뉜다.

Feature ID는 관련 산출물 경로의 기준이다.

SpecKit 단계와 주요 산출물의 관계는 다음처럼 본다.

| 단계 | 주요 산출물 |
| --- | --- |
| `specify`, `clarify` | `spec.md`, `checklists/` |
| `plan` | `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, 필요한 `contracts/` |
| `tasks` | `tasks.md` |
| `analyze` | `spec.md`, `plan.md`, `tasks.md` 사이의 불일치 점검 |

```text
tci-platform/
├─ AGENTS.md                     # Agent 공통 작업 지침
├─ apps/                         # 사용자와 직접 맞닿는 애플리케이션
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
│     ├─ quickstart.md           # 예정 검증 절차
│     ├─ tasks.md                # 작업 순서와 병렬화 기준
│     ├─ checklists/             # 요구사항 품질 검사
│     └─ contracts/              # Feature 전용 협업 경계
├─ evidence/                     # 완료 근거 문서
│  └─ <feature-id>/
│     └─ verification.md         # 실제 검증 결과
├─ feature-registry/             # Feature별 등록부
│  └─ <feature-id>.yml           # 산출물 경로와 범위 정보 연결
├─ boundary-contracts/           # Feature를 넘는 공유 경계 기준
└─ docs/                         # 장기 유지 문서
   ├─ architecture/              # 구조 설명
   └─ adr/                       # 되돌리기 어려운 결정 기록
```

### 책임 분리

| 위치 | 책임 |
| --- | --- |
| `AGENTS.md` | Agent가 repo 진입 시 먼저 읽는 공통 작업 지침 |
| `apps/` | 사용자와 직접 맞닿는 애플리케이션 |
| `services/` | 독립 실행 성격이 강한 내부 서비스와 worker |
| `specs/<feature-id>/` | Feature별 요구사항, 설계 판단, 작업 목록, 검증 절차 |
| `specs/<feature-id>/contracts/` | 해당 Feature에서 사용하는 API, 이벤트, 저장 경계, 관측 기준, 예시 데이터 기준 |
| `evidence/<feature-id>/verification.md` | 완료 근거, 실행한 검증, 증거 링크 |
| `feature-registry/<feature-id>.yml` | Feature ID, 산출물 경로, 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역 연결 |
| `boundary-contracts/` | 여러 Feature가 공유하는 장기 경계 기준 |
| `docs/architecture/` | Feature를 넘어 유지되는 구조 설명 |
| `docs/adr/` | 되돌리기 어려운 결정의 배경과 대안 기록 |

제품 코드는 `apps/`와 `services/`에 둔다. 요구사항, 설계 판단, 검증 절차는 `specs/`에서 추적한다. 완료 근거는 `evidence/`에 남긴다. Feature별 산출물 연결 정보는 `feature-registry/`에 둔다. 루트 `AGENTS.md`는 Agent가 이 repo에서 따라야 할 공통 작업 지침을 제공한다.

### 루트 AGENTS.md

루트 `AGENTS.md`에는 오래 유지될 작업 원칙만 둔다. 개별 Feature 요구사항, 임시 작업 메모, 특정 PR의 완료 근거는 `AGENTS.md`에 넣지 않고 `specs/`, `evidence/`에 남긴다.

## SpecKit 산출물 위치

### 기본 경로 유지

SpecKit 산출물은 `specs/<feature-id>/`를 정식 작업 공간으로 둔다. SpecKit 경로를 그대로 쓰는 이유는 도구의 기본값을 팀 규칙의 출발점으로 삼기 위해서다.

SpecKit 기본 경로를 유지하면 다음 이점이 있다.

- SpecKit 템플릿과 명령이 기대하는 상대 경로 유지
- `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md` 사이의 참조 관계 유지
- Agent가 읽어야 할 시작점 명확화
- SpecKit 업그레이드나 템플릿 변경 시 팀 커스텀 경로와 충돌 가능성 감소

### 산출물 매핑

| 산출물 | 표준 위치 | 필요성 | 생성 시점 |
| --- | --- | --- | --- |
| `spec.md` | `specs/<feature-id>/spec.md` | 필수 | Feature 요구사항 정리 시 |
| `plan.md` | `specs/<feature-id>/plan.md` | 필수 | 구현 전략 결정 시 |
| `research.md` | `specs/<feature-id>/research.md` | 조건부 | 불확실한 선택지 검토 시 |
| `data-model.md` | `specs/<feature-id>/data-model.md` | 조건부 | 도메인 모델이나 상태 변화가 필요할 때 |
| `quickstart.md` | `specs/<feature-id>/quickstart.md` | 필수 | 검증 절차 결정 시 |
| `tasks.md` | `specs/<feature-id>/tasks.md` | 필수 | 구현 작업 분해 시 |
| `checklists/` | `specs/<feature-id>/checklists/` | 조건부 | 요구사항 품질 검사 필요 시 |
| `contracts/` | `specs/<feature-id>/contracts/` | 조건부 | 협업 경계 문서화 필요 시 |
| `verification.md` | `evidence/<feature-id>/verification.md` | 조건부 | 구현 중 초안 또는 PR 준비 시 |

## 계약 위치

### 계약 해석 기준

이 문서에서 `contracts/`는 Feature를 병렬로 구현하거나 검증할 때 여러 작업자가 함께 의존하는 경계 기준을 뜻한다. API 요청/응답뿐 아니라 이벤트 본문, 저장 경계, trace/span 의미, 검증용 예시도 해당 Feature의 구현과 검증을 깨뜨릴 수 있으면 계약으로 다룬다.

TCI에서 `contracts/`를 넓게 잡는 이유는 Agent 병렬 개발 때문이다. 프론트엔드, 백엔드, worker, analyzer, 검증 담당 Agent가 같은 Feature를 나눠 구현하려면 “서로가 무엇을 믿고 작업해도 되는가”가 먼저 고정되어야 한다. 이 기준이 API에만 있으면 저장 경계, 이벤트 의미, 관측 기준, 검증 예시가 늦게 흔들려 병렬 작업이 깨질 수 있다.

업계에서도 계약은 API 요청/응답에만 머물지 않는다. OpenAPI와 Pact는 API 소비자와 제공자 사이의 규약을 다루고, AsyncAPI와 CloudEvents는 이벤트 메시지 형식을 다룬다. dbt model contracts와 Protocol Buffers는 하위 사용자가 의존하는 데이터 구조를 안정적으로 다루며, OpenTelemetry semantic conventions는 trace/span 이름과 속성 의미를 표준화한다.

다만 모든 내부 구현 세부사항이 계약은 아니다. 계약은 다른 작업자, 다른 컴포넌트, 다른 Feature, 검증 절차가 의존하는 경계 기준일 때만 성립한다.

| 구분 | 업계에서 가까운 사례 | TCI에서의 의미 |
| --- | --- | --- |
| API 계약 | OpenAPI, Pact | 요청, 응답, 오류 형식, 필수 필드 기준 |
| 이벤트 계약 | AsyncAPI, CloudEvents | 이벤트 본문, 메시지 공통 구조, 라우팅에 필요한 메타데이터 기준 |
| 저장 계약 | dbt model contracts, Protocol Buffers | Feature가 의존하는 저장 형태, migration 의도, 하위 호환 기준 |
| 관측 계약 | OpenTelemetry semantic conventions | trace/span 이름과 필수 속성 기준 |
| 예시와 검증용 데이터 | OpenAPI examples, 테스트 데이터 | 계약을 이해하고 검증하기 위한 대표 입력과 출력 |

### Feature 전용 계약

Feature 하나에서만 쓰는 경계 기준은 `specs/<feature-id>/contracts/`를 기준 위치로 둔다. 프론트엔드와 백엔드가 같은 기능을 병렬 개발할 때도 이 경로를 기준으로 맞춘다.

Feature 전용 `contracts/`는 기본적으로 파일을 바로 둔다. SpecKit이 만든 계약 파일명을 우선 유지하고, 추가 파일이 필요할 때도 파일명만으로 계약 성격을 알 수 있게 한다. 한 계약 유형의 파일이 여러 개로 커지거나 하위 자료가 많아질 때만 예외적으로 하위 디렉터리를 만든다.

```text
specs/<feature-id>/contracts/
├─ openapi.yaml                  # 예: SpecKit이 만든 API 계약 파일
├─ events.md                     # 필요 시 이벤트 계약
├─ storage-migration-intent.md   # 필요 시 저장 계약
├─ tracing-spans.md              # 필요 시 관측 계약
└─ contract-examples.md          # 필요 시 검증용 예시 데이터
```

파일명은 SpecKit이 생성한 이름을 우선한다. 팀이 직접 추가하는 계약 파일은 다음 기준을 참고하되, 이 표의 이름을 고정 규칙으로 보지 않는다.

| 계약 유형 | 파일명 예시 | 사용 기준 |
| --- | --- | --- |
| API 계약 | `openapi.yaml` | Feature 전용 API 요청, 응답, 오류 응답 형식 기준 |
| 이벤트 계약 | `events.md` | Feature 전용 이벤트 본문과 메시지 기준 |
| 저장 계약 | `storage-migration-intent.md` | 해당 Feature가 의존하는 저장 경계, migration 의도, 하위 호환 기준 |
| 관측 계약 | `tracing-spans.md` | Feature 전용 trace/span 이름과 속성 기준 |
| 예시와 검증용 데이터 | `contract-examples.md` | Feature 전용 계약을 이해하고 검증하기 위한 예시와 검증용 데이터 |

### 공유 계약

여러 Feature가 함께 쓰는 장기 기준은 `boundary-contracts/`로 올린다. 이 위치는 Feature별 계약 복사본을 두는 곳이 아니라 제품 전체에서 반복 적용할 기준을 두는 곳이다.

```text
boundary-contracts/
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
| `events/` | 여러 worker와 analyzer가 함께 쓰는 이벤트 공통 구조와 메시지 규칙 | `event-envelope.md` |
| `mcp/` | 외부 Agent에게 공통으로 제공할 컨텍스트 묶음과 도구 입출력 기준 | `tool-contracts.md` |
| `storage/` | 여러 Feature가 공통으로 따르는 저장 정책, 산출물 저장 위치, 보존 기간 기준 | `artifact-retention.md` |
| `tracing/` | 여러 Feature가 공유하는 trace 속성과 이름 기준 | `trace-attributes.md` |
| `examples/` | 여러 Feature가 함께 쓰는 공통 검증용 예시 데이터 | `contract-examples.md` |

## 실행 산출물 위치

### 기본 원칙

SpecKit 산출물과 계약 기준은 제품 코드 밖에 두지만, 실행 산출물은 소유 주체가 정해진 앱 또는 서비스 쪽에 둔다. 실행 산출물은 실제 런타임과 배포 책임을 가진 코드베이스에 있어야 한다.

실행 파일과 설명 또는 검증 산출물은 분리해서 둔다. 아래는 대표 위치이며, 상세 위치는 소유 앱이나 서비스의 규칙을 따른다.

| 분류 | 항목 | 기준 위치 | 성격 |
| --- | --- | --- | --- |
| 실행 | DB migration | `apps/core-api/alembic/versions/` 또는 `services/<owner>/migrations/` | 실제 실행 산출물 |
| 실행 | worker job 정의 | `services/workers/` 하위 소유 모듈 | 실제 실행 산출물 |
| 실행 | 스크립트 또는 설정 | 소유 앱이나 서비스의 `scripts/`, `config/` | 실제 실행 산출물 |
| 설명/검증 | DB migration 의도 | `specs/<feature-id>/contracts/storage-migration-intent.md` | 실행 산출물의 의도와 설명 기준 |
| 설명/검증 | Feature 전용 검증용 예시 데이터 | `specs/<feature-id>/contracts/contract-examples.md` | 테스트가 참조하는 계약 기준 |
| 설명/검증 | 검증 결과 | `evidence/<feature-id>/verification.md` | 완료 근거 |

### DB migration 의도 파일

Feature 전용 저장 계약은 해당 Feature가 의존하는 저장 경계를 설명한다. DB migration은 Feature 단위로 완전히 나누기 어렵고, 실제 실행 순서와 관리 책임이 DB 책임자에게 묶인다. 따라서 `specs/<feature-id>/contracts/storage-migration-intent.md`에는 실행 migration 파일이 아니라 저장 규약, 테이블 변경 의도, 하위 호환 기준, 데이터 보존 기준을 둔다.

`storage-migration-intent.md`에는 다음 내용을 적는다.

- 변경 의도
- 추가, 변경, 제거할 테이블과 컬럼
- 실제 migration 파일 위치
- backfill 또는 기본값 처리
- API와 사용처 호환성 기준
- DB 책임자

Feature는 DB 변경 이유와 관련 저장 경계를 설명하고, DB 책임자는 실제 migration을 관리한다.
