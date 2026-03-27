# 3. GitNexus 검색 엔진 및 외부 저장소 아키텍처 분석

## 도입 개요
GitNexus의 검색 계층은 "중앙 검색 서버"보다 "레포 로컬 인덱스 + 공통 질의 계층"에 가깝습니다. 각 저장소는 자체 `.gitnexus/kuzu` 인덱스를 가지며, 검색은 그 위의 KuzuDB FTS를 기본으로 하고, 선택적으로 임베딩 기반 semantic 검색을 얹습니다. 여기에 전역 레지스트리와 멀티레포용 read-only 연결 계층을 더해 MCP, HTTP, 웹 UI가 같은 인덱스를 재사용합니다.

본 문서는 실제 코드 기준으로 GitNexus가 검색 저장소를 어떻게 구성하는지, FTS와 semantic 검색을 어떤 층위로 결합하는지, 그리고 멀티레포 환경에서 외부 에이전트와 웹 인터페이스를 어떻게 연결하는지를 정리합니다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 임베디드 KuzuDB를 검색 저장소로 쓰고 CSV bulk load로 적재 비용을 줄이는 구조
외부 그래프 DB 서버를 전제로 하지 않고, 각 저장소 가까이에 임베디드 검색 저장소를 둔 뒤 bulk load로 인덱싱 비용을 제어합니다.

### 채택 기술 구조
- GitNexus는 외부 그래프 DB 서버를 두지 않고 각 레포의 `.gitnexus/kuzu`를 KuzuDB 파일로 직접 엶
- 인덱싱 시 인메모리 그래프를 row-by-row로 넣지 않고 먼저 CSV로 스트리밍한 뒤 `COPY`로 적재함
- 노드 CSV는 타입별로 적재하고 관계 CSV는 `fromLabel|toLabel` 쌍별로 다시 분해해 순차 로딩함
- 적재 실패 시에는 `IGNORE_ERRORS=true` 재시도와 개별 edge insert fallback으로 Kuzu의 물리 제약을 적재 계층에서 흡수함

### 코드 근거 예시
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - `doInitKuzu()`가 `new kuzu.Database(dbPath)`와 `new kuzu.Connection(db)`로 로컬 DB를 직접 엶
  - `loadGraphToKuzu()`가 `streamAllCSVsToDisk()` 결과를 받아 노드별 `COPY`를 수행함
  - 관계는 `rel_${fromLabel}_${toLabel}.csv`로 쪼갠 뒤 `COPY CodeRelation ... (from="X", to="Y")` 형태로 적재함
- `gitnexus/src/core/kuzu/csv-generator.ts`
  - 노드와 관계를 메모리 배열이 아니라 CSV 파일로 스트리밍함

### 제품 적용 포인트
- 검색 엔진이 로컬 개발 도구에 가까운 제품이라면 중앙 DB보다 레포 근처에 임베디드 DB를 두는 편이 배포와 삭제, 재생성이 단순함
- 그래프 적재가 큰 경우 애플리케이션 레벨 반복 `INSERT`보다 CSV 스트리밍 + 엔진의 bulk loader를 먼저 검토하는 편이 유리함
- 관계형 제약이 까다로운 그래프 엔진을 쓴다면 논리 스키마와 물리 적재 포맷을 분리해서 설계해야 함

### 해석과 시사점
- GitNexus의 검색 성능은 "검색 알고리즘" 이전에 "적재 비용을 낮춰 자주 재인덱싱할 수 있게 한 구조"에 많이 의존함
- 이 방식은 실용적이지만 CSV escaping, pair별 분해, cleanup, fallback insert 같은 적재 보조 로직을 함께 관리해야 함

## 2. FTS를 기본 검색으로 두고 여러 노드 테이블 결과를 파일 단위로 병합하는 구조
검색의 기본 경로는 벡터 검색이 아니라 FTS이며, 여러 노드 타입에서 나온 결과를 파일 단위로 다시 합쳐 상위 랭킹을 만듭니다.

### 채택 기술 구조
- GitNexus의 기본 텍스트 검색은 KuzuDB FTS임
- 인덱싱 완료 후 `File`, `Function`, `Class`, `Method`, `Interface`에 대해 각각 별도 FTS 인덱스를 만듦
- 검색 시에는 각 테이블의 FTS 결과를 조회한 뒤 `filePath` 기준으로 합산해 최종 랭킹을 만듦
- 앱 메모리 캐시를 두지 않고 DB를 직접 읽는 방식이라 인덱스가 다시 만들어지면 검색 결과도 즉시 그 상태를 반영함

### 코드 근거 예시
- `gitnexus/src/cli/analyze.ts`
  - 인덱싱 뒤 `createFTSIndex('File', 'file_fts', ['name', 'content'])` 등으로 다섯 개 FTS 인덱스를 생성함
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - `loadFTSExtension()`이 `INSTALL fts`, `LOAD EXTENSION fts`를 처리함
  - `queryFTS()`가 `CALL QUERY_FTS_INDEX(...)`를 감싸고 결과를 `{ nodeId, name, filePath, score }` 형태로 정규화함
- `gitnexus/src/core/search/bm25-index.ts`
  - `searchFTSFromKuzu()`가 다섯 FTS 인덱스를 순차 조회하고 `filePath` 기준으로 점수를 합산함

### 제품 적용 포인트
- 코드 검색에서 "항상 동작하는 기본 검색"은 FTS처럼 준비 비용이 낮고 의존성이 적은 계층이 맡는 편이 안정적임
- 파일과 심벌을 모두 검색해야 할 때는 하나의 거대한 색인보다 GitNexus처럼 테이블별 색인을 두고 결과 병합 규칙을 명시하는 방식이 유지보수에 유리함
- 검색 결과를 파일 단위로 다시 합치는 전략은 UI가 파일 브라우징 중심일 때 특히 잘 맞음

### 해석과 시사점
- GitNexus의 텍스트 검색은 벡터 검색이 없어도 충분히 돌아가도록 설계돼 있음
- 대신 BM25 단계에서 `filePath` 기준으로 병합하므로 동일 파일 안의 어떤 심벌이 핵심 매치였는지는 후속 조회가 필요함

## 3. 임베딩을 별도 테이블로 분리하고 RRF로 FTS와 결합하는 하이브리드 검색 구조
의미 검색은 독립적인 주 저장소가 아니라 보강 계층으로 붙어 있으며, 벡터 저장과 결합 규칙도 기본 검색과 분리되어 있습니다.

### 채택 기술 구조
- semantic 검색은 기본 경로가 아니라 선택적 보강 계층임
- 임베딩은 메인 노드 테이블에 직접 저장하지 않고 `CodeEmbedding`이라는 별도 node table에 `nodeId`와 `embedding`만 저장함
- semantic 검색은 `QUERY_VECTOR_INDEX('CodeEmbedding', 'code_embedding_idx', ...)`로 수행하고, FTS 결과와는 `RRF`로 결합함
- 재인덱싱 시에는 기존 `CodeEmbedding`을 먼저 읽어 재삽입하고, `skipNodeIds`로 이미 임베딩된 노드를 건너뛰는 증분 경로를 지원함

### 코드 근거 예시
- `gitnexus/src/core/embeddings/embedding-pipeline.ts`
  - `batchInsertEmbeddings()`가 `CREATE (e:CodeEmbedding {nodeId: $nodeId, embedding: $embedding})`를 사용함
  - `createVectorIndex()`가 `CALL CREATE_VECTOR_INDEX('CodeEmbedding', 'code_embedding_idx', 'embedding', metric := 'cosine')`를 호출함
  - `runEmbeddingPipeline()`가 `skipNodeIds`를 받아 이미 임베딩된 노드를 필터링함
- `gitnexus/src/core/search/hybrid-search.ts`
  - `mergeWithRRF()`가 BM25와 semantic 결과를 `RRF_K = 60` 기준으로 결합함
- `gitnexus/src/mcp/local/local-backend.ts`
  - `semanticSearch()`가 `distance < 0.6` 필터를 적용하고, 결과 node를 다시 조회해 이름과 파일 위치를 붙임
- `gitnexus/src/cli/analyze.ts`
  - 재빌드 전 `loadCachedEmbeddings()`로 기존 임베딩을 읽고, 그래프 재적재 뒤 cached embedding을 재삽입함

### 제품 적용 포인트
- 벡터를 메인 엔티티에 바로 붙이면 재색인 때 쓰기 비용이 커지므로 GitNexus처럼 별도 테이블로 분리하는 방식이 운영상 유리함
- semantic 검색은 "기본 검색을 대체"하기보다 FTS를 보완하는 계층으로 두는 편이 실패 허용성이 높음
- 재임베딩 비용이 큰 시스템이라면 전체 그래프 재생성과 임베딩 재생성을 같은 정책으로 다루지 말고 계층별로 분리해야 함

### 해석과 시사점
- GitNexus의 하이브리드 검색은 벡터 DB 중심 구조가 아니라 FTS 중심 구조에 semantic 레이어를 얹는 방식임
- 이 설계는 로컬 도구에 적합하지만 semantic 품질과 latency는 모델 준비 여부, 임베딩 수, threshold 정책에 영향을 받음

## 4. 레포별 로컬 인덱스와 전역 레지스트리를 결합해 멀티레포 검색을 제공하는 구조
저장은 저장소별로 분산하고, 탐색과 질의 인터페이스만 통합하는 방식으로 멀티레포 검색을 구현합니다.

### 채택 기술 구조
- 각 레포는 자체 `.gitnexus/` 아래에 인덱스를 저장하고, 전역 discovery는 `~/.gitnexus/registry.json`으로 통합함
- MCP와 HTTP는 모두 이 전역 레지스트리를 읽어 검색 대상 레포를 찾지만, 실제 DB 접근 방식은 동일하지 않음
- MCP 쪽 `LocalBackend`는 레포별 KuzuDB를 lazy init하고, repo ID별 read-only connection pool을 유지함
- HTTP REST 쪽은 요청마다 레지스트리에서 대상 레포를 고른 뒤 core `withKuzuDb()` 경로로 단일 레포 DB를 엶
- 따라서 멀티레포 discovery는 공통이지만, 쿼리 실행 계층은 `MCP pool`과 `core adapter`로 이원화되어 있음

### 코드 근거 예시
- `gitnexus/src/storage/repo-manager.ts`
  - `getStoragePaths()`가 `.gitnexus/kuzu`, `.gitnexus/meta.json` 경로를 계산함
  - `registerRepo()`가 `~/.gitnexus/registry.json`에 `{ name, path, storagePath, indexedAt, lastCommit, stats }`를 기록함
- `gitnexus/src/mcp/local/local-backend.ts`
  - `refreshRepos()`가 전역 레지스트리를 읽어 in-memory repo map을 만듦
  - `ensureInitialized()`가 실제 질의 시점에만 `initKuzu(repo.id, handle.kuzuPath)`를 호출함
- `gitnexus/src/mcp/core/kuzu-adapter.ts`
  - repo별로 `Database`와 connection pool을 보관함
  - `MAX_POOL_SIZE = 5`, `MAX_CONNS_PER_REPO = 8`, `IDLE_TIMEOUT_MS = 5 * 60 * 1000`으로 풀 정책을 둠
  - `new kuzu.Database(dbPath, 0, false, true)`로 read-only 모드로 엶
- `gitnexus/src/server/api.ts`
  - `resolveRepo()`가 전역 레지스트리에서 대상 레포를 고름
  - `/api/search`, `/api/query`, `/api/graph`는 `withKuzuDb(kuzuPath, ...)`로 단일 레포 core adapter를 사용함

### 제품 적용 포인트
- 여러 코드베이스를 한 도구에서 다뤄야 하지만 중앙 집중형 인프라는 피하고 싶다면 "레포 로컬 저장 + 전역 레지스트리" 조합이 실용적임
- 멀티레포 discovery와 실제 DB 연결 정책을 분리하면, 인터페이스는 통합하되 런타임 성격이 다른 경로를 독립적으로 최적화할 수 있음
- 특히 read-only pool이 필요한 경로와 단일 세션 경로를 같은 계층으로 뭉뚱그리지 않는 편이 운영상 안전함
- 멀티레포 도구에서는 "어떤 레포를 검색 중인지"를 명시적으로 해석하는 계층이 꼭 필요함

### 해석과 시사점
- GitNexus는 저장은 분산시키고 discovery는 통합하지만, 질의 경로까지 완전히 단일화하지는 않았음
- 이 방식은 프라이버시와 배포 단순성에 강하지만, `MCP 경로`와 `HTTP core 경로`의 동작 차이를 문서와 운영에서 분명히 관리해야 함

## 5. 외부 인터페이스는 읽기 전용 보호장치와 경량 API로 감싼 구조
외부 에이전트가 직접 검색 계층을 호출할 수 있게 열어 두되, 쓰기 연산과 무제한 쿼리 노출은 방지하는 보호장치를 함께 둡니다.

### 채택 기술 구조
- MCP 경로는 외부 입력이 직접 쓰기 쿼리로 이어지지 않도록 강하게 제한함
- `cypher` 질의는 write 키워드 정규식으로 1차 차단하고, MCP용 Kuzu pool도 read-only로 엶
- MCP 검색 후속 조회는 `executeParameterized()`와 label 검증을 써서 안전한 범위 안에서 메타데이터를 다시 가져옴
- HTTP 서버는 기본적으로 `127.0.0.1`에 바인딩하고 CORS도 localhost와 배포 UI 도메인으로 제한함
- 다만 HTTP `/api/query`는 현재 구현 기준으로 MCP처럼 write regex 차단을 두지 않고 core adapter에 raw Cypher를 전달함

### 코드 근거 예시
- `gitnexus/src/mcp/local/local-backend.ts`
  - `CYPHER_WRITE_RE`가 `CREATE|DELETE|SET|MERGE|REMOVE|DROP|ALTER|COPY|DETACH`를 차단함
  - `cypher()`가 write query를 거부하고 read-only 지식 그래프라고 명시적으로 응답함
  - semantic 검색 후 노드 조회, BM25 후속 조회는 `executeParameterized()`를 사용함
  - semantic 결과의 label은 `VALID_NODE_LABELS`로 검증함
- `gitnexus/src/mcp/core/kuzu-adapter.ts`
  - `initKuzu()`가 MCP용 DB를 read-only 모드로 엶
- `gitnexus/src/server/api.ts`
  - `createServer()`가 기본 host를 `127.0.0.1`로 둠
  - `/api/search`는 임베딩 준비 여부에 따라 hybrid 또는 FTS-only를 선택함
  - `/api/query`는 전달받은 `cypher`를 `withKuzuDb(..., () => executeQuery(cypher))`로 실행함

### 제품 적용 포인트
- 로컬 지식 그래프를 외부 에이전트에 노출할 때는 `MCP 읽기 전용 경로`와 `HTTP raw query 경로`를 같은 수준의 안전 모델로 간주하면 안 됨
- 읽기 전용 DB와 쿼리 레벨 차단은 함께 둘 때 가장 효과가 크며, 둘 중 하나만 있으면 보호 수준이 달라짐
- 검색 API는 하이브리드 검색이 준비되지 않은 경우의 fallback 경로를 반드시 가져야 함
- 외부 인터페이스는 중앙 검색 서비스처럼 크게 만들기보다 GitNexus처럼 핵심 기능만 얇게 노출하는 편이 유지보수에 유리함

### 해석과 시사점
- GitNexus의 보호 계층은 인터페이스별로 다르며, 특히 MCP 쪽이 더 보수적으로 설계돼 있음
- 덕분에 MCP는 에이전트 도구로 쓰기 안전한 편이지만, HTTP raw query 경로는 로컬 호스트 제약 외에도 별도 validation 정책을 더 둘 여지가 있음

## 6. 한계와 trade-off

### 현재 구현 기준에서 주의할 점
- FTS는 인덱싱 후 생성되지만 `analyze.ts`에서 best-effort로 처리되므로 실패해도 전체 인덱싱은 완료될 수 있음
- semantic 검색은 임베딩이 준비된 경우에만 활성화되며, 미준비 시에는 FTS-only fallback으로 동작함
- BM25 결과 병합 기준이 `filePath`라서 파일 내부의 세밀한 심벌 랭킹은 후속 질의가 필요함
- 레포 저장 위치와 전역 레지스트리가 분리돼 있어 둘 중 하나가 깨지면 discovery가 어긋날 수 있음
- MCP와 HTTP가 같은 질의 계층을 공유하는 것이 아니라는 점을 문서화하지 않으면 실제 보호 수준을 과장하게 됨
- 현재 HTTP `/api/query`는 MCP처럼 write 차단이 없으므로, "모든 외부 인터페이스가 읽기 전용"이라고 쓰면 현재 코드와 맞지 않음
- 멀티레포 read-only pool은 유용하지만 rebuild와 질의가 겹칠 때 lock retry나 일시적 unavailable 상태가 발생할 수 있음

### 제품 해석
- GitNexus의 검색 아키텍처는 "FTS를 기본으로 빠르게 동작시키고, semantic과 멀티레포를 점진적으로 얹는 구조"로 요약할 수 있음
- 이 구조는 중앙 인프라 없는 로컬 도구에는 잘 맞지만, 검색 품질과 운영 단순성보다 기능 확장을 계속 늘리면 레이어 간 복잡도가 빠르게 커질 수 있음

# 사내 지식 베이스 구축 시 벤치마킹 인사이트
- 코드 검색 제품은 처음부터 중앙형 벡터 플랫폼으로 가기보다 GitNexus처럼 레포 로컬 인덱스와 기본 FTS를 먼저 갖추는 편이 현실적임
- 임베딩은 메인 엔티티와 분리하고 FTS를 대체하지 않는 보강 레이어로 두는 설계가 운영 리스크를 줄임
- 멀티레포 지원이 필요해도 저장을 중앙화할 필요는 없고, 전역 레지스트리와 read-only pool만으로도 상당한 수준의 통합 검색이 가능함
- 외부 에이전트 연동이 목표라면 검색 품질뿐 아니라 write query 차단, prepared statement, host/CORS 제한, raw query 경로 분리 같은 인터페이스 보호장치를 같이 설계해야 함
