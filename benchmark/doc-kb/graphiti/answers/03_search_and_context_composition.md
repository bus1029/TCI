# 검색과 문맥 구성 분석

## 개요

Graphiti의 검색 계층은 "가장 비슷한 문장 몇 개를 찾는가"보다 "에이전트가 바로 쓸 수 있는 그래프 문맥을 어떻게 조립하는가"에 맞춰 설계돼 있다. 그래서 BM25, 벡터 검색, BFS를 각각 독립 검색기로 두고 조합하며, `search()`와 `search_()`를 분리해 단순 fact 회수와 구조화된 graph context 회수를 다른 인터페이스로 제공한다. 여기에 `SearchConfig`와 recipe를 얹어 reranker 전략을 상황에 맞게 갈아끼울 수 있게 했다.

이 문서에서 먼저 잡아야 할 전제는 아래와 같다.

- Graphiti의 검색 대상은 edge, node, episode, community 네 레이어로 나뉨
- lexical recall, semantic recall, graph expansion을 별도 단계로 조합함
- 기본 `search()`는 빠른 fact retrieval용 인터페이스
- `search_()`는 설정 가능한 고급 graph retrieval 인터페이스
- reranker는 검색 품질뿐 아니라 비용, 다양성, 그래프 locality를 함께 조절하는 장치
- provenance는 검색 결과를 raw episode로 되돌리는 핵심 연결 고리

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| `search()` | 기본 edge 중심 검색 API |
| `search_()` | `SearchResults`를 반환하는 고급 검색 API |
| BM25 | 키워드 기반 full-text 검색 |
| cosine similarity | 임베딩 기반 벡터 검색 |
| BFS | 그래프 이웃 탐색 기반 확장 검색 |
| `SearchConfig` | 레이어별 검색 방법과 reranker를 조합하는 설정 객체 |
| provenance | 검색된 fact를 어떤 `Episode`가 만들었는지 되짚는 연결 |

# 시스템 핵심 동작 방식 및 사용 기술

## 1. Hybrid search와 graph traversal을 결합해 그래프 문맥을 조립하는 구조

### 채택 기술 구조

- 검색 레이어 분리
  - `search()` 내부 구현은 edge, node, episode, community를 각각 독립적으로 검색함
  - 결과도 `SearchResults` 안에서 레이어별로 나뉘어 관리됨
- 검색 방법 분리
  - BM25는 용어 일치와 명시적 fact 문구 회수에 강함
  - cosine similarity는 표현이 달라도 의미적으로 가까운 후보를 끌어옴
  - BFS는 이미 찾은 노드 주변으로 그래프 이웃을 확장해 관계 문맥을 보강함
- 조합 방식
  - `edge_search()`와 `node_search()`는 설정된 검색 방법만 task로 만들고 병렬 실행함
  - BFS origin이 명시되지 않으면 먼저 BM25와 similarity 결과를 얻고, 그 결과의 UUID를 origin으로 다시 BFS를 돌림
  - 즉 traversal은 독립 검색기가 아니라 1차 회수 결과를 문맥으로 확장하는 2차 단계로도 작동함
- 문맥 조립 방식
  - edge 검색은 fact를 직접 회수함
  - node 검색은 관련 개체를 회수함
  - episode 검색은 raw source context를 회수함
  - community 검색은 요약된 topic-level context를 회수함
  - 이 네 결과를 함께 쓰면 Top-K 문장 회수보다 더 넓은 그래프 문맥을 구성할 수 있음

### 코드 근거 예시

- `graphiti_core/search/search.py`
  - `search()`가 edge, node, episode, community 검색을 병렬 실행함
  - `edge_search()`와 `node_search()`가 BM25, cosine similarity, BFS를 설정 기반으로 조합함
  - BFS origin이 없을 때 1차 검색 결과를 기반으로 BFS를 추가 실행함
- `graphiti_core/search/search_utils.py`
  - `edge_fulltext_search()`, `edge_similarity_search()`, `edge_bfs_search()`를 별도 함수로 분리함
  - `node_fulltext_search()`, `node_similarity_search()`, `node_bfs_search()`도 같은 패턴을 따름
  - `episode_fulltext_search()`와 `community_fulltext_search()`가 raw context와 요약 context를 별도 레이어로 유지함
- `README.md`
  - Graphiti의 retrieval을 semantic, keyword, graph traversal의 hybrid retrieval로 설명함
  - 단순 RAG가 아니라 관계와 시간까지 질의하는 구조라는 제품 정체성을 강조함
- `examples/quickstart/README.md`
  - edge search와 graph-aware reranking을 별도 기능으로 설명함
  - node search recipe를 별도 단계로 보여 주며 검색 전략 분리를 예제로 드러냄
- `tests/test_graphiti_mock.py`
  - `test_edge_fulltext_search`, `test_edge_similarity_search`, `test_edge_bfs_search`
  - `test_node_fulltext_search`, `test_node_similarity_search`, `test_node_bfs_search`
  - 각 검색기가 분리된 동작 단위로 검증됨

### 제품 적용 포인트

- 에이전트 메모리 검색은 lexical recall, semantic recall, graph expansion을 분리하는 편이 튜닝이 쉬움
- traversal은 검색기라기보다 "이미 찾은 후보를 문맥으로 확장하는 단계"로 두는 편이 실무적임
- fact, node, episode, community를 한 번에 다루면 검색 결과를 여러 해상도로 조립할 수 있음
- 단순 Top-K 청크 검색보다 그래프 이웃 확장이 들어가면 후속 추론과 답변 생성이 안정적임

### 해석과 시사점

- Graphiti의 hybrid search는 여러 검색기의 점수를 섞는 것에 그치지 않고, 벡터와 키워드로 찾은 후보를 그래프 탐색의 출발점으로 쓰는 구조임
- 이 설계 덕분에 검색 결과는 "정답처럼 보이는 문장"보다 "정답을 둘러싼 구조"에 가까워짐
- 결국 Graphiti의 retrieval 품질은 recall과 graph context assembly를 함께 설계했다는 점에서 문서형 RAG와 다름

## 2. `search()`와 `search_()`를 분리한 이유

### 채택 기술 구조

- 기본 인터페이스와 고급 인터페이스 분리
  - `Graphiti.search()`는 `list[EntityEdge]`를 반환하는 기본 검색 API임
  - `Graphiti.search_()`는 `SearchResults`를 반환하는 고급 검색 API임
- `search()`의 역할
  - 기본 out-of-the-box fact retrieval을 담당함
  - `center_node_uuid`가 없으면 `EDGE_HYBRID_SEARCH_RRF`를 사용함
  - `center_node_uuid`가 있으면 `EDGE_HYBRID_SEARCH_NODE_DISTANCE`로 바꿔 graph-aware reranking을 수행함
  - 반환 타입도 fact list로 좁혀서 바로 응답 생성이나 간단한 memory lookup에 쓰기 좋게 함
- `search_()`의 역할
  - 기본값으로 `COMBINED_HYBRID_SEARCH_CROSS_ENCODER`를 사용함
  - `SearchConfig`, `SearchFilters`, `group_ids`, `center_node_uuid`, `bfs_origin_node_uuids`를 모두 받을 수 있음
  - 결과도 edges, nodes, episodes, communities를 함께 돌려줌
  - 즉 retrieval API이면서 동시에 graph context assembly API 역할을 함
- 소비자 분리
  - FastAPI 서버의 `/search`와 `/get-memory`는 `search()`를 사용해 fact 응답만 돌려줌
  - MCP의 `search_memory_facts`도 `search()`를 사용해 단순 fact retrieval을 제공함
  - MCP의 `search_nodes`는 `search_()`와 `NODE_HYBRID_SEARCH_RRF`를 사용해 node 중심 결과를 반환함
  - 실제 통합 계층도 두 인터페이스를 용도별로 다르게 소비함

### 코드 근거 예시

- `graphiti_core/graphiti.py`
  - `search()` docstring에서 기본 out-of-the-box search라고 설명함
  - 같은 docstring에서 더 강한 결과가 필요하면 `graphiti.search_()`를 쓰라고 명시함
  - `search_()`는 graph object를 반환하는 advanced search라고 설명함
  - `_search()`는 deprecated alias로 남아 있어 인터페이스 전환 과정도 드러남
- `graphiti_core/search/search_config.py`
  - `SearchResults`가 edges, nodes, episodes, communities와 각 reranker score를 함께 가짐
  - 고급 인터페이스가 단순 list 반환보다 더 넓은 검색 상태를 노출함
- `server/graph_service/routers/retrieve.py`
  - `/search`와 `/get-memory`가 `graphiti.search()`만 호출함
  - 서버 레벨에서는 fact 응답이 가장 기본 단위라는 점이 드러남
- `mcp_server/src/graphiti_mcp_server.py`
  - `search_memory_facts()`는 `client.search()`를 사용함
  - `search_nodes()`는 `client.search_()`와 `NODE_HYBRID_SEARCH_RRF`를 사용함
  - agent tool 계층에서도 simple retrieval과 structured retrieval이 분리됨

### 제품 적용 포인트

- 기본 API는 좁고 단순하게 두고, 고급 retrieval은 별도 인터페이스로 여는 편이 통합 난도를 낮춤
- agent integration에서는 "바로 답변에 넣을 fact"와 "추론용 graph context"의 소비 패턴이 다름
- 반환 타입 분리는 기능 분리이면서 비용 통제 장치이기도 함
- 간단한 채널에서는 `search()`만 공개하고, 고급 도구나 내부 파이프라인에서만 `search_()`를 쓰는 운영이 가능함

### 해석과 시사점

- `search()`와 `search_()`의 분리는 단순 API 취향 차이가 아니라 소비자 계층을 나누는 제품 전략임
- Graphiti는 모든 사용자를 복잡한 graph retrieval 인터페이스로 밀어 넣지 않고, 기본값과 확장 경로를 분리해 둠
- 이 구조 덕분에 같은 엔진으로 fact lookup과 graph-aware reasoning support를 동시에 제공할 수 있음

## 3. RRF, MMR, cross-encoder, node-distance 같은 reranker를 recipe로 제공하는 이유

### 채택 기술 구조

- 설정 객체 기반 검색 전략
  - `SearchConfig`는 edge, node, episode, community별 config를 따로 가짐
  - 각 config는 `search_methods`, `reranker`, `sim_min_score`, `mmr_lambda`, `bfs_max_depth`를 가짐
  - 검색 품질 제어를 하드코딩이 아니라 데이터 구조로 다룸
- recipe 상수 제공
  - `search_config_recipes.py`는 `COMBINED_HYBRID_SEARCH_RRF`, `COMBINED_HYBRID_SEARCH_MMR`, `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` 같은 조합을 상수로 제공함
  - edge, node, community 전용 recipe도 따로 제공함
  - 소비자는 내부 구현을 몰라도 search strategy를 바로 선택할 수 있음
- reranker별 역할
  - RRF는 여러 검색기의 순위를 싸게 융합하는 기본값 역할
  - MMR은 relevance와 diversity를 함께 맞춰 중복 후보를 줄이는 역할
  - cross-encoder는 late reranking으로 precision을 높이는 대신 비용과 latency가 큼
  - node-distance는 특정 center node 기준의 graph locality를 강조함
  - episode_mentions는 여러 episode에서 자주 언급된 node를 위로 올려 prominence를 반영함
- 레이어별 전략 차등 적용
  - edge와 node는 BFS, node-distance, episode_mentions 같은 graph-aware 옵션이 있음
  - episode는 BM25와 cross-encoder 중심으로 raw context reranking을 수행함
  - community는 BM25, similarity, MMR, cross-encoder를 사용해 topic-level retrieval을 조정함
  - 즉 recipe는 "검색 전체"가 아니라 각 레이어의 목적에 맞는 조합을 제공함

### 코드 근거 예시

- `graphiti_core/search/search_config.py`
  - 검색 방법 enum과 reranker enum을 레이어별로 분리해 둠
  - `SearchConfig`가 레이어별 조합을 담는 핵심 타입임
- `graphiti_core/search/search_config_recipes.py`
  - 자주 쓰는 조합을 recipe 상수로 정의함
  - combined recipe와 edge, node, community 전용 recipe를 모두 제공함
- `graphiti_core/search/search.py`
  - reranker 종류에 따라 `rrf()`, `maximal_marginal_relevance()`, `cross_encoder.rank()`, `node_distance_reranker()`, `episode_mentions_reranker()`를 분기 호출함
  - 레이어마다 허용된 reranker와 검색 방법 조합이 다름
- `graphiti_core/search/search_utils.py`
  - `rrf()`가 다중 ranking을 점수 융합함
  - `maximal_marginal_relevance()`가 relevance와 diversity를 함께 계산함
  - `node_distance_reranker()`가 center node와의 거리로 재정렬함
  - `episode_mentions_reranker()`가 mention count 기반 재정렬을 수행함
- `tests/test_graphiti_mock.py`
  - `test_node_distance_reranker()`가 그래프 거리 기반 정렬을 검증함
  - `test_episode_mentions_reranker()`가 mention 빈도 기반 정렬을 검증함
- `examples/quickstart/README.md`
  - predefined search recipe를 사용한 node search를 예시로 보여 줌

### 제품 적용 포인트

- 검색 품질 제어는 코드 수정이 아니라 config 교체로 가능한 구조가 운영에 유리함
- 기본값은 RRF처럼 싸고 안정적인 융합기로 두고, 고정밀이 필요할 때만 cross-encoder를 켜는 전략이 실무적임
- 중심 엔터티가 분명한 질의에서는 node-distance가 좋고, 중복이 많은 결과셋에는 MMR이 효과적임
- recipe를 상수로 제공하면 제품 팀, 인프라 팀, 응용 에이전트가 같은 검색 전략을 재사용하기 쉬움

### 해석과 시사점

- Graphiti의 recipe 구조는 "검색 알고리즘을 라이브러리 내부에 숨기는 방식"보다 "운영 가능한 검색 정책으로 노출하는 방식"에 가깝다
- 이 설계 덕분에 사용자는 검색 품질을 모델 교체처럼 취급하지 않고, 비용과 응답 품질 사이의 선택 문제로 다룰 수 있음
- 결국 recipe는 단순 편의 기능이 아니라 multi-domain, multi-budget 환경을 위한 운영 인터페이스다

## 4. provenance가 붙은 fact를 Episode로 역추적할 수 있게 하는 이유

### 채택 기술 구조

- fact에서 episode로 가는 연결
  - `EntityEdge`는 `episodes` 필드에 자신을 만든 Episode UUID 목록을 저장함
  - fact를 찾은 뒤 바로 source episode 집합을 따라갈 수 있음
- episode에서 fact로 가는 연결
  - `EpisodicNode`는 `entity_edges` 필드에 자신이 만든 fact UUID를 저장함
  - `get_nodes_and_edges_by_episode()`는 episode UUID를 받아 관련 edges와 nodes를 다시 조립함
- episode에서 entity로 가는 연결
  - `MENTIONS` 관계를 담당하는 `EpisodicEdge`가 Episode와 Entity를 직접 연결함
  - `get_mentioned_nodes()`는 episode 집합으로부터 언급된 entity를 복원함
- raw context 검색 경로
  - `episode_fulltext_search()`는 raw episode content를 직접 검색함
  - `search_()`는 episode 레이어를 결과에 함께 포함할 수 있음
  - 즉 fact retrieval과 source retrieval이 한 시스템 안에 묶여 있음
- 운영 경로
  - `remove_episode()`는 episode가 만든 edge와 그 episode에서만 언급된 node만 삭제 대상으로 좁힘
  - provenance가 있어야 selective delete와 audit-friendly maintenance가 가능함

### 코드 근거 예시

- `graphiti_core/edges.py`
  - `EntityEdge`가 `episodes`를 저장함
  - `EpisodicEdge`가 `MENTIONS` 관계를 담당함
- `graphiti_core/nodes.py`
  - `EpisodicNode`가 `entity_edges`를 저장함
- `graphiti_core/utils/maintenance/edge_operations.py`
  - 새 `EntityEdge`를 만들 때 `episodes=[episode.uuid]`를 붙임
  - `build_episodic_edges()`가 Episode와 Entity를 직접 연결함
- `graphiti_core/graphiti.py`
  - `_process_episode_data()`가 episode의 `entity_edges`를 채움
  - `get_nodes_and_edges_by_episode()`가 episode 기준 서브그래프 복원을 제공함
  - `remove_episode()`가 provenance를 이용해 삭제 범위를 좁힘
- `graphiti_core/search/search_utils.py`
  - `episode_fulltext_search()`가 raw input 검색 경로를 유지함
  - `get_mentioned_nodes()`가 episode에서 entity 복원을 담당함
- `README.md`
  - episodes와 provenance를 Graphiti의 핵심 차별점으로 설명함

### 제품 적용 포인트

- 에이전트 메모리에서는 "이 fact가 맞는가"만큼 "이 fact가 어디서 나왔는가"가 중요함
- provenance가 있으면 검색 결과를 raw source 상황으로 되돌려 사람 검토와 에이전트 self-check가 쉬워짐
- 메모리 삭제, 데이터 정리, 감사 로그 같은 운영 작업도 episode 기준 역추적이 있어야 안전함
- 잘못된 fact가 들어왔을 때 추출 오류인지 입력 오류인지 분리해서 디버깅할 수 있음

### 해석과 시사점

- provenance 역추적은 검색 품질 보조 기능이 아니라 agent memory의 신뢰성 장치다
- Graphiti는 fact를 뽑아 놓고 끝내지 않고, 그 fact를 다시 raw episode로 되돌릴 수 있게 설계돼 있음
- 이 구조 덕분에 검색 결과는 답변 재료이면서 동시에 검증 가능한 evidence가 됨

## 5. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 검색 파이프라인 복잡도 증가
  - BM25, similarity, BFS, reranker, 레이어별 결과를 함께 다루므로 단순 vector search보다 설정면이 넓음
- cross-encoder 비용
  - `search_()` 기본 recipe가 cross-encoder 기반이라 품질은 좋지만 latency와 모델 비용이 커질 수 있음
- traversal 노이즈 가능성
  - BFS는 문맥 확장에 유리하지만 origin 품질이 낮으면 주변 노이즈도 함께 끌어올 수 있음
- recipe 튜닝 필요
  - 도메인마다 RRF, MMR, node-distance, cross-encoder의 효율이 다르므로 기본값만으로 최적이 되지 않을 수 있음
- provenance 유지 비용
  - `episodes`, `entity_edges`, `MENTIONS` 연결을 모두 유지하므로 저장 모델과 유지보수 경로가 단순 fact store보다 복잡함
- provider별 검색 차이
  - search interface는 추상화돼 있지만 full-text나 vector 처리 방식은 provider 구현에 따라 차이가 남음

### 제품 해석

- Graphiti의 검색 계층은 단순 검색기보다 "문맥 조립기"에 가깝기 때문에 설정과 운영 복잡도가 함께 따라온다
- 그 대신 에이전트 메모리, provenance 감사, graph-aware reasoning 같은 요구사항에는 이 복잡도가 실제 가치로 전환된다
- 따라서 이 구조를 평가할 때는 Top-K 정확도만이 아니라 문맥 복원력, evidence traceability, 전략 교체 용이성까지 같이 봐야 한다

## 적용 인사이트

Graphiti에서 벤치마킹할 핵심은 검색기를 하나 고르는 것이 아니라, 검색을 여러 단계의 문맥 조립 문제로 보는 관점이다. 구체적으로는 lexical recall, semantic recall, graph traversal, reranking, provenance 복원을 서로 분리해 두고, 인터페이스는 `search()`와 `search_()`로 나눠 소비자별 복잡도를 조절하는 구조를 한 세트로 봐야 한다.

- hybrid retrieval은 검색기 나열이 아니라 그래프 문맥 조립 파이프라인으로 설계해야 함
- 기본 API와 고급 API를 분리해야 응용 계층별 복잡도와 비용을 제어할 수 있음
- reranker는 알고리즘이 아니라 운영 정책으로 노출하는 편이 재사용성과 튜닝성이 높음
- provenance 역추적 경로를 검색 설계 안에 넣어야 에이전트 메모리의 신뢰성과 감사 가능성을 확보할 수 있음
- Graphiti의 검색 강점은 fact retrieval보다 graph context assembly에 더 가까운 문제 정의에서 나옴
