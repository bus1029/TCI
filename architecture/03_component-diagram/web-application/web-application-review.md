# TCI Component Diagram 검토 - Web Application

## 검토 목적

- `TCI Component Diagram - Web Application`이 제품 문서의 범위와 의도를 C4 Level 3 관점에서 정확하게 반영하는지 확인
- 인증, 세션, REST 프록시, WebSocket 중계, 알림 허브가 문서와 다른 C2/C3 다이어그램과 일관되게 연결되는지 검토
- Notion 설명과 `tci-03-component-web-application.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Component Diagram - Web Application`
- [tci-03-component-web-application.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/web-application/tci-03-component-web-application.puml)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)

## 총평

현재 `Web Application` 컴포넌트 다이어그램은 전체적으로 잘 정리되어 있다.

- `UI Shell`
- `Auth Gateway`
- `Session Manager`
- `API Router`
- `WebSocket Proxy`
- `Notification Hub`
- `Asset Server`

특히 아래는 문서와 잘 맞는다.

- 모든 사용자의 단일 진입점이라는 점
- REST와 WebSocket 경로를 분리한 점
- `Interactive Assistant`는 WebSocket, `Workflow & Integration`은 REST로 연결한 점
- `Notification Hub`를 따로 둬 실시간 알림을 수신하게 한 점

이번 다이어그램은 구조적 완성도가 높은 편이다.

다만 제품 문서 전체와 대조하면 `사용자 입력 경로` 일부가 아직 비어 있다.

## 핵심 findings

### 1. `파일 업로드`와 `연동 설정` 경로가 Web Application에서 드러나지 않는다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 사용자가 UI를 통해 다룰 기능이 분명히 있다.

- `파일 업로드`
- `인증 정보 관리`
- `연동 상태 모니터링`
- `동기화 정책`

하지만 현재 [tci-03-component-web-application.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/web-application/tci-03-component-web-application.puml)에서 `UI Shell`이 백엔드로 나가는 경로는 두 개뿐이다.

- `UI Shell -> API Router`
- `UI Shell -> WebSocket Proxy`

그리고 `API Router`는 `Workflow & Integration`만 호출한다.

- [tci-03-component-web-application.puml#L76](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/web-application/tci-03-component-web-application.puml#L76)

문제는 `파일 업로드`, `인증 정보 관리`, `동기화 정책`, `연동 상태 모니터링`이 현재 설계상 어느 백엔드 경로로 가는지 명확하지 않다는 점이다.

가능한 해석:

- 모두 `Workflow & Integration` 경유
- 일부는 `Data Collection` 또는 `Operations Manager` 경유

현재는 다이어그램만으로 판단할 수 없다.

권고:

- `API Router` 설명에 `설정/업로드/API 프록시`를 포함
- 또는 외부 참조에 `Data Collection`이나 `Operations Manager`를 추가해 설정/업로드 경로를 명시

### 2. `Asset Server`는 존재하지만 실제 관계가 없다

Notion 설명은 `Asset Server`를 아래처럼 정의한다.

- 정적 자산 서빙
- 캐싱
- 버전 관리
- 브라우저 직접 요청

하지만 [tci-03-component-web-application.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/web-application/tci-03-component-web-application.puml)에는 `Asset Server`와의 관계가 한 줄도 없다.

즉 존재는 하지만 실제 데이터 흐름은 생략된 상태다.

오류라기보다는 표현 누락이다.

권고:

- `Developer/Reviewer/PMPO -> Asset Server` 직접 요청
- 또는 `UI Shell -> Asset Server` 초기 자산 로딩 관계를 보강

### 3. `Notification Hub`의 반환 경로가 명시되지 않는다

`Notification Hub`는 아래 책임을 가진다.

- W&I 알림 푸시 수신
- 알림 큐
- 배지 관리

현재 관계는 다음뿐이다.

- `UI Shell -> Notification Hub` 구독
- `Workflow -> Notification Hub` 푸시

하지만 `Notification Hub`가 실제로 `UI Shell`에 무엇을 전달하는지 역방향 관계는 없다.

Notion 설명만 보면 이해되지만, `puml`만 보면 아래가 생략된 상태다.

- `Notification Hub -> UI Shell`

권고:

- `Notification Hub -> UI Shell` `알림 상태/배지 업데이트` 관계 추가

### 4. `Auth Gateway`의 `RBAC 프론트 체크` 표현은 맞지만 보안 경계를 오해하게 만들 수 있다

현재 `Auth Gateway` 설명에는 `RBAC 프론트 체크`가 있다.

이 자체는 문제는 아니다.

다만 문서 전체 기준으로 접근 권한 기반 제어는 프론트엔드만의 책임이 아니라 아래에도 있다.

- Interactive Assistant의 접근 권한 기반 답변 제어
- Knowledge Base의 접근 권한 필터링

즉 이 다이어그램만 보면 프론트엔드에서 권한이 끝나는 것처럼 읽힐 수 있다.

권고:

- `프론트 체크`라는 표현은 유지하되, 백엔드에서도 재검증한다는 note를 넣으면 오해가 줄어든다

### 5. `API Router`의 대상이 `Workflow & Integration` 하나뿐인 것은 합리적이지만, 장기적으로는 범위가 넓어질 수 있다

현재 구조상 이 판단은 일관적이다.

- 대화형은 `WebSocket Proxy -> Interactive Assistant`
- 나머지 API는 `API Router -> Workflow & Integration`

문제는 당장 명백한 오류는 아니라는 점이다.

다만 제품 문서에 있는 다음 기능이 확대되면 라우팅 대상이 늘 수 있다.

- 업로드
- 연동 설정
- 운영 설정
- 라이선스/권한 관리

즉 지금은 괜찮지만, 나중에 `API Router`가 실질적으로 `W&I BFF`인지 `전체 백엔드 BFF`인지 기준을 정리해야 한다.

## 문서 대비 잘 맞는 부분

### 1. 단일 진입점 구조

개발자, 리뷰어, PM/PO 모두 `Web Application`을 경유한다는 점은 C1/C2와 잘 맞는다.

### 2. REST와 WebSocket 분리

다른 C3들과의 정합성이 좋다.

- `API Router -> Workflow & Integration`
- `WebSocket Proxy -> Interactive Assistant`

이 분리는 실시간 대화와 일반 API 흐름을 명확하게 나눈다.

### 3. `Notification Hub` 도입

이전 C2와 W&I C3에서 보완이 필요했던 `workflow -> webapp` 실시간 알림 경로를 이 다이어그램은 잘 반영하고 있다.

### 4. `WA Session Manager`와 `IA Session Manager` 구분

Notion과 `puml`의 note가 역할 차이를 명확히 설명한다.

- WA: HTTP 인증 세션
- IA: WebSocket 대화 세션

이 구분은 전체 모델 일관성에 도움이 된다.

## 현재 기준 결론

현재 `Web Application` 컴포넌트 다이어그램은 문서와 `대체로 일치`한다.

판단:

- 핵심 웹 경계와 프록시 구조는 잘 맞음
- 다만 `파일 업로드/연동 설정` 같은 사용자 입력 경로, `Asset Server` 실제 관계, `Notification Hub` 반환 경로는 보강이 필요

우선순위:

1. 업로드/설정 기능이 어떤 백엔드 경로를 타는지 명시
2. `Notification Hub -> UI Shell` 관계 추가
3. `Asset Server`의 실제 요청 관계 추가
4. `Auth Gateway`의 프론트 체크가 백엔드 권한 검증을 대체하지 않는다는 설명 보강
