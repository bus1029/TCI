# TCI Component Diagram 검토 - Data Processing

## 검토 목적

- `TCI Component Diagram - Data Processing`이 제품 문서의 범위와 의도를 C4 Level 3 관점에서 정확하게 반영하는지 확인
- 컴포넌트 책임 분리가 문서 근거와 맞는지 검토
- Notion 설명과 `tci-03-component-data-processing.puml` 간 불일치 여부 확인

## 검토 대상

- Notion `TCI Component Diagram - Data Processing`
- [tci-03-component-data-processing.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/data-processing/tci-03-component-data-processing.puml)
- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)
- [tci-prd.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/prd/tci-prd.md)
- [tci-positioning.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/positioning/tci-positioning.md)

## 총평

현재 `Data Processing` 컴포넌트 다이어그램은 전체적으로 잘 정리되어 있다.

- `Pipeline Coordinator` 중심의 파이프라인 오케스트레이션
- `Source Normalizer -> CPG Generator -> 병렬 처리 -> KB 적재` 흐름
- `Pattern Identifier`와 `Analysis Engine`의 비즈니스 규칙 추출 경계 명시
- `Job Queue`를 통한 CPU/GPU 집약 작업 제어

앞선 C3 다이어그램들보다 Notion 설명과 `puml`의 정합성도 높다.

다만 문서와 대조하면 아래 두 가지가 핵심 보완 포인트다.

- `코드용 처리 흐름`과 `문서/티켓용 처리 흐름`이 하나의 선형 파이프라인으로 섞여 보임
- `KB Loader`를 둔 이유와 실제 KB 쓰기 경로가 충돌함

## 핵심 findings

### 1. `문서/티켓`까지 `CPG Generator`로 들어가는 것처럼 읽힌다

[tci-03-component-data-processing.puml](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/03_component-diagram/data-processing/tci-03-component-data-processing.puml)에서는 아래 흐름이 단일 파이프라인으로 표현된다.

- `Data Collection -> Pipeline Coordinator`
- `Pipeline Coordinator -> Source Normalizer`
- `Source Normalizer -> CPG Generator`

문제는 외부 `Data Collection` 설명에 이미 아래가 포함되어 있다는 점이다.

- `Git / Doc / Ticket / PR 수집 · 증분 동기화`
- `파일 업로드`

즉 현재 그림만 보면 `문서`, `티켓`, `PR 메타`, `업로드 파일`까지 모두 `CPG Generator`의 입력처럼 읽힌다.

하지만 문서 기준으로 `CPG`는 본질적으로 코드 구조 분석용 자산이다.

- [whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)의 `코드 속성 그래프 생성 및 관리`
- 구조/흐름 분석, 호출/의존성 분석, 코드 엔티티 관계 생성

반면 문서/티켓은 다음 성격에 가깝다.

- 컨텍스트 자산
- 검색/질의응답/RAG용 텍스트 자산
- 문서-코드 추적용 메타데이터 자산

권고:

- `Source Normalizer` 이후를 `Code Pipeline`과 `Context Artifact Pipeline`으로 분기
- 코드만 `CPG Generator`로 보내기
- 문서/티켓/업로드 텍스트는 `Embedding Generator`나 별도 `Artifact Normalizer`로 보내기

### 2. `KB Loader`의 책임과 실제 쓰기 경로가 서로 충돌한다

Notion 설명과 `puml`은 `KB Loader`를 아래처럼 정의한다.

- `CPG/임베딩/패턴/스냅샷 → KB 스키마 정규화 후 적재`
- 적재 전 검증
- 버저닝/덮어쓰기 정책 관리

그런데 실제 관계는 다음처럼 그려져 있다.

- `dp_embedding -> dp_kbloader`
- `dp_pattern -> dp_kbloader`
- `dp_snapshot -> dp_kbloader`
- `dp_cpg -> dp_kbloader`

동시에 또 아래 직접 쓰기 관계가 있다.

- `dp_kbloader -> KB` `Graph Write`
- `dp_snapshot -> KB` `Object Write`
- `dp_embedding -> KB` `Vector Write`

즉 `KB Loader`가 중앙 적재자처럼 설명되지만, 실제로는 `Snapshot Builder`와 `Embedding Generator`가 KB에 직접 쓰고 있다.

이건 책임 경계를 모호하게 만든다.

가능한 해석:

- `KB Loader`는 그래프 계열만 적재
- `Snapshot Builder`, `Embedding Generator`는 각 저장소에 직접 적재

하지만 그렇다면 `KB Loader` 설명을 바꿔야 한다.

권고:

- 선택 A: `KB Loader`를 유일한 KB Writer로 유지
- 선택 B: `KB Loader`를 `Graph Loader`로 축소하고 `Vector/Object` 직접 적재를 명시

현재 상태는 설명과 그림이 동시에 성립하지 않는다.

### 3. `Snapshot Builder`의 책임 범위가 제품 문서의 `데이터 소스 스냅샷 관리`보다 좁다

[whole-features.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/architecture/features/whole-features.md)에는 `데이터 소스 스냅샷 관리`가 있다.

- 메타데이터 스냅샷 저장
- 스냅샷 버전 이력 관리
- 특정 시점 기준 분석 데이터 재현
- 스냅샷 간 변경 비교

현재 `Snapshot Builder`는 다음으로 정의된다.

- `소스 코드 버전별 스냅샷 생성`
- `delta 계산`
- `버전 관리`

이건 코드 스냅샷 관점으로는 맞지만, 제품 문서가 말하는 전체 데이터 소스 스냅샷 범위보다는 좁다.

즉 둘 중 하나를 정리해야 한다.

- `Data Processing`의 `Snapshot Builder`는 코드 스냅샷만 담당
- 전체 데이터 소스 스냅샷은 다른 컨테이너나 상위 레벨 책임

현재 상태에서는 이름만 보면 더 넓은 책임처럼 읽힐 수 있다.

### 4. `Source Normalizer`의 책임 설명이 다소 과도하다

Notion 설명에서 `Source Normalizer`는 아래를 담당한다.

- 수집 원시 데이터 정규화
- 언어별 파서 선택
- 인코딩 통일
- 포맷 변환

여기서 `언어별 파서 선택`은 `CPG Generator`의 `언어별 프론트엔드 선택`과도 겹친다.

즉 지금은 아래 두 책임이 중복될 여지가 있다.

- `Normalizer`: 파서 선택
- `CPG Generator`: 언어별 프론트엔드 선택

권고:

- `Normalizer`는 입력 정규화와 분류만 담당
- 실제 코드 파서/프론트엔드 선택은 `CPG Generator`로 일원화

### 5. `도메인 용어 사전`이나 `외부 컨텍스트` 준비 책임은 DP에 거의 보이지 않는다

이건 꼭 오류는 아니다.

문서에는 아래가 있다.

- 도메인 용어 사전
- 외부 컨텍스트 추가
- 단일 지식 모델 구성

현재 DP는 아래까지만 담당한다.

- CPG 생성
- 임베딩 생성
- 원시 규칙 패턴 식별
- 스냅샷 적재

즉 DP를 `구조적 전처리와 저장 준비`로 한정한 것은 합리적이다.

다만 향후 C3를 더 세분화할 때는 아래를 어디서 담당하는지 보강이 필요하다.

- 네이밍 분석 기반 용어 후보 추출
- 문서/티켓 메타 정규화
- 외부 컨텍스트를 KB 스키마에 병합하는 전처리

## 문서 대비 잘 맞는 부분

### 1. `Pattern Identifier`와 `AE Business Rule Extractor` 경계

이 경계는 명확하고 문서와 잘 맞는다.

- DP는 후보 패턴 식별
- AE는 의미 해석과 비즈니스 규칙 추출

이는 앞서 문서에서 본 `Data Processing은 원시 패턴 식별`, `Analysis Engine은 비즈니스 규칙 추출`과 일치한다.

### 2. `Embedding Generator`의 보조적 LLM 사용

문서의 방향은 `AI/LLM을 쓰되, 구조 분석의 핵심은 코드 기반 분석`에 가깝다.

따라서 DP에서 LLM을 `임베딩 생성` 정도로 제한한 것은 설득력 있다.

### 3. `Job Queue` 도입

대규모 코드베이스의 CPG 생성과 임베딩 생성은 비용이 큰 작업이므로 큐 기반 제어는 타당하다.

이건 제품 문서의 직접 기능은 아니지만, C3 수준에서 충분히 합리적인 구현 설계다.

### 4. `Knowledge Base`의 `Vector DB` 포함 표기

이전 C2에서 빠졌던 `Vector DB`가 여기선 명시되어 있어, 자연어 질의응답과 컨텍스트 검색 방향과 더 잘 맞는다.

## 현재 기준 결론

현재 `Data Processing` 컴포넌트 다이어그램은 문서와 `대체로 일치`한다.

판단:

- 전체 처리 파이프라인은 설득력 있음
- `Pattern Identifier` 경계 정의도 적절함
- 다만 `코드와 비코드 자산 처리 경로 분리`와 `KB 적재 책임 일원화`는 수정 또는 설명 보강이 필요

우선순위:

1. 문서/티켓/업로드 자산이 `CPG Generator`를 거치는지 여부 명확화
2. `KB Loader`를 중앙 적재자로 유지할지, 저장소별 직접 적재를 허용할지 결정
3. `Snapshot Builder`의 범위를 `코드 스냅샷`으로 제한할지 상위 스냅샷 관리와 연결할지 정리
