# 사용자 진입 / 외부 시스템 #1

출처: [https://www.notion.so/336c21d54f428084af7ff72c223728e9](https://www.notion.so/336c21d54f428084af7ff72c223728e9)

## 1. 사용자 진입 경로 표

**이 산출물이 하는 일**: 사람 액터가 어떤 public 진입 채널로 어떤 Node에 먼저 도달하는지 정리한다. AI Coding Agent 같은 비인간 소비자 채널은 외부 시스템별 접속 지점 표에서 별도 관리한다.

| 액터 | 직접 진입 채널 | 최초 진입 Node | 이후 연결 | 비고 |
|---|---|---|---|---|
| Developer | 웹 브라우저 (HTTPS) | Web Application | Interactive Assistant (WebSocket) · Workflow & Integration (HTTPS) · Data Collection (HTTPS) | 브라우저 기반 직접 진입 경로 |
| Developer | IDE Plugin (IDE UI) | IDE Plugin | Web Application (Plugin API) | IDE Plugin은 Web Application으로만 연결. 이후 경로는 브라우저 진입과 동일 |
| Reviewer | 웹 브라우저 (HTTPS) | Web Application | Interactive Assistant (WebSocket) · Workflow & Integration (HTTPS) · Data Collection (HTTPS) | PR 리뷰 중 질의, Policy Gate 확인, 리뷰 자료 업로드 |
| PM / PO | 웹 브라우저 (HTTPS) | Web Application | Interactive Assistant (WebSocket) · Workflow & Integration (HTTPS) · Data Collection (HTTPS) | 비즈니스 규칙 탐색, 리포트 생성, 스펙 문서 업로드 |

> **public client 해석 원칙**: Deployment 관점에서는 IDE Plugin을 사용자가 직접 접하는 client node로 본다. 따라서 Developer의 직접 진입 경로에 포함하고, 이후 서버측 public node인 Web Application으로 연결한다.
>
> **파일 업로드 → Data Collection 경로**: C1 Actor→TCI Rel에서 "파일 업로드"가 명시되고, C3 Web Application/Data Collection 문서에 Web Application → Data Collection 업로드 경로가 명시돼 있다. Deployment 문서에서는 브라우저 업로드와 IDE Plugin 업로드 모두 Web Application → Data Collection로 수렴하는 경로로 정리한다.

---

## 2. 외부 시스템 역할군 표

**이 산출물이 하는 일**: C1 외부 시스템 전체를 역할군으로 분류하고, 묶음 판단 근거를 기재한다.

**역할군 묶음 4기준** (팀 합의: 외부 시스템을 개별 유지하되, 4기준(연동 컨테이너·프로토콜·흐름 방향·가독성)에 따라 묶음 가능):
1. **연동 컨테이너** — 같은 TCI 컨테이너가 연동하는가
2. **프로토콜** — 프로토콜 패턴이 유사한가
3. **흐름 방향** — inbound / outbound / 양방향이 같은가
4. **가독성** — 묶었을 때 노드 수가 줄어 그림이 간결해지는가

| 역할군 | 외부 시스템 | 표현 방식 | 역할군 지정 이유 | 표현 방식 이유 |
|---|---|---|---|---|
| Data Sources | Code Repository | 단독 유지 | DC가 수집하는 개발 자산 원천(소스 코드·커밋·브랜치) | Git Protocol이 고유하여 REST 기반 시스템과 묶으면 프로토콜 차이가 가려짐 |
|  | Issue Tracker + Docs/Wiki | 단독 유지 | DC가 수집하는 개발 자산 원천(문서·티켓·PR·Wiki) | 통합 명칭 자체를 최종 Node 이름으로 사용하므로 별도 축약명 없이 유지한다 |
| Integration Channels | DevOps Pipeline | 단독 유지 | W&I를 통해 TCI와 이벤트·결과를 교환하는 외부 연동 채널 | Webhook 수신 + Gate 응답 오케스트레이션 패턴이 고유 |
|  | Collaboration Tools | 단독 유지 | W&I를 통해 외부로 알림·코멘트를 전달하는 연동 채널 | Bot API 패턴이 고유하고 outbound 전용이라 다른 채널과 성격 상이 |
|  | AI Coding Agent | 단독 유지 | W&I를 통해 개발자 Agent와 컨텍스트를 교환하는 연동 채널 | MCP 프로토콜 고유, 양방향 컨텍스트 교환 패턴이 다른 채널에 없음 |
|  | Policy Engine | 단독 유지 | W&I를 통해 사내 정책 검증을 수행하는 연동 채널 | 검증 요청→결과 수신 전용 패턴이 고유 |
| Foundation Services | Public LLM Provider / Local LLM | 단독 유지 | Interactive Assistant, Analysis Engine, Data Processing이 용도별로 호출하는 AI 추론·임베딩 기반 서비스 | 호출 주체(Interactive Assistant, Analysis Engine, Data Processing)와 용도(추론·임베딩·해석)가 각각 달라 단일 Node로 표현 |
|  | Platform & Infra | 단독 유지 | Web Application과 Workflow & Integration이 인증·로그·모니터링을 위임하는 인프라 기반 서비스 | Public LLM Provider / Local LLM과 호출 주체·프로토콜·목적이 모두 달라 별도 Node로 표현 |

---

## 3. 외부 시스템별 접속 지점 표

**이 산출물이 하는 일**: 각 외부 시스템이 어느 내부 Node와 연결되는지, 방향·프로토콜을 정리한다.

| 외부 시스템 | 연결 주체 Node | 방향 | 프로토콜 | 비고 |
|---|---|---|---|---|
| Code Repository | Data Collection | Data Collection → Code Repository | Git Protocol | Rel(collection, codeRepo, ...) 기준. 수집 주체와 화살표가 모두 Data Collection에서 출발한다. |
| Issue Tracker + Docs/Wiki | Data Collection | Data Collection → Issue Tracker + Docs/Wiki | REST / Upload | 기준 관계 정의상 문서·티켓·PR 수집 대상이며, REST / Upload 표기가 기준문서와도 일치한다. |
| DevOps Pipeline | Workflow & Integration | Workflow & Integration → DevOps Pipeline | Webhook / REST | Rel(workflow, devops, ...) 기준. PR 이벤트 연동과 Gate 결과 반영 관계라 Webhook / REST를 유지했다. |
| Collaboration Tools | Workflow & Integration | Workflow & Integration → Collaboration Tools | REST API / Bot API | Rel(workflow, collab, ...) 기준. 알림·코멘트·문서 발행을 함께 묶은 채널이라 REST API / Bot API로 표기했다. |
| AI Coding Agent | Workflow & Integration | Workflow & Integration → AI Coding Agent | MCP / REST | Rel(workflow, aiAgent, ...) 기준. W&I가 컨텍스트 패키지를 제공하는 outbound 관계다. |
| AI Coding Agent | Workflow & Integration | AI Coding Agent → Workflow & Integration | MCP / REST | Rel(aiAgent, workflow, ...) 기준. Agent가 작업 변경 전달·영향 분석 요청을 보내는 inbound 관계다. |
| Policy Engine | Workflow & Integration | Workflow & Integration → Policy Engine | REST | Rel(workflow, policyEngine, ...) 기준. 정책 검증 요청을 보내는 outbound 관계다. |
| Policy Engine | Workflow & Integration | Policy Engine → Workflow & Integration | REST | Rel(policyEngine, workflow, ...) 기준. 정책 위반 결과를 반환하는 inbound 관계를 별도 행으로 분리했다. |
| Public LLM Provider / Local LLM | Interactive Assistant | Interactive Assistant → Public LLM Provider / Local LLM | REST / HTTPS | 기준 관계 정의상 대화형 추론 호출이므로 IA가 주체다. |
| Public LLM Provider / Local LLM | Analysis Engine | Analysis Engine → Public LLM Provider / Local LLM | REST / HTTPS | 기준 관계 정의상 비즈니스 규칙 해석 호출을 AE가 수행한다. |
| Public LLM Provider / Local LLM | Data Processing | Data Processing → Public LLM Provider / Local LLM | REST / HTTPS | 기준 관계 정의상 임베딩 생성 호출이므로 DP가 주체다. |
| Platform & Infra | Web Application | Web Application → Platform & Infra | REST / HTTPS | Rel(webapp, platform, ...) 기준. 인증·인가 위임과 SSO는 Web Application 책임이다. |
| Platform & Infra | Workflow & Integration | Workflow & Integration → Platform & Infra | REST / HTTPS | Rel(workflow, platform, ...) 기준. 로그·운영 인프라 사용 주체가 W&I로 명시돼 있다. |

---

## 4. 외부 채널 접점 표

**이 산출물이 하는 일**: 외부 시스템별 접속 지점 표를 채널 단위로 재그룹핑하여 주요 접점을 한눈에 파악한다.

**채널 그룹핑 기준**: 팀 합의 외부 시스템 역할군 분류 (Data Sources / Integration Channels / Foundation Services)

| 외부 채널 | 연결 Node | 대표 예시 | 프로토콜 | 비고 |
|---|---|---|---|---|
| 코드 수집 채널 | Data Collection | Code Repository | Git Protocol | Data Collection이 코드 저장소에서 소스 코드·커밋을 수집하는 입력 채널이다. |
| 개발 맥락 수집 채널 | Data Collection | Issue Tracker + Docs/Wiki | REST / Upload | 문서·티켓·PR을 같은 수집 경로로 받아들이는 입력 채널이다. |
| 자동화 연동 채널 | Workflow & Integration | DevOps Pipeline | Webhook / REST | PR 이벤트 연동과 Gate 결과 반영을 Workflow & Integration이 담당한다. |
| 협업 전달 채널 | Workflow & Integration | Collaboration Tools | REST API / Bot API | 알림·코멘트·문서 발행을 외부 협업 도구로 전달하는 채널이다. |
| AI 연동 채널 | Workflow & Integration | AI Coding Agent | MCP / REST | 컨텍스트 제공과 영향 분석 요청이 오가는 양방향 채널이다. |
| 정책 검증 채널 | Workflow & Integration | Policy Engine | REST | 정책 검증 요청을 보내고 결과를 반환받는 검증 채널이다. |
| LLM 추론 채널 | Interactive Assistant, Analysis Engine, Data Processing | Public LLM Provider / Local LLM | REST / HTTPS | Interactive Assistant·Analysis Engine·Data Processing이 각각 대화형 추론, 규칙 해석, 임베딩 생성에 공통 사용한다. |
| 플랫폼 위임 채널 | Web Application, Workflow & Integration | Platform & Infra | REST / HTTPS | Web Application은 인증·인가를 위임하고 W&I는 로그·운영 인프라를 사용한다. |

---

**완료 기준**: 사용자 진입과 외부 시스템 접점이 한 묶음 안에서 이어진다.

---
