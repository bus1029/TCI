# TCI Container Diagram 검토

## 검토 목적

- `TCI Container Diagram`이 제품 문서의 범위와 의도를 C4 Level 2 관점에서 정확하게 반영하는지 확인
- 컨테이너 분해가 문서 근거에 비해 과도하거나 누락된 부분이 없는지 검토
- Notion `TCI Container Diagram` 설명과 `tci-02-container.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Container Diagram`
- [tci-02-container.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-02-container.puml)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)

## 총평

현재 Container Diagram은 전체 구조 방향이 문서와 대체로 잘 맞는다.

- `수집 → 처리 → 분석 → 지식 저장 → 질의/자동화 소비` 흐름이 선명함
- `Interactive Assistant`, `Analysis Engine`, `Workflow & Integration` 분리는 문서상의 사용자 경험과 운영 흐름을 잘 반영함
- `Knowledge Base`를 중심으로 한 느슨한 결합 구조는 `단일 지식 모델` 방향과 잘 맞음

다만 아래 보완이 필요하다.

- 외부 의존성 하나가 C1과 기능 문서 대비 사라짐
- 사용자 직접 업로드 경로가 잘못 모델링됨
- Notion 설명과 `puml` 간에도 일부 요소가 빠짐

## 핵심 findings

### 1. `Policy Engine` 외부 경계가 C2에서 사라졌다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 `Policy Gate 연동`이 별도 기능으로 명시되어 있다.

- `(외부) Policy Gate 시스템 연동`
- `정책 검증 요청`
- `정책 위반 여부 결과 수신`

하지만 [tci-02-container.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-02-container.puml)에는 별도 `Policy Engine` 또는 `Policy Gate` 외부 시스템이 없다.

- `Workflow & Integration` 책임에는 `Policy Gate`가 포함됨
- 실제 외부 관계는 `DevOps Pipeline`의 `PR 이벤트 ↔ Gate 결과`로 흡수됨

이 표현은 `정책 판단 시스템`과 `파이프라인 트리거 시스템`을 하나로 합쳐 버려 외부 의존성 경계를 흐린다.

권고:

- `Policy Engine`을 외부 시스템으로 복원
- `Workflow & Integration -> Policy Engine` 관계를 별도로 표현
- `DevOps Pipeline`은 이벤트 트리거/응답 채널로만 남기기

### 2. `파일 업로드`가 외부 시스템처럼 표현되어 사용자 입력 경로가 왜곡된다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)와 [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)는 `파일 업로드`를 중요한 입력 방식으로 둔다.

- 사용자가 직접 코드 ZIP 업로드
- 요구사항 문서, 매뉴얼, 사내 규정 업로드
- 업로드 문서도 분석 대상

그런데 [tci-02-container.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-02-container.puml)의 `Development Context` 관계는 아래처럼 표현된다.

- `Data Collection -> Development Context`
- 프로토콜 `REST / Upload`

문제는 `Upload`가 외부 시스템 호출처럼 보인다는 점이다. 실제로 업로드는 외부 시스템이 아니라 사용자가 Web Application을 통해 수행하는 내부 진입 흐름에 가깝다.

권고:

- `사용자 -> Web Application -> Data Collection` 업로드 경로를 별도 표기
- 또는 `Development Context`에서 `Upload`를 제거하고 `REST`만 남기기
- 업로드는 Web Application 또는 별도 `Upload API` 책임으로 표시

### 3. `Knowledge Base`에서 `Vector DB`가 빠져 Notion 설명과 불일치한다

Notion `TCI Container Diagram` 설명은 `Knowledge Base`를 아래처럼 정의한다.

- `Graph DB`
- `Object Storage`
- `Vector DB`

하지만 [tci-02-container.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-02-container.puml)에는 `Graph DB · Object Storage`만 있다.

이 차이는 단순 기술 표기 차이 이상일 수 있다. 문서 전반에는 아래 기능이 있다.

- 자연어 질의응답
- 컨텍스트 검색
- AI 컨텍스트 번들 생성
- 지식 검색 및 재탐색 인덱싱

즉 벡터 인덱스나 임베딩 저장소는 TCI의 질의응답·컨텍스트 검색 설계와 강하게 연결된다.

권고:

- `puml`에 `Vector DB`를 추가
- 또는 Notion에서 벡터 저장을 논리 기능으로만 둘지 물리 저장소로 둘지 기준을 통일

### 4. Notion에 있는 `Workflow & Integration -> Web Application` 푸시 관계가 `puml`에서 빠져 있다

Notion의 내부 관계 설명에는 아래가 있다.

- `Workflow & Integration -> Web Application`
- `SSE/WS`
- `실시간 알림 푸시`

하지만 [tci-02-container.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-02-container.puml)에는 이 관계가 없다.

이건 제품 문서와의 충돌이라기보다 `Notion 설명`과 `puml` 간 불일치다.

권고:

- 실시간 알림 UX를 유지할 계획이면 `W&I -> WebApp` 관계 추가
- 아니라면 Notion 설명에서 해당 문구 제거

### 5. `IDE Plugin 제거` 방향을 C2가 따르지만 기능 문서와는 아직 정렬되지 않는다

C2는 `AI Coding Agent`만 외부 채널로 남기고 `IDE Plugin`은 없다. 이는 C1 Notion 설명의 방향과는 맞는다.

하지만 [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 여전히 아래 기능이 있다.

- `로컬 변경 코드 스냅샷 전송(플러그인)`
- IDE 플러그인에서 diff 캡처

즉 C2는 특정 제품 방향을 선반영했지만, 전체 제품 문서 기준선은 아직 하나로 정리되지 않았다.

권고:

- 제품 기준이 `AI Agent 우선`이면 기능 문서에서도 플러그인 위치를 낮추기
- 플러그인이 공식 범위면 C2에도 채널로 복원하기

## 문서 대비 잘 맞는 부분

### 1. 컨테이너 분해의 큰 방향

아래 7개 컨테이너 구성은 문서와 잘 맞는다.

- Web Application
- Interactive Assistant
- Analysis Engine
- Workflow & Integration
- Knowledge Base
- Data Processing
- Data Collection

이 분해는 PRD와 기능 문서의 흐름을 기술적으로 자연스럽게 풀어낸 결과로 보인다.

### 2. `Interactive Assistant`와 `Analysis Engine`의 분리

문서에는 다음 두 흐름이 모두 있다.

- 자연어 질의응답
- 구조/영향/비즈니스 규칙 분석

이를 `대화형 컨테이너`와 `비동기 분석 컨테이너`로 나눈 것은 타당하다.

### 3. `Workflow & Integration`의 별도 분리

문서에는 PR 자동화, CI/CD 연동, 문서 초안 생성, 비즈니스 리포팅, AI 에이전트 연동, ChatOps 알림 같은 외부 전달 기능이 많다.

이를 분석 엔진과 분리한 것은 응집도 측면에서 적절하다.

### 4. `Knowledge Base 중심 아키텍처`

문서의 `단일 지식 모델 구성`, `코드 속성 그래프`, `도메인 용어 사전`, `비즈니스 규칙`, `문서/티켓/코드 교차 참조`, `컨텍스트 검색`은 모두 중앙 지식 저장소를 전제한다.

따라서 KB 중심 설계는 제품 의도와 잘 맞는다.

## 오해로 보이진 않지만 주의가 필요한 부분

### 1. `Collaboration Tools`와 `Development Context`가 같은 실제 시스템을 다른 방향으로 중복 표현한다

Jira와 Confluence는 수집 대상이면서 동시에 발행 대상일 수 있다.

이걸 C2에서 아래처럼 분리한 것은 논리적으로 가능하다.

- `Development Context`: 인바운드 수집
- `Collaboration Tools`: 아웃바운드 전달

다만 다이어그램만 보면 동일 시스템이 두 번 등장한 것처럼 읽힐 수 있으므로 주석이나 범례 설명이 있으면 좋다.

### 2. `Workflow & Integration`의 `LLM 미사용` 원칙은 설계 선택이지 문서 요구사항은 아니다

문서에는 `AI 기반 문서 초안 자동 생성`, `PR 본문 자동 생성`, `비즈니스 리포팅`이 있다.

현재 C2는 이를 `Analysis Engine이 자연어 결과를 KB에 적재하고 W&I가 그대로 소비`하는 방식으로 설계했다.

이건 가능한 설계다.

다만 향후 채널별 문체 최적화, 템플릿별 생성 변형, 문서 재작성 기능이 늘어나면 W&I에도 일부 생성 책임이 생길 수 있다.

즉 현재는 문제라기보다 향후 확장 포인트다.

## 현재 기준 결론

현재 TCI Container Diagram은 문서와 `대체로 일치`한다.

판단:

- 컨테이너 분해 자체는 설득력 있고 문서 흐름과도 잘 맞음
- 하지만 `Policy Engine`, `직접 업로드 경로`, `Vector DB`, `W&I -> WebApp 푸시`는 보완이 필요

우선순위:

1. 외부 `Policy Engine` 복원 여부 결정
2. 업로드 경로를 사용자 진입 흐름으로 재표현
3. `Knowledge Base` 구성 표기 통일
4. Notion 설명과 `puml` 간 누락 관계 보정
