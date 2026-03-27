# Temporal Context Graph 표현 방식 분석

## 개요

Graphiti의 핵심 선택은 "원문을 얼마나 잘 쪼개서 다시 찾을 것인가"보다 "에이전트가 재사용할 수 있는 사실을 어떤 단위로 누적하고 갱신할 것인가"에 가깝다. 이 프로젝트는 문서 청크를 최종 저장 단위로 두지 않고, 입력 원문을 `Episode`로 보존한 뒤 그 안에서 `EntityNode`와 `EntityEdge`를 추출해 시간 축을 가진 그래프로 유지하는 구조를 택했다. 여기에 더해 `CommunityNode`와 `SagaNode` 같은 상위 계층을 두어 주제 압축과 사건 흐름 보존까지 지원한다.

처음 보는 사람이 이 문서에서 먼저 이해해야 할 전제는 아래와 같다.

- 원문 입력 단위는 `Episode`
- 검색과 추론의 핵심 단위는 `EntityNode`와 `EntityEdge`
- 에피소드는 검색 결과의 최종 형태라기보다 provenance와 문맥 복원의 기준점
- 그래프의 기본 관심사는 문장 조각이 아니라 "누가 누구와 어떤 관계를 가지는가"와 "그 사실이 언제 유효한가"
- `CommunityNode`는 topic-level context를 압축하는 계층
- `SagaNode`는 sequence-level context를 보존하는 계층

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| `Episode` | 대화, 문서, JSON 같은 원문 입력 단위 |
| `EntityNode` | 사람, 조직, 개념, 장소 같은 개체 노드 |
| `EntityEdge` | 개체 간 사실 또는 관계를 표현하는 엣지 |
| `EpisodicEdge` | 어떤 Episode가 어떤 Entity를 언급했는지 나타내는 연결 |
| `valid_at` / `invalid_at` | 사실이 언제부터 참이었고 언제 더 이상 참이 아니게 되었는지 나타내는 시간 정보 |
| `CommunityNode` | 연결된 엔티티 묶음을 상위 주제로 요약한 노드 |
| `SagaNode` | 연속된 Episode를 하나의 흐름으로 묶는 노드 |

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 원문은 Episode로 남기고, KB의 재사용 단위는 Entity와 Fact로 바꾸는 구조

### 채택 기술 구조

- 기본 원칙
  - `Graphiti.add_episode()`는 입력 텍스트를 그대로 저장하는 것으로 끝나지 않음
  - 같은 호출 안에서 엔티티 추출, 노드 dedupe, 관계 추출, 엣지 dedupe, contradiction 처리, 임베딩 생성, 그래프 저장까지 수행함
  - 즉 저장의 목적이 문서 보관이 아니라 사실 그래프 구축에 맞춰져 있음
- 입력 모델
  - `EpisodicNode`는 `content`, `source`, `source_description`, `valid_at`, `entity_edges`를 가짐
  - `EntityNode`는 `name`, `labels`, `summary`, `attributes`, `name_embedding`을 가짐
  - `EntityEdge`는 `fact`, `episodes`, `valid_at`, `invalid_at`, `expired_at`, `fact_embedding`을 가짐
  - 이 모델링 자체가 청크 저장소보다 개체와 사실을 중심에 둔 설계임
- 추출 파이프라인
  - `extract_nodes()`는 Episode 타입에 따라 `message`, `text`, `json` 전용 프롬프트를 사용해 엔티티를 뽑음
  - `extract_edges()`는 현재 Episode, 추출된 노드, 이전 Episode, edge type signature를 함께 넣어 사실을 뽑음
  - 추출 결과는 바로 저장되지 않고 dedupe와 invalidation을 거쳐 그래프 품질이 보정됨
- 저장 파이프라인
  - Episode는 원문 단위로 저장됨
  - 엔티티는 중복 정리 후 canonical node로 수렴됨
  - 사실은 자연어 fact 문장과 시간 정보가 붙은 `EntityEdge`로 저장됨
  - Episode와 Entity는 `MENTIONS`로 연결되고, Episode는 자신이 만든 entity edge UUID도 보관함
- 검색 모델
  - 기본 `search()`는 fact 중심의 `EntityEdge` 목록을 반환함
  - 고급 `search_()`는 `edges`, `nodes`, `episodes`, `communities`를 함께 반환함
  - 검색의 중심축은 청크 회수가 아니라 구조화된 사실과 그래프 문맥 조합임

### 코드 근거 예시

- `README.md`
  - Graphiti를 temporal context graph 엔진으로 정의함
  - context graph의 구성 요소를 `Entities`, `Facts / Relationships`, `Episodes`, `Custom Types`로 설명함
  - RAG 대비 차별점으로 temporal fact management와 provenance를 전면에 둠
- `graphiti_core/graphiti.py`
  - `add_episode()`가 엔티티 추출, 엣지 추출, dedupe, invalidation, 저장을 하나의 ingestion 파이프라인으로 묶음
  - 기본 `search()`는 edge 중심으로 반환하고, `search_()`는 그래프 객체를 함께 반환함
- `graphiti_core/nodes.py`
  - `EpisodicNode`, `EntityNode`, `CommunityNode`, `SagaNode`를 별도 모델로 둠
  - 특히 `EpisodicNode`와 `EntityNode`가 서로 다른 역할을 명확히 가짐
- `graphiti_core/edges.py`
  - `EntityEdge`에 `fact`, `episodes`, `valid_at`, `invalid_at`, `expired_at`가 들어감
  - 단순 링크가 아니라 시간성과 provenance를 가진 사실 모델임
- `graphiti_core/utils/maintenance/node_operations.py`
  - Episode 원문과 이전 Episode를 넣어 엔티티를 추출함
  - 추출된 엔티티를 곧바로 저장하지 않고 검색과 LLM을 섞어 dedupe함
- `graphiti_core/utils/maintenance/edge_operations.py`
  - Episode 원문에서 fact를 뽑아 `EntityEdge`로 변환함
  - 각 fact에 `episodes=[episode.uuid]`를 붙여 provenance를 기록함
- `graphiti_core/search/search.py`
  - edge, node, episode, community 레이어를 동시에 검색할 수 있게 설계됨
  - BM25, cosine similarity, BFS를 결합해 청크 검색보다 그래프 문맥 반환에 초점을 둠
- `examples/quickstart/README.md`
  - 예제 설명도 "에피소드를 그래프에 추가하고, 관계와 fact를 검색한다"는 흐름으로 되어 있음
  - 출력 이해 섹션 역시 edge와 node 구조를 중심으로 설명함

### 제품 적용 포인트

- 에이전트 메모리에서는 긴 원문 조각보다 구조화된 사실이 재사용성이 높음
- 사용자 상태, 조직 정보, 정책 변화처럼 시간이 중요한 지식은 `fact + validity window` 모델이 더 적합함
- 원문은 Episode로 보존하고 검색은 fact 중심으로 수행하면 설명 가능성과 검색 효율을 함께 가져가기 좋음
- 추출 직후 저장이 아니라 dedupe와 contradiction 처리를 파이프라인 안에 넣어야 장기 메모리 품질이 유지됨
- 문서형 RAG와 달리 그래프 구조를 중심에 두면 후속 탐색, 요약, cluster화 같은 확장도 쉬워짐

### 해석과 시사점

- Graphiti가 문서 청크 저장소를 기본 단위로 택하지 않은 이유는 retrieval의 종착점을 "문장 회수"가 아니라 "상태와 관계 회수"로 보기 때문임
- 이 구조 덕분에 에이전트는 단순히 비슷한 문단을 찾는 대신, 현재 유효한 사실과 관련 개체를 함께 회수할 수 있음
- 반대로 이 선택은 ingestion이 더 무겁고, LLM 추출 품질과 dedupe 품질에 시스템 성능이 크게 좌우된다는 트레이드오프도 만듦
- 그래도 장기 메모리, temporal KB, 에이전트 컨텍스트 조립이라는 목적에는 청크 저장소보다 `Episode -> Entity -> Fact`가 더 직접적인 구조다

## 2. Episode를 provenance 기준점으로 삼는 구조

### 채택 기술 구조

- `EpisodicNode`는 원문 내용과 시간 정보를 그대로 보관함
- `EntityEdge`는 자신을 참조한 Episode UUID 목록을 가짐
- `EpisodicEdge`는 Episode와 Entity 사이의 `MENTIONS` 링크를 만듦
- Episode 자신도 `entity_edges` 필드에 파생 fact UUID를 들고 있음

즉 Graphiti의 provenance는 한 방향 링크 하나로 끝나지 않는다. Episode, Entity, Fact 사이에 상호 역추적 가능한 연결을 따로 남긴다.

- 원문 보존 방식
  - `EpisodicNode`는 `content`, `source_description`, `source`, `valid_at`를 저장함
  - `Graphiti`는 `store_raw_episode_content` 옵션이 켜져 있으면 원문을 그대로 보존함
  - 따라서 fact만 남는 시스템이 아니라 raw input을 다시 볼 수 있는 시스템임
- Episode -> Entity 연결
  - `build_episodic_edges()`는 Episode가 언급한 모든 엔티티에 대해 `MENTIONS` 엣지를 생성함
  - 이 연결 덕분에 특정 Episode가 어떤 개체를 등장시켰는지 바로 복원할 수 있음
- Episode -> Fact 연결
  - `extract_edges()`는 새 fact를 만들 때 `episodes=[episode.uuid]`를 넣어 출처를 기록함
  - `_process_episode_data()`는 `episode.entity_edges = [edge.uuid for edge in entity_edges]`로 Episode 쪽에도 fact UUID를 남김
  - 결과적으로 fact에서 Episode로, Episode에서 fact로 모두 이동 가능함
- provenance 기반 복원
  - `get_nodes_and_edges_by_episode()`는 episode UUID를 받아 해당 Episode가 만든 edge와 언급한 node를 다시 가져옴
  - `remove_episode()`는 Episode가 만든 edge와 그 Episode에서만 언급된 node만 골라 삭제함
  - provenance가 없으면 이런 정밀 삭제와 역추적은 어려움
- 검색과 디버깅 관점
  - `search_()`는 episode 레이어까지 함께 반환할 수 있음
  - `episode_fulltext_search()`는 Episode 원문을 직접 찾을 수 있게 해 줌
  - 검색된 fact를 원문 입력까지 되짚어 설명하는 경로가 열려 있음

### 코드 근거 예시

- `graphiti_core/nodes.py`
  - `EpisodicNode`가 `content`, `source_description`, `valid_at`, `entity_edges`를 저장함
  - Episode 자체가 provenance 객체로 설계되어 있음
- `graphiti_core/edges.py`
  - `EntityEdge.episodes`가 fact를 만든 Episode UUID 목록을 보관함
  - `EpisodicEdge`가 Episode와 Entity 사이의 `MENTIONS` 관계를 담당함
- `graphiti_core/utils/maintenance/edge_operations.py`
  - `extract_edges()`에서 생성한 모든 `EntityEdge`에 `episodes=[episode.uuid]`를 넣음
  - `build_episodic_edges()`가 Episode와 Entity를 직접 연결함
- `graphiti_core/graphiti.py`
  - `_process_episode_data()`가 Episode의 `entity_edges`를 채운 뒤 bulk save를 수행함
  - `get_nodes_and_edges_by_episode()`가 episode 기반 서브그래프 복원을 제공함
  - `remove_episode()`가 provenance를 이용해 삭제 대상을 좁힘
- `graphiti_core/search/search.py`
  - advanced search 결과에 `episodes`를 함께 포함할 수 있음
  - provenance를 검색 결과의 일급 객체로 취급함
- `graphiti_core/search/search_utils.py`
  - `episode_fulltext_search()`가 Episode 원문을 검색 가능한 대상으로 유지함

### 제품 적용 포인트

- 장기 메모리 시스템에서는 "정답처럼 보이는 fact"보다 "그 fact가 어디서 왔는가"가 더 중요할 때가 많음
- provenance가 있으면 잘못 추출된 사실을 원문 기준으로 검토하고 수정할 수 있음
- 삭제 요청, 개인정보 정리, 데이터 감사를 할 때 Episode 기준 역추적이 있어야 안전하게 처리할 수 있음
- 검색 결과를 원문 상황으로 되돌릴 수 있으면 에이전트 환각을 줄이고 사람 검토도 쉬워짐
- 운영 중 이상한 fact가 생겼을 때, LLM 추출 문제인지 입력 문제인지 파악하기 쉬워짐

### 해석과 시사점

- Episode를 provenance 기준점으로 두는 구조의 핵심 장점은 "그래프가 똑똑해지는 것"보다 "그래프가 설명 가능해지는 것"에 있음
- Graphiti는 fact만 쌓는 시스템이 아니라 fact를 다시 source context로 되돌릴 수 있는 시스템임
- 이 설계 덕분에 메모리 품질 문제를 추적할 때도 raw input, mentioned entities, derived facts를 같은 축에서 볼 수 있음
- 반대로 provenance 연결을 유지하려면 저장 비용과 모델 복잡도는 올라가지만, 에이전트 메모리와 감사 가능한 KB라는 목표에는 매우 합리적인 비용임

## 3. `CommunityNode`, `SagaNode` 같은 상위 계층을 두는 이유

### 채택 기술 구조

- `CommunityNode`
  - 연결이 촘촘한 엔티티 묶음을 상위 주제로 압축하는 요약 레이어
  - `get_community_clusters()`가 group별 엔티티 그래프 projection을 만들고 `label_propagation()`으로 cluster를 계산함
  - `build_community()`가 member summary를 pairwise로 축약하고 community name과 summary를 생성함
  - `HAS_MEMBER` 엣지로 member entity들과 연결되며 검색 레이어에서도 독립 객체로 다뤄짐
- `SagaNode`
  - 연속된 Episode를 하나의 사건 흐름으로 묶는 시퀀스 레이어
  - `_get_or_create_saga()`가 saga를 재사용하거나 생성함
  - `_process_episode_data()`와 `add_episode_bulk()`가 `HAS_EPISODE`, `NEXT_EPISODE`를 만들어 시간 순서를 보존함
  - `retrieve_episodes(..., saga=...)`로 특정 saga의 episode 흐름만 조회할 수 있음
- 구조적 의미
  - `CommunityNode`는 topic-level context를 제공함
  - `SagaNode`는 sequence-level context를 제공함
  - 두 계층 모두 기본 entity/fact 레이어를 대체하지 않고 그 위에 문맥 계층을 추가함
  - 따라서 Graphiti는 triplet 저장소보다 계층형 agent memory에 더 가까움

### 코드 근거 예시

- `graphiti_core/nodes.py`
  - `CommunityNode`와 `SagaNode`가 독립 노드 타입으로 정의됨
- `graphiti_core/edges.py`
  - `CommunityEdge`가 `HAS_MEMBER` 관계를 담당함
  - `HasEpisodeEdge`와 `NextEpisodeEdge`가 saga-episode 연결과 episode 간 순서를 표현함
- `graphiti_core/utils/maintenance/community_operations.py`
  - graph projection, label propagation, pairwise summary 축약, community name 생성까지 전체 흐름이 구현됨
- `graphiti_core/graphiti.py`
  - community build와 update 경로를 별도 메서드로 제공함
  - `_get_or_create_saga()`가 saga 재사용과 생성을 담당함
  - `_process_episode_data()`가 단건 ingestion에서 saga 연결을 수행함
  - `add_episode_bulk()`도 bulk 입력을 `valid_at` 순으로 정렬해 `NEXT_EPISODE` 체인을 만듦
- `graphiti_core/utils/maintenance/graph_data_operations.py`
  - `retrieve_episodes()`가 `saga` 필터를 지원함
- `graphiti_core/search/search.py`
  - advanced search가 `communities`를 별도 결과 레이어로 반환함
- `mcp_server/src/services/queue_service.py`
  - 같은 `group_id`의 Episode를 순차 처리해 시간 순서가 뒤틀리지 않게 함
- `mcp_server/tests/test_async_operations.py`
  - 같은 group 내 순차 처리와 다른 group 간 병렬 처리를 테스트함

### 제품 적용 포인트

- 에이전트가 거대한 그래프를 그대로 읽기보다 주제 요약을 먼저 읽는 편이 비용과 응답 품질에 유리함
- 군집 요약 노드는 디버깅, 시각화, 탐색 시작점으로도 유용함
- 개별 fact와 상위 topic node를 함께 두면 검색 결과를 여러 해상도로 조립할 수 있음
- 에이전트 메모리에서는 동일 사용자 대화, 작업 플로우, 조사 과정처럼 순서가 중요한 데이터가 많음
- saga 계층이 있으면 fact 단위 회수뿐 아니라 사건 흐름 회수도 가능해짐
- 운영 레벨의 직렬 처리와 데이터 모델의 `NEXT_EPISODE` 체인을 함께 설계해야 시간 축이 깨지지 않음
- 메모리 시스템이 커질수록 raw fact만으로는 탐색 비용이 커지므로 상위 압축 계층이 필요함

### 해석과 시사점

- `CommunityNode`는 triplet 저장소가 약한 주제 레벨 압축을 보완함
- `SagaNode`는 Graphiti가 단순 지식 그래프가 아니라 시간 순서가 있는 agent memory를 지향한다는 신호임
- 두 계층 덕분에 Graphiti는 개별 fact뿐 아니라 대화나 작업의 흐름 자체도 메모리 자산으로 다룰 수 있음
- `CommunityNode`와 `SagaNode`는 Graphiti를 단순 triplet 저장소보다 에이전트 메모리에 더 적합하게 만드는 핵심 장치임
- 이 설계 덕분에 Graphiti는 사실 저장, 주제 압축, 사건 흐름 보존을 한 그래프 안에서 다룸

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- ingestion 비용이 큼
  - `add_episode()`는 원문 저장만 하지 않고 엔티티 추출, dedupe, fact 추출, contradiction 판정, 임베딩 생성을 함께 수행함
  - 따라서 단순 문서 저장소보다 처리 지연과 모델 비용이 큼
- 추출 품질 의존성이 큼
  - fact 표현의 품질은 LLM 출력, dedupe 품질, edge invalidation 품질에 크게 좌우됨
  - 문서 청크 기반 검색보다 구조는 강하지만, 추출 실패 시 오류가 더 구조적으로 남을 수 있음
- bulk 경로와 single 경로의 의미가 완전히 같지 않음
  - `add_episode_bulk()`는 처리량 최적화 경로라 일부 정교한 temporal invalidation 단계를 생략함
  - temporal precision이 중요하면 단건 경로를 써야 함
- 상위 계층은 명시적 또는 배치성 비용이 있음
  - `CommunityNode`는 별도 build/update가 필요하고 LLM 요약 비용도 추가됨
  - `SagaNode`는 모델만 있다고 자동으로 품질이 보장되는 것이 아니라 순차 처리 운영까지 함께 맞춰야 함
- provider parity가 완전하지 않음
  - Neo4j가 기준 구현에 가깝고 FalkorDB, Kuzu, Neptune은 제약이나 특수 처리가 존재함
  - 따라서 같은 모델이라도 백엔드에 따라 동작 차이가 날 수 있음
- 그래프 구조가 단순 청크 검색보다 복잡함
  - provenance, community, saga까지 유지하면 디버깅과 운영 가치는 커지지만 데이터 모델과 저장 경로는 더 복잡해짐

### 제품 해석

- Graphiti는 문서형 RAG보다 더 강한 시간성, provenance, 구조적 검색을 주는 대신 ingestion 복잡도와 운영 복잡도를 함께 요구함
- 이 구조는 "정적인 문서를 빨리 찾는 제품"보다 "변화하는 사실을 오래 관리하는 메모리 제품"에 더 적합함
- 따라서 벤치마킹 포인트도 단순 검색 성능이 아니라 temporal invalidation, provenance 유지, 상위 문맥 계층 운영까지 포함해서 봐야 함

## 적용 인사이트

Graphiti에서 벤치마킹할 핵심은 단순히 fact를 많이 뽑는 것이 아니라, 원문 입력, 구조화된 사실, 상위 문맥 계층을 서로 연결된 형태로 유지하는 방식이다. 구체적으로는 `Episode -> Entity -> Fact`를 기본 단위로 두고, provenance를 Episode에 걸고, `CommunityNode`와 `SagaNode`로 주제와 흐름을 보강하는 설계를 한 세트로 봐야 한다.

- 원문 저장과 사실 저장을 분리하되 서로 역추적 가능하게 연결해야 함
- 청크 회수보다 개체와 관계 회수를 기본 검색 단위로 두는 편이 agent memory에 더 적합함
- provenance를 Episode 기준으로 남겨야 설명 가능성, 삭제 가능성, 감사 가능성을 확보할 수 있음
- topic-level, sequence-level 계층을 추가해야 대형 그래프에서도 에이전트가 쓸 만한 문맥을 안정적으로 조립할 수 있음
- 결국 Graphiti의 차별점은 문서 저장소가 아니라 temporal context graph를 중심으로 memory를 운영한다는 점에 있음
