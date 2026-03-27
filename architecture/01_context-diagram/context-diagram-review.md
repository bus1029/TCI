# TCI Context Diagram 검토

## 검토 목적

- `TCI Context Diagram`이 제품 문서의 범위와 의도를 C4 Level 1 관점에서 정확하게 반영하는지 확인
- 문서 대비 누락, 오해, 과잉 해석 여부 식별
- `Notion 페이지 설명`과 `tci-01-system-context.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Context Diagram`
- [tci-01-system-context.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-01-system-context.puml)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)

## 총평

현재 Context Diagram은 큰 방향에서는 맞다.

- 핵심 사용자 3종
- TCI를 단일 시스템 경계로 둔 점
- Git, Ticket, Docs/Wiki, CI/CD, ChatOps, AI Agent, Policy Engine 같은 외부 관계를 배치한 점
- TCI를 `변경 판단을 지원하는 분석 레이어`로 설명한 점

다만 문서 기준으로 보면 아래 문제가 남아 있다.

- Notion 설명과 `puml`이 서로 다른 설계를 표현
- 일부 관계가 문서 근거보다 앞서 해석됨
- 문서상 중요한 입력 경로와 핵심 가치 일부가 C1에서 약하게 표현됨

## 핵심 findings

### 1. `IDE Plugin 제거` 결정과 실제 `puml`이 충돌

Notion 페이지는 `IDE Plugin 제거 결정`을 명시한다.

- 실질 타겟은 `AI Coding Agent`
- IDE Plugin은 제거
- 필요 시 AI Agent 경유 구조로 대체

하지만 [tci-01-system-context.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/tci-01-system-context.puml)에는 아래가 그대로 남아 있다.

- `Integration Channels` 안의 `IDE Plugin`
- `Developer -> IDE Plugin`
- `TCI <-> IDE Plugin`

이건 해석 차이가 아니라 다이어그램 소스와 설명 문서가 직접 충돌하는 상태다.

정리 필요:

- `IDE Plugin`을 C1에서 유지할지
- 제거한다면 `puml`에서도 삭제할지
- 유지한다면 Notion의 `제거 결정` 문구를 수정할지

### 2. 기능 문서의 `로컬 변경 코드 스냅샷 전송(플러그인)`과 현재 C1 방향이 완전히 정렬되지 않음

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 명시적으로 아래 기능이 있다.

- `로컬 변경 코드 스냅샷 전송(플러그인)`
- IDE 플러그인에서 현재 코드 diff 캡처
- 분석 요청 트리거
- 캡처한 스냅샷을 TCI 서버로 전송

반면 Notion의 Context Diagram 설명은 이 채널을 사실상 `AI Coding Agent`로 대체했다.

이건 C1의 표현 문제가 아니라 제품 정의의 우선순위 문제다.

- IDE 플러그인이 실제 제품 범위라면 C1에서 완전히 제거하면 안 됨
- 반대로 AI Agent 중심으로 재정의했다면 기능 문서에서 플러그인을 `옵션`, `후속`, `대체 가능 채널`로 낮춰야 함

현재 상태는 문서 간 기준선이 하나로 맞춰져 있지 않다.

### 3. `Ticket` 관계의 `분석 코멘트 작성`은 문서 근거가 약함

Context Diagram은 `Ticket`과의 관계를 아래처럼 설명한다.

- 이슈 메타데이터 수집
- 분석 코멘트 작성

하지만 현재 읽은 제품 문서에서 분명하게 확인되는 것은 주로 아래다.

- Jira 연동
- 이슈 메타데이터 수집
- 티켓과 코드/문서/PR 맥락 연결

반면 `TCI가 Jira/Azure DevOps에 분석 코멘트를 다시 쓴다`는 동작은 명시적으로 보이지 않는다.

가능한 해석:

- 향후 자동화 시나리오로는 가능
- 하지만 현재 문서 근거만으로는 C1에 넣기엔 이르다

권고:

- 근거가 없다면 `분석 코멘트 작성` 삭제
- 유지하려면 관련 기능 정의를 제품 문서에 추가

### 4. `Docs / Wiki 양방향 발행`도 문서 근거를 더 명확히 해야 함

Context Diagram은 `Docs / Wiki`를 양방향 관계로 강하게 강조한다.

- 문서 수집
- 생성 문서 발행

문서 전반에 `문서 초안 생성`, `문서 스튜디오`, `설명 자료 생성`, `문서화 자동화`는 분명히 존재한다.
하지만 `Confluence/Notion에 다시 발행한다`가 확정 요구사항으로 명시돼 있는지는 현재 문서만으로는 약하다.

즉 다음 둘 중 하나다.

- 실제 의도가 외부 위키 재발행이라면 기능 문서와 PRD에 outbound publishing을 명시
- 내부 문서화 중심이라면 C1에서 양방향을 약하게 표현하거나 주석 처리

현재는 설계 문서가 제품 문서보다 한 단계 앞서 가 있다.

### 5. `파일 업로드`가 C1에서 사실상 보이지 않음

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)와 [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)에는 아래가 중요하게 나온다.

- 외부 시스템이 아닌 사용자가 직접 관리하는 코드/문서 업로드
- ZIP 코드베이스 업로드
- 매뉴얼, 사내 규정, 요구사항 문서 업로드
- 업로드 문서도 수집·관리 대상

하지만 현재 Context Diagram은 입력 소스를 외부 시스템 중심으로만 보여준다.

C1에서 별도 외부 시스템으로 둘 필요는 없지만, 아래 중 하나는 필요하다.

- 사용자와 TCI 관계에 `문서/코드 업로드` 포함
- `Docs / Wiki` 설명에 `직접 업로드 문서 포함 아님`을 명시
- 검토 문서에서 `직접 업로드는 C1 단순화를 위해 생략`이라고 의도 기록

지금 상태에서는 제품의 한 축인 `직접 업로드 기반 수집`이 빠져 보인다.

### 6. `문서화/설명 산출물`과 `자연어 질의응답` 가치가 C1에서 약하게 드러남

포지셔닝과 PRD에서 TCI의 핵심 축은 단순 분석이 아니다.

- Documentation Platform
- 자연어 질의응답
- 근거 링크 제공
- 문서 초안, 리뷰 리포트, 설명 자료 생성

하지만 현재 Context Diagram의 TCI 설명은 주로 아래에 집중돼 있다.

- 구조 분석
- 영향 분석
- 비즈니스 규칙 변경 탐지
- 정책 위반 검사

이러면 TCI가 `분석 엔진`처럼 보이고, 문서가 강조하는 `설명 가능한 결과물 생성 플랫폼` 성격은 약해진다.

권고:

- 시스템 설명에 `질의응답`, `리포트/문서 초안 생성`, `근거 제공`을 포함
- PM/PO, Reviewer 관계 설명에도 `리포트`, `설명 자료`, `근거 링크`를 더 명시

## 문서 대비 적합한 표현

아래는 현재 Context Diagram이 문서와 잘 맞는 부분이다.

### 사용자 3종

- Developer
- Reviewer
- PM / PO

이는 PRD의 타겟 유저 정의와 일치한다.

### 외부 시스템 큰 축

- Git
- Ticket
- Docs / Wiki
- CI/CD
- ChatOps
- AI Coding Agent
- Policy Engine

이 구성은 기능 문서와 PRD의 연동 방향을 대체로 잘 요약한다.

### TCI의 기본 역할

- 구조 이해 지원
- 변경 영향 분석
- 비즈니스 규칙 파악
- 의사결정 지원

이 기본 방향은 포지셔닝 문서와 잘 맞는다.

## C1에서 굳이 다 넣지 않아도 되는 것

아래는 문서에는 중요하지만 C1에 모두 직접 노출할 필요는 없다.

- 기술 스택 탐지
- 컴포넌트/레이어 추출
- 코드 속성 그래프
- 도메인 용어 사전
- 테스트 영향 분석
- 리스크 점수 계산
- 문서-코드 추적 그래프
- 세션/권한/컨텍스트 우선순위 관리

이 항목들은 C2 이후 컨테이너와 내부 컴포넌트에서 드러나는 편이 자연스럽다.

즉 C1의 문제는 `모든 기능을 안 넣었다`가 아니라, `문서상 중요한 외부 관계와 제품 정체성 일부가 잘못 표현되거나 약하게 표현됐다`는 쪽에 가깝다.

## 권고안

### 권고안 A

`AI Coding Agent 중심`으로 정리

- `puml`에서 `IDE Plugin` 제거
- 기능 문서에서 플러그인을 `후속 옵션`으로 정리
- Developer 관계에 `AI Agent 컨텍스트 제공` 유지

장점:

- Notion 설명과 정렬
- 현재 제품 포지셔닝과 PRD 흐름에 더 가까움

리스크:

- 기능 문서의 플러그인 항목과 충돌

### 권고안 B

`IDE Plugin`을 여전히 공식 입력 채널로 유지

- C1에 `IDE Plugin` 유지
- Notion의 `제거 결정` 문구 수정
- AI Agent와 IDE Plugin을 병렬 채널로 설명

장점:

- 기능 문서와 더 잘 맞음

리스크:

- C1이 다소 복잡해짐
- AI Agent 중심 메시지가 약해질 수 있음

## 현재 기준 결론

현재 TCI Context Diagram은 문서와 `부분적으로 일치`한다.

판단:

- 제품 방향과 주요 외부 관계는 대체로 맞음
- 하지만 `IDE Plugin`, `Ticket comment`, `Docs/Wiki outbound publishing`, `직접 업로드 경로`, `문서화/질의응답 정체성`에서 보완이 필요

가장 먼저 해결할 항목:

1. `IDE Plugin`의 제품 내 지위를 문서 전체에서 하나로 정리
2. `Ticket`과 `Docs/Wiki`의 outbound 동작 중 실제 요구사항만 남기기
3. TCI 설명에 `문서화`, `근거 제공`, `질의응답` 축을 보강
4. 직접 업로드 경로를 C1에서 어떻게 다룰지 명시
