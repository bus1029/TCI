# Node / 경계 / 서비스 산출물 #1

출처: [https://www.notion.so/336c21d54f42802383b7ef69c1e340ec](https://www.notion.so/336c21d54f42802383b7ef69c1e340ec)

## 기준

- 최신 기준은 [tci-deployment-diagram.drawio](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram.drawio)다.
- 이 문서는 drawio에 실제로 그려진 Node, 경계, Execution Environment만 반영한다.
- 현재 메인 그림에서는 `Data Collection`과 `Data Processing`을 분리하지 않고 `Data Collection & Processing` 단일 Deployment Node로 표현한다.

## 1. 포함할 Node 목록

최신 drawio 기준 top-level Node는 총 15개다.

### TCI 내부 (7개)

| Node | 경계 | 비고 | 이유 |
|---|---|---|---|
| Web Application | public | 인증/인가 · 세션 관리 · API 라우팅 | 브라우저 사용자와 IDE Plugin이 모두 연결되는 public gateway이므로 외부 트래픽을 직접 수신하는 public 영역에 배치 |
| IDE Plugin | public | 로컬 코드 변경 스냅샷 수집 · 분석 컨텍스트 조회 | 개발자 로컬 IDE에서 동작하는 public client node이며 `Plugin API`를 통해 Web Application으로 연결 |
| Interactive Assistant | private | 코드베이스 질의응답 · 구조·규칙 설명 | 대화형 세션은 Web Application이 `WebSocket`으로 중계하므로 외부 직접 노출 불필요 |
| Analysis Engine | private | 구조·영향도·테스트 분석 · 규칙 추출 · 갭 분석 | Interactive Assistant, Workflow & Integration을 통해서만 분석 요청이 도달하므로 내부 영역으로 충분 |
| Workflow & Integration | private | PR 자동화 · 전달 워크플로우 · 외부 연동 · 리포트 | Web Application 경유 API 호출과 외부 연동 오케스트레이션을 담당하며 직접 사용자 노출 없음 |
| Data Collection & Processing | private | 개발 자산 수집 · 증분 동기화 · 업로드 · CPG/임베딩 생성 · KB 적재 | 최신 drawio에서는 현재 대표 배포 단위를 기준으로 수집과 처리를 하나의 Node로 통합 |
| Knowledge Base | data | 분석 산출물 SSOT | `Object / Vector / Graph / Metadata` 4계층을 내부에 두는 중앙 지식 허브이므로 data 영역으로 분리 |

### Foundation Services (2개)

| Node | 경계 | 비고 | 이유 |
|---|---|---|---|
| Public LLM Provider / Local LLM | external | 대화 추론 · 임베딩 생성 | TCI가 제어하지 않는 외부 서비스. Interactive Assistant, Analysis Engine, Data Collection & Processing이 용도별 호출 |
| Platform & Infra | external | 인증/인가 · SSO · 로그 · 모니터링 | TCI가 제어하지 않는 외부 서비스. Web Application, Workflow & Integration이 인증·로그 위임 |

### 외부 연동 / 데이터 소스 (6개)

| Node | 경계 | 비고 | 이유 |
|---|---|---|---|
| Code Repository | external | GitHub / GitLab / Bitbucket | Git Protocol이 고유하고 Data Collection & Processing이 소스 코드·커밋·브랜치를 수집 |
| Issue Tracker + Docs/Wiki | external | Jira / Confluence / Notion | 문서·티켓·PR·Wiki 수집 경로를 하나의 외부 Node로 묶어 표현 |
| CI/CD | external | Jenkins / GitHub Actions | `WebHook / REST` 패턴이 고유하며 Workflow & Integration이 연동 |
| Collaboration Tools | external | Slack / Teams | 알림·Bot API 패턴이 고유하며 Workflow & Integration이 연동 |
| AI Coding Agent | external | MCP / REST 기반 AI 에이전트 연동 | 양방향 컨텍스트 교환 패턴이 고유 |
| Policy Engine | external | OPA / Custom Policy | 정책 검증 요청 / 결과 반환 패턴이 고유 |

## 2. Top-level Node 비카운트 / 제외 요소

| 항목 | 처리 방식 | 이유 | 대체 표현 |
|---|---|---|---|
| Execution Environment | 범위 포함, top-level Node 비카운트 | 메인 배포 다이어그램의 Node 수에는 포함하지 않고 Node 내부 nested EE로 표현 | 아래 Node별 Execution Environment 절에서 정의 |
| Actor (Developer / Reviewer / PM / PO) | top-level Node 비카운트 | Deployment Node가 아닌 UML Actor로 표현하는 것이 적절 | UML Actor 표기 |
| 인프라 요소 (LB, MQ, DNS) | 제외 | 아키텍처 설명용 다이어그램이므로 운영 배치도 수준의 인프라는 범위 밖 | 표현하지 않음 |
| 환경별 구분 (Dev / Staging / Prod) | 제외 | 대표 환경 하나만 그리기로 결정 | 단일 대표 환경 |
| Operations Manager | 제외 | 최신 drawio 기준에 미등장 | 표현하지 않음 |

## 3. 서비스 Node 매핑 초안

### 표현 계층 정의

| 계층 | 정의 | 메인 그림 처리 |
|---|---|---|
| Top-level Node | 메인 배포 다이어그램에서 카운트되는 논리 서비스 경계 또는 외부 시스템 | 최신 drawio 기준 15개 Node로 표현 |
| Nested Execution Environment | Top-level Node 내부 또는 외부 서비스 내부에 중첩되는 실행 호스팅 레이어 | 범위에 포함하되 top-level Node 수에는 포함하지 않음 |
| Artifact | 각 Execution Environment 안에 배치되는 물리적 산출물 | Node/EE의 역할 설명용으로 표기 |

### 매핑 원칙

- 기본값은 C2 컨테이너 기준으로 Node를 잡는다.
- 다만 최신 drawio처럼 현재 대표 배포 단위가 같으면 여러 C2 책임을 하나의 Deployment Node로 통합할 수 있다.
- 컨테이너 내부 컴포넌트(C3 수준)는 Node로 승격하지 않는다.
- Knowledge Base는 단일 Top-level Node를 유지하고, 내부에 4개 nested Runtime EE를 둔다.
- Foundation Services의 EE는 conceptual external EE이며 TCI가 직접 관리하는 실행환경으로 간주하지 않는다.

### 매핑표

#### TCI 내부

| C2 컨테이너 / 책임 | Deployment Node | 경계 | 이유 |
|---|---|---|---|
| Web Application | Web Application | public | public gateway 역할이 명확하며 브라우저와 IDE Plugin이 모두 연결 |
| IDE Plugin | IDE Plugin | public | public client node로 별도 표현하는 편이 사용자 진입 구조를 설명하기에 적절 |
| Interactive Assistant | Interactive Assistant | private | 실시간 대화형 세션 전용 내부 서비스 |
| Analysis Engine | Analysis Engine | private | 분석 요청 전용 내부 서비스 |
| Workflow & Integration | Workflow & Integration | private | 외부 채널 연동과 자동화 오케스트레이션을 집중 |
| Data Collection | Data Collection & Processing | private | 최신 drawio에서는 수집과 처리를 하나의 배포 단위로 묶어 표현 |
| Data Processing | Data Collection & Processing | private | 최신 drawio에서는 수집과 처리를 하나의 배포 단위로 묶어 표현 |
| Knowledge Base | Knowledge Base | data | 단일 지식 허브로 표현하고 내부 저장 계층은 nested runtime으로 분리 |

#### Foundation Services

| 외부 시스템 | Deployment Node | 경계 | 이유 |
|---|---|---|---|
| Public LLM Provider / Local LLM | Public LLM Provider / Local LLM | external | TCI 외부 추론/임베딩 서비스 |
| Platform & Infra | Platform & Infra | external | TCI 외부 인증/운영 인프라 서비스 |

#### 외부 연동 / 데이터 소스

| 외부 시스템 | Deployment Node | 경계 | 이유 |
|---|---|---|---|
| Code Repository | Code Repository | external | Git Protocol 고유성 유지 |
| Issue Tracker + Docs/Wiki | Issue Tracker + Docs/Wiki | external | 개발 맥락 수집 경로를 하나의 외부 Node로 묶음 |
| CI/CD | CI/CD | external | `WebHook / REST` 기반 연동 채널 |
| Collaboration Tools | Collaboration Tools | external | `REST API / Bot API` 기반 협업 전달 채널 |
| AI Coding Agent | AI Coding Agent | external | `MCP / REST` 기반 양방향 연동 채널 |
| Policy Engine | Policy Engine | external | `REST` 기반 정책 검증 채널 |

## 4. 서비스별 제공 위치 표

| 서비스 | 제공 Node | 경계 | 접근 주체 | 비고 |
|---|---|---|---|---|
| API 게이트웨이 | Web Application | public | Developer, Reviewer, PM / PO, IDE Plugin | 브라우저와 IDE Plugin이 모두 연결되는 중심 진입점 |
| IDE 확장 | IDE Plugin | public | Developer | 로컬 개발 환경에서 직접 조작하는 client node |
| 대화형 지원 | Interactive Assistant | private | Web Application | WebSocket 기반 질의응답 세션 처리 |
| 코드 분석 | Analysis Engine | private | Interactive Assistant, Workflow & Integration | 구조·영향도·테스트 영향 분석 수행 |
| 워크플로우 관리 | Workflow & Integration | private | Web Application, 외부 연동 채널 | PR 자동화, 외부 연동, 리포트, 알림 처리 |
| 데이터 수집·처리 | Data Collection & Processing | private | Web Application, Code Repository, Issue Tracker + Docs/Wiki | 업로드 intake, 외부 소스 수집, CPG/임베딩 생성, KB 적재를 묶어 표현 |
| 지식 저장 | Knowledge Base | data | Interactive Assistant, Analysis Engine, Workflow & Integration, Data Collection & Processing | SSOT. 내부에 Object / Vector / Graph / Metadata 4계층 유지 |
| LLM 서비스 | Public LLM Provider / Local LLM | external | Interactive Assistant, Analysis Engine, Data Collection & Processing | 대화 추론 · 규칙 해석 · 임베딩 생성 |
| 플랫폼 서비스 | Platform & Infra | external | Web Application, Workflow & Integration | 인증/인가 · 로그 · 모니터링 |

## 5. 상위 경계 초안

| 경계 | 포함 Node | 배치 근거 |
|---|---|---|
| public | Web Application, IDE Plugin | 사용자가 직접 접하는 진입 채널 |
| private | Interactive Assistant, Analysis Engine, Workflow & Integration, Data Collection & Processing | 핵심 분석/처리/연동 로직이 동작하는 내부 서비스 영역 |
| data | Knowledge Base | 단일 top-level Node + 내부 4개 runtime으로 표현하는 지식 허브 |
| external | Code Repository, Issue Tracker + Docs/Wiki, CI/CD, Collaboration Tools, AI Coding Agent, Policy Engine, Public LLM Provider / Local LLM, Platform & Infra | TCI가 직접 통제하지 않는 외부 시스템 |

## 6. 우리 시스템 / 외부 서비스 구분표

| 대상 | 구분 | 통제 수준 | 비고 |
|---|---|---|---|
| Web Application | 우리 시스템 | 직접 통제 | public 경계 |
| IDE Plugin | 우리 시스템 | 직접 통제 | public client node |
| Interactive Assistant | 우리 시스템 | 직접 통제 | private 경계 |
| Analysis Engine | 우리 시스템 | 직접 통제 | private 경계 |
| Workflow & Integration | 우리 시스템 | 직접 통제 | private 경계 |
| Data Collection & Processing | 우리 시스템 | 직접 통제 | private 경계 |
| Knowledge Base | 우리 시스템 | 직접 통제 | data 경계 |
| Public LLM Provider / Local LLM | 외부 서비스 | 연동만 가능 | Foundation Service |
| Platform & Infra | 외부 서비스 | 연동만 가능 | Foundation Service |
| Code Repository | 외부 서비스 | 연동만 가능 | Data Source |
| Issue Tracker + Docs/Wiki | 외부 서비스 | 연동만 가능 | Data Source |
| CI/CD | 외부 서비스 | 연동만 가능 | Integration Channel |
| Collaboration Tools | 외부 서비스 | 연동만 가능 | Integration Channel |
| AI Coding Agent | 외부 서비스 | 연동만 가능 | Integration Channel |
| Policy Engine | 외부 서비스 | 연동만 가능 | Integration Channel |

## 7. Node별 Execution Environment

### EE 표현 원칙

| # | 원칙 | 설명 |
|---|---|---|
| 1 | Docker 기반 | 모든 서버측 내부 서비스의 EE는 Docker 위에서 동작한다. 단, IDE Plugin은 로컬 IDE Host Runtime 위에서 동작한다 |
| 2 | 2-레이어 EE 표현 | 서버측 EE는 `Docker -> Runtime EE -> Artifact` nested 구조로 표현한다 |
| 3 | Top-level Node와 EE 분리 | Execution Environment는 범위에 포함되지만 top-level Node 수에는 포함하지 않는다 |
| 4 | 런타임 추상화 | 내부 앱 런타임은 `Application Runtime`으로 추상화한다 |
| 5 | Data Collection & Processing 통합 EE 유지 | 최신 drawio에서는 수집과 처리를 하나의 Docker + Application Runtime으로 표현한다 |
| 6 | Knowledge Base 내부 runtime 분리 | Knowledge Base 내부에는 4개 runtime을 둔다 |
| 7 | Foundation conceptual external EE | Public LLM Provider / Local LLM과 Platform & Infra에는 conceptual external EE를 부여한다 |
| 8 | 대상 범위 | TCI가 직접 통제하는 Node 7개(서버측 6개 + IDE Plugin 1개) + Foundation Services 2개에 EE를 부여한다 |

### EE 그룹핑 표

정리하면 top-level Node 수는 15개를 유지하고, nested Runtime EE는 TCI 직접 통제 범위 10개 + Foundation conceptual external EE 2개로 표현한다.

| EE 그룹 | Top-level Node | 호스팅 레이어 | Runtime EE | Runtime 역할 |
|---|---|---|---|---|
| 1 | Web Application | Docker - Web App | Web Server Runtime | 정적 자산 서빙 · API 라우팅 |
| 2 | Interactive Assistant | Docker - Interactive Assistant | Application Runtime | 세션 처리 · 대화 오케스트레이션 |
| 3 | Analysis Engine | Docker - Analysis Engine | Application Runtime | 구조/영향 분석 실행 |
| 4 | Workflow & Integration | Docker - Workflow & Integration | Application Runtime | 이벤트 오케스트레이션 · 외부 연동 |
| 5 | Data Collection & Processing | Docker - Data Collection & Processing | Application Runtime | 수집 · 업로드 · CPG/임베딩 생성 · KB 적재 |
| 6 | Knowledge Base | Docker - KB Object Storage | Object Storage Runtime Environment | 원본/산출물 저장 |
| 7 | Knowledge Base | Docker - KB Vector Storage | Vector DB Runtime Environment | 임베딩 인덱싱 · 유사도 검색 |
| 8 | Knowledge Base | Docker - KB Graph Storage | Graph DB Runtime Environment | 그래프 질의 · 저장 |
| 9 | Knowledge Base | Docker - RDB Storage | RDB Runtime Environment | 정형 메타데이터 저장 |
| 10 | IDE Plugin | 로컬 IDE Host | IDE Host Runtime | 로컬 변경 수집 · 컨텍스트 조회 |
| 11 | Public LLM Provider / Local LLM | conceptual external EE | LLM Inference Runtime | 대화 추론 · 임베딩 API 제공 |
| 12 | Platform & Infra | conceptual external EE | Platform Service Runtime | 인증/인가 · 로그 · 모니터링 제공 |

### EE 중첩 개념도

```text
[Top-level Node] Web Application
  └── [Docker] Web App
        └── <<EE>> Web Server Runtime

[Top-level Node] IDE Plugin
  └── <<EE>> IDE Host Runtime

[Top-level Node] Interactive Assistant
  └── [Docker] Interactive Assistant
        └── <<EE>> Application Runtime

[Top-level Node] Analysis Engine
  └── [Docker] Analysis Engine
        └── <<EE>> Application Runtime

[Top-level Node] Workflow & Integration
  └── [Docker] Workflow & Integration
        └── <<EE>> Application Runtime

[Top-level Node] Data Collection & Processing
  └── [Docker] Data Collection & Processing
        └── <<EE>> Application Runtime

[Top-level Node] Knowledge Base
  ├── [Docker] KB Object Storage
  │     └── <<EE>> Object Storage Runtime Environment
  ├── [Docker] KB Vector Storage
  │     └── <<EE>> Vector DB Runtime Environment
  ├── [Docker] KB Graph Storage
  │     └── <<EE>> Graph DB Runtime Environment
  └── [Docker] RDB Storage
        └── <<EE>> RDB Runtime Environment

[Top-level Node] Public LLM Provider / Local LLM (external)
  └── <<conceptual external EE>> LLM Inference Runtime

[Top-level Node] Platform & Infra (external)
  └── <<conceptual external EE>> Platform Service Runtime
```
