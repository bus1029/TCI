# SpecKit 기반 TCI 프로젝트 산출물 구조

## 문서 목적

이 문서는 SpecKit 기반 TCI 프로젝트에서 주요 산출물이 어디에 위치하고, 각 위치가 어떤 책임을 갖는지 정리한다.

이 문서에서는 주요 용어를 다음 의미로 쓴다.

| 용어 | 의미 |
| --- | --- |
| Feature | SpecKit으로 관리하는 완결 기능 단위 |
| Feature ID | `specs/`, `evidence/`, `feature-registry/`를 연결하는 기능 고유 이름. `NNN-kebab-case-topic` 형식이며 예시는 `004-zip-upload-workspace-delete` |
| Feature 등록부 | Feature별 산출물 경로와 범위 정보를 연결하는 `feature-registry/<feature-id>.yml` |
| Agent | SpecKit 산출물과 저장소 지침을 읽고 작업을 수행하는 AI 작업자 |
| worker | 비동기 작업을 실행하는 내부 프로세스 또는 서비스 |
| analyzer | 저장소, 코드, 산출물을 분석하는 내부 서비스 |
| 검증 절차 문서 | 구현자나 운영자가 따라 할 검증 절차를 담는 `specs/<feature-id>/quickstart.md` |
| 완료 근거 문서 | 실제로 실행한 검증과 판단 근거를 남기는 `evidence/<feature-id>/verification.md` |
| DB 책임자 | 소유 앱이나 서비스의 DB 변경을 검토하고 migration 실행 순서를 관리하는 담당자 |

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

TCI 프로젝트의 산출물은 제품 코드, Feature별 SpecKit 산출물, 완료 근거 문서, Feature 등록부, 공유 경계 기준, 장기 문서로 나뉜다. Feature ID는 관련 산출물 경로의 기준이다.

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
│  └─ <feature-id>.yml           # 산출물 경로와 범위 정보 연결
├─ boundary-contracts/           # Feature를 넘는 공유 경계 기준
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
| `feature-registry/<feature-id>.yml` | Feature ID, 산출물 경로, 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역 연결 |
| `boundary-contracts/` | 여러 Feature가 공유하는 장기 경계 기준 |
| `docs/architecture/` | Feature를 넘어 유지되는 구조 설명 |
| `docs/adr/` | 되돌리기 어려운 결정의 배경과 대안 기록 |

제품 코드는 `apps/`와 `services/`에 둔다. 요구사항, 설계 판단, 검증 절차는 `specs/`에서 추적한다. 완료 근거는 `evidence/`에 남긴다. Feature별 산출물 연결 정보는 `feature-registry/`에 둔다. 루트 `AGENTS.md`에는 오래 유지될 작업 원칙만 두고, 개별 Feature 요구사항, 임시 작업 메모, 특정 PR의 완료 근거는 `specs/`, `evidence/`에 남긴다.

## SpecKit 산출물 위치

### 기본 경로 유지

SpecKit 산출물은 `specs/<feature-id>/`를 정식 작업 공간으로 둔다. SpecKit 경로를 그대로 쓰는 이유는 도구의 기본값을 팀 규칙의 출발점으로 삼기 위해서다.

SpecKit 기본 경로를 유지하면 다음 흐름을 지킬 수 있다.

- SpecKit 템플릿과 명령이 기대하는 상대 경로를 유지
- `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md` 사이의 참조 관계를 유지
- Agent가 어느 파일부터 읽어야 하는지 명확해짐
- SpecKit 업그레이드나 템플릿 변경 시 팀이 임의로 바꾼 경로와 충돌할 가능성이 줄어듦

### 산출물 매핑

SpecKit 기본 산출물은 `specs/<feature-id>/` 아래에 둔다. TCI가 완료 판단을 위해 추가로 관리하는 산출물은 별도 표로 구분한다.

| 산출물 | 표준 위치 | 필요성 | 생성 시점 | 비고 |
| --- | --- | --- | --- | --- |
| `spec.md` | `specs/<feature-id>/spec.md` | 필수 | Feature 요구사항 정리 시 | Feature 범위와 성공 기준 |
| `plan.md` | `specs/<feature-id>/plan.md` | 필수 | 구현 전략 결정 시 | 기술 선택과 구현 방향 |
| `research.md` | `specs/<feature-id>/research.md` | 기본 생성 | 기술 선택, 불확실성, 대안 검토 시 | 검토할 선택지가 적으면 짧게 남김 |
| `data-model.md` | `specs/<feature-id>/data-model.md` | 기본 생성 | 도메인 모델이나 상태 변화 검토 시 | 데이터 모델이 없으면 N/A로 정리 |
| `quickstart.md` | `specs/<feature-id>/quickstart.md` | 필수 | 검증 절차 결정 시 | 구현 전 정한 검증 절차 |
| `tasks.md` | `specs/<feature-id>/tasks.md` | 필수 | 구현 작업 분해 시 | 실행 가능한 작업 목록 |
| `checklists/requirements.md` | `specs/<feature-id>/checklists/requirements.md` | 필수 | Feature 요구사항 품질 검사 시 | 기본 요구사항 체크리스트 |
| 추가 `checklists/*.md` | `specs/<feature-id>/checklists/` | 조건부 | 특정 영역의 요구사항 품질 검사 필요 시 | 보안, UX, API 등 별도 점검이 필요할 때 |
| `contracts/` | `specs/<feature-id>/contracts/` | 조건부 | 협업 경계 문서화 필요 시 | 외부 인터페이스나 병렬 작업 기준이 필요할 때 |

TCI에서 추가로 관리하는 산출물은 다음과 같다.

| 산출물 | 표준 위치 | 필요성 | 생성 시점 | 비고 |
| --- | --- | --- | --- | --- |
| `verification.md` | `evidence/<feature-id>/verification.md` | 필수 | 구현 중 초안 또는 PR 준비 시 | 완료 판단에 쓰는 문서 |

## 계약 위치

### 계약 해석 기준

이 문서에서 `contracts/`는 여러 작업자가 같은 Feature를 병렬로 구현하거나 검증할 때 함께 믿고 따르는 경계 기준을 뜻한다. Feature 하나에서만 쓰면 `specs/<feature-id>/contracts/`에 두고, 여러 Feature가 반복해서 의존하면 `boundary-contracts/`로 올린다.

TCI에서 계약을 API 요청/응답에만 한정하지 않는 이유는 Agent 병렬 개발 때문이다. 프론트엔드, 백엔드, worker, analyzer, 검증 담당 Agent가 같은 Feature를 나눠 구현하려면 API, 이벤트, 저장 경계, 관측 기준, 검증 예시가 먼저 고정되어야 한다. 여기서 trace/span은 작업 흐름을 추적하기 위해 남기는 관측 구간과 그 이름을 뜻한다.

다만 모든 내부 구현 세부사항이 계약은 아니다. 다른 작업자, 다른 컴포넌트, 다른 Feature, 검증 절차가 의존하는 기준일 때만 계약으로 다룬다.

| 구분 | 업계에서 가까운 사례 | TCI에서의 의미 |
| --- | --- | --- |
| API 계약 | OpenAPI, Pact | 요청, 응답, 오류 형식, 필수 필드 기준 |
| 이벤트 계약 | AsyncAPI, CloudEvents | 이벤트 본문, 메시지 공통 구조, 라우팅에 필요한 메타데이터 기준 |
| 저장 계약 | dbt model contracts, Protocol Buffers | Feature가 의존하는 저장 형태, migration 의도, 하위 호환 기준 |
| 관측 계약 | OpenTelemetry semantic conventions | trace/span 이름과 필수 속성 기준 |
| 예시와 검증용 데이터 | OpenAPI examples, 테스트 데이터 | 계약을 이해하고 검증하기 위한 대표 입력과 출력 |

### Feature 전용 계약

Feature 하나에서만 쓰는 경계 기준은 `specs/<feature-id>/contracts/`를 기준 위치로 둔다. 프론트엔드와 백엔드가 같은 기능을 병렬 개발할 때도 이 경로를 기준으로 맞춘다.

Feature 전용 `contracts/`에는 기본적으로 하위 디렉터리를 만들지 않고 파일을 둔다. SpecKit이 만든 계약 파일명을 우선 유지하고, 추가 파일이 필요할 때도 파일명만으로 계약의 종류를 알 수 있게 한다. 한 계약 유형의 파일이 여러 개로 커지거나 하위 자료가 많아질 때만 예외적으로 하위 디렉터리를 만든다.

```text
specs/<feature-id>/contracts/
├─ openapi.yaml
├─ events.md
├─ storage-migration-intent.md
├─ tracing-spans.md
└─ contract-examples.md
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

여러 Feature가 함께 쓰는 장기 기준은 `boundary-contracts/`로 올린다. `boundary-contracts/`에는 Feature별 계약 복사본이 아니라 제품 전체에 반복 적용할 기준을 둔다.

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

SpecKit 산출물과 계약 기준은 제품 코드 밖에 두지만, 실행 산출물은 런타임과 배포를 맡는 앱이나 서비스에 둔다.

런타임이 직접 읽거나 배포되는 파일은 `apps/`나 `services/`에 두고, 의도와 검증 기준을 설명하는 문서는 `specs/`와 `evidence/`에 둔다. 아래는 대표 실행 파일 위치이며, 상세 위치는 소유 앱이나 서비스의 규칙을 따른다.

| 분류 | 항목 | 기준 위치 | 성격 |
| --- | --- | --- | --- |
| 실행 | DB migration | `apps/core-api/alembic/versions/` 또는 `services/<owner>/migrations/` | 실제 실행 산출물 |
| 실행 | worker job 정의 | `services/workers/` 하위 소유 모듈 | 실제 실행 산출물 |
| 실행 | 스크립트 또는 설정 | 소유 앱이나 서비스의 `scripts/`, `config/` | 실제 실행 산출물 |

DB migration 의도, Feature 전용 검증용 예시 데이터, 검증 결과처럼 실행 파일의 의미나 결과를 설명하는 문서는 앞에서 정한 `specs/<feature-id>/contracts/`와 `evidence/<feature-id>/verification.md`에 둔다.

### DB migration 의도 파일

Feature 전용 저장 계약은 해당 Feature가 의존하는 저장 경계를 설명한다. DB migration은 Feature 단위로 완전히 나누기 어렵고, 실제 migration은 DB 책임자가 실행 순서와 관리 방식을 정한다. 따라서 `specs/<feature-id>/contracts/storage-migration-intent.md`에는 실행 migration 파일이 아니라 저장 규약, 테이블 변경 의도, 하위 호환 기준, 데이터 보존 기준을 둔다.

`storage-migration-intent.md`에는 다음 내용을 적는다.

- 변경 의도
- 추가, 변경, 제거할 테이블과 컬럼
- 실제 migration 파일 위치
- backfill 또는 기본값 처리
- API와 사용처 호환성 기준
- DB 책임자

Feature 문서에는 DB 변경 이유와 관련 저장 경계를 적고, DB 책임자는 실제 migration을 관리한다.
