# 2. GitNexus 저장소 및 인덱싱 아키텍처 분석

## 도입 개요
GitNexus의 인덱싱은 단순히 메모리에서 그래프를 만든 뒤 한 번 저장하는 흐름이 아닙니다. 저장소 단위로 `.gitnexus/` 아래에 로컬 인덱스를 만들고, 그래프를 CSV로 스트리밍한 뒤 KuzuDB에 bulk load하며, 그 위에 FTS와 선택적 벡터 인덱스를 추가합니다. 여기에 전역 레지스트리와 멀티레포 연결 관리까지 얹어, "각 레포는 로컬에 독립 저장하되 하나의 MCP/HTTP 서버가 여러 레포를 서비스"하는 구조를 완성합니다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 레포 내부 인덱스 + 전역 레지스트리를 결합한 로컬 우선 저장 구조

### 채택 기술 구조
- GitNexus는 중앙 서버에 모든 인덱스를 몰아넣지 않고, 각 Git 저장소 루트 아래 `.gitnexus/`를 만들어 해당 레포 전용 인덱스를 둠
- 로컬 저장의 핵심 산출물은 Kuzu 데이터베이스 파일 경로인 `.gitnexus/kuzu`와 메타데이터 파일 `.gitnexus/meta.json`임
- 동시에 여러 레포를 하나의 MCP 서버에서 다루기 위해 사용자 홈의 `~/.gitnexus/registry.json`에 "어떤 레포가 어디에 인덱싱됐는지"를 별도 등록함
- 저장은 레포 단위로 분산되고 discovery는 전역 레지스트리로 통합되는 2단 구조임

### 코드 근거 예시
- `gitnexus/src/storage/repo-manager.ts`
  - `getStoragePaths()`가 `.gitnexus/kuzu`, `.gitnexus/meta.json` 경로를 계산함
  - `registerRepo()`가 `~/.gitnexus/registry.json`에 `{ name, path, storagePath, indexedAt, lastCommit, stats }`를 기록함
  - `addToGitignore()`가 `.gitnexus`를 `.gitignore`에 추가함
- `gitnexus/src/cli/analyze.ts`
  - 인덱싱 완료 후 메타데이터 저장과 레지스트리 등록 수행
- `gitnexus/src/cli/list.ts`
  - 전역 레지스트리를 읽어 인덱싱된 레포 목록 표시

### 제품 적용 포인트
- 코드 지식 베이스를 제품에 붙일 때는 "인덱스 자체는 워크스페이스 가까이에", "워크스페이스 목록은 별도 디스패처에" 두는 구조가 운영상 유리함
- 이렇게 하면 레포별 휴대성과 삭제·재생성 단순성을 유지하면서도 상위 서비스는 멀티레포를 자연스럽게 지원 가능

### 해석과 시사점
- GitNexus의 저장 전략은 멀티테넌트 중앙 DB보다 로컬 우선 아키텍처에 가까움
- 이 방식은 배포와 프라이버시에 유리하지만 전역 레지스트리가 깨졌을 때 discovery 계층이 분리되어 있다는 점은 운영 측면에서 별도 관리 필요

## 2. 메모리 사용량을 통제하는 청크 기반 인덱싱 파이프라인

### 채택 기술 구조
- 저장소 전체를 한 번에 메모리에 올리지 않고 스캔과 구조 분석은 먼저 수행한 뒤 파싱 가능한 파일만 바이트 예산 기준 청크로 나눠 처리함
- 기본 청크 예산은 `20MB` 소스 기준이며 각 청크는 읽기 → 파싱 → 관계 추출 → 해제 흐름으로 진행됨
- 워커 풀 사용 시 파일 묶음을 다시 서브배치로 나눠 `postMessage`하고 각 서브배치에 타임아웃을 둬 병적인 파일이 전체 파이프라인을 붙잡지 못하게 함
- 심벌 해석과 import 해석은 `SymbolTable`, `ImportMap`, import resolution context를 청크 바깥에서 유지해 청크 분할 때문에 전체 해석이 무너지지 않게 함
- AST는 `LRUCache` 기반 캐시에 넣어 필요한 범위만 유지하고 청크 경계에서는 캐시 크기를 강하게 제한함

### 코드 근거 예시
- `gitnexus/src/core/ingestion/pipeline.ts`
  - `CHUNK_BYTE_BUDGET = 20 * 1024 * 1024`
  - parseable 파일만 모아 byte-budget chunk를 구성함
  - `createWorkerPool()`을 한 번 만들고 청크마다 재사용함
- `gitnexus/src/core/ingestion/workers/worker-pool.ts`
  - `SUB_BATCH_SIZE = 1500`
  - `SUB_BATCH_TIMEOUT_MS = 30_000`
- `gitnexus/src/core/ingestion/ast-cache.ts`
  - `LRUCache`로 AST 관리
  - clear 시 런타임별로 안전하게 tree 삭제 시도

### 제품 적용 포인트
- 대형 코드베이스 인덱싱에서는 "한 번에 전부 읽기"보다 "저장소 스캔과 청크 단위 파싱 분리" 방식이 훨씬 안전함
- 워커를 쓴다면 파일 단위 병렬화만이 아니라 structured clone 비용을 제한하는 서브배치 규칙도 꼭 필요함

### 해석과 시사점
- GitNexus의 인덱싱 강점은 단순 병렬화보다 "메모리 상한을 먼저 정해놓고 파이프라인 전체를 그 한도 안에 맞추는 것"에 있음
- 이 구조는 전역 심벌 해석을 유지하기 위해 일부 보조 인덱스를 장수시켜야 하므로 구현은 단일 패스보다 복잡해짐

## 3. 인메모리 그래프를 바로 INSERT하지 않고 CSV 스트리밍 후 Kuzu `COPY`로 적재

### 채택 기술 구조
- 그래프를 Kuzu에 row-by-row로 밀어 넣기보다 먼저 CSV 파일들로 스트리밍한 뒤 Kuzu의 `COPY`를 사용해 bulk load함
- 노드 CSV는 타입별로 따로 만들고 관계는 전체 CSV 하나를 만든 뒤 다시 `FROM|TO` 레이블 쌍별로 분해해 적재함
- 이는 Kuzu가 관계 테이블에서 출발·도착 레이블 조합을 명시적으로 요구하기 때문임
- CSV 생성 시에는 원본 파일 내용을 전부 메모리에 쥐고 있지 않고 파일 내용을 디스크에서 lazy read하며 LRU 캐시로 재사용함
- File 노드는 전체 내용 일부를, 심벌 노드는 line range 기반 snippet을 저장해 쿼리와 검색에 활용 가능하게 함

### 코드 근거 예시
- `gitnexus/src/core/kuzu/csv-generator.ts`
  - `streamAllCSVsToDisk()`가 노드와 관계를 CSV로 직접 스트리밍함
  - `FileContentCache`가 파일 내용을 lazy read + LRU 캐시함
  - `File`은 최대 10000자, 심벌 snippet은 최대 5000자까지 잘라 저장함
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - `loadGraphToKuzu()`가 node CSV들을 순차 `COPY`함
  - 관계 CSV를 line-by-line으로 읽어 `fromLabel|toLabel`별 파일로 다시 나누고 `COPY CodeRelation ... (from="X", to="Y")` 수행
  - `COPY` 실패 시 `IGNORE_ERRORS=true` 재시도와 마지막 fallback insert 제공

### 제품 적용 포인트
- 그래프 적재가 큰 경우 애플리케이션 레벨 반복 `INSERT`보다 CSV 스트리밍 + 엔진의 bulk loader 우선 검토하는 편이 좋음
- 다형성 관계를 지원하는 그래프 엔진이라도 물리 적재 제약은 남을 수 있으므로 GitNexus처럼 논리 스키마와 적재 포맷 분리해서 생각해야 함
- 코드 검색과 브라우징을 위해 원문을 저장할 때는 전체 파일을 무제한 넣기보다 File·심벌별로 다른 절단 전략 두는 편이 현실적임

### 해석과 시사점
- GitNexus는 저장 엔진의 물리 제약을 피하지 않고 CSV 스트리밍 계층을 둬서 흡수함
- 이 구조는 매우 실용적이지만 CSV escaping, 관계 pair 분할, cleanup 같은 유지보수 포인트가 추가됨

## 4. FTS와 벡터 인덱스를 분리한 하이브리드 인덱싱 구조

### 채택 기술 구조
- GitNexus의 기본 검색 기반은 Kuzu FTS임
- `File`, `Function`, `Class`, `Method`, `Interface`에 대해 별도 FTS 인덱스를 만들고 검색 시 여러 결과를 `filePath` 기준으로 합산함
- 의미 검색은 선택적임
  - 임베딩을 켜면 `CodeEmbedding`이라는 별도 node table에 벡터 저장
  - 여기에 vector index 생성
- 그래프 노드 본체와 임베딩 벡터는 같은 테이블에 같이 박혀 있지 않고 `nodeId`로 연결된 두 레이어로 분리됨
- 하이브리드 검색은 BM25 계열 FTS 결과와 semantic 결과를 `RRF`로 결합함

### 코드 근거 예시
- `gitnexus/src/cli/analyze.ts`
  - 인덱싱 후 `createFTSIndex('File', 'file_fts', ...)` 등으로 FTS 생성
  - `--embeddings` 옵션이 있을 때만 임베딩 파이프라인 수행
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - `loadFTSExtension()`, `createFTSIndex()`, `queryFTS()` 구현
- `gitnexus/src/core/embeddings/embedding-pipeline.ts`
  - `CodeEmbedding`에 `CREATE (e:CodeEmbedding {nodeId, embedding})`
  - `CALL CREATE_VECTOR_INDEX('CodeEmbedding', 'code_embedding_idx', 'embedding', metric := 'cosine')`
- `gitnexus/src/core/search/bm25-index.ts`
  - 각 FTS index를 순차 조회하고 `filePath` 기준으로 병합함
- `gitnexus/src/core/search/hybrid-search.ts`
  - BM25와 semantic 결과를 `RRF_K = 60` 기준으로 합침

### 제품 적용 포인트
- 키워드 검색과 의미 검색을 같이 가져가려면 벡터를 메인 노드 테이블에 직접 업데이트하기보다 GitNexus처럼 별도 테이블로 분리하는 설계가 운영상 유리함
- FTS를 "항상 신선한 기본 검색", 벡터를 "선택적 보강"으로 두면 임베딩 모델이 준비되지 않아도 제품 기능이 망가지지 않음

### 해석과 시사점
- GitNexus의 하이브리드 검색은 구조 그래프 위에 벡터를 덧칠하는 구조이지 벡터 DB 중심 구조는 아님
- 이는 로컬 개발 도구로서 매우 합리적이지만 semantic 품질은 임베딩 준비 여부와 모델 크기에 영향 받음

## 5. 임베딩 재사용과 항상-신선한 검색을 동시에 노리는 증분 전략

### 채택 기술 구조
- 인덱스를 다시 만들 때 기존 `CodeEmbedding` 테이블의 벡터를 먼저 읽어와 재삽입하는 방식으로 재임베딩 비용 줄임
- 변경되지 않은 노드는 `skipNodeIds`로 걸러 재계산 생략 가능
- BM25와 FTS 쪽은 별도 앱 캐시를 두지 않고 Kuzu 인덱스를 직접 질의해 "디스크에 반영된 현재 상태"를 바로 읽음

### 코드 근거 예시
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - `loadCachedEmbeddings()`가 기존 `CodeEmbedding` 노드들을 모두 읽어옴
- `gitnexus/src/cli/analyze.ts`
  - rebuild 전 임베딩 캐시를 읽고 그래프 재적재 후 `executeWithReusedStatement()`로 다시 넣음
  - 노드 수가 `50,000`을 넘으면 임베딩을 자동 건너뛰는 제한이 있음
- `gitnexus/src/core/search/bm25-index.ts`
  - "always fresh, reads from disk" 설계에 맞게 DB 직접 질의

### 제품 적용 포인트
- 대형 코드베이스에서 임베딩은 가장 비싼 후처리이므로 GitNexus처럼 "그래프는 재적재하더라도 벡터는 최대한 재사용"하는 계층을 두는 편이 좋음
- 반대로 텍스트 검색은 앱 캐시 대신 저장 엔진의 인덱스를 직접 질의하면 신선도 관리가 단순해짐

### 해석과 시사점
- GitNexus는 모든 인덱스를 똑같이 다루지 않음
- 구조 그래프와 FTS는 재생성 비용이 상대적으로 낮으니 다시 만들고 임베딩은 비용이 크니 재사용 우선하는 계층별 전략 취함

## 6. 멀티레포 서비스와 읽기 전용 연결 풀

### 채택 기술 구조
- `analyze` 단계는 단일 레포의 `.gitnexus/kuzu`를 갱신하지만 MCP/HTTP 질의 단계는 여러 레포를 동시에 다룰 수 있음
- 이를 위해 MCP 쪽은 repoId별로 Kuzu database와 connection pool 관리
- 각 레포는 read-only로 열리고 idle timeout과 LRU eviction으로 오래 안 쓰는 레포 연결은 풀에서 제거됨
- 같은 레포에 대해 동시 질의가 들어오면 하나의 connection을 공유하지 않고 여러 connection을 checkout/checkin하는 방식으로 처리함
- 반면 core adapter 쪽은 analyze나 단일 레포 컨텍스트를 위해 module-level connection 하나를 잡는 구조임

### 코드 근거 예시
- `gitnexus/src/mcp/core/kuzu-adapter.ts`
  - `MAX_POOL_SIZE = 5`
  - `IDLE_TIMEOUT_MS = 5 * 60 * 1000`
  - `MAX_CONNS_PER_REPO = 8`
  - Kuzu를 read-only로 열고 repo별 pool entry 유지
- `gitnexus/src/mcp/local/local-backend.ts`
  - 전역 레지스트리에서 레포 목록을 읽고 레포별 Kuzu 초기화를 지연 수행함

### 제품 적용 포인트
- 저장소는 레포별로 분리하되 질의 서비스는 멀티레포 단일 프로세스로 운영하고 싶다면 GitNexus처럼 "전역 레지스트리 + 레포별 read-only connection pool" 구조가 적합함
- 인덱서와 질의 서버의 connection 전략 분리도 중요함
  - 쓰기 경로와 읽기 경로가 같은 연결 정책을 쓰면 lock 충돌 늘기 쉬움

### 해석과 시사점
- GitNexus는 인덱스 저장과 질의 서비스를 같은 DB 파일 위에서 운영하지만 접근 방식은 명확히 분리함
- 이 점이 로컬 개발 도구로서 실용적이지만 동시에 쓰기와 읽기가 겹칠 때는 lock/retry 정책과 사용자 메시지가 중요해짐

## 7. 한계와 trade-off

### 현재 구현 기준에서 주의할 점
- 저장 구조는 단순하지만 `.gitnexus/`와 `~/.gitnexus/registry.json`이 분리돼 있어 두 계층 모두 관리 필요
- Kuzu의 물리 제약 때문에 논리적으로 단일 관계 모델이라도 적재 단계는 꽤 복잡함
- 임베딩은 별도 테이블로 분리돼 효율적이지만 인덱스 재구성 시 캐시 복원과 skip 로직을 같이 관리해야 함
- BM25와 FTS는 항상 DB를 직접 읽어 신선하지만 테이블별 검색 후 병합하는 비용 존재
- 멀티레포 connection pool은 유연하지만 analyze와 질의가 동시에 일어날 때 lock 재시도나 풀 고갈 같은 운영 이슈 발생 가능

### 제품 해석
- GitNexus의 저장소·인덱싱 전략은 "작고 독립적인 로컬 인덱스를 많이 만들고 그 위에 얇은 통합 계층을 얹는 방식"으로 요약 가능
- 이는 중앙 인프라 의존을 줄이고 로컬 도구 경험을 좋게 만들지만 반대로 파일 시스템 기반 상태 관리와 엔진 제약 흡수 로직이 중요해짐

# 적용 인사이트
- 인덱스 저장 위치와 레포 discovery를 분리해 "로컬 인덱스의 휴대성"과 "멀티레포 서비스"를 동시에 달성하는 구조 검토 가치 높음
- 인메모리 그래프를 바로 DB에 넣지 않고 CSV 스트리밍과 bulk `COPY`를 사이에 두는 적재 계층 도입 검토 필요
- FTS와 벡터를 같은 계층으로 보지 않고 FTS는 기본 검색, 벡터는 선택적 보강, 임베딩은 재사용 우선으로 계층화하는 방식 참고 가치 높음
- 중앙형 지식 저장소를 무조건 먼저 만들기보다 레포 로컬 인덱스와 전역 레지스트리 조합을 검토할 가치 있음
- 벡터를 메인 엔티티에 직접 업데이트하는 대신 별도 테이블로 격리하고 bulk load와 connection pool 전략을 명확히 나누면 대형 코드베이스에서도 더 안정적인 운영 가능
