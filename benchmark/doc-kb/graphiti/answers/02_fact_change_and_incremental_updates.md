# 사실 변경과 증분 갱신 분석

## 개요

Graphiti의 ingestion 설계는 "새 입력을 얼마나 빨리 저장할 것인가"보다 "이미 축적된 사실 그래프를 시간이 흐르는 현실에 맞게 어떻게 갱신할 것인가"에 더 가깝다. 그래서 이 프로젝트는 사실 변경을 단순 overwrite나 delete로 처리하지 않고 invalidation으로 남기고, 단건 갱신 경로와 벌크 적재 경로도 하나로 합치지 않는다. 여기에 더해 노드와 엣지 dedupe, contradiction 처리를 ingestion 파이프라인 안에 넣어 LLM 추출 결과를 그대로 저장하지 않도록 막는다.

이 문서를 읽을 때 먼저 잡아야 할 전제는 아래와 같다.

- Graphiti의 저장 단위는 문서 조각이 아니라 시간 축을 가진 fact
- 새 fact를 넣는 일과 기존 fact를 안전하게 정리하는 일은 같은 ingestion 단계 안에서 함께 처리됨
- `add_episode()`는 temporal precision 중심 경로
- `add_episode_bulk()`는 처리량 중심 경로
- dedupe와 contradiction 처리는 부가 기능이 아니라 그래프 품질을 유지하는 핵심 계층
- Graphiti는 "추출"보다 "정규화된 사실 그래프 유지"를 더 중요한 목표로 둠

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| invalidation | 기존 fact를 삭제하지 않고 `invalid_at`과 `expired_at`을 채워 과거 사실로 전환하는 처리 |
| contradiction | 새 fact가 기존 fact와 동시에 참일 수 없는 상태 |
| single ingestion | `add_episode()` 기반 단건 처리 경로 |
| bulk ingestion | `add_episode_bulk()` 기반 대량 처리 경로 |
| dedupe | 같은 엔티티 또는 사실을 canonical 객체로 수렴시키는 정규화 과정 |
| temporal precision | 사실의 유효 시점과 무효 시점을 보존하는 정확도 |

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 삭제 대신 invalidation으로 사실 변경을 처리하는 구조

### 채택 기술 구조

- temporal fact model
  - `EntityEdge`는 `fact`, `episodes`, `valid_at`, `invalid_at`, `expired_at`를 함께 가짐
  - 따라서 Graphiti는 현재 사실만 저장하는 구조가 아니라 "언제부터 언제까지 참이었는가"를 저장하는 구조임
- contradiction 해소 방식
  - `resolve_extracted_edges()`는 새 edge를 바로 저장하지 않고 먼저 중복 후보와 invalidation 후보를 따로 모음
  - `resolve_extracted_edge()`는 LLM 판단과 규칙 기반 후처리를 섞어 duplicate와 contradicted fact를 분리함
  - `resolve_edge_contradictions()`는 새 edge가 더 최신 사실이면 기존 edge의 `invalid_at`을 새 edge의 `valid_at`으로 채움
- 과거 사실 보존 방식
  - invalidated edge는 삭제되지 않고 그래프 안에 남음
  - 검색 필터도 `valid_at`, `invalid_at`, `expired_at` 기준 조건을 지원하므로 현재 상태와 과거 상태를 모두 질의할 수 있음
- 운영 안정성 관점
  - 삭제 중심 구조라면 잘못된 추출이 들어왔을 때 원인을 복기하기 어려움
  - invalidation 중심 구조라면 기존 fact를 남긴 채 더 최신 정보로 덮기 때문에 감사와 디버깅이 쉬워짐

### 코드 근거 예시

- `README.md`
  - Graphiti를 `validity windows`와 `automatic fact invalidation`을 가진 temporal context graph로 설명함
  - `temporal history preserved`를 차별점으로 직접 명시함
- `graphiti_core/edges.py`
  - `EntityEdge`가 `valid_at`, `invalid_at`, `expired_at`, `episodes`를 기본 필드로 가짐
  - 사실 모델 자체가 삭제보다 이력 보존을 전제함
- `graphiti_core/utils/maintenance/edge_operations.py`
  - `resolve_extracted_edges()`가 duplicate 후보와 invalidation 후보를 분리해서 검색함
  - `resolve_extracted_edge()`가 LLM 응답으로 중복과 contradiction을 판정한 뒤 후처리함
  - `resolve_edge_contradictions()`가 기존 edge를 삭제하지 않고 `invalid_at`과 `expired_at`을 갱신함
- `graphiti_core/search/search_filters.py`
  - `SearchFilters`가 `valid_at`, `invalid_at`, `expired_at` 필터를 제공함
  - 시간성을 보존한 사실을 검색 계층에서도 직접 다룬다는 뜻임
- `tests/utils/maintenance/test_edge_operations.py`
  - `test_resolve_extracted_edge_exact_fact_short_circuit`는 같은 fact를 재삽입할 때 새 edge를 만들지 않고 기존 edge를 재사용함을 검증함
  - `test_resolve_extracted_edges_fast_path_deduplication`은 exact match를 먼저 걷어내 불필요한 LLM 호출을 줄이는 의도를 보여 줌

### 제품 적용 포인트

- 사용자 선호, 조직 구조, 정책 상태처럼 시간이 지나며 바뀌는 지식은 삭제보다 invalidation이 안전함
- 과거 사실을 남겨야 "지금 왜 이렇게 검색됐는가"를 설명할 수 있음
- 장기 메모리 제품에서는 overwrite보다 상태 전이 기록이 더 중요함
- contradiction 처리를 저장 직전이 아니라 ingestion 안에서 처리해야 KB가 시간이 갈수록 오염되지 않음
- temporal KB는 저장 모델과 검색 필터가 같이 설계되어야 현재 시점 조회와 과거 시점 조회를 모두 지원할 수 있음

### 해석과 시사점

- Graphiti는 "최신 정답 하나"보다 "변화 과정 전체"를 메모리 자산으로 봄
- 이 구조 덕분에 현재 truth store이면서 동시에 과거 상태를 복원할 수 있는 history-aware KB가 됨
- 저장 비용과 처리 복잡도는 늘어나지만, 시간 변화가 중요한 메모리 시스템에는 삭제보다 훨씬 실무적인 선택임

## 2. `add_episode()`와 `add_episode_bulk()`를 분리한 이유

### 채택 기술 구조

- 단건 경로의 목표
  - `add_episode()`는 새 Episode를 기준으로 이전 Episode를 조회하고, node extraction, node dedupe, edge extraction, contradiction 처리, attribute 보강, 저장을 순차적으로 수행함
  - 메서드 주석도 각 Episode를 순차적으로 await 하라고 권장함
  - 즉 temporal consistency가 가장 중요한 경로임
- 벌크 경로의 목표
  - `add_episode_bulk()`는 먼저 Episode들을 저장한 뒤, 각 Episode별 이전 문맥을 가져오고, 배치 안에서 dedupe를 수행한 후 마지막에 일괄 저장함
  - 처리량을 높이기 위한 메모리 내 정규화와 bulk write가 핵심임
- 기능 차이
  - `add_episode_bulk()` 주석은 edge invalidation과 date extraction을 수행하지 않는다고 명시함
  - `dedupe_edges_bulk()`도 현재는 `For now we won't track edge invalidation`이라는 주석처럼 contradiction 이력까지 추적하지 않음
  - 따라서 두 경로는 이름만 다른 것이 아니라 목표와 의미가 다름
- 운영 전략
  - 대화형 agent memory처럼 시간 순서와 상태 전이가 중요하면 단건 경로가 맞음
  - 대량 import, backfill, 초기 데이터 적재처럼 throughput이 중요하면 bulk 경로가 맞음
  - 하나의 API로 통합하면 사용자는 두 모드의 trade-off를 구분하기 어려워짐

### 코드 근거 예시

- `graphiti_core/graphiti.py`
  - `add_episode()`는 `retrieve_episodes()`, `extract_nodes()`, `resolve_extracted_nodes()`, `extract_edges()`, `resolve_extracted_edges()`, `extract_attributes_from_nodes()`를 거친 뒤 저장함
  - `add_episode()` docstring이 순차 처리와 background queue 사용을 권장함
  - `add_episode_bulk()` docstring이 `edge invalidation`과 `date extraction`을 수행하지 않는다고 분명히 밝힘
  - `_extract_and_dedupe_nodes_bulk()`와 `_resolve_nodes_and_edges_bulk()`는 bulk 전용 보조 단계로 분리돼 있음
- `graphiti_core/utils/bulk_utils.py`
  - `dedupe_nodes_bulk()`는 live graph 기준 1차 해소 후 batch 내부 canonicalization을 다시 수행하는 `two-pass strategy`를 사용함
  - `dedupe_edges_bulk()`는 batch 안에서 유사 edge를 정리하지만 invalidation은 추적하지 않음
- `tests/utils/maintenance/test_bulk_utils.py`
  - `test_dedupe_nodes_bulk_reuses_canonical_nodes`는 batch 안에서 같은 엔티티를 canonical node로 모으는 동작을 검증함
  - `test_dedupe_edges_bulk_deduplicates_within_episode`는 같은 Episode 안의 중복 edge도 bulk 경로에서 정리함을 검증함
- `docs/project/workflows.md`
  - bulk ingestion이 단건 경로보다 빠르지만 temporal nuance를 일부 단순화한다고 설명함

### 제품 적용 포인트

- ingestion 경로를 하나로 통합하지 말고 precision 경로와 throughput 경로를 분리하면 운영 의도가 더 명확해짐
- 실시간 메모리와 대량 적재는 실패 비용이 다르므로 같은 파이프라인으로 다루기 어렵다
- bulk 경로는 빠르지만 정교한 temporal invalidation이 빠질 수 있으므로 사용 맥락을 문서와 API에서 분명히 밝혀야 함
- single path와 bulk path를 나누면 성능 최적화가 코어 의미를 훼손하지 않게 설계할 수 있음
- 장기적으로는 bulk 경로도 더 정교해질 수 있지만, 현재는 feature parity보다 역할 분리를 택한 상태로 보는 편이 맞음

### 해석과 시사점

- `add_episode()`와 `add_episode_bulk()`의 분리는 단순 편의성 문제가 아님
- Graphiti는 증분 갱신의 정확도와 대량 적재의 효율을 동일한 목표로 취급하지 않음
- 에이전트 메모리에서는 "새 입력 하나가 기존 사실을 어떻게 바꾸는가"가 중요하고, 대량 import에서는 "많은 입력을 얼마나 싸고 빠르게 넣는가"가 중요함
- 두 목적을 분리해 둔 덕분에 ingestion 품질 기준과 trade-off가 API 수준에서 드러남

## 3. 노드와 엣지 dedupe, contradiction 처리를 ingestion 안에 넣은 이유

### 채택 기술 구조

- node dedupe의 위치
  - `resolve_extracted_nodes()`는 추출 직후 기존 그래프 후보를 모으고, similarity 기반 규칙으로 먼저 빠른 매칭을 수행한 뒤, 남은 holdout만 LLM에 넘김
  - 즉 dedupe는 저장 후 정리 작업이 아니라 저장 전 canonicalization 단계임
- edge dedupe의 위치
  - `resolve_extracted_edges()`는 exact match fast path, existing edge 검색, invalidation 후보 검색, LLM 기반 duplicate 판단, contradiction 후처리를 한 번에 수행함
  - fact extraction과 fact normalization이 분리돼 있지 않고 한 ingestion 경로 안에 결합돼 있음
- contradiction 처리의 이유
  - LLM이 뽑은 fact는 표현이 흔들릴 수 있고, 이미 그래프에 있는 사실과 충돌할 수도 있음
  - 이 결과를 그대로 저장하면 같은 개체가 여러 UUID로 퍼지고, 같은 의미의 fact가 중복되고, 상충하는 사실이 동시에 current state처럼 남게 됨
- 계층적 보정 방식
  - Graphiti는 deterministic similarity, graph search, LLM 판정, time-aware 후처리를 단계적으로 겹침
  - 즉 "LLM이 잘 뽑아주길 기대"하는 시스템이 아니라 "LLM 출력을 그래프 품질 규칙으로 보정"하는 시스템임

### 코드 근거 예시

- `graphiti_core/utils/maintenance/node_operations.py`
  - `resolve_extracted_nodes()`가 candidate collection, similarity 해소, LLM 해소 순서로 동작함
  - docstring도 holdout만 LLM dedupe prompt로 올린다고 명시함
- `graphiti_core/utils/maintenance/edge_operations.py`
  - `resolve_extracted_edges()`가 exact match dedupe를 먼저 수행함
  - 같은 함수 안에서 duplicate 후보 검색과 invalidation 후보 검색을 따로 돌린 뒤 `resolve_extracted_edge()`로 합침
  - `resolve_extracted_edge()`는 duplicate reuse, contradiction 판정, 속성 추출, 시간 후처리를 모두 수행함
- `graphiti_core/graphiti.py`
  - `add_episode()`는 extraction 다음 단계로 바로 `resolve_extracted_nodes()`와 `resolve_extracted_edges()`를 호출함
  - 즉 dedupe와 contradiction이 ingestion 외부의 배치 정리 작업이 아님
- `tests/utils/maintenance/test_edge_operations.py`
  - `test_resolve_extracted_edge_uses_integer_indices_for_duplicates`는 LLM 판정 결과를 기존 edge 후보와 연결해 canonical edge를 재사용하는 흐름을 검증함
  - `test_resolve_extracted_edges_keeps_unknown_names`는 custom edge type 제약이 있어도 추출 edge를 ingestion 과정에서 안전하게 해석하는 흐름을 보여 줌
- `tests/utils/maintenance/test_bulk_utils.py`
  - bulk 경로에서도 node dedupe와 edge dedupe를 생략하지 않고 별도 단계로 유지함
  - 이는 Graphiti가 추출보다 정규화를 더 우선순위 높게 둔다는 신호임

### 제품 적용 포인트

- LLM 기반 KB에서는 extraction 품질만 높이는 것보다 canonicalization 계층을 두는 편이 더 중요함
- 저장 전에 정규화하지 않으면 검색 품질 저하가 장기적으로 누적됨
- 같은 의미의 fact를 재사용 가능한 canonical edge로 모아야 provenance와 temporal history도 안정적으로 축적됨
- contradiction 처리는 검색 단계에서 나중에 해결하는 것보다 ingestion 단계에서 current state를 정리하는 편이 운영상 유리함
- deterministic heuristic와 LLM 판정을 섞으면 비용과 정확도를 동시에 관리하기 좋음

### 해석과 시사점

- Graphiti는 추출 파이프라인의 마지막 결과를 완성된 사실이 아니라 "사실 후보"로 봄
- 이 후보를 그대로 KB에 넣으면 메모리는 커지지만 검색 품질과 일관성은 떨어짐
- 저장 전 canonicalization과 conflict resolution을 거치면 ingest 비용은 늘어나도 장기 메모리로서의 안정성은 높아짐
- 그래서 Graphiti의 강점은 추출 자체보다 추출 후 정규화 계층에 더 많이 들어 있음

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- invalidation 품질은 LLM 판단과 시간 정보 품질에 의존함
  - contradiction 후보를 고르는 과정에 검색과 LLM이 모두 들어감
  - 잘못된 reference time이나 약한 추출은 잘못된 invalidation으로 이어질 수 있음
- bulk 경로는 feature parity가 아님
  - `add_episode_bulk()`는 현재 edge invalidation과 date extraction을 생략함
  - 따라서 realtime memory와 backfill import의 의미가 다름
- ingestion 비용이 큼
  - dedupe와 contradiction을 저장 전에 수행하므로 단순 문서 적재보다 latency와 모델 비용이 큼
- 구조 복잡도가 높음
  - current fact, expired fact, duplicate reuse, contradiction 처리, batch canonicalization이 서로 얽혀 있어 학습 비용이 큼
- provider와 검색 설정의 영향이 큼
  - invalidation 후보 탐색과 검색 품질은 backend, embedder, reranker 설정에 따라 체감 성능 차이가 날 수 있음

### 제품 해석

- Graphiti는 빠른 저장보다 안전한 갱신을 우선하는 설계임
- 이 선택은 실시간 agent memory에는 강하지만, 모든 데이터 적재 상황에서 같은 의미를 보장하지는 않음
- 따라서 벤치마킹할 때는 단순 ingest TPS보다 현재 사실 유지 정확도, 과거 사실 보존력, bulk 경로 제한의 투명성을 함께 봐야 함

## 적용 인사이트

Graphiti의 섹션 2에서 배울 핵심은 세 가지다. 첫째, 시간에 따라 바뀌는 지식은 삭제보다 invalidation으로 관리해야 한다. 둘째, 실시간 갱신 경로와 벌크 적재 경로는 목적이 다르면 분리하는 편이 낫다. 셋째, LLM이 뽑은 결과를 그대로 저장하지 말고 dedupe와 contradiction 계층을 ingestion 안에 넣어야 장기 메모리 품질이 유지된다.

- temporal KB는 overwrite보다 상태 전이 기록이 중요함
- bulk 최적화는 precision 경로와 분리해야 의미가 명확해짐
- 추출 품질보다 canonicalization 품질이 장기 검색 품질을 더 크게 좌우함
