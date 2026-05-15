# TCI 소스코드 프로젝트 구조

## 문서 목적

이 문서는 TCI 제품 소스코드의 상위 디렉터리 구조를 정한다.

앞선 문서가 `specs/`, `evidence/`, `feature-registry/`, `harness/`, `shared-contracts/` 같은 산출물과 Harness 구조를 다뤘다면, 이 문서는 실제 실행되는 제품 코드가 어디에 놓여야 하는지를 다룬다.

이 문서는 하위 구현 디렉터리까지 고정하지 않는다. `src/`, `domain/`, `application/`, `connectors/`, `workers/`, `prompts/` 같은 내부 구조는 실제 Feature를 개발하면서 기술 스택, 프레임워크, 테스트 방식에 맞춰 정한다. 지금 고정할 것은 Agent와 팀원이 같은 기준으로 `code_write_scope`를 잡을 수 있는 상위 경계다.

## 핵심 결정

TCI의 제품 소스코드는 `apps/`, `services/`, 필요 시 `packages/`를 기준으로 나눈다.

```text
tci-platform/
├─ apps/
│  ├─ core-api/
│  └─ web-console/
├─ services/
│  ├─ collection/
│  ├─ processing/
│  ├─ analysis/
│  ├─ knowledge/
│  ├─ assistant/
│  └─ workflow/
├─ packages/                     # 필요할 때만 둠
├─ specs/
├─ evidence/
├─ feature-registry/
├─ shared-contracts/
├─ harness/
└─ docs/
```

`apps/`와 `services/`만 제품 실행 코드의 기본 위치다. `packages/`는 두 개 이상의 app/service가 실제로 같은 코드를 공유할 때만 만든다. `specs/`, `evidence/`, `feature-registry/`, `shared-contracts/`, `harness/`, `docs/`는 앞선 문서에서 정한 산출물과 운영 기준이다.

팀장님 초안의 `workers/` 목록은 기능 분류로는 유효하지만, 루트 디렉터리의 1차 기준으로 바로 쓰지는 않는다. `ingestion-worker`, `analysis-worker`, `cpg-worker`, `impact-worker`, `knowledge-worker`, `llm-worker`, `automation-worker`는 제품 책임보다 실행 프로세스 이름에 가깝다. MVP에서는 먼저 `services/`로 제품 책임 경계를 잡고, worker는 해당 서비스를 구현하는 실행 방식으로 둔다.

## 판단 기준

### 외부 사례에서 얻은 기준

모노레포 도구들은 디렉터리 이름 자체보다 배포 단위와 공유 코드의 경계를 분명히 하라고 권한다. Nx는 함께 변경되는 범위별 프로젝트 그룹화와 shared 영역 분리를 설명하고, Turborepo도 `apps/`에는 배포되는 애플리케이션을, 공유 코드는 library package로 두는 방식을 제시한다.

Agent 기반 개발에서도 같은 기준을 적용할 수 있다. OpenAI Agents SDK와 LangChain/LangGraph는 여러 전문 agent, handoff, guardrail을 다루지만, 제품 저장소의 루트 구조를 agent 이름별로 나누라고 보지는 않는다. 제품 코드에서는 agent 역할보다 소유 경계, 입력과 출력 계약, 검증 가능성이 더 오래 유지되는 기준이다.

TCI에 적용할 기준은 다음과 같다.

- 외부 요청을 받거나 사용자에게 노출되는 실행 진입점은 `apps/`에 둔다
- 오래 유지될 내부 제품 능력은 `services/`에 둔다
- 공유 코드는 두 번째 실제 사용처가 생겼을 때 `packages/`로 승격한다
- worker는 루트 제품 경계가 아니라 특정 service의 실행 방식으로 본다
- agent, prompt, guardrail, context bundle 기준은 제품 코드 안에 흩뿌리지 않고 Harness와 계약 문서에서 먼저 관리한다

### TCI 요구사항에서 보이는 경계

`tci-final-feature-list.md`의 기능은 단순한 backend/frontend 분리가 아니라 데이터가 이동하는 파이프라인이다.

| 흐름 | 주요 기능 |
| --- | --- |
| 수집 | Git 저장소, 티켓, 문서, 파일 업로드, IDE 변경분 수집 |
| 처리 | 스냅샷 준비, 정규화, CPG 생성, 임베딩, 원시 패턴 식별 |
| 분석 | 구조 분석, 의존성 분석, 데이터 흐름, 비즈니스 규칙, 영향도, 리스크, 테스트 영향 |
| 지식화 | 코드 속성 그래프, 지식 모델, 용어 사전, 검색 인덱스, 규칙 카탈로그 |
| 질의 | 대화형 Q&A, 근거 제공, 컨텍스트 구성, 세션과 권한 관리 |
| 자동화 | PR 본문, 리스크 리포트, CI 연동, Policy Gate, 문서 스튜디오, 리포트 발송 |
| 사용자 화면 | 웹 콘솔, 분석 탐색, Q&A, 리포트, 관리 화면 |

이 흐름을 `apps/core-api` 하나에 모두 넣으면 초반 구현은 빠르지만 수집, 처리, 분석, 지식, 질의, 자동화 책임이 한곳에 섞인다. 반대로 처음부터 루트 `workers/`를 여러 개 만들면 실행기는 보이지만 제품 책임 경계가 흐려진다.

따라서 TCI에는 중간 형태가 맞다. 상위 구조에서는 제품 책임을 `services/`로 나누고, 실제 배포 단위와 내부 하위 구조는 Feature 개발이 진행되면서 필요에 따라 정한다.

## 상위 디렉터리 책임

| 위치 | 책임 | 기준 |
| --- | --- | --- |
| `apps/` | 사용자, 외부 시스템, 외부 채널이 붙는 실행 진입점 | 웹, API, 실시간 연결처럼 외부 요청을 받는 코드 |
| `apps/core-api/` | 제품 API, 인증/인가 경계, 요청 조정, 사용자에게 반환할 projection | 외부 API의 안정적인 진입점 |
| `apps/web-console/` | TCI 웹 UI | 사용자 화면과 상호작용 |
| `services/` | 제품 내부 능력과 장기 도메인 경계 | 수집, 처리, 분석, 지식, 질의, 자동화처럼 내부 책임이 있는 코드 |
| `packages/` | 여러 app/service가 공유하는 순수 코드 | 실제 재사용과 독립 테스트가 확인된 코드 |

`core-api`는 모든 상태의 주인이 아니라 외부 API와 사용자 흐름의 조정자다. 상태와 처리 규칙은 가능한 한 해당 `services/` 경계에 둔다. 초기 구현에서 같은 프로세스나 같은 DB를 쓰더라도 코드 책임은 상위 경계 기준으로 분리한다.

## `services/` 기준

### 권장 서비스 경계

`services/`의 1차 경계는 TCI 기능 흐름에 맞춰 다음처럼 둔다.

| 서비스 | 책임 |
| --- | --- |
| `services/collection/` | Git, 티켓, 문서, 업로드, IDE 변경분 수집과 동기화 |
| `services/processing/` | 수집 데이터 정규화, 스냅샷 준비, CPG 생성, 임베딩, 적재 전 처리 |
| `services/analysis/` | 구조, 의존성, 데이터 흐름, 비즈니스 규칙, 영향도, 리스크, 테스트 영향 분석 |
| `services/knowledge/` | 지식 모델, graph/vector/search/object store 접근 경계, 보존 정책 |
| `services/assistant/` | 대화형 질의, 컨텍스트 구성, LLM 응답, 답변 근거와 세션 이력 |
| `services/workflow/` | PR 자동화, CI 연동, Policy Gate, Docs Studio, 리포트, 알림, MCP/API Gateway |

이 이름은 하위 구현 구조를 강제하지 않는다. 예를 들어 `services/analysis/` 안에 `impact/`를 둘지, `workers/`를 둘지, `src/` 아래를 어떻게 나눌지는 실제 Feature를 만들 때 정한다.

### 초안 worker와의 매핑

팀장님 초안의 worker 구분은 다음처럼 해석한다.

| 초안 위치 | 권장 상위 경계 | 판단 |
| --- | --- | --- |
| `workers/ingestion-worker/` | `services/collection/` | 수집 서비스의 실행 방식 |
| `workers/cpg-worker/` | `services/processing/` | 처리 파이프라인의 실행 방식 |
| `workers/analysis-worker/` | `services/analysis/` | 분석 서비스의 실행 방식 |
| `workers/impact-worker/` | `services/analysis/` | MVP에서는 분석 경계 안에 둠 |
| `workers/knowledge-worker/` | `services/knowledge/` | 지식 모델 갱신 실행 방식 |
| `workers/llm-worker/` | `services/assistant/` 또는 `services/analysis/` | 사용자 응답이면 assistant, 분석 보강이면 analysis |
| `workers/automation-worker/` | `services/workflow/` | 외부 workflow 자동화 실행 방식 |

이 매핑은 초안을 버리는 것이 아니다. worker 이름을 제품 책임보다 한 단계 아래의 실행 방식으로 내리는 것이다. 이렇게 해야 Harness의 `code_write_scope`도 실행 프로세스 이름이 아니라 제품 책임 기준으로 좁게 선언할 수 있다.

## `packages/` 기준

`packages/`는 처음부터 만들지 않는다. 여러 app/service가 같은 코드를 실제로 공유하게 되었을 때만 만든다.

공유 코드 승격 기준은 다음과 같다.

| 기준 | 의미 |
| --- | --- |
| 두 번째 실제 사용처 | 두 개 이상의 app/service가 같은 코드를 사용 |
| 독립 테스트 가능 | 특정 서비스 DB나 런타임에 묶이지 않고 테스트 가능 |
| 안정된 계약 | 입력, 출력, 오류가 문서화 가능 |
| 소유자 명확 | 변경 승인 책임자가 있음 |
| 순환 의존 없음 | app/service가 package를 참조하고 package가 app/service를 참조하지 않음 |

`packages/`는 편의상 공통 코드를 모아두는 창고가 아니다. 공유 기준이 약하면 각 서비스 안에 두고 중복을 허용하는 편이 낫다. 중복보다 더 위험한 것은 아직 안정되지 않은 코드를 공통 패키지로 올려 여러 Feature가 함께 흔들리는 것이다.

피해야 할 이름은 다음과 같다.

- `packages/common`
- `packages/utils`
- `services/shared`
- `apps/core-api/src/helpers`

허용되는 이름은 역할과 계약이 분명해야 한다.

- `packages/python/tci-contracts`
- `packages/python/tci-observability`
- `packages/typescript/api-client`
- `packages/typescript/ui-components`

## 루트 `workers/` 기준

루트 `workers/`는 MVP 초기 구조로 두지 않는다.

다음 구조는 피한다.

```text
workers/
├─ ingestion-worker/
├─ analysis-worker/
├─ cpg-worker/
├─ impact-worker/
├─ knowledge-worker/
├─ llm-worker/
└─ automation-worker/
```

이 구조는 실행기 목록은 잘 보이지만 제품 책임이 흐려진다. 예를 들어 `llm-worker`가 사용자 질의 응답을 위한 것인지, 분석 결과 보강을 위한 것인지, 문서 초안 생성을 위한 것인지 이름만으로 구분하기 어렵다. `impact-worker`도 독립 제품 경계인지 `analysis`의 일부인지 애매해진다.

루트 `workers/`를 검토할 수 있는 시점은 다음 조건이 명확할 때다.

- 여러 service가 같은 worker runtime과 queue 운영 방식을 공유
- worker platform 자체를 별도 운영 단위로 관리해야 함
- 독립 배포, 독립 scale, 독립 장애 경계가 필요
- 별도 secret, network permission, resource limit이 필요

그 전에는 각 service 안의 실행 방식으로 둔다.

## Agent 작업 기준

Feature 등록부의 `code_write_scope`는 이 상위 경계를 기준으로 잡는다.

```yaml
feature_id: 004-zip-upload-workspace-delete
code_write_scope:
  - apps/core-api/**
  - apps/web-console/**
  - services/collection/**
required_document_scope:
  - specs/004-zip-upload-workspace-delete/**
  - evidence/004-zip-upload-workspace-delete/**
  - feature-registry/004-zip-upload-workspace-delete.yml
```

하위 구현 디렉터리까지 `code_write_scope`에 강제로 고정하지 않는다. Feature가 충분히 좁으면 더 세부 경로를 쓸 수 있지만, 이 문서의 역할은 app/service/package 수준의 기본 경계를 정하는 것이다.

공동 수정 영역은 별도로 표시한다.

- DB migration
- generated API client
- root lockfile
- 공통 설정
- `shared-contracts/`
- queue schema와 event schema
- MCP tool schema

## 하위 구조 결정 기준

하위 구조는 이 문서에서 정하지 않는다. 대신 다음 기준으로 Feature 개발 중 결정한다.

- 해당 Feature가 실제로 수정하는 코드 흐름이 확인되었는가
- 테스트 경계가 명확한가
- 같은 이름의 하위 구조가 다른 app/service에도 반복될 필요가 있는가
- 하위 `AGENTS.md`로 별도 규칙을 둘 만큼 작업 방식이 다른가
- 구조를 만들지 않아도 읽기와 검증에 문제가 없는가

하위 구조를 만들 때는 한 Feature 안에서 필요한 만큼만 만든다. 이후 여러 Feature에서 반복되는 구조가 확인되면 그때 표준화한다.

## 완료 판단 기준

이 구조가 제대로 잡혔는지는 다음 질문에 답할 수 있으면 된다.

- 사용자가 직접 접근하는 실행 진입점이 `apps/` 아래에 있는가
- 내부 제품 능력이 `services/` 아래에서 책임별로 나뉘는가
- worker가 루트 제품 경계처럼 흩어지지 않는가
- `core-api`가 모든 도메인 상태를 흡수하지 않는가
- 공유 코드는 실제 두 번째 사용처가 생긴 뒤 `packages/`로 승격되는가
- Feature 등록부의 `code_write_scope`가 app/service/package 경계로 선언되는가
- 하위 구현 구조를 지금 문서에서 불필요하게 고정하지 않는가

## 참고 기준

- [Nx Folder Structure](https://nx.dev/docs/concepts/decisions/folder-structure): 모노레포에서 함께 변경되는 scope별 그룹화와 shared project 분리 기준
- [Turborepo Package Types](https://turborepo.dev/docs/core-concepts/package-types): 배포되는 application package와 공유 library package의 구분
- [The Twelve-Factor App](https://12factor.net/): 하나의 코드베이스, 명시적 의존성, 환경 설정, backing service 분리 원칙
- [OpenAI Agents SDK Guardrails](https://openai.github.io/openai-agents-python/guardrails/): agent, tool, handoff 경계별 guardrail 적용 기준
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/): specialist agent로 제어를 넘기는 handoff 개념
- [LangChain Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent/index): multi-agent가 필요한 조건과 supervisor, handoff, custom workflow 구분
- [LangChain Handoffs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs): 상태 기반 handoff, subgraph handoff, context engineering 기준
