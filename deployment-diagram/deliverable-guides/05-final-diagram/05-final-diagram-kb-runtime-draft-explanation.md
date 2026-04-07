# TCI Deployment Diagram 설명 문서

## 목적

이 문서는 [tci-deployment-diagram.drawio](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram.drawio)와 [tci-deployment-diagram.drawio.png](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram.drawio.png)를 발표나 공유 자리에서 빠르게 설명하기 위한 문서다.

이 다이어그램의 초점은 운영 배치 상세가 아니라 `TCI 서비스가 어디서 제공되고, 어떤 경계 안에서, 어떤 연결로 동작하는가`를 설명하는 데 있다.

## 한 줄 요약

TCI는 `Web Application`과 `IDE Plugin`을 public 진입점으로 두고, 내부의 분석·수집·자동화 서비스가 `Knowledge Base`를 중심 허브로 공유하며, 외부 개발 자산 소스와 협업/자동화 채널, Foundation Services와 연결되는 구조다.

## 다이어그램 소스

- 다이어그램 파일: [tci-deployment-diagram.drawio](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram.drawio)
- exported image: [tci-deployment-diagram.drawio.png](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram.drawio.png)
- 기준 산출물
  - [01-node-boundary-service-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/01-node-boundary-service/01-node-boundary-service-output-1.md)
  - [02-touchpoint-external-system-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/02-touchpoint-external-system/02-touchpoint-external-system-output-1.md)
  - [03-artifact-knowledge-base-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/03-artifact-knowledge-base/03-artifact-knowledge-base-output-1.md)
  - [04-communication-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/04-communication/04-communication-output-1.md)

> 참고: [tci-deployment-diagram-kb-runtime-draft.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram-kb-runtime-draft.puml)은 초안 기록이며 최신 기준은 아니다.

## 이 다이어그램이 답하는 질문

- 사용자는 어디로 들어오는가
- 내부 서비스는 어떤 경계로 분리되는가
- 지식 저장 계층은 어디에 있고 누가 접근하는가
- 어떤 외부 시스템과 어떤 방식으로 연결되는가
- 왜 `Knowledge Base`만 별도의 내부 runtime을 드러내는가
- 왜 외부 연동과 `Knowledge Base` 연결의 표기 기준이 다른가

## 먼저 봐야 할 구조

이 다이어그램은 4개 상위 경계로 읽으면 된다.

- `public`
  - 사용자와 개발자가 직접 접하는 진입 경계
  - `Web Application`과 `IDE Plugin`이 위치
- `private`
  - TCI 내부 애플리케이션 서비스 경계
  - `Interactive Assistant`, `Analysis Engine`, `Workflow & Integration`, `Data Collection & Processing`이 위치
- `data`
  - 지식 저장 계층 경계
  - `Knowledge Base`가 단일 top-level node로 위치
- `external`
  - TCI가 직접 통제하지 않는 외부 시스템 경계
  - `Code Repository`, `Issue Tracker + Docs/Wiki`, `CI/CD`, `Collaboration Tools`, `AI Coding Agent`, `Policy Engine`, `Public LLM Provider / Local LLM`, `Platform & Infra`가 위치

## 발표할 때 이렇게 설명하면 된다

### 1. 사용자 진입

사람 사용자는 기본적으로 `Web Application`으로 들어온다.

- `Developer`, `Reviewer`, `PM / PO`는 브라우저를 통해 `HTTPS`로 `Web Application`에 진입
- `Developer`는 추가로 `IDE Plugin`을 통해 로컬 IDE에서 직접 들어올 수 있음
- `IDE Plugin`은 별도 외부 시스템이 아니라 `public client node`로 본다
- `IDE Plugin`은 `Plugin API`를 통해 `Web Application`으로 연결된다

즉, TCI는 브라우저와 IDE 두 경로를 가지지만, 서버측 public gateway는 `Web Application`이 중심이다.

### 2. 내부 서비스 계층

`private` 경계에는 역할이 다른 4개 서비스가 배치돼 있다.

- `Interactive Assistant`
  - 대화형 질의응답과 코드베이스 설명 담당
- `Analysis Engine`
  - 구조 분석, 영향 분석, 규칙 추출 같은 중심 분석 담당
- `Workflow & Integration`
  - PR 자동화, 외부 연동, 리포트, 알림 담당
- `Data Collection & Processing`
  - 코드, 문서, 티켓 등 원천 자산 수집과 CPG·임베딩 생성, KB 적재를 함께 담당

이 4개를 분리한 이유는 실행 패턴과 책임 경계가 다르기 때문이다.

- `Interactive Assistant`는 실시간 대화형
- `Analysis Engine`은 분석 작업 중심
- `Workflow & Integration`은 이벤트/오케스트레이션 중심
- `Data Collection & Processing`은 현재 단계에서 수집과 처리 책임을 하나의 배포 단위로 묶은 파이프라인 중심 서비스다

## Knowledge Base를 어떻게 설명할 것인가

이 다이어그램에서 가장 중요한 특칙은 `Knowledge Base`다.

- 메인 구조에서는 `Knowledge Base`를 `data` 경계의 단일 top-level node로 본다
- 하지만 내부 상세는 runtime level에서 4개로 분리해 표현한다
  - `Graph DB Runtime Environment`
  - `Vector DB Runtime Environment`
  - `Object Storage Runtime Environment`
  - `RDB Runtime Environment`
- 대응 artifact는 각각 아래와 같다
  - `Graph DB (Graph Artifact)`
  - `Vector DB (Vector Artifact)`
  - `Object Storage (Object Artifact)`
  - `Metadata Artifact`

여기서 핵심은 두 가지다.

- `Knowledge Base`는 하나의 논리적 지식 허브다
- 내부 저장 기술은 이질적이므로 runtime 수준에서는 분리해서 보는 편이 설명력이 높다

이번 버전에서는 인덱싱 관련 계층을 별도 runtime이나 artifact로 승격하지 않는다. 검색과 인덱싱 관련 책임은 `Graph` 또는 `Vector` 계층의 내부 책임으로 본다. `RDB Runtime Environment`는 정형 메타데이터와 운영성 정보를 담는 저장 계층으로 함께 본다.

## Execution Environment를 왜 넣었는가

이 다이어그램은 아키텍처 설명용이지만, 이번 버전에서는 실행 환경도 일부 포함한다.

다만 중요한 규칙이 있다.

- `Execution Environment`는 범위에 포함
- 하지만 `top-level Node` 수에는 포함하지 않음
- 즉, `Node -> Docker -> Runtime -> Artifact` 구조로 중첩해서 읽어야 함

서버측 내부 서비스는 공통적으로 아래 패턴을 따른다.

- 바깥 레이어
  - `Docker - <Service>`
- 안쪽 레이어
  - `Application Runtime` 또는 저장소별 runtime
- 가장 안쪽
  - artifact

예외는 두 개다.

- `IDE Plugin`
  - Docker가 아니라 `IDE Host Runtime`을 사용
- `Public LLM Provider / Local LLM`, `Platform & Infra`
  - TCI가 직접 통제하는 runtime이 아니라 `conceptual external EE`로만 표현

## 연결 표기 원칙

이 다이어그램은 연결 대상의 성격에 따라 표기 기준을 다르게 쓴다.

- 외부 시스템과의 연결
  - 프로토콜 중심으로 표기
  - 예: `REST`, `WebHook / REST`, `MCP / REST`, `Git Protocol`
- `Knowledge Base`와의 연결
  - 접근 방식 중심으로 표기
  - 예: `Knowledge Read`, `Knowledge R/W`, `Knowledge Write`

이렇게 나누는 이유는 외부 연동에서는 "어떻게 붙는가"가 중요하고, `Knowledge Base`에서는 "어떻게 사용하는가"가 더 중요하기 때문이다.

## 주요 연결

발표에서는 모든 화살표를 하나씩 읽기보다, 아래 6개 묶음으로 설명하는 편이 좋다.

### 사용자 접근

- `Developer/Reviewer/PM / PO -> Web Application` via `HTTPS`
- `Developer -> IDE Plugin` via `IDE UI`
- `IDE Plugin -> Web Application` via `Plugin API`

### public에서 private로 들어가는 연결

- `Web Application -> Interactive Assistant` via `WebSocket`
- `Web Application -> Workflow & Integration` via `HTTPS`
- `Web Application -> Data Collection & Processing` via `HTTPS`
- `Workflow & Integration -> Web Application` via `SSE / WebSocket`

### 내부 서비스 간 연결

- `Interactive Assistant -> Analysis Engine` via `gRPC (async)`
- `Workflow & Integration -> Analysis Engine` via `Internal API`
- 현재 버전에서는 수집과 처리를 하나의 Node로 통합했기 때문에 `Data Collection -> Data Processing` 내부 연결은 별도 선으로 그리지 않는다

### Knowledge Base 접근

- `Interactive Assistant <-> Knowledge Base` via `Knowledge R/W`
- `Analysis Engine <-> Knowledge Base` via `Knowledge R/W`
- `Workflow & Integration <- Knowledge Base` via `Knowledge Read`
- `Data Collection & Processing -> Knowledge Base` via `Knowledge Write`

### 외부 원천 자산 수집

- `Data Collection & Processing -> Code Repository` via `Git Protocol`
- `Data Collection & Processing -> Issue Tracker + Docs/Wiki` via `REST / Upload`

### 외부 연동과 Foundation 연결

- `Workflow & Integration -> CI/CD` via `WebHook / REST`
- `Workflow & Integration -> Collaboration Tools` via `REST API / Bot API`
- `Workflow & Integration <-> AI Coding Agent` via `MCP / REST`
- `Workflow & Integration <-> Policy Engine` via `REST`
- `Interactive Assistant / Analysis Engine / Data Collection & Processing -> Public LLM Provider / Local LLM` via `REST / HTTPS`
- `Web Application / Workflow & Integration -> Platform & Infra` via `REST / HTTPS`

## 이 다이어그램에서 강조할 메시지

### 메시지 1

TCI는 하나의 웹앱이 아니라, 역할이 분리된 내부 서비스 구조를 가진다.

### 메시지 2

사용자 진입점은 `Web Application`이 중심이지만, 개발자 로컬 흐름을 위해 `IDE Plugin`도 public client로 포함한다.

### 메시지 3

`Knowledge Base`는 단순 DB 하나가 아니라, TCI 전체의 SSOT 역할을 하는 중앙 지식 허브다.

### 메시지 4

외부 연동은 `Workflow & Integration`과 `Data Collection & Processing`에 집중시켜 내부 분석 서비스의 경계를 보호한다.

### 메시지 5

이 그림은 운영 배치도보다 상위 수준의 설명용 다이어그램이지만, 필요한 곳에서는 `Docker`와 `Runtime` 레이어를 드러내 설명력을 높였다.

## 발표 순서 제안

내일 공유에서는 아래 순서로 설명하면 가장 자연스럽다.

1. 다이어그램 목적
  - 운영 상세가 아니라 서비스 제공 구조 설명용
2. 상위 4개 경계
  - `public`, `private`, `data`, `external`
3. 사용자 진입
  - 브라우저와 IDE Plugin
4. 내부 서비스 4개
  - Assistant, Analysis, Workflow, Collection & Processing
5. Knowledge Base 특칙
  - 단일 node + 내부 4 runtime
6. 외부 연결
  - Code Repository, Issue Tracker + Docs/Wiki, CI/CD, Collaboration Tools, AI Agent, Policy, Public LLM Provider / Local LLM, Platform
7. 왜 이렇게 나눴는가
  - 역할 분리, 스케일링, 책임 분리, SSOT 표현

## 질문이 나오기 쉬운 포인트

### 왜 `IDE Plugin`이 external이 아니라 public인가

이 다이어그램에서는 외부 SaaS가 아니라 `TCI가 직접 배포하는 client node`로 보기 때문이다.

### 왜 `Knowledge Base`만 내부 runtime을 드러냈는가

지식 허브의 내부 저장 구조가 다이어그램 이해에 직접 중요하기 때문이다.

### 왜 `Public LLM Provider / Local LLM`과 `Platform & Infra`는 runtime을 두면서도 external인가

실제 운영 주체가 TCI가 아니기 때문이다. 이들은 `conceptual external EE`로만 본다.

### 왜 `Operations Manager`는 없는가

현재 산출물 기준에서는 C2 주요 node 집합에서 제외된 상태이기 때문이다.

## 오픈 이슈

- `Knowledge Base` 내부 4개 runtime을 메인 그림에 계속 둘지, 보조 다이어그램으로 분리할지 최종 결정 필요
- artifact 명칭은 EE 가이드명과 artifact 표 명칭이 함께 적혀 있어, 최종 발표본에서 한쪽 naming으로 정리할지 검토 가능

## 발표용 마무리 문장 예시

`이 다이어그램은 TCI를 단일 서비스가 아니라, public 진입점과 내부 분석/자동화 서비스, 그리고 중앙 Knowledge Base를 중심으로 움직이는 구조로 설명합니다. 특히 Knowledge Base를 SSOT로 두고, 수집·처리·분석·자동화 계층이 이를 공유한다는 점이 TCI 아키텍처의 핵심입니다.`
