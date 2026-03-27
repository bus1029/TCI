# 추상화와 백엔드 전략 분석

## 개요

Graphiti의 강점 중 하나는 temporal graph 자체보다도 그 graph를 만드는 실행 환경을 교체 가능하게 설계했다는 점에 있다. 이 프로젝트는 graph DB, LLM, embedder, cross-encoder를 각각 독립 주입 가능하게 두고, driver/provider 계층으로 DB 차이를 흡수하며, 장기적으로는 namespace + operations 구조로 모델과 DB I/O를 분리하려고 한다. 다만 이 추상화는 "모든 provider가 완전히 동일하게 동작한다"는 뜻이 아니라, 공통 코어를 유지한 채 provider별 제약을 드러내는 현실적 다중 백엔드 전략에 가깝다.

이 문서를 읽을 때 먼저 잡아야 할 전제는 아래와 같다.

- Graphiti의 코어 오케스트레이션은 `Graphiti` 클래스에 모여 있음
- 실행 구성 요소는 기본값이 있지만 대부분 외부에서 주입 가능함
- DB 차이는 `GraphDriver`와 provider별 operations 구현으로 흡수하려는 방향임
- 현재 구조는 완전한 최종형이 아니라 Phase 1 호환을 유지하는 과도기임
- namespace + operations 리팩터링의 목적은 코드 정리보다 장기 확장성과 backend 추가 비용 절감에 있음
- 공통 API가 있어도 provider parity는 완전하지 않음

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| `GraphDriver` | graph DB 연결과 query execution의 공통 진입점 |
| provider | Neo4j, FalkorDB, Kuzu, Neptune 같은 실제 백엔드 구현 |
| operations | object type별 DB I/O 인터페이스와 provider 구현 |
| namespace | `graphiti.nodes.*`, `graphiti.edges.*` 형태의 사용자 API 래퍼 |
| legacy interface | Phase 1 하위 호환을 위해 남겨 둔 기존 driver 인터페이스 |
| provider parity | 서로 다른 provider가 같은 기능과 보장을 얼마나 비슷하게 제공하는가 |

# 시스템 핵심 동작 방식 및 사용 기술

## 1. graph DB, LLM, embedder, cross-encoder를 모두 교체 가능한 계층으로 분리한 이유

### 채택 기술 구조

- 주입 가능한 코어 구성
  - `Graphiti.__init__()`는 `graph_driver`, `llm_client`, `embedder`, `cross_encoder`를 모두 외부에서 주입받을 수 있음
  - 아무 것도 주입하지 않으면 `Neo4jDriver`, `OpenAIClient`, `OpenAIEmbedder`, `OpenAIRerankerClient`를 기본값으로 사용함
  - 즉 기본 조합은 정해져 있지만 코어 파이프라인은 특정 provider에 고정되지 않음
- 오케스트레이션과 구현의 분리
  - `add_episode()`, `search_()` 같은 고수준 흐름은 `Graphiti`에 남음
  - 실제 모델 호출, 임베딩 생성, reranking, DB 저장은 각각 별도 클라이언트와 driver 계층이 담당함
  - 이 구조 덕분에 코어 유스케이스는 유지한 채 실행 구성 요소만 바꿀 수 있음
- 운영 환경 대응
  - README는 Neo4j, FalkorDB, Kuzu, Neptune을 지원 대상으로 설명함
  - LLM도 OpenAI 기본 외에 Azure OpenAI, Gemini, Anthropic, Groq 등을 옵션으로 둠
  - embedder와 reranker도 같은 방향으로 provider를 교체 가능하게 설계함
- 통합 레이어 확장
  - `mcp_server/src/services/factories.py`는 설정값에 따라 LLM, embedder, database 구성을 고르는 팩터리 계층을 둠
  - 코어 추상화가 있어야 MCP나 서비스 레이어에서 provider 조합을 설정 기반으로 바꿀 수 있음

### 코드 근거 예시

- `graphiti_core/graphiti.py`
  - `Graphiti.__init__()`가 `graph_driver`, `llm_client`, `embedder`, `cross_encoder`를 선택적으로 주입받음
  - 기본값이 비어 있을 때만 OpenAI + Neo4j 조합을 생성함
  - 초기화 후 `GraphitiClients`에 이 구성 요소들을 묶어 하위 오케스트레이션에 전달함
- `README.md`
  - 설치 문서가 DB backend별 extras와 여러 LLM provider 설정 예시를 따로 제공함
  - 제품 설명도 특정 모델보다 provider-agnostic한 파이프라인 유지에 초점을 둠
- `mcp_server/src/services/factories.py`
  - `LLMClientFactory`, `EmbedderFactory`, `DatabaseDriverFactory`가 provider 이름으로 구현체를 선택함
  - OpenAI 호환 endpoint, Azure, Gemini, Voyage 같은 옵션을 설정 레벨에서 바꿀 수 있게 함
- `docs/project/project-guide.md`
  - 프로젝트의 방향성을 LLM, embedder, graph DB를 추상화해 더 많은 환경에서 쓰게 하는 쪽으로 정리함

### 제품 적용 포인트

- 에이전트 메모리 인프라는 모델과 DB가 바뀌어도 핵심 파이프라인을 유지할 수 있어야 함
- LLM, embedder, reranker, DB를 한 계층에 묶어 두면 비용 최적화와 성능 실험이 어려워짐
- 코어 로직과 실행 provider를 분리하면 특정 벤더에 잠기지 않고 배포 환경에 맞춰 조합을 바꿀 수 있음
- 서비스 레이어에서 설정 기반 팩터리를 두려면 코어에 먼저 안정적인 추상화가 있어야 함
- 제품이 커질수록 "기능 로직"보다 "구성 변경 가능성"이 운영 유연성을 더 크게 좌우함

### 해석과 시사점

- Graphiti는 특정 모델이나 특정 DB 위에서만 의미가 있는 라이브러리가 아니라, temporal graph 파이프라인 자체를 제품 핵심으로 둠
- 기본값은 OpenAI + Neo4j지만, 그 기본값이 아키텍처의 고정점은 아님
- 이 구조 덕분에 비용, 성능, 규제, 배포 환경이 바뀌어도 코어 메모리 엔진을 재사용할 수 있음
- 추상화 비용은 늘어나지만, 장기 운영 관점에서는 lock-in 회피와 조합 실험 가능성이 더 큰 가치가 됨

## 2. driver/provider 추상화가 흡수하는 범위와 provider별 제약이 드러나는 지점

### 채택 기술 구조

- 공통 드라이버 계약
  - `GraphDriver`는 `execute_query()`, `session()`, `transaction()`, `build_indices_and_constraints()` 같은 공통 계약을 제공함
  - object type별 operations 접근자도 driver 위에 노출함
  - 따라서 상위 계층은 구체 DB 대신 driver 계약에 의존할 수 있음
- 차이를 흡수하는 범위
  - provider 이름은 `GraphProvider` enum으로 통일됨
  - 각 provider driver는 `entity_node_ops`, `entity_edge_ops`, `search_ops`, `graph_ops` 같은 속성으로 동일한 역할을 제공함
  - `NodeNamespace`, `EdgeNamespace`는 driver가 제공하는 ops만 연결하고, 없으면 `NotImplementedError`를 명시적으로 던짐
- 제약이 드러나는 범위
  - 트랜잭션 보장은 provider마다 다름
  - 인덱스 생성, fulltext search, edge 표현 방식, bulk query 지원 여부도 provider마다 다름
  - 즉 공통 API는 맞추되 저장소의 물리적 제약까지 완전히 숨기지는 않음
- 실제 제약 사례
  - Neo4j는 실제 transaction commit/rollback을 제공함
  - Kuzu는 edge fulltext index 제약 때문에 `RELATES_TO`를 중간 노드 `RelatesToNode_`로 표현함
  - Kuzu는 `database_`, `routing_` 같은 인자를 지원하지 않고 dynamic index creation도 no-op임
  - Neptune은 OpenSearch를 별도 AOSS client로 붙여 인덱싱과 검색을 보완함
  - 테스트 계층에서는 Neptune이 아예 비활성화돼 있어 지원 선언과 운영 성숙도가 다름을 보여 줌
- 코어와 통합 레이어의 차이
  - 코어 README는 Neo4j, FalkorDB, Kuzu, Neptune을 지원 대상으로 설명함
  - 하지만 MCP 서버 팩터리는 database provider로 Neo4j와 FalkorDB만 직접 다룸
  - 따라서 추상화가 있어도 모든 소비 채널이 동일한 provider matrix를 제공하는 것은 아님

### 코드 근거 예시

- `graphiti_core/driver/driver.py`
  - `GraphDriver`가 provider 공통 계약과 operations 접근자를 정의함
  - base `transaction()`은 no-op wrapper를 제공하고, driver가 실제 보장을 override 하게 설계함
  - legacy `search_interface`, `graph_operations_interface`도 Phase 1 호환용으로 남아 있음
- `graphiti_core/driver/neo4j_driver.py`
  - `transaction()`을 override해 실제 commit/rollback semantics를 제공함
  - range index와 fulltext index를 비동기로 생성하는 기준 구현 역할을 함
- `graphiti_core/driver/kuzu_driver.py`
  - edge fulltext 제약 때문에 `RelatesToNode_` 스키마를 별도로 둠
  - 지원하지 않는 query parameter를 제거하고, index/constraint 빌드는 사실상 no-op임
  - 즉 같은 엔티티/엣지 모델을 쓰더라도 내부 표현은 달라짐
- `graphiti_core/driver/neptune_driver.py`
  - Neptune backend에 더해 AOSS OpenSearch client를 함께 요구함
  - 단일 graph DB driver만으로 끝나지 않고 검색 인프라까지 결합된 경로임
- `graphiti_core/namespaces/nodes.py`
  - driver가 ops를 제공할 때만 namespace를 붙이고, 미구현 시 명시적 `NotImplementedError`를 던짐
- `graphiti_core/namespaces/edges.py`
  - edge 계층도 동일한 capability gating 방식을 사용함
- `tests/helpers_test.py`
  - Neptune은 `DISABLE_NEPTUNE=True`로 기본 비활성화돼 있음
  - 지원 목록과 테스트 성숙도가 같지 않다는 운영 신호임
- `mcp_server/src/services/factories.py`
  - database factory는 현재 Neo4j와 FalkorDB만 직접 처리함
  - 코어의 추상화 가능 범위와 MCP 레이어의 실제 지원 범위가 다름을 보여 줌

### 제품 적용 포인트

- 공통 API는 상위 계층을 단순화하지만, provider의 물리적 제약까지 완전히 숨길 필요는 없음
- 트랜잭션 보장, 검색 인덱스, bulk write 제약은 공통 인터페이스 밖에서 명시적으로 드러내는 편이 안전함
- "지원한다"와 "동일한 수준으로 성숙하다"는 다른 문제이므로 테스트와 운영 문서가 같이 있어야 함
- 소비 채널마다 지원 provider matrix가 달라질 수 있으므로 코어 추상화와 제품 통합 레이어를 구분해서 봐야 함
- 다중 백엔드 전략은 이상적인 완전 추상화보다 현실적 제약을 투명하게 관리하는 방식이 실무적임

### 해석과 시사점

- Graphiti의 driver/provider 추상화는 백엔드 차이를 충분히 줄여 주지만 완전히 제거하지는 않음
- 이 프로젝트는 "같은 API, 다른 보장"이라는 현실을 숨기지 않고 코드와 문서에 남겨 두는 편에 가깝다
- Neo4j는 기준 구현이고, Kuzu와 Neptune은 별도 보정이나 외부 인프라가 필요한 경향이 보임
- 따라서 Graphiti의 강점은 완전한 parity보다 공통 코어를 유지하면서도 provider별 제약을 관리 가능한 범위로 묶는 데 있음

## 3. namespace + operations 구조로 리팩터링하려는 이유

### 채택 기술 구조

- 현재 구조의 문제
  - 기존 모델 객체는 데이터 표현과 DB I/O를 함께 가지고 있음
  - 이 방식은 빠르게 시작하기는 좋지만 backend를 늘릴수록 모델 클래스가 무거워지고 테스트 분리가 어려워짐
- 목표 구조
  - spec은 data model을 pure data로 줄이고, DB I/O를 provider별 operations 구현으로 이동시키는 방향을 제시함
  - 사용자 API는 `graphiti.nodes.entity.save(node)` 같은 namespace로 정리하려고 함
  - namespace는 얇은 orchestration만 맡고, embedding generation 같은 cross-cutting concern을 처리함
- 리팩터링의 장점
  - object type별로 flat operations를 두면 provider 추가 시 구현 범위가 명확해짐
  - QueryExecutor와 Transaction ABC를 사이에 두어 import cycle 없이 driver를 확장할 수 있음
  - 모델은 데이터와 검증에 집중하고, persistence는 driver별 ops에 집중할 수 있음
- 호환 전략
  - spec은 Phase 1 비파괴 전환을 명시함
  - `GraphDriver`에도 legacy interfaces가 남아 있고, 기존 모델 메서드도 즉시 제거하지 않음
  - 즉 리팩터링 목표는 급격한 rewrite가 아니라 점진적 구조 이동임

### 코드 근거 예시

- `spec/driver-operations-redesign.md`
  - 목표를 operations 중심 구조, namespace API, pure data model, non-breaking Phase 1로 명확히 적어 둠
  - 새 backend 추가를 "operations interfaces를 채운 driver 구현" 문제로 축소하려는 의도를 드러냄
- `graphiti_core/graphiti.py`
  - 초기화 시 `self.nodes = NodeNamespace(...)`, `self.edges = EdgeNamespace(...)`를 생성함
  - 고수준 client가 namespace API를 이미 노출하고 있어 리팩터링 방향이 코드에 반영돼 있음
- `graphiti_core/namespaces/nodes.py`
  - namespace가 embedding 생성과 ops 위임만 수행하는 얇은 래퍼 역할을 함
  - driver capability에 따라 서브 namespace를 조건부로 붙임
- `graphiti_core/namespaces/edges.py`
  - edge namespace도 동일하게 DB I/O를 직접 구현하지 않고 ops에 위임함
- `graphiti_core/driver/driver.py`
  - operations 접근자를 driver 프로퍼티로 제공하고 legacy interfaces를 Phase 1 호환용으로 유지함
- `docs/project/project-guide.md`
  - 현재 방향성을 namespace + operations 중심 구조로 재편하는 중이라고 정리함

### 제품 적용 포인트

- 데이터 모델과 DB I/O를 분리하면 backend 추가 시 수정 범위를 예측하기 쉬워짐
- namespace layer를 두면 embedding, tracing, validation 같은 횡단 관심사를 한곳에 모을 수 있음
- operations를 object type별로 나누면 테스트 단위가 선명해지고 provider 구현 책임도 명확해짐
- 점진적 리팩터링에서는 non-breaking Phase를 먼저 두는 편이 기존 사용자와 내부 코드 모두에게 안전함
- 장기적으로는 모델 객체에 메서드를 계속 붙이는 방식보다 namespace + operations 방식이 확장성과 유지보수성에 유리함

### 해석과 시사점

- 이 리팩터링의 핵심은 문법 변경이 아니라 책임 분리임
- Graphiti는 데이터 모델을 점점 pure data로 만들고, persistence 책임을 provider별 operations로 밀어내려 함
- namespace는 사용자 API를 단순하게 유지하면서도 cross-cutting concern을 수용하는 완충층 역할을 함
- 결과적으로 namespace + operations 구조는 backend 추가, 테스트, 장기 유지보수를 동시에 쉽게 만들기 위한 기반 공사에 가깝다

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 추상화가 곧 parity를 의미하지는 않음
  - 같은 API가 있어도 provider별 트랜잭션 보장과 검색 인덱스 구현은 다름
- 기본값의 영향은 여전히 큼
  - 아키텍처는 provider-agnostic하지만 실제 기준 구현과 문서 예시는 Neo4j + OpenAI 쪽에 더 무게가 실려 있음
- 통합 레이어 지원 범위가 코어보다 좁을 수 있음
  - MCP 팩터리처럼 실제 소비 채널에서는 지원 provider matrix가 축소될 수 있음
- 과도기 구조의 복잡도가 존재함
  - legacy interface와 new operations가 함께 살아 있어 처음 읽는 사람에게는 중복처럼 보일 수 있음
- backend 추가 비용이 완전히 사라지지는 않음
  - operations 인터페이스가 정리돼도 provider별 검색, 인덱스, transaction semantics는 따로 구현해야 함

### 제품 해석

- Graphiti의 백엔드 전략은 "완전 투명한 추상화"보다 "핵심 코어 유지 + 제약의 명시적 관리"에 가깝다
- 이 방식은 다중 provider를 억지로 동일하게 보이게 만드는 것보다 운영상 더 정직하다
- 따라서 이 프로젝트를 벤치마킹할 때는 추상화 계층의 존재뿐 아니라 provider maturity와 소비 채널별 지원 범위까지 같이 봐야 한다

## 적용 인사이트

Graphiti의 섹션 4에서 배울 핵심은 세 가지다. 첫째, 코어 메모리 파이프라인과 실행 provider를 분리해야 장기 운영에서 lock-in을 줄일 수 있다. 둘째, 공통 driver API는 백엔드 차이를 줄여 주지만, provider별 보장과 제약은 숨기지 말고 드러내야 한다. 셋째, namespace + operations 구조는 단순 리팩터링이 아니라 backend 추가와 테스트를 쉽게 만드는 확장 전략이다.

- provider 교체 가능성은 제품 유연성의 핵심 자산임
- 공통 API와 provider maturity는 구분해서 관리해야 함
- 책임 분리가 잘된 구조가 장기적인 다중 백엔드 운영 비용을 낮춤
