# 에이전트 메모리와 인터페이스 설계 분석

## 개요

Graphiti는 스스로를 답변 생성 엔진이 아니라 에이전트 메모리 엔진으로 정의한다. 이 차이는 문구 수준의 포지셔닝이 아니라 API 표면, 서버 구성, 운영 규칙에서 실제로 드러난다. 코어 라이브러리는 ingestion, retrieval, maintenance에 집중하고, 답변 생성은 외부 agent나 애플리케이션이 맡는다. `server`와 `mcp_server`는 이 메모리 엔진을 서로 다른 소비 채널에 맞게 노출하는 인터페이스 레이어다. 여기에 `group_id` 단위 순차 처리와 `Saga` 연결을 붙여 메모리의 시간 일관성을 운영 계층에서 지키도록 설계했다.

이 문서에서 먼저 잡아야 할 전제는 아래와 같다.

- Graphiti 코어는 knowledge graph를 구축하고 조회하는 엔진임
- 답변 생성은 코어 API의 책임이 아니라 외부 LLM 오케스트레이션의 책임임
- `server`는 단순 HTTP 래퍼에 가깝고 `mcp_server`는 agent tool 인터페이스에 가깝다
- `group_id`는 단순 태그가 아니라 독립 메모리 파티션이자 순차 처리 단위다
- `Saga`는 개별 episode를 사건 흐름으로 묶는 sequence-level memory 구조다
- 시간 순서가 깨지면 temporal memory 품질도 같이 깨진다

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| 에이전트 메모리 엔진 | 답변을 직접 만들지 않고 에이전트에 줄 컨텍스트를 저장, 갱신, 조회하는 엔진 |
| `server` | FastAPI 기반의 간단한 HTTP 서비스 레이어 |
| `mcp_server` | MCP 도구 형태로 Graphiti를 노출하는 agent integration 레이어 |
| `group_id` | 데이터 파티션이자 순차 처리 기준이 되는 메모리 경계 |
| `SagaNode` | 연속된 episode를 하나의 흐름으로 묶는 상위 노드 |
| `HAS_EPISODE` | saga와 episode를 연결하는 관계 |
| `NEXT_EPISODE` | episode 간 순서를 보존하는 관계 |

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 답변 생성 엔진이 아니라 에이전트 메모리 엔진으로 자신을 정의하는 이유

### 채택 기술 구조

- 코어 책임 분리
    - `Graphiti`의 핵심 API는 `add_episode()`, `add_episode_bulk()`, `search()`, `search_()`, `retrieve_episodes()`, community build, graph maintenance에 집중돼 있음
    - 즉 입력을 메모리 구조로 바꾸고, 다시 꺼내는 일까지가 코어 책임임
- 반환 타입의 성격
    - `search()`는 `EntityEdge` 목록을 반환함
    - `search_()`는 `SearchResults` 안에 edges, nodes, episodes, communities를 담아 반환함
    - 코어가 돌려주는 것은 답변 문장보다 fact, entity, episode 같은 컨텍스트 재료임
- LLM 사용 위치
    - LLM은 엔티티 추출, 엣지 추출, dedupe 판정, community summary 생성 같은 memory construction 과정에 쓰임
    - 사용자 질문에 대한 최종 natural language answer를 생성하는 public API는 없음
- 메모리 컨텍스트 출력 방식
    - `search_results_to_context_string()`는 검색 결과를 LLM에 직접 넣을 context string으로 바꾸는 helper임
    - 이 helper는 Graphiti가 answer engine이라기보다 downstream answer engine에 공급할 memory layer라는 점을 보여 줌
- 제품 정의
    - README는 Graphiti를 temporal context graph engine, context infrastructure, agent memory 관련 엔진으로 설명함
    - MCP 서버 instructions도 Graphiti를 "memory service for AI agents"라고 직접 정의함

### 코드 근거 예시

- `README.md`
    - Graphiti를 AI agents를 위한 temporal context graph framework로 설명함
    - "Give agents rich, structured context"라는 표현으로 컨텍스트 공급자 역할을 명시함
    - Zep와의 비교에서도 managed context infrastructure의 코어 엔진으로 위치시킴
- `graphiti_core/graphiti.py`
    - 주요 public API가 ingestion, search, episode retrieval, graph maintenance 중심으로 구성됨
    - 답변 생성이나 dialogue policy를 담당하는 메서드는 노출되지 않음
- `graphiti_core/search/search_helpers.py`
    - `search_results_to_context_string()`가 검색 결과를 "LLM에 바로 넘길 컨텍스트"로 포맷함
    - Graphiti 결과가 answer가 아니라 answer material이라는 점을 직접 보여 줌
- `mcp_server/src/graphiti_mcp_server.py`
    - `GRAPHITI_MCP_INSTRUCTIONS`가 Graphiti를 memory service로 설명함
    - MCP 도구도 `add_memory`, `search_nodes`, `search_memory_facts`, `get_episodes`처럼 메모리 조작과 조회에 집중함
- `server/graph_service/routers/retrieve.py`
    - `/search`와 `/get-memory`도 facts만 반환함
    - FastAPI 레이어도 answer synthesis 없이 retrieval 결과만 노출함

### 제품 적용 포인트

- 생성 모델과 메모리 인프라는 분리하는 편이 제품 경계가 선명해짐
- memory layer는 retrieval 품질, provenance, temporal consistency에 집중하고 answer layer는 response style과 reasoning에 집중하게 할 수 있음
- 같은 메모리 엔진을 여러 agent, 여러 응답 정책, 여러 채널에서 재사용하기 쉬워짐
- 메모리 계층이 답변 생성까지 품으면 교체 단위가 커지고 운영 책임이 섞이기 쉬움

### 해석과 시사점

- Graphiti가 메모리 엔진이라는 자기 정의는 "LLM을 안 쓴다"는 뜻이 아니라 "LLM을 어디에 쓰는가"를 분리한다는 뜻
- 이 구조 덕분에 Graphiti는 답변을 대신하는 시스템이 아니라 답변 시스템이 믿고 쓸 수 있는 상태 저장소가 됨
- 에이전트 제품에서 중요한 것은 한 번의 답변보다 장기적으로 일관된 memory state이므로, 이 경계 설정은 매우 실무적

## 2. MCP 서버와 FastAPI 서버를 별도 레이어로 둔 이유

### 채택 기술 구조

- 코어와 인터페이스 분리
    - `graphiti_core`는 라이브러리이자 도메인 엔진 역할을 함
    - `server`와 `mcp_server`는 같은 코어를 서로 다른 소비자에게 맞춰 감싼 인터페이스 레이어임
- FastAPI 서버의 역할
    - `server/graph_service`는 단순 HTTP API 제공에 초점을 둠
    - `retrieve.py`는 facts와 episodes를 REST 응답으로 반환함
    - `ingest.py`는 `/messages`로 메시지를 받아 내부 `AsyncWorker` 큐에 넣고 `graphiti.add_episode()`를 호출함
    - `zep_graphiti.py`도 core `Graphiti`를 상속해 몇 가지 HTTP용 편의 메서드만 추가함
- MCP 서버의 역할
    - `mcp_server`는 Graphiti를 tool-oriented memory service로 노출함
    - `FastMCP` 인스턴스 위에 `add_memory`, `search_nodes`, `search_memory_facts`, `get_episodes`, `clear_graph` 같은 도구를 올림
    - 설정도 YAML, env, CLI를 병합하고 provider 팩토리, queue service까지 별도 계층으로 둠
    - 즉 HTTP API보다 agent integration을 더 직접 지원하는 제품형 래퍼에 가깝다
- 채널별 맞춤 반환
    - FastAPI는 일반적인 REST 소비자에게 JSON 응답을 제공함
    - MCP는 도구 설명, 입력 스키마, 결과 포맷을 통해 agent runtime과 바로 연결되도록 설계됨

### 코드 근거 예시

- `server/README.md`
    - graph-service를 Graphiti 패키지를 구현한 FastAPI 서버라고 설명함
    - Docker 이미지와 실행 방법 중심으로 서술돼 있어 예시 서비스 성격이 강함
- `server/graph_service/main.py`
    - 라우터를 붙이고 시작 시 인덱스를 초기화하는 얇은 앱 엔트리포인트임
- `server/graph_service/routers/ingest.py`
    - `AsyncWorker` 큐를 두고 `/messages`에서 `graphiti.add_episode()`를 비동기 처리함
    - REST 수신과 memory ingestion을 느슨하게 연결하는 래퍼 역할이 드러남
- `server/graph_service/routers/retrieve.py`
    - `graphiti.search()` 결과를 DTO로 바꿔 돌려주는 단순 retrieval API임
- `mcp_server/README.md`
    - MCP 서버를 experimental implementation이자 AI assistants용 통합 계층으로 설명함
    - queue-based processing, multiple providers, transport 설정 등 제품형 통합 기능을 강조함
- `mcp_server/src/graphiti_mcp_server.py`
    - `FastMCP` 기반으로 도구를 정의함
    - `search_nodes()`와 `search_memory_facts()`처럼 agent memory use case에 맞춘 툴 단위 인터페이스를 제공함

### 제품 적용 포인트

- 같은 코어 엔진이라도 REST 소비자와 MCP 소비자는 기대하는 인터페이스가 다르므로 채널 레이어를 분리하는 편이 나음
- 라이브러리, 서비스, 도구를 분리하면 코어를 건드리지 않고 새로운 소비 채널을 추가하기 쉬움
- agent tool 채널에는 큐, 설정 병합, provider 선택 같은 운영 기능이 더 많이 필요
- 단순 HTTP 서버를 유지하면 사람이 직접 호출하거나 다른 백엔드 서비스에서 붙이기 쉬움

### 해석과 시사점

- Graphiti는 하나의 애플리케이션이 아니라 memory core와 여러 delivery surface를 가진 제품 구조에 가까움
- `server`와 `mcp_server`의 분리는 중복 구현이 아니라, 같은 메모리 엔진을 다른 상호작용 모델에 맞게 패키징하는 방식
- 이런 구조는 장기적으로 SDK, CLI, workflow engine integration 같은 다른 인터페이스를 추가하기도 쉬운 형태

## 3. group 단위 직렬 처리와 saga 연결이 agent memory에서 중요한 이유

### 채택 기술 구조

- `group_id`의 의미
    - `group_id`는 데이터 필터 수준을 넘어서 독립 메모리 파티션 역할을 함
    - README와 MCP instructions 모두 group별로 separate knowledge domain을 유지한다고 설명함
    - `Graphiti.add_episode()`도 group이 다르면 driver database를 clone해 다른 파티션으로 처리함
- 순차 처리 규칙
    - `add_episode()` docstring은 각 episode를 sequentially awaited 해야 한다고 직접 적고 있음
    - 이유는 이전 episode를 읽고 현재 episode를 추출, dedupe, invalidation하는 파이프라인이 시간 순서에 의존하기 때문임
    - 같은 group에서 순서가 꼬이면 previous episode context와 contradiction 판정이 어긋날 수 있음
- MCP 운영 구현
    - `QueueService`는 `group_id`마다 별도 `asyncio.Queue`와 worker를 유지함
    - 같은 group은 `_process_episode_queue()`에서 하나씩 처리하고, 다른 group은 서로 다른 worker로 병렬 처리됨
    - `add_memory()` docstring도 same group sequential processing을 명시함
- 테스트 신호
    - `mcp_server/tests/test_async_operations.py`는 같은 group 내 순차 처리와 다른 group 간 동시 처리 둘 다 검증함
    - 즉 시간 일관성과 처리량을 함께 맞추는 운영 규칙이 테스트로 고정돼 있음
- saga 연결 구조
    - `SagaNode`는 episode 흐름을 담는 별도 노드임
    - `_get_or_create_saga()`가 saga를 이름 기준으로 재사용하거나 생성함
    - `_process_episode_data()`는 saga가 있으면 `HAS_EPISODE`와 `NEXT_EPISODE`를 저장함
    - bulk path도 episode를 `valid_at` 기준으로 정렬한 뒤 `NEXT_EPISODE` 체인을 만듦
    - `retrieve_episodes(..., saga=...)`는 특정 saga에 속한 episode만 시간순으로 가져올 수 있음

### 코드 근거 예시

- `graphiti_core/graphiti.py`
    - `add_episode()` docstring이 background queue와 sequential processing 필요성을 직접 설명함
    - `add_episode()`는 이전 episode를 읽은 뒤 현재 episode를 처리하므로 순서 의존성이 큼
    - `_process_episode_data()`가 `HasEpisodeEdge`와 `NextEpisodeEdge`를 저장함
    - `add_episode_bulk()`도 `valid_at` 기준 정렬 후 saga chain을 생성함
- `graphiti_core/utils/maintenance/graph_data_operations.py`
    - `retrieve_episodes()`가 saga 이름으로 episode 흐름을 조회할 수 있게 함
    - saga 조회 결과를 chronological order로 반환함
- `graphiti_core/nodes.py`
    - `SagaNode`를 독립 모델로 정의함
- `graphiti_core/edges.py`
    - `HasEpisodeEdge`와 `NextEpisodeEdge`를 별도 관계 타입으로 정의함
- `mcp_server/src/services/queue_service.py`
    - group별 queue와 worker를 유지하며 한 group 안에서는 순차 처리함
- `mcp_server/tests/test_async_operations.py`
    - `test_sequential_queue_processing()`가 같은 group의 처리 순서를 검증함
    - `test_concurrent_group_processing()`가 다른 group은 병렬 처리되는지 검증함

### 제품 적용 포인트

- temporal memory에서는 병렬성보다 순서 보장이 더 중요한 구간이 존재함
- 파티션 키를 `group_id`처럼 명시하면 같은 사용자의 메모리는 순차 처리하고, 서로 다른 사용자의 메모리는 병렬 처리하는 운영이 가능함
- saga 같은 sequence-level 구조를 두면 단순 fact 검색을 넘어 사건 흐름 복원과 작업 이력 추적이 가능해짐
- sequence edge를 데이터 모델로 남기고 queue 규칙을 운영 계층에 두면 시간 일관성을 이중으로 방어할 수 있음

### 해석과 시사점

- 에이전트 메모리에서 "무엇을 저장했는가"만큼 중요한 것이 "어떤 순서로 저장했는가"임
- Graphiti는 이 문제를 모델 계층의 `Saga`와 운영 계층의 group queue를 함께 써서 품
- 이 설계 덕분에 개별 fact뿐 아니라 대화 흐름과 상태 전이를 메모리 자산으로 유지할 수 있음

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 코어와 인터페이스 분리 비용
    - `graphiti_core`, `server`, `mcp_server`가 분리돼 있어 구조는 깔끔하지만 설정과 배포 지점은 늘어남
- answer synthesis 부재
    - Graphiti 단독으로는 최종 답변을 생성하지 않으므로, 실제 제품에서는 별도 agent orchestration이 필요함
- 순차 처리로 인한 처리량 제약
    - 같은 group은 순차 처리해야 하므로 hot partition에서는 ingestion throughput이 제한될 수 있음
- saga 운영 복잡도
    - saga 이름 관리, 이전 episode 연결, bulk path 정렬까지 신경 써야 하므로 단순 message log보다 구현과 운영이 복잡함
- 채널별 기능 편차
    - FastAPI 서버는 얇고 단순한 반면 MCP 서버는 더 제품화된 기능을 갖고 있어, 두 인터페이스의 성숙도가 다르게 보일 수 있음

### 제품 해석

- Graphiti의 인터페이스 설계는 단순함보다 역할 분리와 시간 일관성을 우선
- 이 구조는 빠른 프로토타입 하나를 만드는 데는 더 무거울 수 있지만, 여러 agent와 채널이 같은 memory core를 공유하는 제품에는 더 적합
- 따라서 이 설계를 평가할 때는 기능 수보다 책임 경계, 재사용성, temporal consistency 보장 방식을 같이 봐야함

## 적용 인사이트

Graphiti에서 벤치마킹할 핵심은 메모리 엔진의 책임을 끝까지 좁게 유지하는 방식이다. 코어는 memory construction과 retrieval에 집중하고, 인터페이스는 REST와 MCP처럼 소비 채널별로 분리하며, 시간 일관성은 `group_id` 기반 순차 처리와 `Saga` 기반 sequence model을 함께 써서 보장한다.

- memory engine과 answer engine의 경계를 분리해야 교체성과 운영 책임이 선명해짐
- 같은 코어를 여러 채널에 재사용하려면 라이브러리와 인터페이스 레이어를 나눠야 함
- temporal memory에서는 파티션 키 기반 순차 처리 규칙이 필수 운영 장치가 됨
- sequence-level 모델을 별도 계층으로 두면 대화와 작업의 흐름까지 메모리 자산으로 다룰 수 있음
- Graphiti의 인터페이스 설계 강점은 기능의 많고 적음보다 agent memory에 맞는 책임 분리와 시간 보존 규칙에 있음