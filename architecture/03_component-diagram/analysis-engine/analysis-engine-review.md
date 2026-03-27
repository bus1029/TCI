# TCI Component Diagram 검토 - Analysis Engine

## 검토 목적

- `TCI Component Diagram - Analysis Engine`이 제품 문서의 범위와 의도를 C4 Level 3 관점에서 정확하게 반영하는지 확인
- 분석 책임 분해와 컴포넌트 간 의존 관계가 문서 근거와 맞는지 검토
- Notion 설명과 `tci-03-component-analysis-engine.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Component Diagram - Analysis Engine`
- [tci-03-component-analysis-engine.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/analysis-engine/tci-03-component-analysis-engine.puml)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)

## 총평

현재 `Analysis Engine` 컴포넌트 다이어그램은 제품 문서의 핵심 분석 기능을 가장 직접적으로 잘 반영한 편이다.

- 구조 분석
- 기술 스택 탐지
- 의존성 분석
- 영향 분석
- 비즈니스 규칙 추출
- 데이터 흐름 추적
- 리스크 분석
- 트레이드오프 분석
- 테스트 영향 분석

또한 아래 설계 판단도 설득력 있다.

- `Analysis Coordinator`를 단일 진입점으로 둔 점
- `Business Rule Extractor`와 `Trade-off Analyzer`만 LLM을 쓰도록 제한한 점
- `KB Writer`를 통해 자연어 결과를 적재하고 W&I가 이를 재사용하게 한 점

다만 실제 관계를 보면 `분석기가 무엇을 읽고 어떻게 분석하는지`가 일부 빠져 있어서, 현재 그림만으로는 실행 가능성이 완전히 설명되진 않는다.

## 핵심 findings

### 1. Notion 설명의 `내부 컴포넌트 10개`와 실제 목록이 맞지 않는다

Notion 페이지는 `내부 컴포넌트 (10개)`라고 적고 있다.

하지만 실제 목록과 [tci-03-component-analysis-engine.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/analysis-engine/tci-03-component-analysis-engine.puml)에는 11개가 있다.

- Coordinator
- Structure
- Tech Stack
- Dependency
- Impact
- BizRule
- DataFlow
- Risk
- Trade-off
- Test Impact
- KB Writer

이건 다이어그램 논리 문제라기보다 Notion 문서 품질 문제지만, 추후 검토 기준선이 흔들릴 수 있으니 정리 필요하다.

### 2. `Business Rule Extractor`가 무엇을 읽는지 관계가 빠져 있다

[tci-03-component-analysis-engine.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/analysis-engine/tci-03-component-analysis-engine.puml)에서 `Business Rule Extractor`는 아래만 가진다.

- Coordinator가 실행
- LLM 호출

하지만 비즈니스 규칙 추출은 문서상 다음에 의존한다.

- 제어/데이터 흐름 분석
- 코드 구조와 조건 분기
- 코드 근거와의 연결

즉 최소한 아래 중 하나는 보여야 자연스럽다.

- `Business Rule Extractor -> Knowledge Base` `Graph Query`
- `Business Rule Extractor -> Data Flow Tracer`

현재 상태에서는 `LLM이 무엇을 근거로 규칙을 해석하는지`가 빠져 있다.

### 3. `Data Flow Tracer`도 입력 관계가 없다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에서 `데이터 흐름 및 화면 영향 추적`은 다음을 기반으로 한다.

- 변수 정의 → 전파 → 출력 경로 추적
- 화면 입력 → 서비스 → DB 흐름 추적
- API 엔드포인트와 보안/권한 처리 지점 식별

현재 `Data Flow Tracer`는 컴포넌트로는 존재하지만, 관계는 없다.

- Coordinator가 실행하는 관계도 없음
- Knowledge Base 질의 관계도 없음
- 다른 분석기와의 연계도 없음

정확히 말하면 [tci-03-component-analysis-engine.puml#L56](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/analysis-engine/tci-03-component-analysis-engine.puml#L56)에서 실행만 되고, 실제 데이터 소스 접근이 없다.

권고:

- `Data Flow Tracer -> KB` `Graph Query` 추가
- 필요하면 `Business Rule Extractor -> Data Flow Tracer` 의존도 추가

### 4. `Tech Stack Detector`도 독립 실행으로만 되어 있어 입력 자산이 보이지 않는다

`Tech Stack Detector`는 문서상 아래를 식별한다.

- 언어
- 프레임워크
- 빌드 시스템
- 실행 환경 구성
- API 스타일
- 메시지 브로커
- SDK와 라이브러리

이 기능은 실제로는 아래 자산을 읽어야 한다.

- 빌드 파일
- 설정 파일
- 코드 구조 메타데이터

하지만 현재 다이어그램에서는 `Coordinator에서 실행 지시 수신` 외의 관계가 없다.

권고:

- `Tech Stack Detector -> KB` `Graph/Object Query`
- 또는 `Tech Stack Detector`가 `Data Processing` 산출물을 직접 조회한다는 관계 추가

### 5. `Impact Analyzer`의 Diff 입력 경로가 불명확하다

문서상 `변경 영향 분석`의 핵심 선행 기능은 명확하다.

- `Diff 조회`
- `호출/의존성 분석`

현재 [tci-03-component-analysis-engine.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/analysis-engine/tci-03-component-analysis-engine.puml)에서 `Impact Analyzer`는 아래만 가진다.

- `Knowledge Base` 질의
- `Dependency Analyzer` 조회
- `Business Rule Extractor` 조회

하지만 Diff 자체가 어디서 오는지는 안 보인다.

가능한 해석:

- W&I가 분석 실행 트리거와 함께 Diff 식별자를 넘긴다
- KB에 스냅샷/분석 이력로 저장된 Diff를 조회한다

현재는 둘 다 명시되지 않았다.

권고:

- `Analysis Coordinator` note에 `Diff reference/target`가 입력으로 포함됨을 명시
- 또는 `Impact Analyzer -> KB` 설명에 `snapshot/diff metadata query` 포함

### 6. `비즈니스 규칙 검증/정합성 체크` 기능이 별도 책임으로 드러나지 않는다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 아래 기능이 별도 존재한다.

- 규칙과 코드 위치 연결
- 규칙-코드 정합성 점검
- 잠재 충돌 규칙 탐지
- 잠재 데드 규칙 후보 탐지

현재 다이어그램에는 이를 명시적으로 담당하는 컴포넌트가 없다.

가능한 흡수 위치:

- `Business Rule Extractor`
- `Impact Analyzer`
- `Risk Scorer`

하지만 현재 설명만으로는 어느 쪽인지 분명하지 않다.

권고:

- `Business Rule Extractor` 책임에 `정합성 체크` 포함
- 또는 `Rule Validator` 별도 컴포넌트 추가

### 7. `Structure Analyzer`에 너무 많은 책임이 몰려 있다

현재 `Structure Analyzer`는 아래를 함께 담당한다.

- 컴포넌트/레이어 식별
- 아키텍처 관계 추출
- External Integration 분석

문서 기준으로 이건 다음 여러 기능을 덮는다.

- 컴포넌트/레이어 추출
- 구조 메타데이터 추출 일부
- 아키텍처 관계 분석
- 서비스 인터페이스 분석 일부
- 시스템 경계 분석의 기반

이걸 한 컴포넌트로 묶는 것 자체는 가능하다.

다만 `구조 메타데이터 추출`이 빠져 보여서, 현재 설명만 보면 어노테이션/설정 파일/역할 분류 같은 메타데이터 생성 책임이 누락된 것처럼 읽힌다.

권고:

- `Structure Analyzer` 설명에 `구조 메타데이터 추출` 포함
- 또는 `Metadata Extractor`를 별도 컴포넌트로 분리

## 문서 대비 잘 맞는 부분

### 1. 핵심 분석 기능 분해

주요 기능은 거의 모두 커버된다.

- 기술 스택 탐지
- 구조 분석
- 의존성 분석
- 영향도 분석
- 비즈니스 규칙 추출
- 데이터 흐름 추적
- 테스트 영향 분석
- 리스크 분석

이건 문서와 높은 수준으로 잘 정렬된다.

### 2. `Dependency Analyzer`에 `Change Coupling`을 통합한 판단

기능 문서의 `호출/의존성 분석`과 `변경 결합도 분석`을 하나의 관계 분석 컴포넌트로 묶은 것은 설계적으로 납득 가능하다.

정적 의존성과 시간적 결합도를 함께 보면 영향 분석 품질이 좋아질 수 있다.

### 3. `Trade-off Analyzer` 추가

기능 문서의 `변경안(A vs B) 적용 시 영향 범위 수치 비교`와 `기술 지표를 비즈니스 언어로 번역한 영향 요약`을 기술적으로 잘 받쳐 준다.

### 4. `KB Writer` 분리

문서상 `리포트`, `자연어 설명`, `비즈니스 언어 번역`, `문서 초안`은 다른 컨테이너들이 소비하는 자산이다.

이를 `KB Writer`를 통해 정규화해 적재하게 한 것은 `W&I는 LLM 미사용`이라는 설계와 잘 맞는다.

## 현재 기준 결론

현재 `Analysis Engine` 컴포넌트 다이어그램은 문서와 `대체로 일치`한다.

판단:

- 분석 기능 분해와 전체 방향은 좋음
- 하지만 `BizRule`, `DataFlow`, `TechStack`, `Impact`의 입력 관계가 부족해 실행 근거가 약하게 보임
- `비즈니스 규칙 정합성 체크`와 `구조 메타데이터 추출` 책임은 보강 필요

우선순위:

1. `Business Rule Extractor`, `Data Flow Tracer`, `Tech Stack Detector`의 KB/상호 의존 관계 명시
2. `Impact Analyzer`의 Diff 입력 경로 명확화
3. `비즈니스 규칙 검증/정합성 체크` 책임을 어디에 둘지 정리
4. Notion의 `컴포넌트 10개` 표기를 실제 개수와 맞추기
