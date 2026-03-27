# Doc KB 세 제품 원페이저

## 목적

이 문서는 내일 상급자 질문에 바로 답할 수 있도록 `AnythingLLM`, `Basic Memory`, `Graphiti`의 차이와 우리 팀 시사점을 한 장으로 압축한 요약본이다.

## 한 줄 결론

- 지금 단계의 추천 축은 `AnythingLLM + Basic Memory`
- 이유는 문서 수집과 운영은 `AnythingLLM`이 강하고, 원본 소유권과 장기 지식 저장은 `Basic Memory`가 강하기 때문
- `Graphiti`는 중요한 참고 대상이지만, 지금 바로 중심축으로 두기에는 에이전트 메모리 복잡도가 높음

## 제품별 한 줄 정의

| 제품 | 한 줄 정의 | 가장 잘 푸는 문제 |
| --- | --- | --- |
| `AnythingLLM` | 다종 문서를 워크스페이스 단위로 수집하고 검색하는 문서형 AI 앱 | 문서 수집, 워크스페이스 운영, 문서 기반 질의응답 |
| `Basic Memory` | Markdown 파일을 원본으로 유지하는 local-first 지식 인프라 | 사람과 AI가 함께 쓰는 장기 지식 저장소 |
| `Graphiti` | 시간성과 provenance를 다루는 에이전트 메모리 그래프 엔진 | 상태 변화 추적, 사실 관리, 장기 메모리 |

## 제품별 핵심 특징

### `AnythingLLM`

- 핵심 정체성: 문서형 지식 베이스 운영 제품
- 강점 1: PDF, DOCX, 링크, raw text를 공통 문서 계약으로 수집 가능
- 강점 2: 워크스페이스 중심으로 문서, 채팅, 설정, 권한을 묶어 운영 가능
- 강점 3: query 모드 숏서킷처럼 무근거 응답을 정책적으로 차단 가능
- 우리 팀 적용 포인트: 문서 ingest 파이프라인, 저장 계층 분리, 워크스페이스 운영 모델
- 한계: 장기 메모리나 시간성 있는 사실 관리까지는 중심 문제가 아님

### `Basic Memory`

- 핵심 정체성: 파일 원본 기반 지식 저장 인프라
- 강점 1: Markdown 파일이 source of truth라서 사람이 직접 읽고 수정 가능
- 강점 2: observation, relation, permalink로 검색 가능한 약한 구조를 만들 수 있음
- 강점 3: watcher, checksum, sync, doctor로 파일과 인덱스 정합성을 유지함
- 우리 팀 적용 포인트: 파일 원본과 인덱스 분리, permalink 기반 추적성, 검색과 문맥 구성 분리
- 한계: 대규모 범용 문서 수집기라기보다 저장소형 제품에 가까움

### `Graphiti`

- 핵심 정체성: temporal agent memory 엔진
- 강점 1: `Episode -> Entity -> Fact` 구조로 사실과 관계를 저장함
- 강점 2: invalidation으로 과거 사실과 현재 사실을 함께 관리함
- 강점 3: provenance를 Episode 기준으로 역추적할 수 있음
- 우리 팀 적용 포인트: provenance를 일급 객체로 보는 태도, search와 context composition 분리, 시간 일관성 운영 규칙
- 한계: 문서형 KB 초기 단계에 바로 넣기에는 구조와 운영 복잡도가 큼

## 세 제품의 차이

| 비교 축 | `AnythingLLM` | `Basic Memory` | `Graphiti` |
| --- | --- | --- | --- |
| 지식의 기본 단위 | 문서 JSON과 청크 | Markdown 노트, observation, relation | Episode, Entity, Fact |
| 원본 저장 관점 | 문서 수집 자산 | 파일 원본 소유권 | 원문 + 사실 그래프 |
| 검색 철학 | 문서 검색 결과를 프롬프트로 조립 | 검색 후 다시 탐색 가능한 주소로 연결 | 그래프 레이어를 함께 조립 |
| 신뢰성 장치 | citation 메타데이터 + 무근거 응답 차단 | permalink, file path, matched chunk | provenance, invalidation, fact 역추적 |
| 운영 강점 | 워크스페이스와 권한 모델 | 로컬 우선 저장과 sync | 시간 일관성과 멀티 provider 운영 |

## 우리 팀 기준 권장 선택

### 지금 먼저 가져올 것

- `AnythingLLM`의 문서 수집 구조
- `AnythingLLM`의 공통 문서 계약과 저장 계층 분리
- `Basic Memory`의 파일 원본 우선 원칙
- `Basic Memory`의 permalink 중심 추적성
- 검색과 문맥 조립을 분리하는 설계 원칙

### 나중에 확장할 것

- `Graphiti`의 provenance 모델
- `Graphiti`의 상태 전이와 invalidation
- `Graphiti`의 agent memory 운영 규칙

### 지금 하지 않을 것

- 완전한 temporal fact graph의 조기 도입
- 모든 provider를 같은 수준으로 지원하는 과도한 추상화
- 고비용 reranker와 복잡한 그래프 탐색의 조기 도입

## 예상 질문과 짧은 답변

### Q. 세 제품 중 무엇이 가장 좋나

제품 우열의 문제라기보다 푸는 문제가 다르다. 지금 우리 목적이 문서 기반 KB라면 `AnythingLLM + Basic Memory` 조합이 가장 현실적이다.

### Q. 왜 `Graphiti`를 바로 쓰지 않나

`Graphiti`는 강력하지만 에이전트 메모리 엔진이다. 지금 단계에서는 문서 수집, 저장 계약, 검색 기본기가 먼저라서 도입 복잡도가 더 크다.

### Q. `AnythingLLM`과 `Basic Memory`의 차이는 무엇인가

`AnythingLLM`은 문서 운영과 워크스페이스 제품에 가깝고, `Basic Memory`는 파일 원본 기반 지식 저장 인프라에 가깝다.

### Q. 우리 팀이 바로 벤치마킹해야 할 기술 포인트는 무엇인가

공통 문서 계약, 파일 원본과 인덱스 분리, permalink 기반 추적성, 검색과 문맥 조립 분리, 무근거 응답 차단이다.

### Q. 장기적으로 `Graphiti`에서 배워야 할 것은 무엇인가

provenance, 시간성 있는 사실 관리, search와 context composition 분리, 순차 처리 기반 메모리 운영 규칙이다.

## 최종 메시지

지금 우리 팀은 문서형 지식 베이스의 기본기를 먼저 세워야 한다. 따라서 출발점은 `AnythingLLM`의 ingest와 운영 구조, `Basic Memory`의 저장 원칙과 추적성을 결합하는 방향이 맞고, `Graphiti`는 이후 에이전트 메모리 확장 단계에서 흡수하는 것이 적절하다.
