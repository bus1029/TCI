# 최적화된 검색 파이프라인과 저장소 아키텍처 분석

## 개요

AnythingLLM의 검색 저장소 구조는 단순한 `RDBMS + Vector DB` 조합이 아니다. 현재 구현을 기준으로 보면 파싱된 문서 원문은 디스크의 JSON 문서로 보관하고, 워크스페이스와 문서의 관계는 Prisma 스키마로 관리하며, 실제 벡터 값은 선택한 벡터 저장소에 넣는 3계층 구조를 기본으로 삼는다. 다만 이 구조는 벡터 백엔드 선택에 따라 물리 배치가 달라질 수 있다. 예를 들어 기본 조합인 SQLite + LanceDB에서는 저장 공간이 분리되지만, `pgvector`를 선택하면 메타데이터와 벡터가 모두 PostgreSQL 계열에 놓인다.

또한 현재 코드에서 가장 강하게 구현된 캐시는 LLM 응답 캐시보다 임베딩 재사용 캐시다. 따라서 AnythingLLM을 벤치마킹할 때는 슬로건보다 실제 코드가 보장하는 설계 단위를 기준으로 이해하는 편이 맞다.

처음 보는 사람이 이 문서에서 먼저 이해해야 할 전제는 아래와 같다.

- AnythingLLM은 문서 원문, 관계 메타데이터, 실제 벡터 값을 서로 다른 책임 계층에 나눠 저장하려는 구조를 기본으로 삼음
- 검색은 전역 단위가 아니라 workspace namespace 안에서 먼저 범위를 좁히고 그 안에서 문맥을 조합함
- 검색 최적화는 vector DB 하나로 끝나지 않고 pinned docs, parsed files, similarity search, prompt compression까지 이어지는 체인으로 구성됨
- 현재 구현에서 비용 최적화의 핵심 캐시는 답변 텍스트보다 임베딩 재사용 캐시임
- 저장 구조와 검색 품질은 분리해서 봐야 하며, 저장 구조만 좋아도 검색 품질이 자동으로 보장되지는 않음

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| 문서 원문 저장 | `collector`가 만든 JSON 문서를 디스크에 보관하는 계층 |
| Prisma 메타데이터 | 문서와 워크스페이스의 연결, 최소 메타데이터, 벡터 매핑을 관리하는 관계형 계층 |
| vector namespace | 워크스페이스별 검색 범위를 나누는 벡터 저장소 내부 논리 공간 |
| `workspace_documents` | 어떤 문서가 어떤 워크스페이스에 연결됐는지 관리하는 테이블 |
| `document_vectors` | 문서 ID와 실제 벡터 ID를 연결하는 브리지 테이블 |
| vector cache | 이미 계산한 임베딩 청크를 디스크에 저장해 재사용하는 캐시 |
| prompt compression | 검색 결과와 히스토리를 모델 컨텍스트 한도에 맞게 줄이는 단계 |

처음 읽을 때는 아래 흐름으로 이해하면 된다.

1. `collector`가 파싱된 문서 JSON을 디스크에 저장함
2. `server`가 문서를 워크스페이스에 연결하고 청킹 및 임베딩을 수행함
3. 실제 벡터는 선택된 vector DB provider에 저장되고, `document_vectors`에는 문서 ID와 벡터 ID 매핑만 남김
4. 채팅 시에는 workspace namespace 존재 여부와 문서 수를 먼저 확인함
5. pinned docs, parsed files, similarity search 결과를 합쳐 프롬프트를 만들고 모델 한도에 맞게 압축함

예를 들어 워크스페이스에 문서가 추가되고 이후 검색이 일어날 때의 흐름은 아래처럼 볼 수 있다.

```text
문서 JSON 저장
-> workspace_documents 연결
-> TextSplitter 청킹
-> vector DB 적재
-> document_vectors 매핑 저장
-> 채팅 시 namespace 범위 검색
-> prompt compression
```

즉 이 문서의 핵심 질문은 "벡터 DB를 무엇으로 쓰는가"보다 "원문, 메타데이터, 벡터, 검색 문맥 조립을 어떻게 나눠 관리하는가"다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 파일 시스템, Prisma 메타데이터, 벡터 저장소를 분리하는 기본 구조

### 채택 기술 구조

- AnythingLLM은 파싱이 끝난 문서를 먼저 디스크에 JSON 형태로 저장함
- `collector`는 문서를 처리한 뒤 `server/storage/documents` 아래에 결과를 기록함
- `server`는 그 파일의 상대 경로를 기준으로 워크스페이스 연결을 관리함
- 관계형 DB에는 원문 전체를 넣지 않고 문서 식별자, 워크스페이스 연결 정보, 최소 메타데이터만 남김
- 벡터 값과 유사도 검색은 별도 벡터 저장소에 위임함
- 파싱 산출물은 `collector/utils/files/index.js`의 `writeToServerDocuments()`를 통해 `server/storage/documents`에 JSON으로 저장됨
- 서버는 `server/utils/files/index.js`의 `fileData()`로 해당 JSON을 다시 읽어 임베딩에 사용함
- `server/prisma/schema.prisma`의 `workspace_documents`는 `docId`, `docpath`, `workspaceId`, `metadata` 같은 연결 정보 위주로 유지됨
- `server/prisma/schema.prisma`의 `document_vectors`는 문서와 벡터 ID의 매핑만 저장함
- 실제 벡터 값은 `server/utils/vectorDbProviders/*` 구현체가 각 provider namespace에 적재함

### 코드 근거 예시

- `collector/processRawText/index.js`
  - `pageContent`, `token_count_estimate`, `chunkSource` 등을 포함한 문서 객체를 만들고 디스크에 저장함
- `server/models/documents.js`
  - `addDocuments()`가 디스크 문서를 읽은 뒤 `VectorDb.addDocumentToNamespace()`를 호출하고, 성공 시에만 `workspace_documents` 레코드를 생성함
- `server/storage/README.md`
  - 이 저장소 아래에 `documents`, `vector-cache`, `lancedb`, `anythingllm.db`가 놓인다고 명시함

### 제품 적용 포인트

- 원문과 메타데이터를 한 저장소에 몰아넣지 말고 역할별로 분리하는 편이 운영에 유리함
- 문서 자체는 파일 또는 오브젝트 스토리지에 두고 서비스 로직은 `docId`, `docpath` 같은 안정적인 참조값으로 움직이게 설계하는 편이 좋음
- 검색 결과 삭제와 재색인을 고려하면 문서 논리 ID와 벡터 물리 ID를 처음부터 분리해 두는 편이 안전함

### 해석과 시사점

- 이 구조의 장점은 ORM이 무거운 원문 저장 책임을 떠안지 않는다는 점임
- 반면 "항상 3개의 물리 저장소가 완전히 분리된다"라고 설명하면 과장임
- 현재 구현은 기본적으로 분리 지향이지만 `pgvector`처럼 벡터 백엔드 선택에 따라 물리 분리가 약해질 수 있음

## 2. 워크스페이스 네임스페이스 중심으로 검색 범위를 줄이는 질의 파이프라인

### 채택 기술 구조

- AnythingLLM의 검색은 먼저 워크스페이스 단위로 범위를 좁힌 뒤 그 안에서만 컨텍스트를 조합하는 방식으로 동작함
- 채팅 시점에는 곧바로 전역 검색을 하지 않고 해당 워크스페이스의 벡터 namespace 존재 여부와 문서 수를 먼저 확인함
- 이후 pinned document, parsed file, vector similarity search 결과를 합쳐 최종 컨텍스트를 만듦
- 마지막에 LLM 프롬프트 윈도우에 맞게 압축함
- `server/utils/chats/stream.js`는 `VectorDb.hasNamespace()`와 `namespaceCount()`로 검색 가능 상태를 먼저 확인함
- `query` 모드에서 벡터가 없거나 검색 결과가 비어 있으면 일반 답변을 만들지 않고 조기 종료함
- pinned document는 `server/utils/DocumentManager/index.js`에서 문서 파일을 직접 읽어 미리 컨텍스트에 주입함
- parsed file은 `workspace_parsed_files` 흐름으로 별도 주입되며 일반 워크스페이스 문서와 구분됨
- similarity search는 `similarityThreshold`, `topN`, `vectorSearchMode`를 기준으로 provider 구현체에 위임됨
- 최종 프롬프트는 `server/utils/helpers/chat/index.js`의 `messageArrayCompressor()`가 모델 컨텍스트 한도에 맞춰 압축함

### 코드 근거 예시

- `server/utils/chats/stream.js`
  - pinned docs, parsed files, vector search 결과를 순서대로 합친 뒤 `LLMConnector.compressMessages()`를 호출함
- `server/utils/DocumentManager/index.js`
  - pinned 문서 누적 토큰이 `maxTokens`를 넘기면 더 이상 컨텍스트에 넣지 않음
- `server/utils/helpers/chat/index.js`
  - 시스템 프롬프트, 히스토리, 사용자 프롬프트를 서로 다른 비율로 압축함

### 제품 적용 포인트

- 테넌트 또는 워크스페이스 단위 namespace 분리는 검색 범위 축소와 권한 경계 형성에 동시에 유리함
- 벡터 검색 전에 검색 가능한 상태인지 빠르게 판단하는 조기 종료 분기를 두면 불필요한 LLM 호출을 줄일 수 있음
- 검색 파이프라인은 벡터 검색만으로 끝내지 말고 pinned context, 세션 첨부 문맥, 히스토리 압축까지 하나의 흐름으로 봐야 함

### 해석과 시사점

- AnythingLLM의 검색 최적화는 단순히 벡터 DB를 붙인 데서 나오지 않음
- 워크스페이스 범위 제한, 조기 거절, `topN` 제한, 프롬프트 압축이 함께 묶여 있어야 검색 속도와 컨텍스트 안정성이 같이 나옴

## 3. 현재 구현의 핵심 캐시는 DB 응답 캐시가 아니라 디스크 기반 임베딩 재사용이다

### 채택 기술 구조

- 문서를 다시 임베딩할 때 가장 비싼 단계는 embedding API 호출임
- AnythingLLM은 이 비용을 줄이기 위해 최종 LLM 답변을 캐시하는 대신 이미 벡터화된 청크 묶음을 `server/storage/vector-cache`에 저장해 재사용함
- 벡터 provider 구현체는 문서 추가 전에 먼저 `cachedVectorInformation()`을 조회함
- 캐시가 있으면 새 벡터를 다시 계산하지 않고 기존 청크 값을 재삽입함
- `server/utils/files/index.js`의 `cachedVectorInformation()`은 문서 경로 기반 `uuidv5` 키로 캐시 파일 존재 여부를 확인함
- `storeVectorResult()`는 벡터화된 청크 배열을 JSON으로 디스크에 저장함
- `server/utils/vectorDbProviders/lance/index.js`
- `server/utils/vectorDbProviders/pinecone/index.js`
- `server/utils/vectorDbProviders/pgvector/index.js`
- 위 구현들은 모두 `addDocumentToNamespace()` 초반에 캐시를 먼저 조회함
- 캐시 히트 시 새 `vectorId`를 발급한 뒤 바로 provider에 upsert 함

### 코드 근거 예시

- `server/utils/vectorDbProviders/lance/index.js`
  - 캐시 히트 시 청크 메타데이터에서 기존 ID를 제거하고 새 UUID를 발급해 삽입함
- `server/utils/vectorDbProviders/pinecone/index.js`
- `server/utils/vectorDbProviders/pgvector/index.js`
  - 같은 흐름을 반복함
- `server/jobs/sync-watched-documents.js`
  - 문서 내용이 바뀐 경우 `skipCache = true`로 재색인해 캐시를 갱신함

### 제품 적용 포인트

- 가장 비싼 단계가 임베딩이면 응답 텍스트보다 임베딩 결과물 캐싱이 비용 절감 효과를 더 직접적으로 낼 수 있음
- 캐시 키를 문서 경로로 잡을지 내용 해시로 잡을지는 운영 정책에 따라 의도적으로 결정해야 함
- 재색인 잡이 있다면 캐시 우회와 캐시 재생성 경로를 함께 마련해야 함

### 해석과 시사점

- 현재 구현을 기준으로 보면 "DB 단 응답 캐싱 레이어가 핵심이다"라는 설명은 맞지 않음
- `cache_data` 테이블과 모델은 존재하지만 주력 워크스페이스 채팅 경로인 `server/utils/chats/stream.js`에는 이를 읽거나 쓰는 흐름이 없음
- 즉 AnythingLLM이 실제로 강하게 구현한 것은 일반 LLM 답변 캐시보다 임베딩 재사용 캐시임

## 4. LLM, 임베딩, Vector DB를 교체하기 위한 선택 함수와 공통 계약 계층

### 채택 기술 구조

- AnythingLLM은 벤더별 구현을 직접 호출하지 않고 중앙 선택 함수에서 provider 인스턴스를 결정함
- LLM, embedding engine, vector DB가 각각 별도 팩토리 함수로 분리돼 있음
- 벡터 저장소는 공통 베이스 클래스 계약을 따름
- 이 덕분에 상위 로직은 구체 벤더명을 거의 몰라도 됨
- `server/utils/helpers/index.js`의 `getVectorDbClass()`가 벡터 저장소를 선택함
- 같은 파일의 `getEmbeddingEngineSelection()`이 임베딩 엔진을 선택함
- 같은 파일의 `getLLMProvider()`가 채팅 모델 provider를 선택함
- `server/utils/vectorDbProviders/base.js`는 `addDocumentToNamespace()`, `deleteDocumentFromNamespace()`, `performSimilaritySearch()` 같은 공통 메서드 계약을 정의함
- 실제 구현은 `server/utils/AiProviders/*`, `server/utils/EmbeddingEngines/*`, `server/utils/vectorDbProviders/*`에 분리돼 있음

### 코드 근거 예시

- `stream.js`, `apiChatHandler.js`, `documents.js`
  - 모두 구체 벤더 클래스를 직접 import 하지 않고 선택 함수를 통해 인스턴스를 받음
- `workspace.chatProvider`, `workspace.chatModel`
  - 워크스페이스 단에서 LLM 선택을 덮어쓸 수 있음
- 벡터 저장소 선택
  - 주로 `VECTOR_DB` 환경변수에 의해 결정됨

### 제품 적용 포인트

- 벤더 교체가 잦은 제품이라면 상위 서비스 로직에서 provider별 SDK를 직접 참조하지 않는 구조가 유리함
- 공통 계약은 실제로 필요한 최소 메서드 집합만 정의하는 편이 좋음
- LLM, embedding, vector DB를 한 추상화에 몰아넣기보다 별도 선택 축으로 나누면 조합 가능성이 높아짐

### 해석과 시사점

- 이 구조는 분명한 adapter 또는 factory 패턴에 가깝다
- 다만 이를 "무중단 교체"라고 표현할 때는 주의가 필요함
- 현재 구현은 코드 변경 없는 설정 전환에는 강하지만, 실제 운영 중 벡터 데이터를 다른 백엔드로 옮기는 데이터 마이그레이션이나 인덱스 준비까지 자동으로 해결하지는 않음

## 5. 고아 벡터를 방지하기 위한 문서-벡터 브리지 테이블

### 채택 기술 구조

- 문서 삭제 시 중요한 일은 워크스페이스 문서 레코드만 지우는 것이 아니라 그 문서에서 파생된 벡터 ID를 정확히 찾아 함께 제거하는 일임
- AnythingLLM은 이를 위해 `document_vectors`를 별도 유지함
- 문서 임베딩이 끝나면 각 청크의 `vectorId`를 `docId`와 함께 저장함
- 삭제 시에는 이 브리지 정보를 사용해 provider에서 정확한 벡터만 제거함
- `server/models/vectors.js`의 `bulkInsert()`가 다수의 `docId`-`vectorId` 매핑을 저장함
- `server/models/documents.js`의 `removeDocuments()`는 먼저 `VectorDb.deleteDocumentFromNamespace()`를 호출함
- 이후 `workspace_documents`와 `document_vectors` 레코드를 함께 삭제함
- 각 provider의 `deleteDocumentFromNamespace()`는 `DocumentVectors.where({ docId })`로 물리 벡터 ID 목록을 얻어 삭제함

### 코드 근거 예시

- `server/utils/vectorDbProviders/pgvector/index.js`
  - 브리지 테이블에서 꺼낸 `vectorId` 목록만 SQL로 삭제함
- `server/utils/vectorDbProviders/pinecone/index.js`
- `server/utils/vectorDbProviders/lance/index.js`
  - 같은 개념으로 문서별 벡터 삭제를 수행함

### 제품 적용 포인트

- 문서 삭제 정확도가 중요하면 `문서 1건 삭제 = 관련 벡터 전부 삭제`를 추적할 별도 브리지 테이블이 필요함
- 벡터 저장소 내부 ID를 애플리케이션이 직접 관리해야 세밀한 정리 작업이 가능함
- 검색 품질보다 먼저 정합성과 삭제 비용을 고려하면 이 계층은 초기에 넣는 편이 낫다

### 해석과 시사점

- 이 구조는 운영비 통제와 데이터 정합성 측면에서 실용적임
- 특히 외부 벡터 DB를 쓰는 경우 문서 삭제가 곧바로 비용 절감과 연결되기 때문에 이런 보조 관계 설계는 단순 편의 기능이 아니라 운영 필수 기능에 가까움

## 6. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- `cache_data` 테이블은 존재하지만 현재 주력 워크스페이스 채팅 검색 경로의 응답 캐시로 연결돼 있지 않음
- 기본 아키텍처는 저장소 분리를 지향하지만 `pgvector`를 선택하면 물리 계층이 다시 합쳐질 수 있음
- 벡터 캐시는 내용 해시가 아니라 문서 경로 기반이라 경로가 달라지면 같은 내용이어도 캐시 미스가 날 수 있음
- provider 전환은 선택 함수로 쉬워졌지만 데이터 마이그레이션과 인덱스 준비는 별도 운영 절차가 필요함
- 검색 품질은 저장소 구조만으로 보장되지 않고 `topN`, threshold, pinned docs, prompt compression 설정과 함께 움직임

### 제품 해석

- AnythingLLM에서 가져올 포인트는 "삼원화"라는 구호보다 디스크 원문 보관, 관계 메타데이터 관리, 벡터 ID 브리지, 임베딩 재사용 캐시, provider 선택 함수 같은 구체 패턴임
- 우리 시스템에 적용할 때도 이 패턴을 그대로 옮기되 응답 캐시가 정말 필요하다면 별도 계층으로 명시적으로 설계하는 편이 맞음

## 적용 인사이트

- 무거운 원문은 파일 또는 오브젝트 스토리지에 두고 RDBMS는 제어 평면 역할에 집중시키는 구조가 안정적임
- 벡터 삭제 정합성을 위해 `docId`와 `vectorId`를 잇는 브리지 테이블은 초기에 설계해 두는 편이 좋음
- 비용 절감이 목적이라면 일반 응답 캐시보다 임베딩 결과 캐시가 더 직접적인 효과를 낼 수 있음
- 검색 파이프라인은 namespace 분리, 조기 거절, context 조립, 프롬프트 압축까지 하나의 체인으로 설계해야 함
- adapter 계층은 반드시 필요하지만 백엔드 교체를 실제 운영 수준에서 쉽게 만들려면 마이그레이션 도구와 캐시 무효화 정책까지 함께 설계해야 함
