# TCI Component Diagram 검토 - Data Collection

## 검토 목적

- `TCI Component Diagram - Data Collection`이 제품 문서의 범위와 의도를 C4 Level 3 관점에서 정확하게 반영하는지 확인
- 컴포넌트 책임 분리가 문서 근거와 맞는지 검토
- Notion 설명과 `tci-03-component-data-collection.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Component Diagram - Data Collection`
- [tci-03-component-data-collection.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/data-collection/tci-03-component-data-collection.puml)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)

## 총평

현재 `Data Collection` 컴포넌트 다이어그램은 핵심 수집 흐름 자체는 잘 정리되어 있다.

- 소스별 커넥터 분리
- 이벤트 기반 수집과 스케줄 기반 수집의 공존
- 증분 동기화 공통화
- Processing으로 넘기기 전 Dispatcher 버퍼를 둔 점

특히 아래 구조는 설득력이 있다.

- `Collection Orchestrator`
- `Git Connector`와 `PR Collector` 분리
- `Sync Engine` 공통화
- `Data Dispatcher`를 통한 Processing 전달

다만 문서 기준으로 보면 `Data Collection`이 담당해야 할 운영성 책임 일부가 누락되어 있다.

## 핵심 findings

### 1. `인증 정보 관리` 책임이 컴포넌트 수준에서 보이지 않는다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 `인증 정보 관리`가 별도 기능으로 명시되어 있다.

- OAuth 인증 정보 등록
- API 토큰 등록
- SSH Key 등록
- 인증 정보 암호화 저장
- 인증 정보 삭제

하지만 현재 [tci-03-component-data-collection.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/data-collection/tci-03-component-data-collection.puml)에는 이를 담당하는 컴포넌트나 외부 의존성이 없다.

- `Git Connector`는 Git SSH/HTTPS를 사용
- `PR Collector`는 REST/GraphQL과 OAuth/PAT를 사용
- `Ticket Connector`는 REST/OAuth를 사용

즉 각 커넥터가 인증을 필요로 하지만, 자격 증명을 어디서 관리하고 어떻게 주입받는지는 보이지 않는다.

권고:

- `Credential Manager` 또는 `Connection Manager` 컴포넌트 추가
- 또는 `Platform & Infra` 같은 외부 비밀관리 서비스 의존성을 명시

### 2. `파일 업로드`가 `Document Collector` 책임으로만 표현되어 진입 경로가 불명확하다

문서에는 `파일 업로드`가 독립 기능으로 존재한다.

- 코드베이스 ZIP 업로드
- 매뉴얼, 사내 규정 업로드
- 스펙 문서 업로드
- 문서 버전 관리

하지만 현재 다이어그램은 `Document Collector`의 설명에만 `문서 업로드 처리`를 넣고, 실제 업로드 요청이 어디서 들어오는지는 보여주지 않는다.

현재 인바운드는 아래 두 개뿐이다.

- `Code Repository -> Webhook Receiver`
- `Development Context -> Webhook Receiver`

즉 사용자 또는 Web Application에서 직접 업로드하는 경로가 사라져 있다.

권고:

- `Web Application` 또는 `Upload API`를 외부 참조로 추가
- `Web Application -> Document Collector` 또는 `Web Application -> Collection Orchestrator` 경로 추가

### 3. `로컬 변경 코드 스냅샷 전송(플러그인)` 경로가 없다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 아래 기능이 존재한다.

- `로컬 변경 코드 스냅샷 전송(플러그인)`
- IDE 플러그인에서 현재 코드 Diff 캡처
- 코드 스냅샷 생성
- 분석 요청 트리거
- 캡처한 스냅샷을 TCI 서버로 전송

현재 `Data Collection` 컴포넌트 다이어그램에는 이 입력 채널이 전혀 없다.

다만 이 이슈는 이전 C1, C2 검토와 연결된다.

- 제품 기준이 `AI Agent 중심`이면 이 기능을 문서에서 후순위로 내려야 함
- 실제 지원 범위라면 DC에도 입력 경로가 있어야 함

즉 현재 상태에서는 `Data Collection`이 제품 문서 전체 범위를 완전히 반영한다고 보기 어렵다.

### 4. `데이터 소스 스냅샷 관리` 책임이 누락되거나 경계가 불명확하다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 `데이터 소스 스냅샷 관리`가 별도 기능으로 있다.

- 메타데이터 스냅샷 저장
- 스냅샷 버전 이력 관리
- 특정 시점 기준 분석 데이터 재현
- 스냅샷 간 변경 비교

현재 다이어그램에는 다음은 있다.

- `Git Connector`: 소스 코드 스냅샷 생성
- `Sync Engine`: 증분 동기화 커서 관리
- `Data Dispatcher`: Processing 전달

하지만 `스냅샷을 어디에 어떤 단위로 보존하고 버전화하는가`를 담당하는 컴포넌트는 보이지 않는다.

이 책임이 다른 컨테이너에 있는 것인지, `Data Collection` 내부 책임인지 경계를 분명히 해야 한다.

권고:

- `Snapshot Manager`를 DC 내부에 추가
- 또는 이 책임이 `Knowledge Base`로 간다면 설계 문서에 명시

### 5. `연동 상태 모니터링`과 `오류 로그` 관점이 C3에서 드러나지 않는다

기능 문서에는 다음이 있다.

- 연동 대상 목록
- 채널 연결 상태
- 마지막 동기화 시각
- 오류 로그

현재 `Collection Orchestrator` 설명에 `상태 관리`가 들어가긴 하지만, 운영자가 보는 연동 상태와 로그 관점까지 책임이 포함되는지는 불분명하다.

이건 반드시 별도 컴포넌트로 그려야 하는 수준은 아닐 수 있다.

다만 최소한 아래 중 하나는 필요하다.

- `Collection Orchestrator` 설명에 `연동 상태/오류 기록` 포함
- 운영성은 `Platform & Infra` 책임이라는 주석 추가

### 6. `Development Context -> Webhook Receiver`는 문서 근거가 약하다

현재 [tci-03-component-data-collection.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/data-collection/tci-03-component-data-collection.puml)에는 아래가 있다.

- `Development Context -> Webhook Receiver`
- `문서/티켓 변경 이벤트`

하지만 기능 문서에서 명시적으로 Webhook 기반 실시간 이벤트 수신이 보이는 것은 주로 소스 코드 수집 쪽이다.

- 코드 변경 이벤트 감지
- Webhook 기반 실시간 이벤트 수신

티켓/문서 시스템에 대해서는 연동과 메타데이터 수집, 변경 이력 동기화는 보이지만, Webhook 수신이 확정 요구사항으로 보이진 않는다.

즉 이 관계는 가능성은 있지만 현재 문서 근거만으로는 다소 앞선 설계 해석이다.

권고:

- 문서에 근거가 없다면 `Development Context -> Webhook Receiver`를 점선이나 옵션으로 낮추기
- 또는 문서에 티켓/문서 변경 이벤트 구독 요구를 추가

## 문서 대비 잘 맞는 부분

### 1. `Git Connector`와 `PR Collector` 분리

이 분리는 타당하다.

- Git 프로토콜 기반 코드/커밋 수집
- 플랫폼 API 기반 PR 메타/리뷰 수집

기능 문서의 `소스 코드 수집`, `PR Diff 조회`, `커밋/Push/PR 이벤트 감지` 흐름과도 잘 맞는다.

### 2. `Sync Engine` 공통화

기능 문서의 `동기화 정책`과 잘 맞는다.

- 증분 동기화
- 전체 스냅샷 동기화
- 동기화 주기 설정

현재 표현은 최소한 `증분 동기화 로직 중앙화`라는 점에서 충분히 설득력 있다.

### 3. `Data Dispatcher`의 버퍼 역할

`Data Collection`과 `Data Processing` 사이를 바로 붙이지 않고 배치 전달 버퍼를 둔 것은 좋다.

- 배치 그룹핑
- 전달 보장
- 재시도

이 구조는 C2의 느슨한 결합 방향과도 잘 맞는다.

### 4. `Collection Orchestrator` 단일 제어점

수집 범위 설정, 상태 관리, 커넥터 조율을 한곳에서 처리하는 구조는 문서상 `동기화 정책`, `연동 상태`, `멀티 레포지토리 관리`를 기술적으로 수용하기 좋다.

## 현재 기준 결론

현재 `Data Collection` 컴포넌트 다이어그램은 문서와 `부분적으로 일치`한다.

판단:

- 핵심 수집 파이프라인은 잘 표현됨
- 하지만 `인증 정보 관리`, `직접 업로드`, `로컬 변경분 입력`, `스냅샷 관리`, `운영 상태 가시화`는 보완이 필요

우선순위:

1. 인증 정보 관리 책임을 어디에 둘지 명시
2. 파일 업로드의 실제 진입 경로를 다이어그램에 반영
3. 스냅샷 관리 책임의 경계 결정
4. 티켓/문서 Webhook이 확정 요구사항인지 재확인
