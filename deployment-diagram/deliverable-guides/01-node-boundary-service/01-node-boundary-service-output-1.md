# Node / 경계 / 서비스 산출물 #1

출처: [https://www.notion.so/336c21d54f42802383b7ef69c1e340ec](https://www.notion.so/336c21d54f42802383b7ef69c1e340ec)

## 1. 포함할 Node 목록

팀 합의로 확정된 16개 Node를 전수 나열한다.

### TCI 내부 (C2 Container 기준, 8개)

| Node | 경계 | 비고 | 이유 |
|---|---|---|---|
| Web Application | public | 인증/인가 · 세션 관리 · API 라우팅 | 브라우저 사용자와 IDE Plugin이 모두 연결되는 public gateway이므로 외부 트래픽을 직접 수신하는 public 영역에 배치 |
| IDE Plugin | public | 로컬 코드 변경 스냅샷 수집 · 분석 컨텍스트 조회 | TCI 내부 컨테이너(C2). 개발자 로컬 IDE에서 동작하는 public client node로 Web Application과 함께 public 영역에 배치 |
| Interactive Assistant | private | 코드베이스 질의응답 · 구조·규칙 설명 | 대화형 세션은 Web Application이 WebSocket으로 중계하므로 외부 직접 노출 불필요 |
| Analysis Engine | private | 구조·영향도·테스트 분석 · 규칙 추출 · 갭 분석 | Interactive Assistant, Workflow & Integration을 통해서만 분석 요청이 도달하므로 내부 영역으로 충분 |
| Workflow & Integration | private | PR 자동화 · 전달 워크플로우 · 외부 연동 · 리포트 | Web Application 경유 API 호출 또는 Webhook 수신으로 동작하며 직접 사용자 노출 없음 |
| Knowledge Base | data | 분석 산출물 SSOT (Graph DB · Object Storage · Vector DB) | Knowledge Base 중심 아키텍처의 SSOT로서 접근 주체가 한정(Interactive Assistant, Analysis Engine, Workflow & Integration, Data Processing)되어 독립 data 영역으로 분리 |
| Data Processing | private | CPG 생성 · 임베딩 생성 · 규칙 패턴 식별 · Knowledge Base 적재 | 내부 전처리/적재 전용으로 외부 노출 없음 |
| Data Collection | private | 개발 자산 수집 · 증분 동기화 · 업로드 | 외부 Data Sources에서 데이터를 당겨오는 수집 전용으로 외부 노출 없음 |

### Foundation Services (C2 기준, 2개)

| Node | 경계 | 비고 | 이유 |
|---|---|---|---|
| Public LLM Provider / Local LLM | external | 대화 추론 · 임베딩 생성 | TCI가 제어하지 않는 외부 서비스. Interactive Assistant, Analysis Engine, Data Processing이 용도별 호출 |
| Platform & Infra | external | 인증/인가 · SSO · 로그 · 모니터링 | TCI가 제어하지 않는 외부 서비스. Web Application, Workflow & Integration이 인증·로그 위임 |

### 연동 / 클라이언트 Node (Data Sources + Integration Channels, 6개)

| Node | 경계 | 비고 | 이유 |
|---|---|---|---|
| Code Repository | external | GitHub / GitLab / Bitbucket. Git 프로토콜로 소스 코드·커밋·브랜치 수집 | 프로토콜 고유성으로 단독 유지. TCI 외부 시스템 |
| Issue Tracker + Docs/Wiki | external | Jira / Confluence / Notion. 문서·티켓·PR·ADR·Wiki 수집 | Ticket + Docs/Wiki를 동일 수집 경로(REST)·동일 흐름 방향(inbound)으로 묶음 |
| CI/CD | external | Jenkins / GitHub Actions. CI/CD 파이프라인 연동 | Webhook 수신 + Gate 결과 응답 패턴이 고유하여 단독 유지 |
| Collaboration Tools | external | Slack / Teams. 알림·Bot 연동 | 알림 전용, Bot API 패턴이 고유하여 단독 유지 |
| AI Coding Agent | external | MCP / API. AI 코딩 에이전트 연동 | MCP 프로토콜, 양방향 컨텍스트 교환 패턴이 고유하여 단독 유지 |
| Policy Engine | external | OPA / Custom Policy. 사내 아키텍처·보안 정책 검증 | 검증 요청/결과 수신 패턴이 고유하여 단독 유지 |

---

## 2. Top-level Node 비카운트 / 제외 요소

| 항목 | 처리 방식 | 이유 | 대체 표현 |
|---|---|---|---|
| Execution Environment | 범위 포함, top-level Node 비카운트 | 이번 범위에 포함되지만 메인 배포 다이어그램의 Node 수에는 포함하지 않는다. Node 내부의 nested EE로 표현 | 아래 Node별 Execution Environment 절에서 정의 |
| Actor (Developer / Reviewer / PM/PO) | top-level Node 비카운트 | Deployment Node가 아닌 UML Actor로 표현하는 것이 적절 | UML Actor 표기 |
| 인프라 요소 (LB, MQ, DNS) | 제외 | 아키텍처 설명용 다이어그램이므로 운영 배치도 수준의 인프라 불필요 | 표현하지 않음 |
| 환경별 구분 (Dev / Staging / Prod) | 제외 | 대표 환경 하나만 그리기로 결정 | 단일 대표 환경 |
| Operations Manager | 제외 | C2 Container Diagram에 미등장 (2026-03-31 기준 제거됨) | 표현하지 않음 |

---

## 3. 서비스 Node 매핑 초안

### 표현 계층 정의

Deployment Diagram의 표현 계층을 아래 3단계로 정의한다.

| 계층 | 정의 | 메인 그림 처리 |
|---|---|---|
| Top-level Node | 메인 배포 다이어그램에서 카운트되는 논리 서비스 경계 또는 외부 시스템 | 앞의 포함할 Node 목록에서 확정한 16개 Node를 이 계층으로 표현 |
| Nested Execution Environment | Top-level Node 내부 또는 외부 서비스 내부에 중첩되는 실행 호스팅 레이어 | 범위에 포함하되 top-level Node 수에는 포함하지 않음 |
| Artifact | 각 Execution Environment 안에 배치되는 물리적 산출물 | Node/EE의 역할 설명용으로 표기 |

C2 컨테이너/외부 시스템 1개를 Deployment Diagram의 Top-level Node 1개로 매핑한다 (1:1 원칙).

### 왜 1:1 Top-level Node 매핑인가

팀 합의: C2에서 컨테이너를 분리한 근거 자체가 논리 서비스 경계를 나눠야 하는 근거와 일치하기 때문이다.

| 분리 근거 | 설명 | 해당 컨테이너 예시 |
|---|---|---|
| 스케일링 프로파일 차이 | CPU/메모리 집약(CPG 분석) vs GPU/토큰 집약(LLM 호출) vs 네트워크 I/O 집약(수집·연동)이 서로 달라 독립적으로 스케일링해야 한다 | Analysis Engine·Data Processing (CPU) vs Interactive Assistant (GPU/토큰) vs Data Collection·Workflow & Integration (I/O) |
| 실행 패턴 차이 | 실시간 대화형(저지연 필수) vs 비동기 배치(처리량 우선) vs 이벤트 오케스트레이션(Webhook 응답)이 서로 달라 배포·운영 주기가 다르다 | Interactive Assistant (실시간) vs Data Processing·Data Collection (비동기) vs Workflow & Integration (이벤트) |
| 외부 인터페이스 응집도 | 외부 채널 연동(CI/CD, Collaboration Tools, Policy Engine 등)을 Workflow & Integration에 집중시켜 나머지 컨테이너가 외부 프로토콜 변경에 영향받지 않도록 격리한다 | Workflow & Integration (외부 연동 집중) vs Analysis Engine·Interactive Assistant (내부 로직 집중) |
| 데이터 접근 경계 | Knowledge Base는 SSOT로서 접근 주체가 한정(Interactive Assistant, Analysis Engine, Workflow & Integration, Data Processing)되며, 저장 기술(Graph DB, Object Storage, Vector DB)이 다른 컨테이너와 본질적으로 다르다 | Knowledge Base (data 영역 독립) |

### 추가 규칙

- 컨테이너 내부 컴포넌트(C3 수준)는 Node로 분해하지 않는다
- 서로 다른 컨테이너를 하나의 Top-level Node로 통합하지 않는다
- Knowledge Base는 단일 Top-level Node + 내부 3개 Artifact 구분을 유지하되, 필요 시 내부 3개 nested Runtime EE를 둔다
- Top-level Node는 메인 그림에서 카운트되는 논리 서비스 경계다. 실제 실행 호스팅 레이어는 Node별 Execution Environment 절의 nested EE로 정의한다
- Foundation Services의 EE는 conceptual external EE이며, TCI가 직접 관리하는 실행환경으로 간주하지 않는다

### 매핑표

포함할 Node 목록에서 확정한 16개 Node 전수를 매핑한다.

#### TCI 내부 (8개)

| C2 컨테이너 | Deployment Node | 경계 | 이유 |
|---|---|---|---|
| Web Application | Web Application | public | 브라우저 사용자와 IDE Plugin이 연결되는 public gateway. 외부 트래픽을 직접 수신하므로 public |
| IDE Plugin | IDE Plugin | public | TCI 내부 컨테이너(C2). 개발자 로컬 IDE에서 동작하는 public client node. Web Application으로 요청을 중계 |
| Interactive Assistant | Interactive Assistant | private | 대화형 세션은 Web Application이 WebSocket으로 중계. 외부 직접 노출 불필요 |
| Analysis Engine | Analysis Engine | private | Interactive Assistant, Workflow & Integration을 통해서만 분석 요청이 도달. 외부 직접 노출 불필요 |
| Workflow & Integration | Workflow & Integration | private | Web Application 경유 API 호출 또는 Webhook 수신. 직접 사용자 노출 없음 |
| Knowledge Base | Knowledge Base | data | SSOT. 접근 주체가 Interactive Assistant, Analysis Engine, Workflow & Integration, Data Processing으로 한정되어 독립 data 영역으로 분리 |
| Data Processing | Data Processing | private | 내부 전처리/적재 전용. 외부 노출 없음 |
| Data Collection | Data Collection | private | 외부 Data Sources에서 데이터를 당겨오는 수집 전용. 외부 노출 없음 |

#### Foundation Services (2개)

| C2 외부 시스템 | Deployment Node | 경계 | 이유 |
|---|---|---|---|
| Public LLM Provider / Local LLM | Public LLM Provider / Local LLM | external | TCI 외부 서비스. Interactive Assistant, Analysis Engine, Data Processing이 용도별(대화 추론·임베딩) 호출 |
| Platform & Infra | Platform & Infra | external | TCI 외부 서비스. Web Application, Workflow & Integration이 인증·로그·모니터링 위임 |

#### 연동 / 클라이언트 Node (6개)

| C2 외부 시스템 | Deployment Node | 경계 | 이유 |
|---|---|---|---|
| Code Repository | Code Repository | external | Git 프로토콜 고유성. DC가 소스 코드·커밋·브랜치 수집 |
| Issue Tracker + Docs/Wiki | Issue Tracker + Docs/Wiki | external | Ticket + Docs/Wiki를 동일 수집 경로(REST)로 묶음. DC가 문서·티켓 수집 |
| DevOps Pipeline | CI/CD | external | Webhook 수신 + Gate 결과 응답 패턴 고유. W&I가 연동 |
| Collaboration Tools | Collaboration Tools | external | 알림 전용 Bot API 패턴 고유. W&I가 연동 |
| AI Coding Agent | AI Coding Agent | external | MCP 프로토콜, 양방향 컨텍스트 교환 패턴 고유. W&I가 연동 |
| Policy Engine | Policy Engine | external | 검증 요청/결과 수신 패턴 고유. W&I가 연동 |

---

## 4. 서비스별 제공 위치 표

서비스명은 C2 컨테이너의 핵심 책임을 포괄하는 이름으로 정의한다.

| 서비스 | 제공 Node | 경계 | 접근 주체 | 이유 | 비고 |
|---|---|---|---|---|---|
| API 게이트웨이 | Web Application | public | Developer, Reviewer, PM / PO, IDE Plugin | 브라우저와 IDE Plugin이 모두 연결되는 public gateway이므로 public에 위치 | 인증/인가 · 세션 관리 · API 라우팅 |
| 대화형 지원 | Interactive Assistant | private | Web Application | 사용자 요청은 Web App이 WebSocket으로 중계하므로 직접 노출할 필요 없음 | 코드베이스 질의응답 · 구조·규칙 설명 |
| 코드 분석 | Analysis Engine | private | Interactive Assistant, Workflow & Integration | 분석 요청은 Interactive Assistant·Workflow & Integration을 통해서만 도달하며 독립 스케일링이 필요한 CPU 집약 작업 | 구조·영향도·테스트 분석 · 규칙 추출 · 갭 분석 |
| 워크플로우 관리 | Workflow & Integration | private | Web Application, 외부 Integration Channels | 외부 채널 프로토콜을 이 Node에 집중시켜 내부 컨테이너를 프로토콜 변경으로부터 격리 | PR 자동화 · 전달 워크플로우 · 외부 연동 · 리포트 |
| 지식 관리 | Knowledge Base | data | Interactive Assistant, Analysis Engine, Workflow & Integration, Data Processing | SSOT로서 접근 주체가 한정되며 저장 기술(Graph DB·Object Storage·Vector DB)이 고유하여 독립 영역 분리 | CPG 그래프 · 원본 스냅샷 · 분석 산출물 · 임베딩 |
| 데이터 처리 | Data Processing | private | Data Collection | 수집 원본을 CPG·임베딩으로 변환하여 Knowledge Base에 적재하는 내부 전용 파이프라인 | CPG 생성 · 임베딩 생성 · 규칙 패턴 식별 · Knowledge Base 적재 |
| 데이터 수집 | Data Collection | private | 외부 Data Sources (Code Repository, Issue Tracker + Docs/Wiki) | 외부 소스에서 데이터를 당겨오는 수집 전용으로 외부 노출 불필요 | 개발 자산 수집 · 증분 동기화 · 업로드 |
| LLM 서비스 | Public LLM Provider / Local LLM | external | Interactive Assistant, Analysis Engine, Data Processing | TCI 외부 서비스이며 용도별(대화 추론·임베딩 생성·규칙 해석) 호출 | 대화 추론 · 임베딩 |
| 플랫폼 서비스 | Platform & Infra | external | Web Application, Workflow & Integration | TCI 외부 서비스이며 인증·로그·모니터링을 위임받아 처리 | 인증/인가 · SSO · 로그 · 모니터링 |
| IDE 확장 | IDE Plugin | public | Developer | 개발자 로컬 환경에서 직접 조작하는 public client node이며 Web Application으로 요청을 중계 | 로컬 코드 변경 수집 · 컨텍스트 조회 |

---

## 5. 상위 경계 초안

### 4영역 정의 (팀 합의: 4영역(public/private/data/external) 확정)

| 영역 | 정의 | 핵심 특성 | 선택 근거 |
|---|---|---|---|
| **public** | 사용자가 직접 접근할 수 있는 클라이언트/진입 영역 | 사용자가 직접 상호작용하는 client node와 외부 트래픽을 수신하는 gateway를 포함한다 | 팀 합의: 4영역 정의에서 확정 |
| **private** | 우리 시스템 내부 영역 | 핵심 분석/처리/수집/연동 로직이 동작하는 영역. 사용자가 직접 접근할 수 없으며 반드시 public을 경유해야 한다 | 팀 합의: 4영역 정의에서 확정 |
| **data** | 저장소/지식 허브처럼 데이터 중심 역할을 하는 영역 | 영속 데이터를 보관하는 영역. private 영역의 특정 서비스에서만 접근하며 외부에 직접 노출되지 않는다 | 팀 합의: 4영역 정의에서 확정. Knowledge Base 중심 아키텍처 근거로 data 영역을 독립 경계로 선택 |
| **external** | 우리 시스템 바깥에 있는 외부 서비스 영역 | TCI가 직접 통제하지 않는 시스템. Data Sources, 외부 연동 채널, Foundation Services를 포함한다 | 팀 합의: 4영역 정의에서 확정 |

### data를 4번째 영역으로 선택한 근거 (팀 합의: data 영역 선택 근거)

1. **Knowledge Base 중심 아키텍처** -- TCI의 핵심 설계 원칙. 모든 분석 산출물의 SSOT이므로 독립 경계가 타당
2. **접근 제어 표현** -- Knowledge Base에 직접 접근하는 컨테이너가 한정됨(Interactive Assistant, Analysis Engine, Workflow & Integration, Data Processing). 경계를 분리하면 접근 관계가 다이어그램에서 명확히 드러남
3. **표준 패턴 부합** -- Presentation / Application / Data / External 4계층은 엔터프라이즈 배포에서 널리 사용되는 패턴
4. **admin 미채택** -- Platform & Infra는 TCI 외부 시스템(external)으로 이미 분류 가능. 별도 admin 영역 분리 시 설명 이득이 크지 않음

### 영역별 Node 배치

| 경계 | 포함 Node | 배치 근거 |
|---|---|---|
| **public** | Web Application, IDE Plugin | Web Application은 브라우저 기반 gateway, IDE Plugin은 개발자 로컬 IDE에서 동작하는 public client node다. 둘 다 사용자가 직접 접하는 진입 채널이다. 팀 합의: 영역별 Node 배치에서 확정 |
| **private** | Interactive Assistant, Analysis Engine, Workflow & Integration, Data Processing, Data Collection | 핵심 분석/처리/수집/연동 로직. public을 경유해야만 사용자 요청이 도달하며, 직접 외부 노출 없음. 팀 합의: 영역별 Node 배치에서 확정 |
| **data** | Knowledge Base (단일 Top-level Node, 내부 nested EE: Graph DB Runtime / Object Storage Runtime / Vector DB Runtime) | Knowledge Base 중심 아키텍처의 SSOT. private 영역의 특정 컨테이너(Interactive Assistant, Analysis Engine, Workflow & Integration, Data Processing)에서만 접근. 팀 합의: 영역별 Node 배치에서 확정 |
| **external** | Code Repository, Issue Tracker + Docs/Wiki, CI/CD, Collaboration Tools, AI Coding Agent, Policy Engine, Public LLM Provider / Local LLM, Platform & Infra | TCI가 직접 통제하지 않는 외부 시스템. Foundation Services도 TCI 시스템 경계 밖이므로 이 영역에 포함. 팀 합의: 영역별 Node 배치에서 확정 |

---

## 6. 우리 시스템 / 외부 서비스 구분표

구분 기준: Deployment Diagram에서는 배포 주체와 통제 수준을 기준으로 우리 시스템/외부 서비스를 구분한다.

| 대상 | 구분 | 통제 수준 | 비고 |
|---|---|---|---|
| Web Application | 우리 시스템 | 직접 통제 | C2 Container Diagram: System_Boundary 내부에 정의됨. public 경계 |
| Interactive Assistant | 우리 시스템 | 직접 통제 | C2 Container Diagram: System_Boundary 내부에 정의됨. private 경계 |
| Analysis Engine | 우리 시스템 | 직접 통제 | C2 Container Diagram: System_Boundary 내부에 정의됨. private 경계 |
| Workflow & Integration | 우리 시스템 | 직접 통제 | C2 Container Diagram: System_Boundary 내부에 정의됨. private 경계 |
| Knowledge Base | 우리 시스템 | 직접 통제 | C2 Container Diagram: System_Boundary 내부에 정의됨. data 경계 |
| Data Processing | 우리 시스템 | 직접 통제 | C2 Container Diagram: System_Boundary 내부에 정의됨. private 경계 |
| Data Collection | 우리 시스템 | 직접 통제 | C2 Container Diagram: System_Boundary 내부에 정의됨. private 경계 |
| Public LLM Provider / Local LLM | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Foundation) |
| Platform & Infra | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Foundation) |
| Code Repository | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Data Sources) |
| Issue Tracker + Docs/Wiki | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Data Sources) |
| CI/CD | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Integration) |
| Collaboration Tools | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Integration) |
| AI Coding Agent | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Integration) |
| Policy Engine | 외부 서비스 | 연동만 가능 | C2 External View: System_Ext로 정의됨. external 경계 (Integration) |
| IDE Plugin | 우리 시스템 | 직접 통제 (배포형 클라이언트) | C2 Container Diagram: System_Boundary 내부에 정의됨. public 경계 |

---

## 7. Node별 Execution Environment

### 변경 경위

초기 팀 합의(기준문서 전제 조건 #3)에서 Execution Environment를 이번 범위에서 제외했으나, 배포 다이어그램의 실행 환경 명시가 필요하다는 후속 요청에 따라 범위에 포함한다. 다만 EE는 Top-level Node를 대체하는 요소가 아니라 Node 내부에 중첩되는 실행 호스팅 레이어로 다룬다.

### EE 표현 원칙

| # | 원칙 | 설명 |
|---|---|---|
| 1 | **Docker 기반** | 모든 TCI 서버측 내부 서비스의 EE는 Docker 위에서 동작한다. 단, IDE Plugin은 예외적으로 로컬 IDE Host Runtime 위에서 동작하며 Docker를 사용하지 않는다 |
| 2 | **2-레이어 EE 표현** | TCI 서버측 EE는 Docker(외부 컨테이너) + Runtime EE(내부 실행환경) 2단계로 표현한다. IDE Plugin은 client runtime이므로 로컬 IDE Host Runtime 단일 레이어로 표현한다. OS 레이어는 아키텍처 설명용 그림의 추상 수준을 넘으므로 표기하지 않는다 |
| 3 | **Top-level Node와 EE 분리** | Execution Environment는 범위에 포함되지만 Top-level Node 수에는 포함하지 않는다. C2 1:1 매핑은 Top-level Node 계층에만 적용한다 |
| 4 | **런타임 추상화** | 내부 개발 스택이 미선정이므로 구체적 언어 런타임(Python, JVM 등)을 명시하지 않고 `Application Runtime`으로 추상화한다. 스택 확정 시 갱신한다 |
| 5 | **Data Collection/Data Processing 독립 EE 유지** | Data Collection과 Data Processing은 각각 독립 Docker + Application Runtime을 사용한다. 파이프라인 연속성은 직접 통신선으로 표현한다 |
| 6 | **Knowledge Base 내부 runtime 분리** | Knowledge Base는 단일 Top-level Node를 유지하되, 내부에 Graph DB Runtime / Object Storage Runtime / Vector DB Runtime 3개를 중첩한다 |
| 7 | **Foundation conceptual external EE** | Public LLM Provider / Local LLM과 Platform & Infra에는 conceptual external EE를 부여한다. 이는 외부 서비스 특성 표현용이며 TCI 관리 대상이 아니다 |
| 8 | **대상 범위** | TCI가 직접 통제하는 Node 8개(서버측 7개 + IDE Plugin 1개) + Foundation Services 2개에 EE를 부여한다 |
| 9 | **클라이언트 Runtime 포함** | IDE Plugin은 public client node이므로 IDE Host Runtime을 별도 EE로 포함한다. 따라서 Docker 인스턴스 수와 nested EE 수는 동일하지 않을 수 있다 |

### EE 그룹핑 표

정리하면 Top-level Node 수는 16개를 유지하고, EE는 TCI가 직접 통제하는 10개 nested EE(서버측 Docker 9개 + IDE Host Runtime 1개) + Foundation 2개 conceptual external EE로 추가된다.

#### TCI 직접 통제 Node (9 Docker 인스턴스 + 1 Client Runtime / 10 nested EE)

| EE 그룹 | Top-level Node | 호스팅 레이어 | Runtime EE | Runtime 역할 | 그룹핑 근거 |
|---|---|---|---|---|---|
| 1 | Web Application | Web App | Web Server Runtime | 정적 자산 서빙 · API 라우팅 | 프론트엔드 고유 기술 스택과 사용자 진입점 특성이 있어 독립 Docker 인스턴스 |
| 2 | Interactive Assistant | Interactive Assistant | Application Runtime | 세션 처리 · 대화 오케스트레이션 | GPU/토큰 독립 스케일링 필요. 실시간 대화형 패턴이 고유 |
| 3 | Analysis Engine | Analysis Engine | Application Runtime | 구조/영향 분석 실행 | CPU/메모리 독립 스케일링 필요. 비동기 배치 분석 패턴이 고유 |
| 4 | Workflow & Integration | Workflow & Integration | Application Runtime | 이벤트 오케스트레이션 · 외부 연동 | I/O 독립 스케일링 필요. 이벤트/스케줄 오케스트레이션 패턴이 고유 |
| 5 | Data Collection | Data Collection | Application Runtime | 수집 커넥터 · 증분 동기화 | 외부 소스 커넥터, 동기화 스케줄, 네트워크 I/O 프로파일이 고유 |
| 6 | Data Processing | Data Processing | Application Runtime | CPG/임베딩 처리 · Knowledge Base 적재 | CPG 생성, 임베딩 생성, Knowledge Base 적재가 CPU/메모리 중심 배치 처리 패턴을 가짐 |
| 7 | Knowledge Base | KB — Graph DB | Graph DB Runtime | 그래프 질의 · 저장 | 그래프 탐색과 질의 최적화가 필요한 저장 엔진이므로 독립 인스턴스 |
| 8 | Knowledge Base | KB — Object Storage | Object Storage Runtime | 스냅샷 · 산출물 저장 | 대용량 파일 저장과 객체 스토리지 엔진 특성이 별도 |
| 9 | Knowledge Base | KB — Vector DB | Vector DB Runtime | 임베딩 인덱싱 · 유사도 검색 | 벡터 인덱스와 ANN 검색 엔진 특성이 별도 |
| 10 | IDE Plugin | 로컬 IDE Host | IDE Host Runtime | 로컬 변경 수집 · 컨텍스트 조회 | TCI가 직접 배포하는 public client node이며 로컬 IDE 프로세스 안에서 동작하므로 Docker 대신 Host IDE Runtime으로 표현 |

#### Foundation Services (conceptual external EE, Docker 레이어 없음)

| EE 그룹 | Top-level Node | Runtime EE | Runtime 역할 | 비고 |
|---|---|---|---|---|
| 11 | Public LLM Provider / Local LLM | LLM Inference Runtime | 대화 추론 · 임베딩 API 제공 | conceptual external EE. 외부 서비스 특성 표현용이며 TCI가 실제 런타임을 통제하지 않는다 |
| 12 | Platform & Infra | Platform Service Runtime | 인증/인가 · 로그 · 모니터링 제공 | conceptual external EE. 외부 플랫폼 서비스 특성을 나타내며 vendor 내부 구현을 단정하지 않는다 |

### EE 그룹 상세

#### Data Collection / Data Processing 독립 Application Runtime (EE 그룹 5, 6)

C2에서 Data Collection과 Data Processing은 이미 별개 컨테이너다. Deployment EE도 이 분리를 유지한다.

| 항목 | 설명 |
|---|---|
| C2 정의 | Data Collection·Data Processing은 별개 컨테이너 (관심사 분리: 수집 vs 전처리) |
| EE 결정 | 각각 독립 Docker 인스턴스 + 독립 Application Runtime |
| 분리 근거 | Data Collection은 외부 소스 커넥터와 증분 동기화 중심의 네트워크 I/O 프로파일, Data Processing은 CPG/임베딩 생성 중심의 CPU·메모리 프로파일을 가진다 |
| 운영 근거 | 수집 커넥터 장애와 전처리 배치 장애를 분리해 격리할 수 있고, 스케줄 운영 주기도 다르다 |
| 통신 보완 | Data Collection→Data Processing 직접 연결은 02 통신표의 내부 호출로 이미 표현되므로, 저지연 전달 요구는 co-location 없이도 설명 가능하다 |

#### Interactive Assistant/Analysis Engine/Workflow & Integration 독립 Application Runtime (EE 그룹 2, 3, 4)

C2 분리 근거와 동일한 이유로 각각 독립 Docker 컨테이너 + 독립 Application Runtime을 부여한다.

| 비교 축 | Interactive Assistant | Analysis Engine | Workflow & Integration |
|---|---|---|---|
| 핵심 리소스 | GPU/토큰 | CPU/메모리 | 네트워크 I/O |
| 실행 패턴 | 실시간 대화형 | 배치/온디맨드 | 이벤트/스케줄 |
| 스케일링 | 세션 수 비례 | 분석 작업량 비례 | 외부 이벤트 빈도 비례 |

세 서비스의 스케일링 프로파일과 실행 패턴이 근본적으로 다르므로 독립 배포·스케일링이 필요하다.

#### Knowledge Base 단일 Top-level Node + 내부 3개 Nested Runtime (EE 그룹 7, 8, 9)

기존 Knowledge Base 특칙은 "단일 Node + 내부 Artifact 3개"였다. 이 원칙은 유지하되, 각 Artifact는 필요 시 서로 다른 nested Runtime EE 안에 놓인다.

| DB 유형 | Nested Runtime EE | 분리 근거 |
|---|---|---|
| Graph DB | Graph DB Runtime | CPG 그래프 질의는 그래프 엔진 고유의 리소스 프로파일(메모리 집약, 탐색 최적화)을 가진다 |
| Object Storage | Object Storage Runtime | 대용량 파일(코드 스냅샷, 분석 산출물) 저장은 별도 스토리지 엔진이 필요하다 |
| Vector DB | Vector DB Runtime | 임베딩 유사도 검색은 벡터 인덱스 전용 엔진(ANN 알고리즘)이 필요하다 |

메인 그림에서는 Knowledge Base를 하나의 Top-level Node로만 카운트한다. 필요 시 그 내부에 3개의 Docker + Runtime EE를 중첩한다. 즉, 논리적 Node(Knowledge Base)와 내부 runtime EE 수는 동일하지 않다.

#### IDE Plugin 로컬 Client Runtime (EE 그룹 10)

IDE Plugin은 server-side runtime이 아니지만, C2 내부 컨테이너로서 TCI가 직접 통제하는 public client node이므로 EE 표에도 포함한다.

| 항목 | 설명 |
|---|---|
| C2 출처 | C2 Container Diagram: System_Boundary 내부의 IDE Plugin 컨테이너 |
| Deployment 처리 | C2 내부 컨테이너이며 public client node로 Web Application과 별도 Top-level Node 유지 |
| EE 결정 | Docker 없이 IDE Host Runtime 1개를 부여 |
| 분리 근거 | VS Code / IntelliJ 프로세스 안에서 실행되며 로컬 workspace 접근, IDE UI 상호작용, Plugin API 호출이 모두 클라이언트 런타임 특성에 속한다 |
| 표현 효과 | 서버측 EE와 별도로 로컬 개발자 환경까지 포함한 end-to-end 배포 경로를 설명할 수 있다 |

#### Foundation conceptual external EE (EE 그룹 11, 12)

Foundation Services는 TCI가 직접 배포하거나 통제하는 런타임이 아니다. 그럼에도 연동 설계상 런타임 특성 구분이 중요하므로 conceptual external EE를 부여한다.

| 대상 | 표현 원칙 |
|---|---|
| Public LLM Provider / Local LLM | 대화 추론/임베딩 API를 제공하는 외부 추론 런타임으로 추상화하되, 특정 벤더의 내부 배포 구조를 단정하지 않는다 |
| Platform & Infra | 인증/인가, 로그, 모니터링을 제공하는 외부 플랫폼 런타임으로 추상화하되, 실제 운영 방식은 TCI 관리 범위 밖으로 둔다 |

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

[Top-level Node] Data Collection
  └── [Docker] Data Collection
        └── <<EE>> Application Runtime

[Top-level Node] Data Processing
  └── [Docker] Data Processing
        └── <<EE>> Application Runtime

[Top-level Node] Knowledge Base
  ├── [Docker] KB — Graph DB
  │     └── <<EE>> Graph DB Runtime
  ├── [Docker] KB — Object Storage
  │     └── <<EE>> Object Storage Runtime
  └── [Docker] KB — Vector DB
        └── <<EE>> Vector DB Runtime

[Top-level Node] Public LLM Provider / Local LLM (external)
  └── <<conceptual EE>> LLM Inference Runtime

[Top-level Node] Platform & Infra (external)
  └── <<conceptual EE>> Platform Service Runtime
```

### C2 매핑과의 관계

EE 레이어의 추가로, 논리적 서비스 구조(C2)와 물리적 배포 구조(Deployment)에 차이가 생긴다. 이 차이는 의도된 것이며, 각각 다른 관점의 정보를 전달한다.

| 관점 | C2 (논리적) | Deployment — EE (물리적) | 차이 |
|---|---|---|---|
| Web Application | 별개 컨테이너 (1개) | Top-level Node 1개 + Docker 1개 + Runtime EE 1개 | EE 레이어만 추가됨 |
| Interactive Assistant, Analysis Engine, Workflow & Integration | 각각 별개 컨테이너 (3개) | 각각 독립 Docker 인스턴스 + Runtime EE | 변화 없음 — C2 분리와 EE 분리가 일치 |
| Data Collection | 별개 컨테이너 (1개) | 독립 Docker 인스턴스 + Application Runtime | 변화 없음 — I/O 중심 런타임으로 독립 유지 |
| Data Processing | 별개 컨테이너 (1개) | 독립 Docker 인스턴스 + Application Runtime | 변화 없음 — CPU/배치 중심 런타임으로 독립 유지 |
| Knowledge Base | 단일 ContainerDb (1개) | 단일 Top-level Node + 내부 3개 nested Runtime EE | 논리적 단일 Node 유지, 저장소별 runtime 분리 |
| IDE Plugin | System_Boundary 내부 컨테이너 (1개) | Top-level Node 1개 + IDE Host Runtime 1개 | C2 내부 컨테이너이며 클라이언트 런타임을 별도 표현 |
| Foundation Services | 외부 서비스 (2개) | 외부 Node + conceptual external EE | 연동 특성 표현용 EE만 추가됨 |

---
