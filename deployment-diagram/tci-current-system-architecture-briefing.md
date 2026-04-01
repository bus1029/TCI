# TCI Current System Architecture Briefing

## 목적

이 문서는 다른 에이전트가 `/architecture` 하위 문서를 다시 처음부터 읽지 않아도, TCI가 현재 어떤 시스템 아키텍처를 가지려고 하는지 바로 파악할 수 있도록 정리한 브리핑 문서다.

정리 기준:

- 최신 기준은 항상 Notion `C4 검토 비교표 결정사항 반영` 페이지다.
- 로컬 `/architecture` 문서와 `.puml`은 참고 자료이지만, Notion과 충돌하면 Notion을 우선한다.
- TCI의 C4 아키텍처는 Level 1, Level 2, Level 3까지만 고려한다.
- Level 4 다이어그램은 그릴 계획이 없다.

관련 기준 문서:

- [PRD](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [제품 포지셔닝](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)
- [전체 기능 리스트](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [C4 검토 방법](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/c4-diagram-review-method.md)
- [로컬 비교표 초안](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/findings-consolidated-table-draft.md)
- Notion 최신 기준: `https://www.notion.so/334c21d54f42803b9babff230c0c3a30`

핵심 다이어그램 원본:

- [C1 System Context](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-01-system-context.puml)
- [C2 Container](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-02-container.puml)
- [C3 Web Application](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/web-application/tci-03-component-web-application.puml)
- [C3 Data Collection](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/data-collection/tci-03-component-data-collection.puml)
- [C3 Data Processing](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/data-processing/tci-03-component-data-processing.puml)
- [C3 Analysis Engine](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/analysis-engine/tci-03-component-analysis-engine.puml)
- [C3 Interactive Assistant](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/interactive-assistant/tci-03-component-interactive-assistant.puml)
- [C3 Knowledge Base](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/knowledge-base/tci-03-component-knowledge-base.puml)
- [C3 Workflow & Integration](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/workflow-integration/tci-03-component-workflow-integration.puml)

## 한 줄 요약

TCI는 코드, 문서, 티켓, 업로드 자산, 로컬 변경분을 통합 수집하고, 이를 구조 분석, 영향 분석, 비즈니스 규칙 분석, 질의응답, PR 자동화, 문서 초안 생성, AI Agent 컨텍스트 제공으로 연결하는 `Engineering Context Platform + Change Intelligence Platform + Business Logic Intelligence + Documentation Platform` 성격의 시스템이다.

즉 TCI는 코드 생성기 자체가 아니라, 사람과 AI Agent가 복잡한 코드베이스를 이해하고 변경 판단을 내릴 수 있도록 맥락과 근거를 제공하는 인텔리전스 레이어다.

## 제품 정체성

PRD와 포지셔닝 문서를 합쳐 보면 TCI의 본질은 아래 네 축으로 정리된다.

- Engineering Context Platform
  - 코드, 문서, 티켓, 스펙, 외부 컨텍스트를 연결해 단일 탐색 경로 제공
- Change Intelligence Platform
  - 코드 변경과 코드베이스 구조를 기준으로 영향 범위와 리스크 분석
- Business Logic Intelligence
  - 코드에 숨어 있는 규칙, 조건 분기, 상태 전이, 정책 로직을 사람이 이해 가능한 형태로 정리
- Documentation Platform / Documentation Automation
  - 분석 결과를 질의응답, 리포트, 문서 초안, 리뷰 자료, 보고 자료로 전환

이 제품은 아래 사용자 집단을 직접 대상으로 한다.

- Developer
- Reviewer / Senior Developer
- PM / PO

그리고 AI Coding Agent도 중요한 소비자다. 다만 TCI는 AI Agent와 경쟁하는 도구가 아니라, AI Agent가 코드베이스를 더 잘 이해하게 만드는 보조 레이어라는 점이 중요하다.

## 최상위 시스템 해석

현재 기준으로 TCI의 상위 구조는 다음 흐름으로 이해하면 된다.

`사용자/외부 채널 -> Web Application -> TCI 내부 서비스 -> Knowledge Base -> 분석/자동화/대화형 소비`

좀 더 구체적으로는 아래와 같다.

`Data Sources / Upload / Plugin / Agent Diff`
-> `Data Collection`
-> `Data Processing`
-> `Knowledge Base`
-> `Analysis Engine`
-> `Interactive Assistant / Workflow & Integration / AI Agent`

웹 사용자는 항상 `Web Application`을 통해 진입한다. 이것은 C2와 여러 C3 검토에서 반복적으로 유지되는 상위 기준이다.

## C1 System Context에서 이해해야 할 것

TCI의 C1 레벨에서 중요한 것은 세부 구현이 아니라 시스템의 역할과 외부 경계다.

핵심 사용자:

- Developer
- Reviewer
- PM / PO

핵심 외부 시스템/채널:

- Code Repository
- Ticket System
- Docs / Wiki
- CI/CD / DevOps Pipeline
- ChatOps / Collaboration
- AI Coding Agent
- Policy Engine
- IDE Plugin

여기서 주의할 점:

- 로컬 초안과 일부 검토 문서는 `IDE Plugin 제거` 쪽으로 읽힌다.
- 하지만 최신 Notion 결정표에서는 C2와 Data Collection 맥락에서 `IDE Plugin`을 다시 공식 외부 시스템/입력 채널로 보는 쪽이 더 최신이다.
- 따라서 현재 해석 기준에서는 `IDE Plugin`을 완전히 삭제된 범위로 보면 안 된다.

또한 C1에서 반드시 드러나야 하는 제품 가치:

- 구조 분석
- 영향 분석
- 비즈니스 규칙 탐색
- 자연어 질의응답
- 근거 링크 제공
- 리포트 / 문서 초안 생성
- AI 컨텍스트 패키지 제공

기존 로컬 C1 puml은 아직 아래 항목들에서 최신 기준과 충돌한다.

- 시스템 명칭이 `Tmax Code Intelligence`로 남아 있음
- Ticket에 대한 `분석 코멘트 작성`이 남아 있음
- Docs/Wiki 양방향 발행이 강하게 표현돼 있음
- IDE Plugin 처리 방향이 최신 Notion과 정리되지 않음

## C2 Container 기준선

TCI의 컨테이너 구조는 현재 다음이 뼈대다.

- Web Application
- Data Collection
- Data Processing
- Knowledge Base
- Analysis Engine
- Interactive Assistant
- Workflow & Integration
- Operations Manager

중요:

- 로컬 [C2 puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-02-container.puml)에는 아직 `Operations Manager`가 독립 컨테이너로 올라와 있지 않다.
- 최신 Notion 결정은 `Operations Manager는 C2 Diagram의 컨테이너로 생성`이다.
- 따라서 현재 기준선은 `Operations Manager를 Workflow 내부 서브기능이 아니라 C2 독립 컨테이너`로 이해하는 것이 맞다.

### C2에서의 표준 데이터/기능 흐름

1. 사용자는 `Web Application`을 통해 진입한다.
2. 업로드, 연동 설정, 운영 화면, PR/리포트/문서 요청은 웹 경유로 들어온다.
3. `Data Collection`이 코드, PR, 문서, 티켓, 업로드 파일, 플러그인/Agent 기반 변경분을 수집한다.
4. `Data Processing`이 수집 자산을 정규화하고 코드/비코드 자산을 처리한다.
5. `Knowledge Base`가 그래프, 벡터, 원본 스냅샷, 검색 인덱스를 유지한다.
6. `Analysis Engine`이 구조/영향/규칙/리스크/테스트 영향 분석을 수행한다.
7. `Interactive Assistant`는 대화형 Q&A와 설명 인터페이스를 제공한다.
8. `Workflow & Integration`은 PR 자동화, 문서 초안, 리포트, 알림, Policy Gate, AI Agent 연동을 맡는다.
9. `Operations Manager`는 운영/설정/권한/라이선스/분석 작업 제어의 상위 관리 경계를 맡는다.

### C2에서 중요하게 유지해야 하는 구조적 원칙

- 사용자의 단일 진입점은 항상 `Web Application`
- `Knowledge Base`는 중앙 지식 허브
- `Data Collection -> Data Processing -> Knowledge Base`는 상류 파이프라인
- `Analysis Engine`, `Interactive Assistant`, `Workflow & Integration`은 KB를 읽고 쓰는 하류 소비/실행 계층
- `Policy Engine`은 별도 외부 시스템으로 분리하는 해석이 제품 문서 근거상 강함
- 파일 업로드는 외부 시스템이 아니라 사용자 진입 흐름으로 봐야 함

## C3 요약

Level 3는 각 컨테이너의 책임과 경계를 잡는 수준까지만 생각한다. Level 4는 가지 않는다.

### 1. Web Application

역할:

- 단일 사용자 진입점
- 인증/인가
- HTTP 세션 관리
- API 라우팅
- WebSocket 중계
- 실시간 알림 수신

핵심 구성 의도:

- `UI Shell`
- `Auth Gateway`
- `Session Manager`
- `API Router`
- `WebSocket Proxy`
- `Notification Hub`

최신 Notion 기준 보정점:

- `Asset Server`는 제거하는 쪽으로 결정됨
- 로컬 puml에는 아직 남아 있음
- 업로드/연동 설정/인증 정보 관리/동기화 정책/연동 상태 조회가 어떤 백엔드 경로를 타는지 명시돼야 함
- `Auth Gateway`의 `RBAC 프론트 체크`는 오해 소지가 있어서 `RBAC 체크` 수준으로 정리하는 방향
- `WA -> UI Shell` 의미를 UI뿐 아니라 Plugin/MCP 포괄 형태로 확장해야 한다는 메모가 Notion에 남아 있음

실제 읽는 기준:

- 사용자는 절대 Assistant나 Workflow에 직접 붙지 않는다.
- Interactive Assistant와는 `WebSocket Proxy`를 통해 연결
- Workflow와는 `API Router`를 통해 REST로 연결
- 실시간 알림은 Workflow 쪽에서 WebApp으로 푸시된다

### 2. Data Collection

역할:

- 코드/PR/문서/티켓/업로드/플러그인 기반 입력 수집
- 증분 동기화
- 스냅샷 기준 수집
- 상태/오류 관리의 시작점

핵심 구성 의도:

- `Collection Orchestrator`
- `Git Connector`
- `PR Collector`
- `Document Collector`
- `Ticket Connector`
- `Webhook Receiver`
- `Sync Engine`
- `Data Dispatcher`
- 최신 Notion 기준 추가 예정: `Credential Manager`

최신 Notion 기준 보정점:

- `Credential Manager` 추가
- 파일 업로드는 Web Application 또는 그 경유 경로에서 들어오는 입력으로 명시
- 플러그인은 공식 범위이므로 입력 채널 생성
- `Sync Engine` 설명에 스냅샷 관리 책임 보강
- `Collection Orchestrator` 설명에 연동 상태/오류 기록 보강
- 문서/티켓의 Webhook 입력은 점선 또는 옵션으로 낮추는 쪽

중요 해석:

- Data Collection은 단순 커넥터 묶음이 아니다.
- 인증 정보 관리, 연동 상태, 동기화 정책, 스냅샷 경계까지 포함한 “수집 운영 계층”으로 봐야 한다.

### 3. Data Processing

역할:

- 수집 자산 정규화
- 코드 자산의 CPG 생성
- 문서/비코드 자산의 임베딩/컨텍스트 자산화
- 패턴 추출
- KB 적재

핵심 구성 의도:

- `Pipeline Coordinator`
- `Source Normalizer`
- `CPG Generator`
- `Embedding Generator`
- `Pattern Identifier`
- `Snapshot Builder`
- `KB Loader` 또는 최신 결정 후 성격 축소된 로더
- `Job Queue`

최신 Notion 기준 보정점:

- `Code Pipeline`과 `Context Artifact Pipeline`으로 분기
- 코드만 `CPG Generator`로 전달
- `KB Loader`는 중앙 적재자가 아니라 `Graph Loader`에 가까운 역할로 축소
- `Snapshot Builder`는 코드 스냅샷 전용임을 명확히 하고, 문서/외부 컨텍스트 관련 컴포넌트는 별도 추가 방향
- `Source Normalizer`는 파서 선택까지 맡지 않고 입력 정규화/분류만 담당

중요 해석:

- 현재 로컬 puml은 모든 입력이 CPG로 흘러가는 것처럼 보이는데, 최신 방향은 그게 아니다.
- 코드와 비코드 자산은 다른 처리 경로를 타야 한다.

### 4. Analysis Engine

역할:

- 구조 분석
- 기술 스택 분석
- 의존성 분석
- 영향도 분석
- 비즈니스 규칙 추출 및 정합성 점검
- 데이터 흐름 분석
- 리스크 스코어링
- 트레이드오프 분석
- 테스트 영향 분석

핵심 구성 의도:

- `Analysis Coordinator`
- `Structure Analyzer`
- `Tech Stack Detector`
- `Dependency Analyzer`
- `Impact Analyzer`
- `Business Rule Extractor`
- `Data Flow Tracer`
- `Risk Scorer`
- `Trade-off Analyzer`
- `Test Impact Analyzer`
- 적재 컴포넌트

최신 Notion 기준 보정점:

- `Business Rule Extractor -> Knowledge Base` 관계 추가
- `Data Flow Tracer -> KB Query` 추가
- `Tech Stack Detector`도 KB 또는 처리 산출물 조회 경로 추가
- `Impact Analyzer`는 snapshot/diff 질의를 명시
- `Business Rule Extractor` 책임에 정합성 검사 포함
- `Structure Analyzer` 설명에 구조 메타데이터 추출까지 포함
- Interactive Assistant에 있던 `Gap Analyzer` 성격은 AE 쪽으로 이관하는 해석이 최신이다

중요 해석:

- Analysis Engine은 단순 정적 분석기가 아니라, 구조/변경/규칙/설명 기반의 중심 분석 계층이다.
- LLM은 결과 의미 해석이나 비즈니스 언어 변환에 보조적으로 쓰이지만, 분석의 근거 데이터는 KB/CPG/구조 질의에서 나온다.

### 5. Interactive Assistant

역할:

- 자연어 질의응답
- 코드베이스 설명
- 분석 결과 설명
- 대화형 탐색 인터페이스

최신 방향에서의 중요한 재해석:

- Interactive Assistant는 점점 “범용 분석기”보다는 “챗봇/설명 인터페이스”로 좁혀진다.
- `Gap Analyzer`는 여기서 빠지고 Analysis Engine 쪽으로 이동하는 것이 최신 결정에 가깝다.
- 사용자 액터가 직접 붙는 구조는 버리고, `Web Application` 경유 또는 `WebSocket Proxy -> Session Manager` 흐름으로 보는 것이 맞다.

핵심 구성 의도:

- `Session Manager`
- `Query Router`
- `QA Handler`
- `Codebase Explainer`
- `Explainability Engine`
- `Context Assembler`
- `Response Renderer`

최신 Notion 기준 보정점:

- Actor를 WA로 변경
- `Context Assembler -> KB`는 `Graph Read`가 아니라 더 넓은 `Hybrid Query` 성격
- `Gap Analyzer -> Analysis Engine` 이관
- 근거 포함 렌더링 경로 명시
- 대화 이력/답변/피드백 저장 모델은 아직 상세 확정 전

중요 해석:

- IA는 사용자용 설명 채널이다.
- 분석 수행 자체보다는 KB 조회와 AE 위임을 통해 설명 가능한 응답을 만드는 것이 핵심이다.

### 6. Knowledge Base

역할:

- 단일 지식 모델의 논리적 중심
- 그래프/벡터/원본/검색 인덱스를 통합
- 분석/질의/리포트/컨텍스트 생성의 기반 저장 계층

핵심 구성 의도:

- `Graph Store`
- `Vector Store`
- `Object Store`
- `Search Index`
- `Query Facade`
- `Schema Manager`
- `Retention Manager`

최신 Notion 기준 보정점:

- KB는 단일 DB가 아니라 컨테이너로 해석
- `Query Facade`는 읽기/적재와 인덱싱 컴포넌트로 분리하는 방향
- `Retention Manager -> Search Index` 관계 추가
- Graph 중심 자산 목록은 더 명확히 써야 함

중요 해석:

- Graph에는 CPG, 구조/의존성, 비즈니스 규칙, 교차 참조, 도메인 용어, 외부 컨텍스트, 팀 컨벤션 같은 지식이 축적될 가능성이 높다.
- Vector는 RAG/유사도 검색
- Object는 스냅샷과 원본 문서
- Search는 키워드 탐색과 재탐색

아직 덜 닫힌 부분:

- Q&A 이력/피드백/문서화된 답변 저장 위치의 세부 모델은 완전히 확정되지 않음
- Search Index를 누가 갱신하는지에 대한 구조는 최신 Notion에서 분리 방향이 제시됨

### 7. Workflow & Integration

역할:

- PR 자동화
- Policy Gate 연동
- CI/CD 연동
- 문서 초안 생성과 발행
- 리포트 생성
- ChatOps / Collaboration 발송
- MCP/API 기반 AI Agent 연동
- 알림 발송

핵심 구성 의도:

- `Event Router`
- `PR Automation Handler`
- `Policy Gate Adapter`
- `CI/CD Adapter`
- `Docs Studio Engine`
- `Report Generator`
- `ChatOps Connector`
- `Collaboration Connector`
- `MCP/API Gateway`
- `Analysis Trigger`
- `Notification Dispatcher`
- 로컬 puml에는 아직 `Operations Manager`가 내부 컴포넌트로 있음

최신 Notion 기준 보정점:

- 사용자 액터 직접 연결 제거, WebApp 경유로 통일
- `Scheduler` 추가
- `Event Router`와 `Scheduler`를 모두 `Analysis Trigger`에 연결
- `PR Automation Handler`는 외부 `Code Repository`에 write-back 경로 추가
- `Notification Dispatcher -> Web Application` 추가
- `Operations Manager`는 C2 독립 컨테이너로 승격
- `MCP/API Gateway`의 KB 조회 범위는 로컬 문서상 하이브리드 질의가 더 자연스럽지만, 최신 Notion 표에는 “고려 사항 아님” 메모도 남아 있음

중요 해석:

- W&I는 “분석 결과를 실제 업무 채널로 연결하는 실행 계층”이다.
- PR, 리포트, 문서 초안, ChatOps, Policy Gate, Agent Context를 모두 묶는 곳이다.

### 8. Operations Manager

최신 Notion 기준에서 중요하게 추가된 구조다.

역할 후보:

- 분석 작업 모니터링
- 운영 설정
- 권한 관리
- 라이선스 / 에디션 기반 기능 관리
- 스케줄 기반 제어와 운영 관점 상위 조정

중요:

- 로컬 C2/C3에서는 아직 이 역할이 충분히 반영되지 않았다.
- 최신 기준에서는 Workflow 내부 부속품보다 상위 운영 컨테이너에 가깝다.
- 나중에 Deployment Diagram을 생각할 때도 분리 배치 가능성을 염두에 둘 필요가 있다.

## 입력 자산과 유입 채널

TCI가 다루는 입력은 생각보다 넓다.

정식 입력 자산:

- 소스코드 Repository
- PR / Branch / Commit / Diff
- Jira / Azure DevOps 계열 티켓
- Confluence / Wiki / Notion 계열 문서
- 사용자가 직접 업로드한 ZIP/PDF/DOCX/매뉴얼/규정/스펙 문서
- IDE Plugin 기반 로컬 변경분
- AI Agent 경유 diff / context request

유입 채널:

- Git
- REST API
- GraphQL
- OAuth
- Webhook
- Upload
- MCP / REST

중요 판단:

- `파일 업로드`는 외부 시스템이 아니다.
- `IDE Plugin`은 최신 기준상 완전히 제거된 기능이 아니다.
- `AI Coding Agent`는 주요 외부 소비/연동 채널이다.

## Knowledge Base에 들어가야 하는 지식 자산

기능 문서 기준으로 TCI는 단순 코드 그래프만 저장하는 것이 아니다.

지식 자산 예시:

- CPG
- 구조/호출/의존성 관계
- 데이터 흐름 분석 결과
- 비즈니스 규칙
- 규칙-코드 매핑
- 도메인 용어 사전
- 외부 컨텍스트
- 팀 컨벤션 / 규칙 / 주의사항
- 문서, 티켓, 코드 간 교차 참조
- 문서 원본과 업로드 산출물
- 임베딩 벡터
- 검색 인덱스
- 스냅샷
- 분석 이력
- 리포트 산출물
- AI 컨텍스트 번들 생성에 필요한 메타데이터

## 사람이 보는 출력과 AI가 받는 출력

TCI의 출력은 크게 두 부류다.

사람 대상 출력:

- 구조 설명
- 영향 분석 결과
- 비즈니스 규칙 설명
- 자연어 질의응답
- 근거 링크
- PR 리뷰 요약
- PR 본문 초안
- 인수 검증 체크리스트
- 비즈니스 리포트
- 시스템 구조 설명 문서
- 문서 초안 / 공유 자료

AI Agent 대상 출력:

- AI 컨텍스트 번들
- 관련 모듈/파일 목록
- 팀 컨벤션 / 주의사항
- Deprecated 경로 정보
- 실제 실행 경로
- 유사 구현 위치
- LLM 최적화 컨텍스트 패키지

## 현재 문서 집합에서 가장 중요한 충돌과 주의점

다른 에이전트가 반드시 알고 있어야 하는 포인트다.

### 1. 최신 기준은 Notion이다

- 로컬 `findings-consolidated-table-draft.md`는 초안이다.
- `결정`란이 비어 있거나, 최신 Notion과 다른 방향이 있다.
- 해석이 충돌하면 Notion을 우선한다.

### 2. 로컬 `.puml`은 최신 결정 미반영 상태가 많다

특히 아래는 아직 최신 기준과 어긋난다.

- C1
  - 시스템 명칭
  - Ticket write-back
  - Docs/Wiki 발행 강도
  - IDE Plugin 처리
- C2
  - Operations Manager 컨테이너 누락
  - IDE Plugin/플러그인 채널 재정렬 미완료
  - 일부 알림/업로드/정책 경계 미정리
- C3 WebApp
  - Asset Server 제거 미반영
- C3 DataCollection
  - Credential Manager 미반영
  - Plugin 입력 채널 미반영
- C3 DataProcessing
  - 코드/비코드 파이프라인 분리 미반영
- C3 InteractiveAssistant
  - Actor 직접 연결 유지
  - Gap Analyzer 잔존
- C3 Workflow
  - Operations Manager 아직 내부 컴포넌트
  - Scheduler/Write-back/WebApp 푸시 일부 미반영

### 3. IDE Plugin 방향은 혼재하지만 최신은 “완전 제거”가 아니다

이 부분은 문서들 사이에 가장 혼선이 큰 영역 중 하나다.

- 로컬 C1/C2 리뷰 문서는 `IDE Plugin 제거` 쪽을 많이 말한다.
- 로컬 C1/C2 puml은 플러그인이 아직 남아 있거나, C2는 빠져 있는 등 일관되지 않다.
- 최신 Notion 결정표에서는 C2, Data Collection에서 플러그인을 공식 범위로 되살리는 쪽 결정이 더 강하다.

따라서 현재 작업 기준으로는:

- 플러그인을 제거 완료된 기능으로 간주하지 말 것
- 공식 입력 채널 후보이자, 최신 결정상 복원되는 범위로 볼 것

### 4. Operations Manager는 중요도가 올라갔다

- 단순 내부 보조 컴포넌트가 아니라 C2 컨테이너로 승격되는 것이 최신 방향이다.
- 향후 배포 구조나 운영 다이어그램에서도 별도 취급 가능성이 높다.

### 5. Interactive Assistant는 “챗봇/설명 계층”으로 좁혀진다

- 갭 분석, 구조 분석, 영향 분석의 중심은 결국 Analysis Engine
- IA는 사용자와 Analysis/KB 사이의 대화형 인터페이스

## 다른 에이전트가 작업할 때의 실무 지침

이 브리핑을 읽은 뒤 작업할 때는 아래 순서를 권장한다.

1. 최신 결정을 판단해야 할 때는 먼저 Notion `C4 검토 비교표 결정사항 반영`을 본다.
2. 세부 구현을 확인하려면 위에 링크한 `.puml`을 직접 읽는다.
3. `.puml`과 Notion이 다르면 “로컬 소스 미반영”으로 해석하고 Notion을 따른다.
4. 기능 근거가 필요한 경우 [전체 기능 리스트](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)를 기준으로 누락/과잉 해석을 판별한다.
5. Level 4까지 파고들지 말고, Level 3에서 책임/경계/흐름까지만 고정한다.

## 현재 기준 최종 그림

현재 TCI가 가지려는 시스템 아키텍처를 가장 짧게 압축하면 다음과 같다.

- `Web Application`이 사람의 단일 진입점이다.
- `Data Collection`이 코드/문서/티켓/업로드/플러그인/에이전트 변경분을 모은다.
- `Data Processing`이 코드 자산과 비코드 자산을 분리 처리한다.
- `Knowledge Base`가 Graph/Vector/Object/Search를 합친 중앙 지식 허브다.
- `Analysis Engine`이 구조/영향/비즈니스 규칙/리스크/테스트 영향 분석의 중심이다.
- `Interactive Assistant`는 KB와 AE를 활용해 대화형 설명과 탐색을 제공한다.
- `Workflow & Integration`은 PR/문서/리포트/알림/Policy Gate/Agent 연동을 맡는다.
- `Operations Manager`는 운영, 설정, 권한, 라이선스, 스케줄 제어를 위한 독립 상위 경계로 분리되는 방향이다.

이 구조는 PRD, 포지셔닝, 기능 문서의 공통 분모를 유지하면서, 최신 Notion의 결정으로 경계와 책임을 더 정교하게 정렬한 결과로 보면 된다.
