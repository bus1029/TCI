# 3. 검색과 문맥 구성 분석

## 개요

Basic Memory에서 검색과 문맥 구성은 같은 문제를 두 단계로 나눠 푸는 구조다. 검색은 "어디를 볼 것인가"를 빠르게 좁히는 계층이고, 문맥 구성은 "그 결과를 어떤 연결망으로 다시 엮을 것인가"를 담당하는 계층이다. 이 프로젝트가 단순 RAG 툴보다 한 단계 더 제품답게 보이는 이유도 여기 있다. Top-K 검색만 잘하는 것이 아니라, 검색 결과를 다시 `memory://` 주소와 relation traversal로 이어 붙여 후속 도구 호출에 재사용 가능한 흐름을 만든다.

처음 보는 사람이 이 문서를 읽을 때 먼저 잡아야 할 제품 정의는 아래와 같다.

- Basic Memory는 Markdown 파일을 원본 지식 저장소로 두고, 그 내용을 검색 인덱스와 지식 그래프로 동기화한 뒤, AI가 검색과 컨텍스트 도구를 통해 다시 탐색하게 만드는 local-first 지식 베이스 제품임

이 문서에서 먼저 알아야 할 전제는 아래와 같다.

- 검색은 "후보를 잘 찾는 일"이고, 문맥 구성은 "찾은 후보를 이어 읽을 수 있게 다시 엮는 일"임
- Basic Memory는 entity, observation, relation을 모두 검색 가능한 인덱스 단위로 다룸
- 검색 결과는 끝이 아니라 다음 도구 호출의 시작점이며, `memory://`는 그 시작점을 다시 참조하기 위한 논리 주소임
- 이 제품의 핵심은 단순 RAG 응답 생성보다 "저장된 지식을 다시 탐색 가능한 흐름"으로 만드는 데 있음

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| SearchService | 키워드, 벡터, hybrid retrieval로 후보를 찾는 검색 진입점 |
| ContextService | 검색 결과나 memory URL을 기준으로 relation 그래프를 확장해 문맥을 조립하는 계층 |
| hybrid search | FTS와 vector search를 함께 사용해 후보를 찾는 검색 방식 |
| graph traversal | relation을 따라 관련 entity를 확장해 읽을 문맥을 만드는 방식 |
| `memory://` | LLM 도구가 저장된 지식을 다시 참조할 때 쓰는 논리 주소 |
| matched chunk | 검색 결과가 왜 뽑혔는지 보여 주는 실제 텍스트 조각 |
| provenance | 검색 결과를 다시 원문으로 추적할 수 있게 하는 출처 정보 축 |

예를 들어 사용자가 "pour over coffee와 관련된 이전 메모를 찾아서 연결된 내용까지 보여줘" 같은 요청을 하면 대략 아래 흐름이 일어난다.

1. `SearchService`가 FTS 또는 vector, hybrid retrieval로 관련 entity나 observation 후보를 찾음
2. 결과에는 `permalink`, `file_path`, `matched_chunk`가 함께 붙어 후속 추적이 가능하게 남음
3. `ContextService`가 그중 primary result를 기준으로 relation을 따라 관련 entity를 확장함
4. 확장 결과는 `memory://` 주소와 함께 다음 `read_note`, `build_context` 같은 도구 호출에 재사용됨

즉 이 문서의 주제는 "검색을 잘하는 방법" 자체보다 "검색 결과를 어떻게 다시 탐색 가능한 문맥 흐름으로 바꾸는가"에 가깝다.

이번 섹션에서 벤치마킹할 지점은 네 가지다.

- hybrid search와 graph traversal을 한 기능으로 섞지 않고 분리하는 방식
- `memory://`를 LLM 친화적인 논리 주소로 도입하고 도구 라우팅에 연결하는 방식
- 검색 결과에 permalink, file path, matched chunk를 남겨 추적 가능성을 확보하는 방식
- page size, related limit, chunk limit, preview truncation을 상수와 기본값으로 운영하는 방식

# 시스템 핵심 동작 방식 및 사용 기술

## 1. Hybrid search는 후보를 찾고, graph traversal은 문맥을 엮는 구조

### 채택 기술 구조

- 역할 분리
  - Basic Memory의 검색 계층은 retrieval과 context assembly를 분리함
  - `SearchService`와 `SearchRepositoryBase`는 질의에 맞는 후보를 찾는 역할을 맡음
  - `ContextService`는 그 후보를 relation 그래프 위에서 확장해 실제로 이어 읽을 수 있는 문맥으로 바꿈
- hybrid search 역할
  - hybrid search의 역할은 두 검색 신호를 합치는 데 있음
  - FTS는 permalink, title, content 기반의 정확한 키워드 매칭을 담당함
  - vector search는 chunk 단위 임베딩으로 의미적으로 가까운 내용을 찾음
  - hybrid는 두 결과를 같은 `search_index` row id 기준으로 합쳐 점수를 재계산함
- graph traversal 역할
  - graph traversal의 역할은 검색 품질이 아니라 문맥 연결성에 있음
  - primary result를 먼저 찾음
  - 그 primary result가 entity일 때 relation을 따라 연결된 entity와 relation을 재귀적으로 탐색함
  - observation을 다시 붙여 한 항목을 읽을 때 필요한 사실과 주변 링크를 함께 반환함
- 구조적 의미
  - hybrid search는 "후보 검색기"이고, graph traversal은 "문맥 확장기"임
  - 이 둘을 분리했기 때문에 검색 점수 조정과 그래프 확장을 독립적으로 바꿀 수 있음

### 코드 근거 예시

- `src/basic_memory/services/search_service.py`
  - `SearchQuery.retrieval_mode`에 따라 FTS, vector, hybrid를 선택함
  - 일반 텍스트 검색은 strict FTS가 실패했을 때만 relaxed OR fallback을 한 번 수행함
- `src/basic_memory/repository/search_repository_base.py`
  - `SearchRetrievalMode.VECTOR`, `HYBRID`를 공통 로직에서 분기 처리함
  - hybrid는 `max(vec, fts) + 0.3 * min(vec, fts)` 공식을 사용함
  - vector retrieval은 chunk 수준 similarity를 모은 뒤 search row 수준으로 다시 집계함
- `src/basic_memory/services/context_service.py`
  - `build_context()`가 primary result를 구한 뒤 `find_related()`로 relation traversal을 수행함
  - `find_related()`는 recursive CTE로 relation과 connected entity를 함께 찾음
  - entity observations를 다시 붙여 hierarchical result를 만듦
- `src/basic_memory/api/v2/utils.py`
  - 검색 결과는 `SearchResult`
  - 문맥 결과는 `GraphContext`로 별도 직렬화함

### 제품 적용 포인트

- 검색과 문맥 생성을 한 함수에 몰아넣지 말고 후보 검색과 후처리 문맥 조립을 분리하는 편이 확장성이 좋음
- hybrid retrieval은 ranking 문제로 다루고, graph traversal은 structure enrichment 문제로 다루는 편이 설계가 단순해짐
- entity, observation, relation을 같은 인덱스 축에 올려두되 문맥 조립 단계에서 다시 계층형으로 재구성하면 검색 유연성과 읽기 경험을 함께 가져갈 수 있음

### 해석과 시사점

- Basic Memory는 "검색 결과를 많이 뽑는 시스템"보다 "후속 탐색 가능한 지식 흐름을 만드는 시스템"에 가깝다
- 이 구조의 강점은 검색 정확도와 문맥 연결성을 별개로 개선할 수 있다는 점이다
- 반대로 graph traversal은 검색 랭킹을 대체하지 않으므로, initial recall 품질이 나쁘면 후속 문맥도 약해진다

## 2. `memory://`는 검색 입력값이 아니라 도구 간 공통 식별자다

### 채택 기술 구조

- 주소 체계의 목적
  - `memory://`는 사용자 친화적인 링크 형식이면서 동시에 LLM 도구 호출의 공통 식별자임
  - 목적은 "세션 안에서 우연히 나온 문자열"이 아니라 "저장된 지식을 다시 찾을 수 있는 안정된 논리 주소"를 LLM에게 주는 데 있음
- 연결 계층
  - 이 프로젝트에서 `memory://`는 세 층에서 연결됨
  - 문서 포맷 층: `docs/NOTE-FORMAT.md`가 permalink, title, path를 `memory://`로 참조할 수 있다고 정의함
  - 스키마/검증 층: `MemoryUrl` 타입이 `memory://` prefix, invalid character, double slash를 검증하고 정규화함
  - MCP 라우팅 층: `resolve_project_and_path()`가 memory URL에서 project prefix를 해석하고, 실제 active project와 canonical path를 결정함
- project prefix 처리
  - 중요한 구현 포인트는 project prefix 처리임
  - `memory://research/specs/search` 같은 URL이 들어오면, MCP는 project parameter가 없어도 첫 path segment를 프로젝트로 해석해 해당 프로젝트로 라우팅함
  - prefix가 없으면 active project를 기준으로 canonical permalink를 보정함
  - 즉 `memory://`는 단순 문자열이 아니라 routing hint까지 포함한 주소임
- 도구별 사용 방식
  - 검색 도구와 문맥 도구는 이 주소 체계를 다르게 씀
  - `search_notes()`는 memory URL을 받으면 permalink search로 바꿔 검색 시작점을 찾음
  - `build_context()`는 memory URL을 canonical path로 바꾼 뒤 memory API에 전달하고, 그 결과를 graph context로 조립함

### 코드 근거 예시

- `docs/NOTE-FORMAT.md`
  - permalink, title, path 기반 `memory://` URL 예시를 정의함
  - wildcard path 패턴도 지원함
- `src/basic_memory/schemas/memory.py`
  - `normalize_memory_url()`, `validate_memory_url_path()`
  - `MemoryUrl` 타입과 `memory_url_path()`를 정의함
- `src/basic_memory/mcp/project_context.py`
  - `detect_project_from_url_prefix()`가 로컬 config 기준으로 project prefix를 감지함
  - `resolve_project_and_path()`가 project-aware canonical path를 계산함
- `src/basic_memory/mcp/tools/search.py`
  - memory URL 입력을 감지하고 permalink search로 전환함
- `src/basic_memory/mcp/tools/build_context.py`
  - memory URL을 normalize한 뒤 typed `MemoryClient`로 전달함
- `src/basic_memory/mcp/clients/memory.py`
  - `/v2/projects/{project_id}/memory/*` API 호출로 연결함

### 제품 적용 포인트

- LLM 도구를 여러 개 둘 계획이라면, free-form title 문자열 대신 재사용 가능한 논리 주소 체계를 먼저 설계하는 편이 좋음
- 주소 체계는 단순 식별뿐 아니라 라우팅 힌트까지 담을 수 있어야 멀티 프로젝트 구조에서 강해짐
- 인간이 읽기 쉬운 URL과 내부 canonical lookup을 분리하면 사용자 경험과 안정성을 함께 가져갈 수 있음

### 해석과 시사점

- Basic Memory의 `memory://`는 웹 URL 흉내가 아니라 LLM용 지식 참조 프로토콜에 가깝다
- 이 구조 덕분에 "이전 대화의 텍스트"가 아니라 "저장된 지식의 주소"를 다음 도구 호출에 넘길 수 있다
- 세션 히스토리를 길게 붙잡는 방식보다, 저장된 지식을 다시 탐색하게 만드는 점이 이 제품의 memory 철학에 더 가깝다

## 3. 검색 결과는 citation 시스템까지는 아니지만, 원문 복귀에 필요한 출처 축은 남긴다

### 채택 기술 구조

- 기본 원칙
  - Basic Memory의 검색 결과는 완전한 논문식 citation 시스템은 아님
  - 대신 "원문으로 돌아갈 수 있는 최소 추적성"을 강하게 보존함
- 핵심 출처 축
  - `permalink`: 논리 주소이며 후속 `read_note`, `build_context`, `move_note` 등의 식별자 역할을 함
  - `file_path`: 실제 파일 위치이며 사람이 로컬 저장소에서 직접 원문을 찾는 데 필요함
  - `matched_chunk`: vector 또는 hybrid 검색에서 실제로 유사도가 높았던 텍스트 조각임
  - FTS-only hybrid 결과도 비어 있지 않도록 `content_snippet`을 fallback으로 채움
- 인덱스 단위 설계
  - 이 정보는 단순 entity 결과에만 붙지 않음
  - 검색 인덱스 자체가 entity, observation, relation을 모두 row로 저장함
  - 각 row가 parent entity의 `file_path`, 자체 `permalink`, type-specific metadata를 가짐
  - 그래서 검색 결과는 "문서 하나"가 아니라 "문서 안의 사실"이나 "문서 안의 관계"까지 별도 row로 추적 가능함
- matched chunk 처리
  - vector search는 chunk-level similarity를 구한 뒤 search row 기준으로 다시 묶음
  - 작은 노트는 note 전체를 matched chunk로 줌
  - 큰 노트는 상위 관련 chunk 여러 개만 이어 붙임
  - 검색 결과가 왜 나왔는지를 사용자가 바로 역추적할 수 있게 설계돼 있음

### 코드 근거 예시

- `src/basic_memory/repository/search_index_row.py`
  - `permalink`, `file_path`, `metadata`, `matched_chunk_text` 필드를 가짐
  - `content`는 4000자까지만 노출함
- `src/basic_memory/services/search_service.py`
  - entity, observation, relation 각각을 별도 `SearchIndexRow`로 인덱싱함
  - observation과 relation도 parent file path를 보존함
- `src/basic_memory/repository/search_repository_base.py`
  - vector search에서 chunk-level similarity를 row-level score로 집계함
  - 작은 노트는 전체 content를, 큰 노트는 top 5 chunk를 `matched_chunk_text`로 만듦
  - hybrid 결과에서 FTS-only row도 `matched_chunk_text`를 채움
- `src/basic_memory/api/v2/utils.py`
  - API 응답 `SearchResult`에 `permalink`, `file_path`, `matched_chunk`, relation/entity 정보까지 매핑함
- `src/basic_memory/schemas/search.py`
  - `SearchResult`가 `matched_chunk`, `file_path`, `permalink`, `from_entity`, `to_entity`를 노출함
- `src/basic_memory/mcp/tools/search.py`
  - text 출력에서는 `matched_chunk`를 200자까지 보여 줌

### 제품 적용 포인트

- 검색 결과에는 최소한 `논리 주소`, `실제 파일 위치`, `매칭 근거 텍스트` 세 축이 함께 있어야 환각 억제에 도움이 됨
- 벡터 검색을 쓴다면 "왜 이 문서가 뽑혔는지"를 chunk 수준으로 남기는 편이 실제 사용성에 중요함
- entity만 보여 주는 단순 검색보다 observation, relation까지 검색 row로 올려두면 디버깅과 provenance가 훨씬 좋아짐

### 해석과 시사점

- Basic Memory는 citation-heavy 연구 시스템은 아니지만, "찾은 결과를 다시 열어볼 수 있어야 한다"는 실무 기준은 충족한다
- 특히 permalink와 file path를 함께 남기는 점이 local-first 제품에 잘 맞는다
- 반대로 graph traversal 결과의 relation summary는 recursive query에서 빈 permalink를 내려주는 구현이 있어, 검색 결과만큼 강한 출처성을 모든 문맥 결과에 동일하게 보장하지는 않는다

## 4. 컨텍스트 윈도우 관리는 정교한 토큰 계산보다 제품 상수와 기본값으로 운영한다

### 채택 기술 구조

- 운영 원칙
  - Basic Memory는 LLM 컨텍스트 예산을 초정밀 토큰 계산기로 다루기보다, 제품 상수와 페이지네이션 기본값으로 안정적으로 제어함
  - 관리 방식은 네 층으로 나뉨
- 첫째, 결과 수 제한
  - search API와 MCP tool의 기본 `page_size`는 10
  - context API와 MCP tool의 기본 `page_size`도 10
  - API는 항상 `page_size + 1`개를 먼저 가져와 `has_more`만 계산하고, 실제 응답은 요청 개수만 반환함
- 둘째, related expansion 제한
  - `build_context()`와 memory API는 기본 `max_related=10`
  - relation traversal depth는 기본 1이며, MCP tool 설명에서는 1-3을 권장함
  - timeframe 기본값도 MCP `build_context()`에서는 `"7d"`라서 오래된 전체 히스토리를 무한정 끌어오지 않음
- 셋째, candidate pool과 최종 반환 분리
  - vector search는 candidate pool과 returned context를 따로 관리함
  - internal candidate limit은 `max(semantic_vector_k, (limit + offset) * 10)`으로 넉넉히 잡음
  - 하지만 최종 반환은 다시 page 단위로 자름
  - filter-only recheck는 `VECTOR_FILTER_SCAN_LIMIT = 50000`까지 허용해 recall을 보정함
- 넷째, preview와 chunk 수 제한
  - `TOP_CHUNKS_PER_RESULT = 5`
  - `SMALL_NOTE_CONTENT_LIMIT = 2000`
  - `SearchIndexRow.CONTENT_DISPLAY_LIMIT = 4000`
  - MCP text formatter는 `matched_chunk[:200]`만 보여 줌
- 구조적 의미
  - 이 제품은 "후보 생성은 넉넉하게, 최종 노출은 보수적으로"라는 운영 원칙을 택하고 있음

### 코드 근거 예시

- `src/basic_memory/api/v2/routers/search_router.py`
  - `page_size + 1` fetch 후 `has_more`를 계산함
- `src/basic_memory/api/v2/routers/memory_router.py`
  - `page_size=10`, `max_related=10` 기본값으로 context API를 노출함
- `src/basic_memory/mcp/tools/search.py`
  - 기본 `page_size=10`
  - 출력 포맷에서 `matched_chunk`는 200자까지만 보여 줌
- `src/basic_memory/mcp/tools/build_context.py`
  - 기본 `page_size=10`, `max_related=10`, `timeframe="7d"`
  - depth 1-3을 권장함
- `src/basic_memory/repository/search_repository_base.py`
  - `TOP_CHUNKS_PER_RESULT = 5`
  - `SMALL_NOTE_CONTENT_LIMIT = 2000`
  - `candidate_limit = max(self._semantic_vector_k, (limit + offset) * 10)`
- `src/basic_memory/repository/search_index_row.py`
  - `CONTENT_DISPLAY_LIMIT = 4000`

### 제품 적용 포인트

- 실전 제품에서는 토큰 예산을 전부 동적으로 계산하기보다, page size와 preview 상수로 1차 제어하는 편이 단순하고 안정적임
- retrieval candidate 수와 최종 응답 수를 분리하면 recall과 latency를 동시에 관리하기 쉬움
- graph expansion도 depth와 max_related를 별도 파라미터로 분리해야 검색 결과 폭주를 막을 수 있음

### 해석과 시사점

- Basic Memory의 컨텍스트 관리 방식은 "정밀 최적화"보다 "보수적 운영 규칙"에 가깝다
- 이 접근은 구현이 단순하고 디버깅이 쉽다
- 반대로 모델별 토큰 예산, tool chain 길이, 응답 포맷 차이를 세밀하게 반영하는 동적 budgeter는 아직 강하지 않다

## 5. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- hybrid와 graph traversal이 잘 분리돼 있지만, initial retrieval recall이 약하면 후속 문맥 품질도 같이 약해진다
- `memory://`는 강한 논리 주소지만 hard reference ID 시스템은 아니므로 title/path/permalink 해석 정책의 영향을 받는다
- 검색 결과 provenance는 실용적이지만 완전한 citation graph나 passage-level source map은 아니다
- page size와 preview 길이는 상수 중심이라, 모델별 토큰 budget을 정밀하게 맞추는 시스템과는 거리가 있다
- context traversal의 relation row는 검색 응답만큼 풍부한 provenance를 주지 않는 구현 구간이 있다

### 제품 해석

- Basic Memory의 강점은 검색 엔진 자체보다 "검색 결과를 다시 탐색 가능한 문맥 구조로 연결하는 방식"에 있다
- 이 제품은 범용 QA RAG보다 지식 주소 체계와 그래프 확장을 갖춘 memory infrastructure에 더 가깝다
- 따라서 벤치마킹 초점도 retrieval 모델 종류보다 `주소 체계`, `검색-문맥 분리`, `출처 보존`, `상수 기반 budget 운영`에 두는 편이 맞다

# 적용 인사이트

우리 제품이 Basic Memory에서 바로 가져와 볼 만한 것은 검색 정확도 알고리즘 자체보다, 검색 결과를 지식 주소와 문맥 흐름으로 재사용하게 만드는 인터페이스 설계다. 핵심은 `hybrid retrieval`, `graph traversal`, `memory:// 같은 논리 주소`, `permalink/file_path/matched_chunk 기준의 provenance`, `page size와 chunk 상수로 운영하는 budget 규칙`을 한 세트로 묶는 것이다.

- 검색은 "정답 생성"이 아니라 "좋은 시작점 찾기"로 정의하는 편이 좋음
- 후속 문맥 확장은 검색 랭킹 로직과 분리된 별도 계층으로 두는 편이 유지보수에 유리함
- LLM 도구 체인에 재사용 가능한 주소 체계가 없으면 세션이 길어질수록 탐색 품질이 무너질 가능성이 큼
- provenance는 거대한 citation 시스템이 아니어도 `permalink`, `file_path`, `matched_chunk`만 제대로 남겨도 체감 품질이 크게 올라감
- 토큰 예산은 완전 동적 최적화보다 `page_size=10`, `max_related=10`, `top_chunks=5` 같은 제품 상수부터 먼저 설계하는 편이 실용적임
