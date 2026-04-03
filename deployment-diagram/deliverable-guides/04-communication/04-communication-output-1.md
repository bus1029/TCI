# 통신 표 산출물 #1

출처: [https://www.notion.so/336c21d54f42809ca252d2980739a103](https://www.notion.so/336c21d54f42809ca252d2980739a103)

## 1. 표기 기준

- 포트 번호는 쓰지 않는다
- 같은 연결은 같은 이름으로 표기한다

---

## 2. Node 간 연결 표

### Actor 진입 (4행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| Developer | Web Application | → | HTTPS | 코드 탐색 · 질의 | 브라우저 경유 |
| Developer | IDE Plugin | → | IDE UI | 로컬 변경 업로드 · 컨텍스트 조회 시작 | IDE 내부 UI/명령 진입 |
| Reviewer | Web Application | → | HTTPS | PR 리뷰 · 리스크 판단 | 브라우저 경유 |
| PM / PO | Web Application | → | HTTPS | 갭 분석 · 리포트 | 브라우저 경유 |

### public ↔ public (1행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| IDE Plugin | Web Application | → | Plugin API | 로컬 변경 업로드 · 컨텍스트 조회 | public client → public gateway |

### public ↔ private (4행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| Web Application | Interactive Assistant | → | WebSocket | 대화형 세션 중계 | 실시간 양방향 스트리밍 |
| Web Application | Workflow & Integration | → | HTTPS | 리포트·자동화 API 호출 | 단발성 요청-응답 |
| Web Application | Data Collection | → | HTTPS | 파일·문서 업로드 전달 | 업로드 intake · 변경 업로드 라우팅 |
| Workflow & Integration | Web Application | → | SSE / WebSocket | 실시간 알림 푸시 | 서버→클라이언트 단방향 푸시 |

### private ↔ private (3행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| Interactive Assistant | Analysis Engine | → | gRPC (async) | 온디맨드 분석 요청 | 비동기 내부 고성능 통신 |
| Workflow & Integration | Analysis Engine | → | Internal API | 분석 실행 트리거 | 내부 서비스 간 직접 호출 |
| Data Collection | Data Processing | → | Internal API | 수집 데이터 전달 | 내부 서비스 간 직접 호출 |

### private ↔ data (4행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| Interactive Assistant | Knowledge Base | ↔ | Graph R/W | 구조·규칙 검색 / 답변·이력 적재 | 그래프 DB 네이티브 프로토콜 |
| Analysis Engine | Knowledge Base | ↔ | Graph R/W | 그래프 질의 · 분석 결과 적재 | 그래프 DB 네이티브 프로토콜 |
| Workflow & Integration | Knowledge Base | <- | Graph Read | 분석 산출물 조회 · 추적 메타 적재 | 읽기 전용 |
| Data Processing | Knowledge Base | → | Graph Write | CPG·임베딩 적재 | 쓰기 전용 |

### private → external — Data Sources (2행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| Data Collection | Code Repository | → | Git Protocol | 코드 저장소 수집 | 소스 코드·커밋·브랜치 |
| Data Collection | Issue Tracker + Docs/Wiki | → | REST / Upload | 문서·티켓·PR 수집 | 문서·티켓·PR·Wiki |

### private ↔ external — Integration Channels (4행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| Workflow & Integration | CI/CD | → | Webhook / REST | PR 이벤트 연동 · Gate 결과 반영 | 이벤트 기반 비동기 연동 |
| Workflow & Integration | Collaboration Tools | → | REST API / Bot API | 알림 · 코멘트 · 문서 발행 | Slack / Teams 봇 연동 |
| Workflow & Integration | AI Coding Agent | ↔ | MCP / REST | 컨텍스트 패키지 제공 / 작업 변경 전달·영향 분석 요청 | AI 에이전트 양방향 연동 |
| Workflow & Integration | Policy Engine | ↔ | REST | 정책 검증 요청 / 정책 위반 결과 반환 | 검증 요청-결과 수신 |

### Foundation Services (5행)

| 출발 Node | 도착 Node | 방향 | 프로토콜 | 목적 | 비고 |
|---|---|---|---|---|---|
| Interactive Assistant | Public LLM Provider / Local LLM | → | REST / HTTPS | 대화형 추론 | 용도별 호출 |
| Analysis Engine | Public LLM Provider / Local LLM | → | REST / HTTPS | 비즈니스 규칙 해석 | 용도별 호출 |
| Data Processing | Public LLM Provider / Local LLM | → | REST / HTTPS | 임베딩 생성 | 용도별 호출 |
| Web Application | Platform & Infra | → | REST / HTTPS | 인증·인가 위임 | SSO 포함 |
| Workflow & Integration | Platform & Infra | → | REST / HTTPS | 로그·운영 인프라 사용 | 모니터링 포함 |

---

## 3. 프로토콜 요약

| 프로토콜 | 사용 위치 | 특성 |
|---|---|---|
| **HTTPS** | Actor 브라우저 진입 (Developer/Reviewer/PM·PO → Web Application), API 호출 (Web Application → Workflow & Integration, Web Application → Data Collection) | 단발성 요청-응답 |
| **IDE UI** | Developer → IDE Plugin | 로컬 IDE 내부 UI/명령 기반 진입 |
| **REST / HTTPS** | Foundation 연동 (Interactive Assistant/Analysis Engine/Data Processing → Public LLM Provider / Local LLM, Web Application/Workflow & Integration → Platform & Infra) | 외부 서비스 API 호출 |
| **WebSocket** | Web Application → Interactive Assistant, Workflow & Integration → Web Application | 실시간 양방향 스트리밍 |
| **SSE** | Workflow & Integration → Web Application | 서버→클라이언트 단방향 푸시 |
| **gRPC (async)** | Interactive Assistant → Analysis Engine | 비동기 분석 요청, 내부 고성능 통신 |
| **Internal API** | Workflow & Integration → Analysis Engine, Data Collection → Data Processing | 내부 서비스 간 직접 호출 |
| **Graph R/W** | Interactive Assistant ↔ Knowledge Base, Analysis Engine ↔ Knowledge Base, Workflow & Integration <- Knowledge Base (Read), Data Processing → Knowledge Base (Write) | 그래프 DB 네이티브 프로토콜 |
| **Git Protocol** | Data Collection → Code Repository | 코드 저장소 수집 전용 |
| **REST / Upload** | Data Collection → Issue Tracker + Docs/Wiki | 문서·티켓 수집 |
| **Webhook / REST** | Workflow & Integration → CI/CD | 이벤트 기반 비동기 연동 |
| **REST API / Bot API** | Workflow & Integration → Collaboration Tools | Slack / Teams 봇 연동 |
| **MCP / REST** | Workflow & Integration ↔ AI Coding Agent | Model Context Protocol, AI 에이전트 연동 |
| **REST** | Workflow & Integration ↔ Policy Engine | 정책 검증 요청-결과 수신 |
| **Plugin API** | IDE Plugin → Web Application | 로컬 IDE 확장과 public gateway 간 연동 |

---

## 4. 완료 기준

표기 기준과 연결 표가 같은 문서 안에 있고, 최종 그림의 모든 선이 표에 있다.
