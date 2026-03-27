# TCI Component Diagram 검토 - Interactive Assistant

## 검토 목적

- `TCI Component Diagram - Interactive Assistant`가 제품 문서의 범위와 의도를 C4 Level 3 관점에서 정확하게 반영하는지 확인
- 질의응답, 컨텍스트 검색, 설명 생성, 갭 분석, 세션/피드백 관리의 책임 분리가 문서 근거와 맞는지 검토
- Notion 설명과 `tci-03-component-interactive-assistant.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Component Diagram - Interactive Assistant`
- [tci-03-component-interactive-assistant.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/interactive-assistant/tci-03-component-interactive-assistant.puml)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)

## 총평

현재 `Interactive Assistant` 컴포넌트 다이어그램은 사용자 대면 기능을 비교적 잘 분해했다.

- `Session Manager`
- `Query Router`
- `QA Handler`
- `Codebase Explainer`
- `Gap Analyzer`
- `Explainability Engine`
- `Context Assembler`
- `Response Renderer`

특히 아래는 문서와 잘 맞는다.

- 자연어 질의응답 중심 구조
- 컨텍스트 조립을 별도 컴포넌트로 둔 점
- 근거 링크와 평가 수집을 `Response Renderer`로 분리한 점
- 답변을 지식 자산으로 축적하려는 방향

다만 문서와 대조하면 아래 보완이 필요하다.

- 사용자와 IA의 직접 연결은 C2/C3 경계와 맞지 않음
- `Context Assembler`의 검색 범위가 제품 문서보다 너무 좁게 표현됨
- `Gap Analyzer`의 책임 경계가 AE/W&I와 겹쳐 보임

## 핵심 findings

### 1. 사용자 액터가 `Interactive Assistant`에 직접 붙어 있어 Web Application 경계와 충돌한다

[tci-03-component-interactive-assistant.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/interactive-assistant/tci-03-component-interactive-assistant.puml)에서는 아래처럼 표현된다.

- `Developer -> Session Manager`
- `Reviewer -> Session Manager`
- `PM / PO -> Session Manager`

그리고 note로만 `Web Application 경유`라고 설명한다.

하지만 이미 C2와 Web Application C3에서는 아래가 설계 기준이다.

- 사용자의 단일 진입점은 `Web Application`
- IA와의 WebSocket 연결은 `WebSocket Proxy`가 중계

즉 현재 표현은 설명 note로 보정하고는 있지만, 실제 구조를 그린 C3 기준으로는 외부 참조가 잘못 잡혀 있다.

권고:

- 액터 대신 `Web Application` 또는 `WebSocket Proxy`를 외부 참조로 두기
- `WebSocket Proxy -> Session Manager`로 인바운드 관계 변경

### 2. `Context Assembler -> KB`가 `Graph Read`만으로는 부족하다

문서와 KB 다이어그램을 기준으로 `Interactive Assistant`의 컨텍스트 검색은 아래를 포함한다.

- 코드
- 문서
- 메타데이터
- 구조 그래프
- 유사 코드/문서 검색
- 키워드 검색

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에도 명시적으로 있다.

- `컨텍스트 검색`
- `LLM에게 전달할 컨텍스트와 관련된 코드, 문서, 메타데이터 검색`
- `답변 근거 제공`

하지만 [tci-03-component-interactive-assistant.puml#L79](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/interactive-assistant/tci-03-component-interactive-assistant.puml#L79)은 `Graph Read`만 표현한다.

이건 KB C3의 `Query Facade` 설계와도 어긋난다. KB는 Graph/Vector/Search/Object를 결합한 하이브리드 질의를 의도하고 있다.

권고:

- `Context Assembler -> Knowledge Base` 관계를 `Hybrid Query` 또는 `Graph/Vector/Search/Object Read`로 확장
- 설명에도 `RAG + keyword + graph` 조합을 명시

### 3. `Gap Analyzer`의 책임 경계가 AE/W&I와 겹쳐 보여 정리가 필요하다

문서에는 아래 기능이 따로 있다.

- `문서와 코드 간 불일치 분석`
- `문서-코드 추적`
- `비즈니스 규칙 추출`
- `변경 영향 분석`

현재 `Interactive Assistant`의 `Gap Analyzer`는 아래를 담당한다.

- 스펙-코드 불일치 탐지
- 갭 심각도 분류
- 리포트 생성

이건 문서상 PM/PO 중심의 대화형 사용 패턴과는 맞는다. 다만 이미 문서에서는 대규모 갭 탐지와 리포트가 `워크플로우 자동화`에도 들어 있다.

즉 지금 구조는 가능하지만, 다음 구분을 더 분명히 해야 한다.

- IA `Gap Analyzer`: 대화형, 질의 기반, 소규모/온디맨드
- AE/W&I: 배치형, 문서 추적 기반, 자동 리포트/알림

현재 Notion 설명에는 이 구분이 있지만, `puml`만 보면 AE의 영향 분석과 거의 같은 기능처럼 읽힐 수 있다.

권고:

- `Gap Analyzer` 설명에 `대화형 갭 분석`을 명시
- AE/W&I와의 역할 구분 note 추가

### 4. `Response Renderer`가 평가만 저장하고, 근거 링크의 출처 결합 경로는 보이지 않는다

문서에서 `답변 근거 제공`은 핵심 기능이다.

- 코드 링크
- 문서 링크
- 티켓 링크

현재 `Response Renderer` 설명에는 `근거 링크 포함`이 있다.
하지만 실제로 링크 메타를 어디서 받아오는지는 다이어그램에서 드러나지 않는다.

가능한 해석:

- 핸들러가 이미 근거를 포함한 결과를 준다
- `Context Assembler`가 링크 가능한 소스 메타를 같이 준다

현재는 둘 중 무엇인지 알기 어렵다.

권고:

- `Context Assembler -> Response Renderer` 관계 또는 note 추가
- 또는 핸들러 설명에 `근거 링크 후보 포함 결과 생성` 명시

### 5. `Explainability Engine`은 설득력 있지만, 최신 분석 트리거가 필요한 경우 처리 경로가 보이지 않는다

`Explainability Engine`이 `Analysis Engine`에 직접 요청하지 않는 점은 Notion 설명과 맞는다.

- 이미 KB에 적재된 분석 결과를 재해석

이건 좋은 분리다.

다만 사용자가 최신 상태 설명을 요구할 때는 아래 질문이 남는다.

- KB에 필요한 분석 결과가 없으면 어떻게 하는가
- `Explainability Engine`이 스스로 `Analysis Engine`을 호출할 수 있는가

오류는 아니지만, 운영 흐름 설명이 있으면 더 좋다.

### 6. `QA Handler`, `Session Manager`, `Response Renderer`가 각각 KB에 쓰는 구조는 가능하지만 저장 책임이 분산돼 있다

현재 쓰기 관계는 아래처럼 흩어져 있다.

- `QA Handler -> KB` 답변 적재
- `Session Manager -> KB` 질의 이력 저장
- `Response Renderer -> KB` 평가 저장

문서상으로는 맞는 기능이다.

- 답변 문서화
- 질의 이력 저장 및 팀 공유
- Good/Bad/코멘트 저장

하지만 KB 리뷰에서 이미 확인했듯, 이 자산들이 어디에 어떻게 저장되는지는 아직 명확하지 않다.

즉 IA C3만 놓고 보면 기능은 맞지만, KB 쪽 저장 모델과 함께 다시 정렬이 필요하다.

## 문서 대비 잘 맞는 부분

### 1. `Query Router -> 4개 핸들러` 분리

문서상 주요 질의 유형을 기술적으로 잘 반영한다.

- 범용 Q&A
- 코드베이스 설명
- 갭 분석
- 분석 결과 설명

### 2. `Context Assembler` 중앙화

문서의 `컨텍스트 검색`, `우선순위/범위 설정`, `AI 컨텍스트 제공` 방향과 잘 맞는다.

핸들러마다 RAG 로직을 중복하지 않게 하는 점도 타당하다.

### 3. `Response Renderer` 분리

문서의 `답변 근거 제공`, `답변 평가 시스템`, `다이어그램 포함 답변`을 수용하기 좋은 구조다.

### 4. `답변 지식 베이스화`

PRD와 기능 문서가 강조하는 `지식 축적 및 재사용`과 잘 맞는다.

`QA Handler -> KB`로 답변을 자산화하는 방향은 제품 의도에 부합한다.

## 현재 기준 결론

현재 `Interactive Assistant` 컴포넌트 다이어그램은 문서와 `대체로 일치`한다.

판단:

- 기능 분해는 적절함
- 하지만 `사용자 -> IA 직접 연결`, `Context Assembler의 좁은 질의 범위`, `Gap Analyzer의 경계`, `근거 링크 조립 경로`는 보강이 필요

우선순위:

1. 액터 직접 연결을 `Web Application/WebSocket Proxy` 경유 구조로 수정
2. `Context Assembler -> KB`를 하이브리드 질의로 확장
3. `Gap Analyzer`의 대화형 범위를 AE/W&I와 구분해 명시
4. 근거 링크 메타가 어디서 렌더러로 전달되는지 보강
