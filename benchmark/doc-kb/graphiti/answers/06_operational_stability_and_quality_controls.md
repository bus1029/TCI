# 운영 안정성과 품질 장치 분석

## 개요

Graphiti의 운영 안정성 장치는 부가 기능이 아니라 코어 설계 일부다. 이 프로젝트는 LLM 호출, 그래프 DB, 검색 쿼리, 다중 provider를 함께 다루기 때문에 품질 문제를 모델 성능 하나로 해결할 수 없다. 대신 동시성 상한, tracing, telemetry, provider별 테스트 신호, 입력 검증을 분리된 장치로 두고 서로 보완하게 만든다.

이 문서에서 먼저 잡아야 할 전제는 아래와 같다.

- Graphiti의 품질 문제는 추출 정확도만이 아니라 rate limit, provider parity, query safety까지 포함함
- 동시성 제어는 성능 최적화 옵션이 아니라 ingestion 안정성 제어 장치임
- tracing과 telemetry는 디버깅과 제품 운영 판단을 위한 서로 다른 계층임
- provider 추상화가 곧 provider 성숙도 동등성을 의미하지는 않음
- 입력 검증은 Pydantic 한 곳에만 두지 않고 query builder와 테스트까지 중첩 배치함
- Graphiti는 운영 실패가 주 기능을 깨지 않도록 fail-safe 성격의 장치를 여러 군데 둠

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| `SEMAPHORE_LIMIT` | 병렬 코루틴 수를 제한해 LLM 호출량과 처리량을 조절하는 상한 |
| `max_coroutines` | `Graphiti` 인스턴스별 동시성 override 값 |
| tracing | 개별 연산의 span과 속성을 남겨 흐름과 지연을 추적하는 관측성 계층 |
| telemetry | 어떤 provider 조합과 환경에서 Graphiti가 사용되는지 익명 통계로 수집하는 계층 |
| provider 성숙도 | API 지원 여부를 넘어 문서화, 테스트 범위, 런타임 fallback, 제약 노출까지 포함한 운영 신뢰도 |
| defense in depth | 입력 검증을 한 계층에만 두지 않고 여러 계층에서 중복 검증하는 방식 |

# 시스템 핵심 동작 방식 및 사용 기술

## 1. `SEMAPHORE_LIMIT` 같은 동시성 제어를 제품 핵심 설정으로 두는 이유

### 채택 기술 구조

- 공통 병렬 실행 지점 통제
  - `graphiti_core.helpers.semaphore_gather()`가 내부 fan-out 실행의 공통 entrypoint 역할을 함
  - 노드 요약, edge 저장, community 갱신 같은 병렬 구간이 같은 제어 장치를 공유함
- 환경 변수와 인스턴스 override 병행
  - 코어는 `SEMAPHORE_LIMIT` 환경 변수로 기본 동시성 상한을 읽음
  - `Graphiti(max_coroutines=...)`로 인스턴스 단위 override도 가능함
- ingestion 특성에 맞춘 운영 변수 노출
  - `add_episode()`와 `add_episode_bulk()`는 한 번의 API 호출 안에서 여러 LLM 요청과 DB 작업을 연쇄적으로 발생시킴
  - 따라서 동시성은 단순 asyncio 튜닝이 아니라 rate limit, 비용, latency를 함께 좌우하는 운영 변수임
- 소비 채널별 별도 튜닝
  - MCP 서버는 별도 `SEMAPHORE_LIMIT`를 두고 provider tier별 권장 범위를 코드 주석으로 안내함
  - 같은 코어라도 agent tool 환경에서는 운영자가 더 직접적으로 상한을 조정하게 만든 구조임

### 코드 근거 예시

- `README.md`
  - `SEMAPHORE_LIMIT`를 ingestion 성능과 `429` rate limit 대응의 핵심 설정으로 설명함
  - 기본값을 낮게 잡아 안정성을 우선하라고 안내함
- `graphiti_core/helpers.py`
  - `SEMAPHORE_LIMIT`와 `semaphore_gather()`를 정의해 병렬 코루틴 수를 중앙에서 제어함
  - 이 함수가 실제 병렬 실행 경로의 공통 게이트 역할을 함
- `graphiti_core/graphiti.py`
  - `max_coroutines`를 생성자 인자로 받고, `update_community()`, embedding 생성, 저장 fan-out에 전달함
  - 즉 동시성은 보조 옵션이 아니라 public API에서 직접 받는 운영 파라미터임
- `mcp_server/src/graphiti_mcp_server.py`
  - provider RPM 예시와 함께 `SEMAPHORE_LIMIT` 튜닝 가이드를 코드에 포함함
  - agent memory 서비스 운영에서 throughput과 rate limit 안정성을 함께 다루는 의도가 드러남

### 제품 적용 포인트

- LLM 기반 KB는 모델 품질만이 아니라 호출 밀도도 제품 품질에 직접 연결됨
- 병렬 fan-out이 많은 파이프라인은 동시성 상한을 전역 규칙으로 두는 편이 운영이 단순해짐
- 동시성 값을 코드 내부 상수로 숨기지 말고 환경 변수나 생성자 인자로 노출해야 운영자가 비용과 속도를 조절하기 쉬움
- 라이브러리 기본값과 서비스 기본값을 분리하면 소비 채널별 워크로드 특성에 맞춘 튜닝이 가능함

### 해석과 시사점

- Graphiti에서 동시성 제어는 "빠르게 돌리기 위한 옵션"보다 "무너지지 않게 돌리기 위한 안전장치"에 가깝다
- 특히 ingestion은 한 episode가 여러 LLM 호출로 번지기 때문에, 요청 수보다 내부 fan-out을 기준으로 제어해야 한다
- 이 구조는 메모리 품질을 모델 정확도와 동급의 운영 문제로 다루는 실전형 설계다

## 2. tracing, telemetry, 테스트 스킵 정책까지 포함해 provider 성숙도를 관리하는 방식

### 채택 기술 구조

- 관측성과 제품 통계의 분리
  - tracing은 개별 실행 흐름을 관찰하기 위한 장치임
  - telemetry는 어떤 provider 조합과 환경에서 제품이 실제 사용되는지 보기 위한 장치임
  - 둘 다 품질 관리에 쓰이지만 목적과 실패 허용 방식이 다름
- tracing의 optional no-op 설계
  - `create_tracer()`는 tracer가 없으면 `NoOpTracer`를 반환함
  - OpenTelemetry가 설치되지 않았거나 span 기록에 실패해도 주 기능은 계속 진행됨
  - `add_episode()` 같은 핵심 경로는 span 속성과 예외를 남기되 tracing 오류는 삼켜 서비스 경로를 보호함
- telemetry의 fail-silent 설계
  - `Graphiti` 초기화 시 provider 타입을 추정해 `graphiti_initialized` 이벤트를 보냄
  - telemetry는 pytest 환경에서 자동 비활성화되고, PostHog 초기화나 전송 실패도 조용히 무시함
  - 운영 데이터 수집이 ingestion과 search 성공 여부를 좌우하지 않게 분리한 구조임
- provider 지원과 성숙도의 구분
  - MCP factory는 optional import와 `HAS_*` 플래그로 provider 가용성을 판단함
  - 지원되지 않는 provider는 명시적 `ValueError`로 드러내고, 연결 실패도 provider별 메시지로 노출함
  - 테스트는 실제 키나 의존성이 없으면 `skipif`로 건너뛰며, 환경별 드라이버 행렬도 조건부로 구성됨
- 성숙도 신호의 다층 관리
  - README는 provider 지원과 telemetry 목적을 문서화함
  - tracing 문서는 별도 `OTEL_TRACING.md`로 분리해 사용법을 제시함
  - 테스트는 "지원 코드가 존재하는가"와 "지금 환경에서 실제로 검증됐는가"를 구분해서 표현함

### 코드 근거 예시

- `graphiti_core/tracer.py`
  - `NoOpTracer`, `OpenTelemetryTracer`, `create_tracer()`를 통해 tracing을 선택 기능으로 구현함
  - span attribute 추가, 상태 설정, 예외 기록이 모두 실패 안전하게 감싸져 있음
- `graphiti_core/graphiti.py`
  - 초기화 시 tracer를 세팅하고 provider 타입을 telemetry로 남김
  - telemetry 수집이 실패해도 예외를 올리지 않음
- `graphiti_core/telemetry/telemetry.py`
  - 익명 ID, 버전, 아키텍처, provider 조합만 수집함
  - `pytest` 감지 시 비활성화하고 모든 telemetry 오류를 silent 처리함
- `README.md`
  - telemetry가 무엇을 수집하고 무엇을 수집하지 않는지, 왜 필요한지, 어떻게 끌 수 있는지 설명함
  - 사용자가 provider 지원 범위와 운영 판단 기준을 문서에서 먼저 이해하게 함
- `OTEL_TRACING.md`
  - tracing을 기본 기능이 아니라 선택 기능으로 문서화함
  - 설치와 사용 예시를 분리해 관측성 도입 비용을 낮춤
- `mcp_server/src/services/factories.py`
  - optional import와 `HAS_ANTHROPIC`, `HAS_GROQ`, `HAS_GEMINI` 같은 플래그로 provider 사용 가능 여부를 관리함
  - 미지원 provider는 조용히 fallback하지 않고 명시적 오류를 던짐
- `tests/llm_client/test_anthropic_client_int.py`
  - API 키가 없으면 integration 테스트를 `skipif` 처리함
  - provider 지원 코드 존재와 실제 외부 API 검증을 분리해 관리함
- `tests/driver/test_falkordb_driver.py`
  - FalkorDB 의존성이 없으면 driver 테스트를 스킵함
  - optional backend를 현실적인 테스트 행렬 안에서 다룸
- `tests/helpers_test.py`
  - 환경 변수로 FalkorDB, Kuzu, Neptune 드라이버를 포함하거나 제외함
  - 특히 Neptune은 기본 비활성화돼 있어 provider parity가 코드상 완전 자동 검증 상태는 아님을 보여 줌
- `graphiti_core/decorators.py`
  - `handle_multiple_group_ids`가 FalkorDB에서만 다중 group 처리를 별도 분기함
  - 추상화 뒤에 provider별 특수 처리 지점이 남아 있다는 신호다

### 제품 적용 포인트

- 다중 provider 시스템에서는 "지원한다"와 "운영에 자신 있다"를 다른 수준으로 관리해야 함
- tracing, telemetry, 문서, 테스트는 각각 다른 품질 신호를 주므로 한 장치만 보고 성숙도를 판단하면 안 됨
- optional dependency와 conditional test는 현실적인 방식이지만, 그만큼 provider별 검증 강도가 달라질 수 있음을 드러내야 함
- provider 특수 처리가 남아 있는 지점을 문서와 코드에서 명시하면 parity 착시를 줄일 수 있음

### 해석과 시사점

- Graphiti는 provider 추상화를 제공하지만, 모든 provider를 완전히 동일하게 취급하지는 않는다
- 대신 지원 가능성, 운영 관측성, 테스트 신호를 분리해 "현재 어느 정도까지 믿을 수 있는가"를 관리한다
- 이런 태도는 멀티 provider 제품에서 더 정직하고 실무적이다

## 3. 입력 검증과 검색 필터 방어를 helpers와 테스트 계층에 함께 넣은 이유

### 채택 기술 구조

- 공통 검증 함수의 중앙 배치
  - `validate_group_id()`, `validate_group_ids()`, `validate_node_labels()`가 `helpers.py`에 모여 있음
  - 검색과 저장 경로가 같은 규칙을 재사용하게 만들어 검증 기준을 한 곳에 고정함
- 모델 계층의 조기 차단
  - `SearchFilters`는 Pydantic validator에서 `node_labels`를 검사함
  - 정상 경로에서는 unsafe label이 query builder까지 내려가기 전에 막힘
- query builder의 재검증
  - `node_search_filter_query_constructor()`와 `edge_search_filter_query_constructor()`는 다시 `validate_node_labels()`를 호출함
  - `model_construct()`처럼 Pydantic 검증을 우회한 경우까지 방어하는 defense in depth 구조임
- full-text 검색 입력 정리
  - `lucene_sanitize()`가 Lucene 특수 문자를 escape해 full-text query 조립 시 위험을 줄임
  - 저장 쿼리와 검색 쿼리 모두에서 "문자열을 그대로 삽입하지 않는다"는 원칙을 유지함
- 에러 타입의 명시화
  - `GroupIdValidationError`, `NodeLabelValidationError`를 별도 예외로 두어 보안 실패를 일반 오류와 구분함
  - 실패 이유를 개발자에게 명확히 보여 주되, 검증 규칙도 코드에 문서화함
- 테스트를 통한 우회 경로 고정
  - 정상 생성 경로뿐 아니라 validation bypass 경로, provider별 query 생성 경로까지 테스트함
  - 보안 규칙이 리팩터링 중 사라지지 않게 회귀 테스트로 묶은 구조다

### 코드 근거 예시

- `graphiti_core/helpers.py`
  - `validate_group_id()`가 `group_id`를 영숫자, `-`, `_`로 제한함
  - `validate_node_labels()`가 Cypher identifier 형태만 허용함
  - `lucene_sanitize()`가 full-text query용 escape를 수행함
- `graphiti_core/search/search_filters.py`
  - `SearchFilters`의 validator가 node label을 조기 검증함
  - query constructor에서 같은 검증을 다시 호출해 bypass 경로를 막음
- `graphiti_core/errors.py`
  - 검증 실패를 `GroupIdValidationError`, `NodeLabelValidationError`로 분리함
- `tests/utils/search/test_search_security.py`
  - unsafe `node_labels`, 잘못된 `group_id`, bypass된 filter model을 모두 테스트함
  - Neo4j와 FalkorDB full-text query 경로까지 검증함
- `tests/test_node_label_security.py`
  - `EntityNode` 생성과 assignment뿐 아니라 save query helper의 bypass 경로까지 확인함
  - 라벨 injection 방어가 모델 계층에만 의존하지 않음을 보여 줌

### 제품 적용 포인트

- 식별자와 파티션 키처럼 query shape를 바꾸는 입력은 일반 텍스트보다 더 엄격하게 다뤄야 함
- 검증 로직은 helper 한 곳에 모으되, 실제 query 조립 직전에도 다시 확인해야 우회 경로를 막을 수 있음
- 보안 테스트는 happy path보다 bypass path와 injection 시나리오를 더 집요하게 고정해야 함
- KB 제품도 query safety를 검색 품질과 별개가 아니라 같은 품질 축으로 다뤄야 함

### 해석과 시사점

- Graphiti는 검색 보안을 "프레임워크가 알아서 해 줄 것"이라고 넘기지 않는다
- 대신 identifier validation, full-text sanitization, explicit error, regression test를 조합해 방어선을 여러 겹 둔다
- 이 접근은 agent memory 시스템에서 특히 중요하다. 파티션 경계와 query 조립이 깨지면 메모리 품질과 보안이 동시에 무너지기 때문이다

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 기본 동시성 값의 해석 차이
  - 코어 `helpers.py` 기본값은 `20`이고 README와 MCP 서버 가이드는 `10`을 기본 전제로 설명함
  - 소비 채널마다 안전 기본값이 달라 운영자가 문서와 실제 동작을 함께 확인해야 함
- fail-silent 관측성의 양면성
  - tracing과 telemetry 오류가 주 기능을 막지 않는 장점이 있음
  - 반대로 계측이 실제로 꺼졌거나 실패해도 초기에 눈치채기 어려울 수 있음
- provider parity의 불균등
  - optional import, conditional test, provider별 분기가 많아 "코드상 지원"과 "운영상 검증" 범위가 다를 수 있음
  - 특히 일부 provider는 기본 테스트 행렬에서 제외되거나 조건부 검증에 머뭄
- 보안 검증 범위의 편중
  - `group_id`, `node_labels`, full-text query 방어는 비교적 명시적임
  - 다른 입력 면까지 같은 수준으로 체계화돼 있는지는 추가 점검이 필요함

### 제품 해석

- Graphiti의 운영 품질 장치는 실제 장애를 막는 방향으로 설계돼 있다
- 다만 fail-safe와 optional support가 많을수록 운영자는 "무엇이 지원되고 무엇이 검증됐는가"를 더 분명히 읽어야 한다
- 즉 이 구조의 강점은 완전 자동화보다, 복잡한 멀티 provider 환경을 안전하게 다루기 위한 현실적 방어선에 있다

## 적용 인사이트

Graphiti에서 가장 배울 만한 점은 운영 안정성을 코어 기능 밖으로 밀어내지 않는 태도다. 동시성은 LLM 비용과 rate limit을 다루는 핵심 설정으로 노출하고, provider 성숙도는 tracing, telemetry, optional dependency, 테스트 스킵 정책을 함께 보며 판단하고, query safety는 helper와 query builder와 테스트에 중첩 배치한다. 이 조합 덕분에 Graphiti는 멀티 provider 기반의 agent memory 시스템에서 "돌아가는 코드"보다 "운영 가능한 코드"에 더 가까워진다.

- LLM 기반 ingestion은 내부 fan-out 기준으로 동시성을 제어해야 함
- provider 추상화만으로 성숙도를 판단하지 말고 문서, 계측, 테스트 신호를 함께 봐야 함
- fail-safe 관측성은 주 기능을 보호하지만 운영 가시성 보완 장치가 필요함
- query safety는 입력 모델 검증만으로 끝내지 말고 query 조립 직전과 회귀 테스트까지 이어져야 함
- 운영 품질 장치는 검색 품질과 별개가 아니라 같은 제품 품질 축으로 다뤄야 함
