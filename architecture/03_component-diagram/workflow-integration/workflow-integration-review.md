# TCI Component Diagram 검토 - Workflow & Integration

## 검토 목적

- `TCI Component Diagram - Workflow & Integration`이 제품 문서의 범위와 의도를 C4 Level 3 관점에서 정확하게 반영하는지 확인
- PR 자동화, Policy Gate, CI/CD, 문서화, 알림, AI Agent 연동, 운영 기능의 책임 분리가 문서 근거와 맞는지 검토
- Notion 설명과 `tci-03-component-workflow-integration.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Component Diagram - Workflow & Integration`
- [tci-03-component-workflow-integration.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/workflow-integration/tci-03-component-workflow-integration.puml)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)

## 총평

현재 `Workflow & Integration` 컴포넌트 다이어그램은 문서상 워크플로우 자동화 축을 비교적 잘 받치고 있다.

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
- `Operations Manager`

특히 아래 설계는 타당하다.

- `Policy Gate`를 외부 엔진 어댑터로 둔 점
- `Report Generator`를 LLM 미사용으로 둔 점
- `Notification Dispatcher`를 중앙화한 점
- `ChatOps`와 `Collaboration` 커넥터를 분리한 점

다만 문서와 대조하면 몇 가지 중요한 경계와 출력 경로가 빠져 있거나 어색하다.

## 핵심 findings

### 1. 사용자 액터가 `Workflow & Integration`에 직접 붙어 있어 C2/Web Application 경계와 충돌한다

[tci-03-component-workflow-integration.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/workflow-integration/tci-03-component-workflow-integration.puml)에서는 아래처럼 표현된다.

- `Reviewer -> PR Automation Handler`
- `PM / PO -> Docs Studio Engine`
- `PM / PO -> Report Generator`

하지만 C2와 Web Application C3에서는 사용자의 단일 진입점이 `Web Application`으로 정의되어 있다.

즉 현재 표현은 note로만 보정하고 있지만, C3 실제 구조 기준으로는 아래가 더 맞다.

- `Web Application/API Router -> PR Automation Handler`
- `Web Application/API Router -> Docs Studio Engine`
- `Web Application/API Router -> Report Generator`

권고:

- 액터 직접 연결을 제거
- `Web Application` 또는 `API Router`를 외부 참조로 추가

### 2. `Event Router`의 입력 정의와 실제 인바운드 관계가 맞지 않는다

Notion과 `puml` 모두 `Event Router` 책임을 아래처럼 설명한다.

- `PR/Push/Merge/스케줄` 이벤트 수신/분류/라우팅

하지만 실제 인바운드 관계는 [tci-03-component-workflow-integration.puml#L66](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/workflow-integration/tci-03-component-workflow-integration.puml#L66)의 `DevOps Pipeline -> Event Router` 하나뿐이다.

즉 아래가 빠져 있다.

- 스케줄 이벤트 출처
- Push/Merge가 DevOps Pipeline인지 Code Repository인지 구분

문서상 `분석 자동화`에는 명확히 아래가 있다.

- 스케줄 기반 분석 실행
- 이벤트 기반 영향 분석 자동 트리거

권고:

- `Operations Manager` 또는 별도 `Scheduler`에서 `Event Router`로 들어가는 경로 추가
- Push/Merge 이벤트의 실제 원천이 `DevOps Pipeline`인지 `Code Repository`인지 기준 명시

### 3. `PR Automation Handler`가 PR 본문을 어디에 쓰는지 빠져 있다

기능 문서의 `PR 본문 자동 생성`은 아래를 포함한다.

- PR Diff 기반 문서 초안 생성
- 관련 Jira 티켓 링크 자동 삽입
- 인수 검증 체크리스트 자동 생성
- 수동 편집 및 커스터마이징 지원

하지만 현재 `PR Automation Handler`의 관계는 아래뿐이다.

- `KB` 읽기
- `Report Generator` 호출
- `Notification Dispatcher` 호출

즉 생성한 PR 본문을 실제로 어디에 반영하는지가 보이지 않는다.

가능한 대상:

- GitHub/GitLab PR API
- DevOps Pipeline 또는 Code Hosting API
- Collaboration Connector 경유

현재 다이어그램만으로는 `생성`은 보이는데 `적용`은 보이지 않는다.

권고:

- `PR Automation Handler -> DevOps Pipeline/Code Repository` write 경로 추가
- 또는 외부 시스템 명칭을 `Code Hosting / DevOps Platform`으로 더 정확히 바꾸기

### 4. `Docs Studio Engine`도 생성한 문서를 어디에 발행하는지 직접 관계가 없다

문서에는 `문서 템플릿 및 승인 워크플로우 관리`, `AI 기반 문서 초안 자동 생성`, `문서 버전 관리 및 이력 추적`이 있다.

현재 `Docs Studio Engine`은 아래 관계만 가진다.

- `KB` 읽기
- `Notification Dispatcher` 호출

하지만 실제 산출물의 발행/수정/버전 관리 대상은 보이지 않는다.

`Collaboration Connector`가 `Confluence 문서 발행`을 담당하므로, 아래 관계가 필요해 보인다.

- `Docs Studio Engine -> Collaboration Connector`

권고:

- Docs Studio가 문서를 발행/갱신할 때 `Collaboration Connector`를 사용한다는 경로 추가
- 아니면 Docs Studio 내부에 외부 발행 책임이 포함된다는 점을 명시

### 5. `Notification Dispatcher`가 Web Application으로 푸시하는 경로가 없다

이전 C2와 Web Application C3에서 이미 확인된 흐름이 있다.

- `Workflow & Integration -> Web Application`
- 실시간 알림 푸시

그런데 현재 W&I C3에는 이 경로가 없다.

지금 표현상 알림은 모두 아래로만 간다.

- `wi_notify -> wi_chatops`
- `wi_notify -> wi_collab`

문서와 이전 다이어그램 기준으로는 최소한 아래 중 하나가 있어야 한다.

- `Notification Dispatcher -> Web Application Notification Hub`
- `Notification Dispatcher -> Web Application`

권고:

- Web Application 또는 `Notification Hub`를 외부 참조로 추가

### 6. `Event Router -> Report Generator`는 Notion 설명과 `puml`이 어긋난다

Notion의 `Event Router` 인터페이스 설명은 아웃바운드를 아래 4개로 적고 있다.

- `PRHandler`
- `PolicyGate`
- `CICD`
- `Trigger`

하지만 [tci-03-component-workflow-integration.puml#L73](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/workflow-integration/tci-03-component-workflow-integration.puml#L73)에는 아래가 추가돼 있다.

- `Event Router -> Report Generator`

이건 다이어그램 소스와 설명 문서 간 직접 불일치다.

가능한 선택:

- 실제로 리포팅 이벤트를 라우팅한다면 Notion 설명 수정
- 아니라면 `puml`에서 해당 관계 제거

### 7. `MCP/API Gateway`의 KB 읽기 범위가 문서 대비 좁다

기능 문서의 `AI 에이전트 컨텍스트 제공 및 연동`은 아래를 포함한다.

- 관련 모듈, 파일 목록 온디맨드 반환
- 팀 컨벤션, 주의사항 포함
- Deprecated 경로, 실제 실행 경로 정보 포함
- 유사 구현 위치 탐지
- Export 형태 컨텍스트 패키지 제공

현재 `MCP/API Gateway -> KB`는 [tci-03-component-workflow-integration.puml#L95](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/workflow-integration/tci-03-component-workflow-integration.puml#L95)에서 `Graph Read`만 표현한다.

하지만 이 기능들은 문서/검색/규칙/스냅샷/유사도 검색까지 함께 필요할 가능성이 높다.

즉 KB C3의 `Query Facade` 설계와 맞추면 이 경로도 `Hybrid Query` 수준으로 표현하는 편이 낫다.

### 8. `Operations Manager`의 책임이 너무 넓고 실제 연결은 너무 적다

`Operations Manager`는 아래를 맡는다.

- 분석 작업 모니터링
- 사용자/권한 관리
- 시스템 설정
- 에디션/라이선스 기반 기능 관리

하지만 실제 관계는 아래 하나뿐이다.

- `Operations Manager -> Analysis Trigger`
- `Operations Manager -> Platform & Infra`

즉 운영 기능 중 아래가 실제로 어디에 반영되는지 보이지 않는다.

- Notification 설정
- Docs Studio 설정
- 사용자/권한 관리와 각 기능 연결
- 라이선스에 따른 기능 활성/비활성

오류라기보다 과도하게 넓은 책임 선언에 비해 관계가 적은 상태다.

## 문서 대비 잘 맞는 부분

### 1. `Policy Gate Adapter`

문서의 `Policy Gate 연동`을 가장 정확하게 반영한다.

- 외부 시스템 연동
- 요청/결과 수신
- 요약/표시

이건 현재 구조가 명확하다.

### 2. `Report Generator`의 LLM 미사용 원칙

이전 `Analysis Engine` 다이어그램과도 잘 이어진다.

- AE가 자연어 번역 생성
- KB에 적재
- W&I는 읽고 포맷팅만 수행

설계 일관성이 좋다.

### 3. `Notification Dispatcher` 중앙화

문서의 `분석 결과 알림`, `비즈니스 리포팅 발송`, `문서 변경 알림`, `PR 리포트 알림`을 기술적으로 받치기 좋은 구조다.

### 4. `ChatOps Connector`와 `Collaboration Connector` 분리

동일한 외부 시스템이라도 `알림 발송`과 `자산 CRUD`를 분리한 점은 실무적으로 타당하다.

## 현재 기준 결론

현재 `Workflow & Integration` 컴포넌트 다이어그램은 문서와 `대체로 일치`한다.

판단:

- 내부 기능 분해는 좋음
- 특히 Policy Gate, Report Generator, Notification 구조는 설득력 있음
- 하지만 `사용자 진입 경로`, `PR/문서 산출물의 실제 쓰기 대상`, `WebApp 알림 푸시`, `Event Router 입력/출력 정합성`, `MCP Gateway 질의 범위`는 보강이 필요

우선순위:

1. 사용자 직접 연결을 `Web Application/API Router` 경유 구조로 수정
2. `PR Automation Handler`와 `Docs Studio Engine`의 실제 외부 write 경로 추가
3. `Notification Dispatcher -> Web Application/Notification Hub` 경로 반영
4. `Event Router`의 스케줄 입력과 `Report Generator` 라우팅 여부 정리
5. `MCP/API Gateway -> KB`를 하이브리드 질의 관점으로 확장
