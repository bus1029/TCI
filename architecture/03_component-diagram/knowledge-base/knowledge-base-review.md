# TCI Component Diagram 검토 - Knowledge Base

## 검토 목적

- `TCI Component Diagram - Knowledge Base`가 제품 문서의 범위와 의도를 C4 Level 3 관점에서 정확하게 반영하는지 확인
- 지식 저장 구조와 질의 구조가 문서 근거와 맞는지 검토
- Notion 설명과 `tci-03-component-knowledge-base.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Component Diagram - Knowledge Base`
- [tci-03-component-knowledge-base.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/knowledge-base/tci-03-component-knowledge-base.puml)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)

## 총평

현재 `Knowledge Base` 컴포넌트 다이어그램은 전체 방향이 좋다.

- `Query Facade`를 단일 진입점으로 둔 점
- `Graph Store`, `Vector Store`, `Object Store`, `Search Index`를 분리한 점
- `Schema Manager`, `Retention Manager`를 운영성 컴포넌트로 둔 점
- `단일 지식 모델`을 단일 저장소가 아니라 다중 저장소 + 단일 접근 계층으로 해석한 점

Notion 설명과 `puml`의 정합성도 높은 편이다.

다만 문서와 대조하면 아래 보완이 필요하다.

- `Search Index`가 어떻게 채워지는지 보이지 않는다
- 문서가 강조하는 지식 자산 종류 일부가 저장 모델에 충분히 드러나지 않는다
- 보존/정리 정책이 `Search Index`까지 닿지 않는다

## 핵심 findings

### 1. `Search Index`의 인덱싱 경로가 빠져 있다

현재 [tci-03-component-knowledge-base.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/knowledge-base/tci-03-component-knowledge-base.puml)에서 `Search Index`는 아래처럼 표현된다.

- 책임: `전문 검색`, `코드/문서/규칙 텍스트 인덱싱`, `자동완성`
- 관계: `Query Facade -> Search Index` 질의만 존재

문제는 `누가 Search Index를 갱신하는가`가 다이어그램에 없다는 점이다.

현재 보이는 쓰기 경로는 없다.

- `Analysis Engine -> Query Facade`
- `Interactive Assistant -> Query Facade`
- `Workflow & Integration -> Query Facade`
- `Data Processing -> Query Facade`

하지만 그 이후 `Query Facade -> Search Index`는 `전문 검색 질의`만 있다.

즉 문서상 중요한 `지식 검색 및 재탐색을 위한 인덱싱`은 있는데, 실제 인덱싱 파이프라인이 비어 있다.

권고:

- `Index Builder` 또는 `Search Projector` 같은 컴포넌트 추가
- 또는 `Query Facade`가 검색 인덱스 갱신까지 수행한다는 점을 명시

### 2. `단일 지식 모델`의 주요 자산 일부가 저장 구조 설명에 충분히 드러나지 않는다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에서 `단일 지식 모델 구성`은 아래를 결합한다.

- CPG
- 도메인 용어 사전
- 외부 컨텍스트 추가
- 비즈니스 규칙
- 문서, 티켓, 사용자 컨텍스트
- 코드, 문서, 티켓 간 교차 참조

현재 KB 다이어그램에서는 아래는 잘 드러난다.

- CPG
- 비즈니스 규칙 카탈로그
- 임베딩 벡터
- 문서 원본

하지만 아래는 저장 구조 설명에서 암묵적이거나 빠져 있다.

- 도메인 용어 사전
- 사용자 수동 컨텍스트
- 팀 컨벤션 / 주의사항
- 문서-코드-티켓 교차 참조 노드/엣지

이걸 꼭 별도 컴포넌트로 쪼갤 필요는 없다.

다만 최소한 아래 중 하나는 필요하다.

- `Graph Store` 설명에 `도메인 용어`, `외부 컨텍스트`, `교차 참조` 포함
- 별도 note로 `단일 지식 모델`에 포함되는 주요 지식 자산 목록 명시

### 3. `Interactive Assistant`의 `답변·이력 적재`를 담을 저장 위치가 명확하지 않다

현재 [tci-03-component-knowledge-base.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/knowledge-base/tci-03-component-knowledge-base.puml)에서 `Interactive Assistant`는 아래 관계를 가진다.

- `구조/규칙/분석 결과 검색`
- `답변·이력 적재`

문서에는 실제로 아래 기능이 있다.

- `채팅 인터페이스 / 세션 / 권한 관리`
- `답변을 문서화해 지식 베이스화`
- `답변 평가 시스템`

하지만 KB 내부 저장소 설명에서는 아래가 명확하지 않다.

- 대화 이력은 어디에 저장되는가
- 답변 문서화 자산은 어떤 스토어에 저장되는가
- Good/Bad/코멘트 같은 피드백은 어디에 저장되는가

가능한 해석은 있다.

- 대화/피드백 메타는 `Graph Store`
- 문서화된 답변은 `Search Index`와 `Graph Store`
- 긴 아티팩트는 `Object Store`

하지만 현재 다이어그램만으로는 불명확하다.

권고:

- `Query Facade` note 또는 `Graph Store` 설명에 `Q&A history / feedback / curated answer assets` 포함
- 또는 별도 `Conversation Store` 성격을 명시

### 4. `Retention Manager`가 `Search Index`를 정리하지 않아 인덱스 고아 데이터 위험이 있다

현재 `Retention Manager`는 아래만 정리한다.

- `Graph Store`
- `Object Store`
- `Vector Store`

하지만 `Search Index`는 빠져 있다.

문제는 원본 문서, 규칙, 스냅샷, 분석 산출물이 만료/삭제되면 검색 인덱스에도 삭제 반영이 필요하다는 점이다.

그렇지 않으면:

- 검색 결과에 삭제된 문서가 남을 수 있음
- 자동완성에 오래된 규칙 이름이 남을 수 있음
- 인덱스와 원본 스토어 간 정합성이 깨질 수 있음

권고:

- `Retention Manager -> Search Index` 관계 추가
- 또는 인덱스 재구축 정책을 별도 note로 명시

### 5. `Schema Manager`가 Graph만 다루는 것은 타당하지만, Search/Vector 메타 스키마는 별도 설명이 필요하다

현재 `Schema Manager`는 `Graph Store`만 관리한다.

이건 CPG와 분석 산출물 스키마 측면에서는 합리적이다.

다만 실제 Knowledge Base 운영 관점에서는 아래도 존재한다.

- Vector metadata schema
- Search index mapping
- Object metadata layout

이걸 모두 `Schema Manager`로 확장할 필요는 없다.

하지만 운영자가 보면 아래 질문이 남는다.

- 검색 인덱스 매핑 버전은 누가 관리하는가
- 벡터 메타 필드는 어디서 관리하는가

즉 현재는 오류라기보다 운영 설계 설명의 공백이다.

## 문서 대비 잘 맞는 부분

### 1. `Query Facade` 도입

문서의 `단일 지식 모델 구성`, `컨텍스트 검색`, `자연어 질의응답`, `근거 제공` 방향과 잘 맞는다.

여러 저장소를 외부 컨테이너가 직접 알지 않고, 하나의 질의 계층으로 접근하는 구조는 타당하다.

### 2. `Graph Store + Vector Store + Object Store + Search Index` 4분할

이 분리는 설득력이 있다.

- Graph: 관계 탐색
- Vector: 유사도 검색
- Object: 원본/스냅샷 저장
- Search: 키워드 검색

문서가 요구하는 구조 탐색, RAG, 문서 원본 보존, 전문 검색을 모두 수용할 수 있다.

### 3. `Graph Store`의 비즈니스 규칙 카탈로그 역할

기능 문서의 `비즈니스 규칙 관리`, `규칙-코드 매핑`, `규칙 버전 이력 추적`과 잘 맞는다.

특히 note에서 규칙 노드와 CPG 노드 연결을 명시한 점은 좋다.

### 4. `Retention Manager` 도입

엔터프라이즈 환경에서 스토리지 보존 정책을 별도 컴포넌트로 둔 것은 설계적으로 타당하다.

코드 스냅샷, 임베딩 벡터, 분석 산출물의 라이프사이클을 통제해야 한다는 점은 문서의 운영 맥락과도 맞는다.

## 현재 기준 결론

현재 `Knowledge Base` 컴포넌트 다이어그램은 문서와 `대체로 일치`한다.

판단:

- 핵심 저장 구조와 질의 구조는 잘 설계됨
- 다만 `Search Index 인덱싱 경로`, `단일 지식 모델의 자산 종류`, `Q&A/피드백 저장 위치`, `Search Index 보존 정리`는 보강이 필요

우선순위:

1. `Search Index` 갱신 주체를 다이어그램에 추가
2. `Graph Store` 설명에 `도메인 용어`, `외부 컨텍스트`, `교차 참조` 포함 여부 명시
3. `Interactive Assistant`가 적재하는 대화 이력/피드백 자산의 저장 위치를 명확화
4. `Retention Manager -> Search Index` 정리 경로 추가 여부 결정
