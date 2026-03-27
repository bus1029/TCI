# 4. GitNexus 확장성과 컨텍스트 폭발 제어 아키텍처 분석

## 도입 개요
GitNexus는 대형 저장소를 다룰 때 "모든 것을 한 번에 메모리에 올리지 않는 것"과 "에이전트에게 모든 검색 결과를 그대로 넘기지 않는 것"을 동시에 설계 원칙으로 둡니다. 현재 구현 기준의 확장성은 무제한 병렬화보다 메모리 상한 관리, 순차적 DB 접근, 단계별 생명주기 정리에 더 가깝습니다.

본 문서는 실제 코드 기준으로 GitNexus가 인덱싱 파이프라인, KuzuDB 접근, 검색 랭킹, 에이전트 응답 포맷에서 어떻게 병목과 컨텍스트 폭발을 제어하는지 정리합니다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 경로 스캔 분리와 청크 파싱으로 인덱싱 메모리 상한 관리

### 채택 기술 구조
- 저장소 스캔 단계에서 파일 내용을 읽지 않고 경로와 크기만 먼저 수집함
- `filesystem-walker.ts`에서 512KB 초과 파일을 기본적으로 파싱 대상에서 제외함
- `pipeline.ts`에서 파싱 가능한 파일을 총 20MB 바이트 예산 단위 청크로 묶음
- 각 청크만 읽고 파싱한 뒤 바로 해제하는 흐름 사용
- 순차 파싱 경로에서 Tree-sitter 버퍼 크기를 파일 크기의 2배 기준으로 계산하고 512KB~32MB 범위로 제한함
- `analyze.ts`에서 V8 힙 제한이 부족하면 `--max-old-space-size=8192`로 재실행함

### 코드 근거 예시
- `gitnexus/src/core/ingestion/filesystem-walker.ts`
  - `walkRepositoryPaths()`에서 `ScannedFile { path, size }`만 수집함
  - `MAX_FILE_SIZE = 512 * 1024` 초과 파일 경고 후 건너뜀
- `gitnexus/src/core/ingestion/pipeline.ts`
  - `CHUNK_BYTE_BUDGET = 20 * 1024 * 1024` 사용
  - 청크별 `readFileContents() -> processParsing() -> astCache.clear()` 순서 적용
  - 청크 종료 후 `chunkContents`, `chunkFiles`, 추출 결과를 스코프 밖으로 밀어냄
- `gitnexus/src/core/ingestion/constants.ts`
  - `getTreeSitterBufferSize(contentLength)`에서 2배 버퍼 계산 후 512KB~32MB 범위 제한
- `gitnexus/src/cli/analyze.ts`
  - `ensureHeap()`에서 8GB 힙 미확보 시 재실행함

### 제품 적용 포인트
- 인덱싱 경로 확인 시 [analyze.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/cli/analyze.ts), [pipeline.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/ingestion/pipeline.ts), [filesystem-walker.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/ingestion/filesystem-walker.ts), [constants.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/ingestion/constants.ts) 함께 확인 필요
- 메모리 제어 핵심은 AST 자체 최적화보다 내용 읽기 지연과 청크 단위 파이프라인에 있음

### 해석과 시사점
- GitNexus 확장성 기반은 대형 저장소 전체 동시 처리보다 상한이 있는 작업 단위 분할에 있음
- 경로 스캔과 내용 읽기 분리 구조는 저장소 규모가 커질수록 효과 확대
- 512KB 초과 파일 건너뛰기는 안정성 확보 대신 일부 대형 소스 파일 분석 누락 가능성 동반

## 2. AST 캐시와 워커 생명주기 정리로 네이티브 메모리 누수 완화

### 채택 기술 구조
- AST 캐시를 무제한 맵이 아니라 `lru-cache` 기반으로 관리함
- 캐시 축출 시 `dispose` 훅에서 `tree.delete?.()` 호출
- `pipeline.ts`에서 청크 종료마다 `astCache.clear()` 호출
- 워커 풀을 청크마다 새로 만들지 않고 재사용 후 마지막에 `terminate()`로 정리함

### 코드 근거 예시
- `gitnexus/src/core/ingestion/ast-cache.ts`
  - `createASTCache()`의 `LRUCache.dispose`에서 `(tree as any).delete?.()` 호출
- `gitnexus/src/core/ingestion/pipeline.ts`
  - 청크 루프 안에서 `astCache.clear()` 반복 호출
  - `finally` 블록에서 `workerPool?.terminate()` 보장

### 제품 적용 포인트
- 파싱 단계 메모리 이슈 확인 시 [ast-cache.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/ingestion/ast-cache.ts)와 [pipeline.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/ingestion/pipeline.ts) 함께 확인 필요
- 이 캐시는 장기 보관용이 아니라 한 청크 안 재사용용 단기 캐시라는 점이 핵심

### 해석과 시사점
- GitNexus는 AST 장기 축적보다 짧은 사용 후 즉시 정리 전략 우선
- 이 구조는 메모리 압박 완화에 유리하지만 청크 경계 너머 재사용 이점 일부 포기

## 3. KuzuDB 단일 세션 직렬화로 멀티레포 전환과 쓰기 충돌 제어

### 채택 기술 구조
- Kuzu 접근에서 모듈 전역 `db`, `conn`, `currentDbPath` 공유
- 저장소 전환과 쿼리 실행을 동시에 허용하지 않는 구조 채택
- `kuzu-adapter.ts`에서 `sessionLock` 기반 직렬화 계층 사용
- 그래프 적재를 순차 `COPY` 중심으로 진행함
- FTS 검색도 단일 연결 경로에서는 `Promise.all` 대신 순차 실행 사용

### 코드 근거 예시
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - `sessionLock`과 `runWithSessionLock()`으로 DB 전환과 작업 실행 직렬화
  - `withKuzuDb(dbPath, operation)`에서 활성 DB를 맞춘 뒤 같은 락 범위 안에서 실행
  - `loadGraphToKuzu()`에서 노드 CSV와 관계 CSV를 순차 `COPY`로 적재
- `gitnexus/src/core/search/bm25-index.ts`
  - repoId 경로에서 FTS를 병렬 호출하지 않고 순차 호출
  - 주석으로 단일 연결과 교착 상태 회피 의도 명시

### 제품 적용 포인트
- 멀티레포 환경과 Kuzu 접근 방식 확인 시 [kuzu-adapter.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/kuzu/kuzu-adapter.ts), [bm25-index.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/search/bm25-index.ts) 확인 필요
- HTTP 서버와 MCP 백엔드 모두 같은 직렬화 계층 위에서 동작함
- 고부하 상황 병목은 대체로 Kuzu 앞단에서 발생

### 해석과 시사점
- GitNexus는 동시성 최적화보다 무결성과 안정성 우선
- 이 선택은 레포 전환 중 커넥션 충돌과 잘못된 DB 핸들 재사용 위험 완화
- 대신 쓰기 집약 구간에서는 병렬 처리량 제한 발생

## 4. RRF 결합과 결과 상한으로 검색 결과 폭발을 제어

### 채택 기술 구조
- 하이브리드 검색에서 BM25 FTS와 의미 검색 결과를 그대로 합치지 않고 RRF로 재정렬함
- `mergeWithRRF()`에서 두 결과 집합을 `filePath` 기준으로 병합함
- `score = 1 / (60 + rank)` 계열 점수로 다시 정렬함
- HTTP 검색 API에서 `limit` 기본값 10, 범위 1~100 적용
- 임베딩 준비 전에는 의미 검색을 강제하지 않고 FTS 전용 경로로 전환함

### 코드 근거 예시
- `gitnexus/src/core/search/hybrid-search.ts`
  - `RRF_K = 60` 사용
  - `mergeWithRRF()`에서 재정렬 후 `slice(0, limit)` 적용
  - `hybridSearch()`에서 BM25와 의미 검색 결과를 RRF로 병합
- `gitnexus/src/server/api.ts`
  - `/api/search`에서 `limit` 기본값 10, 최대값 100 강제
  - 임베더 준비 시에만 `hybridSearch()` 호출
  - 미준비 시 `searchFTSFromKuzu()`로 대체

### 제품 적용 포인트
- 검색 확장성과 결과 품질 확인 시 [hybrid-search.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/search/hybrid-search.ts), [bm25-index.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/search/bm25-index.ts), [api.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/server/api.ts) 함께 읽기 권장
- 검색 품질 개선 포인트는 임베딩 자체보다 결과 수 상한과 병합 방식에도 있음

### 해석과 시사점
- GitNexus는 검색 포괄 범위를 무한히 키우기보다 작은 결과 묶음 안에서 우선순위를 정교하게 조정하는 방식 선택
- 이 구조는 토큰 낭비 완화에 유리하지만 넓은 탐색이 필요할 때는 사용자가 limit을 의식적으로 조정해야 함

## 5. 프로세스 중심 응답 포맷으로 에이전트 컨텍스트 비용 절감

### 채택 기술 구조
- MCP `query` 도구에서 단순 파일 매치 목록 대신 검색 결과를 프로세스 단위로 그룹화해 반환함
- 기본 파라미터로 `limit = 5`, `max_symbols = 10`, `include_content = false` 사용
- 처음부터 큰 본문을 싣지 않는 방향으로 설계됨
- 내부 검색량도 `processLimit * maxSymbolsPerProcess`로 계산해 상한 설정
- 최종 반환 시 독립 정의는 최대 20개로 제한
- 프로세스 심벌은 ID 기준으로 중복 제거

### 코드 근거 예시
- `gitnexus/src/mcp/tools.ts`
  - `query` 도구 설명에서 프로세스 그룹형 결과와 기본 파라미터 명시
- `gitnexus/src/mcp/local/local-backend.ts`
  - `processLimit = params.limit || 5`
  - `maxSymbolsPerProcess = params.max_symbols || 10`
  - `searchLimit = processLimit * maxSymbolsPerProcess`
  - `definitions.slice(0, 20)`으로 독립 정의 수 제한
  - `process_symbols` ID 중복 제거

### 제품 적용 포인트
- 에이전트 친화적 응답 형식 확인 시 [tools.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/mcp/tools.ts), [local-backend.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/mcp/local/local-backend.ts) 중심 확인 권장
- 핵심은 단순 검색 정확도보다 LLM이 실제로 소비 가능한 응답 구조 설계에 있음

### 해석과 시사점
- GitNexus는 검색 엔진이자 동시에 에이전트용 응답 압축 계층 역할 수행
- 프로세스 단위 그룹화, 기본 본문 비포함, 정의 수 제한은 모두 토큰 비용 절감을 위한 설계로 해석 가능

## 6. 워커 IPC와 병적 파일 처리 시간을 상한으로 묶는 보호 장치

### 채택 기술 구조
- 워커 풀을 CPU 개수 기준으로 생성하되 최대 8개로 제한함
- 각 워커에 맡은 파일 전체를 한 번에 보내지 않고 `SUB_BATCH_SIZE = 1500` 단위 서브배치로 분할 전달
- 각 서브배치에 30초 타임아웃 적용
- 비정상 파일 하나가 워커를 장시간 점유하는 상황을 실패로 전환함
- 워커 스크립트 부재나 실패 시 순차 대체 경로로 전환 가능

### 코드 근거 예시
- `gitnexus/src/core/ingestion/workers/worker-pool.ts`
  - 풀 크기 `Math.min(8, Math.max(1, os.cpus().length - 1))`
  - `SUB_BATCH_SIZE = 1500`
  - `SUB_BATCH_TIMEOUT_MS = 30_000`
  - 서브배치 완료 신호 후 다음 배치 전달하는 체인 구조 사용
- `gitnexus/src/core/ingestion/pipeline.ts`
  - 워커 풀 생성 실패 시 경고 후 순차 대체 경로 사용

### 제품 적용 포인트
- 대형 저장소에서 워커 불안정이나 OOM 확인 시 [worker-pool.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/ingestion/workers/worker-pool.ts), [pipeline.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/core/ingestion/pipeline.ts) 함께 확인 필요
- GitNexus의 워커는 처리량 확대 도구이면서 동시에 보호 장치가 포함된 보수적 병렬화 계층으로 보는 편이 정확함

### 해석과 시사점
- 이 설계는 평균 처리량보다 최악 사례 방어에 더 초점
- 특히 난독화 파일이나 비정상 초대형 파일이 전체 인덱싱을 멈추게 하지 않도록 상한을 강제한 점이 실무적임

## 7. 임베딩 단계는 선택적 무거운 작업으로 분리하고 규모가 크면 자동 건너뛴다

### 채택 기술 구조
- 임베딩은 기본 활성 기능이 아니라 `--embeddings` 옵션 사용 시에만 수행
- 노드 수 50,000개 초과 시 임베딩 단계 자동 건너뜀
- 기존 인덱스 임베딩 캐시가 있으면 먼저 읽어와 재삽입함
- 이후 부족한 부분만 새로 계산함
- 검색 단계에서도 임베딩 미준비 시 즉시 FTS 전용 경로로 전환함

### 코드 근거 예시
- `gitnexus/src/cli/analyze.ts`
  - `EMBEDDING_NODE_LIMIT = 50_000`
  - 기존 인덱스 존재 시 `loadCachedEmbeddings()`로 캐시 복원
  - `EMBED_BATCH = 200` 단위 재삽입
  - 노드 수 초과 시 임베딩 단계 건너뜀
- `gitnexus/src/server/api.ts`
  - `isEmbedderReady()`가 false면 의미 검색 없이 FTS만 사용

### 제품 적용 포인트
- 임베딩은 검색 품질뿐 아니라 인덱싱 비용에도 직접 영향
- [analyze.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/cli/analyze.ts), [api.ts](/Users/seokhyunbae_1/Desktop/projects_study/GitNexus/gitnexus/src/server/api.ts) 함께 보는 편이 적절
- 대형 사내 코드베이스에서는 항상 켜는 구조보다 규모 기준 건너뛰기와 캐시 복원 구조가 운영 현실에 더 가까움

### 해석과 시사점
- GitNexus는 의미 검색을 필수 기반 기능으로 강제하지 않음
- 덕분에 대형 저장소에서도 동작 유지 가능
- 대신 검색 품질은 FTS 중심으로 후퇴할 수 있음

## 8. 한계와 절충점

### 현재 구현 기준에서 주의할 점
- 현재 `analyze` 메인 경로는 기존 Kuzu 파일 삭제 후 다시 적재하는 전체 재인덱싱 방식
- `deleteNodesForFile()` 같은 파일 단위 삭제 헬퍼는 존재하지만 기본 흐름은 부분 증분 업데이트 중심 아님
- 512KB 초과 파일 건너뛰기와 Tree-sitter 최대 버퍼 제한은 안정성 강화 대신 분석 완전성 일부 희생
- Kuzu 접근 직렬화는 충돌 완화에 유리하지만 쓰기 병렬화에는 불리
- HTTP 검색은 최대 100건 허용 구조라 호출자가 큰 값을 주면 응답 크기 자체는 다시 커질 수 있음

### 제품 해석
- GitNexus 확장성 전략은 완전한 온라인 증분 인덱서나 대규모 분산 검색 시스템과는 다름
- 현재 구현은 로컬 환경에서 안정적으로 돌아가는 상한 제어형 인덱서이자 에이전트 응답 압축용 실용 검색 계층으로 이해하는 편이 가장 정확함

# 적용 인사이트

- 대형 코드베이스 인덱싱에서는 더 빠른 파서보다 경로 스캔 분리, 바이트 예산 청크, 청크 종료 후 즉시 해제가 먼저임
- 임베디드 DB 사용 시 단일 커넥션 직렬화 계층을 명시적으로 두는 편이 멀티레포 전환과 무결성 유지에 유리함
- 하이브리드 검색에서는 모델 품질 자체보다 결과 수 상한과 재랭킹 정책이 실제 에이전트 성능에 더 직접적 영향을 줄 수 있음
- 에이전트용 검색 인터페이스에서는 원시 결과 목록보다 프로세스 그룹화, 기본 본문 제외, 정의 수 제한 같은 응답 구조 설계가 중요함
- 워커 병렬화는 처리량 최적화 수단이면서 동시에 서브배치, 타임아웃, 대체 경로를 갖춘 보호 장치여야 함
- 임베딩은 항상 켜는 기능보다 저장소 규모와 비용에 따라 선택적으로 켜고 캐시로 보강하는 단계로 분리하는 편이 현실적임
