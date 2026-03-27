# 환각 억제 및 컨텍스트 안정성 분석

## 개요

RAG 시스템에서 환각을 줄이려면 검색된 텍스트의 출처를 모델이 식별할 수 있어야 하고, 동시에 검색 결과와 대화 이력이 모델 입력 한계를 넘지 않도록 런타임에서 잘라내야 한다. AnythingLLM은 이 문제를 하나의 장치로 해결하지 않는다. 문서 인입 단계의 청크 헤더 메타데이터 주입, 벡터 저장 시 메타데이터 보존, 채팅 단계의 source backfill, 워크스페이스 단위 검색 제한값, 모델별 프롬프트 압축기를 조합해 안정성을 확보한다.

처음 보는 사람이 이 문서에서 먼저 이해해야 할 전제는 아래와 같다.

- AnythingLLM의 환각 억제는 프롬프트 문구 하나가 아니라 인덱싱, 검색, 컨텍스트 조립, LLM 호출 전 숏서킷의 조합으로 동작함
- citation 품질과 모델 입력 안정성은 같은 문제가 아니라 연결된 두 문제이며, 이 프로젝트는 둘을 별도 계층에서 함께 다룸
- 현재 검색 결과가 부족해도 후속 질문 품질을 위해 과거 source를 일부 backfill하지만, 그 source를 그대로 UI citation에 다 노출하지는 않음
- 토큰 한계 방어는 워크스페이스 설정값과 provider별 압축기의 이중 구조로 작동함
- `query` 모드에서는 근거가 없을 때 LLM을 아예 호출하지 않는 정책이 들어가 있음

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| 청크 헤더 메타데이터 | 청크 앞에 붙는 `<document_metadata>` 블록 |
| 벡터 메타데이터 | vector DB에 함께 저장되는 문서 메타데이터와 청크 텍스트 |
| source backfill | 현재 검색 결과가 부족할 때 과거 대화의 source를 모델 입력용으로만 보충하는 단계 |
| `topN` | 한 번의 검색에서 가져올 최대 문서 수 |
| `similarityThreshold` | 벡터 검색 결과를 통과시킬 유사도 기준값 |
| prompt compression | 모델 컨텍스트 한도에 맞게 시스템 프롬프트, 히스토리, 사용자 입력을 줄이는 단계 |
| `query` 모드 | 워크스페이스 근거가 없으면 답변을 거절하는 검색 중심 채팅 모드 |

처음 읽을 때는 아래 흐름으로 이해하면 된다.

1. 문서 인입 시 `TextSplitter`가 청크 앞에 출처 헤더를 붙임
2. vector DB 적재 시 청크 본문과 메타데이터를 함께 저장함
3. 채팅 시 현재 벡터 검색 결과, pinned docs, parsed files를 먼저 모음
4. 검색 결과가 부족하면 최근 대화의 source를 모델 입력용으로만 backfill 함
5. 마지막에 모델 한도에 맞춰 프롬프트를 압축하고, `query` 모드면 무근거 상태를 다시 검사함

예를 들어 사용자가 "방금 문서에서 말한 배포 조건 다시 정리해줘" 같은 후속 질문을 했는데 현재 검색 결과가 적게 나오면 파이프라인은 아래처럼 움직인다.

```text
현재 검색 결과 부족
-> 최근 대화의 source backfill
-> 모델 입력 컨텍스트 보강
-> citation 노출은 현재 검색 결과 중심 유지
-> 필요 시 prompt compression
```

즉 이 문서의 핵심 질문은 "모델에게 환각하지 말라고 어떻게 지시하는가"보다 "근거, 문맥, 토큰 한계를 런타임에서 어떻게 함께 통제하는가"다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 청크 단위 출처 보존은 텍스트 헤더와 벡터 메타데이터의 이중 구조로 처리

### 채택 기술 구조

- `TextSplitter.buildHeaderMeta()`는 문서 메타데이터에서 `sourceDocument`, `published`, `source`만 골라 청크 헤더용 구조를 만듦
- `source`는 아무 값이나 넣지 않고 `chunkSource`가 `link://` 또는 `youtube://` 접두사를 가질 때만 추출함
- `TextSplitter.stringifyHeader()`는 이 값을 `<document_metadata> ... </document_metadata>` 블록으로 직렬화해 각 청크 앞부분에 붙임
- 실제 벡터 적재 시에는 청크 본문만 저장하지 않고 `metadata: { ...metadata, text: textChunks[i] }` 형태로 원본 메타데이터와 청크 텍스트를 함께 보존함
- 이 로직은 특정 벡터 DB 하나의 예외 구현이 아니라 `lance`, `pinecone`, `weaviate`, `pgvector`, `qdrant`, `chroma`, `milvus`, `astra` 계열 적재 코드에서 공통으로 사용됨

### 코드 근거 예시

- `server/utils/TextSplitter/index.js`
  - `buildHeaderMeta()`는 `title -> sourceDocument`, `published -> published`, `chunkSource -> source`만 추출함
  - `stringifyHeader()`는 `<document_metadata>` 블록을 청크 앞에 붙임
- `server/utils/vectorDbProviders/lance/index.js`
  - `new TextSplitter({ chunkHeaderMeta: TextSplitter.buildHeaderMeta(metadata) })`
  - 각 벡터에 `metadata: { ...metadata, text: textChunks[i] }`를 함께 저장함
- `server/__tests__/utils/TextSplitter/index.test.js`
  - 청크가 `testing3: <document_metadata>` 형태로 시작하는지 검증함

```js
const chunkHeaderMeta = TextSplitter.buildHeaderMeta(metadata);

return this.#applyPrefix(
  `<document_metadata>\n${content}</document_metadata>\n\n`
);
```

### 제품 적용 포인트

- 청크 분할기에서 출처 헤더를 주입하는 책임과 벡터 저장소에 메타데이터를 보존하는 책임을 분리해야 함
- 인덱싱 파이프라인 어디서든 공통 splitter를 호출하게 만들어야 저장소를 바꿔도 citation 품질이 흔들리지 않음
- 문서 링크가 없는 내부 파일도 고려해 `파일명`, `문서 제목`, `발행일`, `원본 URI`를 별도 필드로 관리하는 편이 좋음

### 해석과 시사점

- AnythingLLM의 장점은 citation 정보를 UI 단계에서 사후 조립하지 않고 청크 생성 시점부터 텍스트와 메타데이터 양쪽에 심어 둔다는 점임
- 다만 현재 구현은 모든 청크에 URL을 강제 삽입하는 구조는 아님
- 로컬 파일처럼 `chunkSource`가 `link://` 또는 `youtube://`가 아니면 `source` 필드는 빠질 수 있으므로 "항상 원본 링크가 들어간다"라고 해석하면 과장임

## 2. 응답 citation 안정성은 현재 검색 결과와 과거 source backfill을 분리해 유지

### 채택 기술 구조

- 채팅 시 서버는 `pinned docs`, `parsed files`, 현재 벡터 검색 결과를 먼저 `contextTexts`에 적재함
- 이어서 `fillSourceWindow()`가 과거 대화 이력의 `sources`를 뒤져 부족한 컨텍스트를 최근 순서대로 backfill함
- 이때 backfill된 텍스트는 모델 입력용 `contextTexts`에는 포함되지만 최종 응답의 노출용 `sources`에는 현재 검색 결과만 주로 남김
- 구현 의도는 후속 질문에서 검색 결과가 부족해도 답변 맥락은 유지하되 사용자에게 갑자기 관련 없어 보이는 과거 citation을 과도하게 노출하지 않으려는 데 있음

### 코드 근거 예시

- `server/utils/chats/stream.js`
  - `contextTexts = [...contextTexts, ...filledSources.contextTexts]`
  - `sources = [...sources, ...vectorSearchResults.sources]`
- `server/utils/helpers/chat/index.js`
  - `fillSourceWindow()`는 현재 검색 결과가 `nDocs`보다 적으면 최근 채팅의 `sources`에서 보충함
  - `filterIdentifiers`, `seenChunks`, `source.hasOwnProperty("score")` 조건으로 중복과 pinned 문서를 걸러냄

```js
const filledSources = fillSourceWindow({
  nDocs: workspace?.topN || 4,
  searchResults: vectorSearchResults.sources,
  history: rawHistory,
  filterIdentifiers: pinnedDocIdentifiers,
});

contextTexts = [...contextTexts, ...filledSources.contextTexts];
sources = [...sources, ...vectorSearchResults.sources];
```

### 제품 적용 포인트

- 검색 결과 부족 시 과거 source를 backfill하는 기능과 사용자에게 보여줄 citation 목록은 분리하는 편이 안정적임
- follow-up 질문이 많은 업무형 챗에서는 최근 대화의 출처 재활용이 실제 응답 품질을 크게 좌우함
- pinned 문서나 임시 첨부 파일은 별도 source class로 다뤄 검색 결과와 구분하는 편이 좋음

### 해석과 시사점

- 이 구조는 모델이 볼 컨텍스트와 사용자에게 노출할 citation을 동일하게 취급하지 않는다는 점에서 실무적임
- 환각 억제는 citation을 많이 노출하는 것만으로 해결되지 않음
- 후속 질문 문맥을 유지할 최소한의 source backfill과 UI에서의 citation 과잉 노출 억제를 함께 설계해야 한다는 점을 보여줌

## 3. 토큰 한계 방어는 워크스페이스 제한값과 모델별 압축기의 이중 구조로 작동

### 채택 기술 구조

- 워크스페이스 스키마에는 `openAiHistory`, `similarityThreshold`, `topN`, `queryRefusalResponse`가 있어 검색량과 대화 이력량을 1차 제한함
- `recentChatHistory()`는 `openAiHistory`만큼의 최근 대화만 가져옴
- 벡터 검색은 `similarityThreshold`와 `topN`으로 검색 결과 수를 제한함
- 그 뒤에도 프롬프트가 모델 한계를 넘을 수 있으므로 각 LLM provider는 공통 계약인 `compressMessages()`를 구현함
- 대표 구현인 OpenAI provider는 `promptWindowLimit()` 기반으로 `system 15%`, `history 15%`, `user 70%` 한도를 잡고 초과 시 `messageArrayCompressor()`로 메시지를 압축함
- 압축 방식은 요약 모델을 다시 호출하지 않고 토큰 단위로 가운데를 도려내는 `cannonball` 방식임

### 코드 근거 예시

- `server/prisma/schema.prisma`
  - `openAiHistory @default(20)`
  - `similarityThreshold @default(0.25)`
  - `topN @default(4)`
  - `queryRefusalResponse`
- `server/models/workspace.js`
  - 각 필드의 기본값과 상하한을 검증함
- `server/utils/chats/stream.js`
  - `messageLimit = workspace?.openAiHistory || 20`
  - similarity search에 `similarityThreshold`, `topN`을 전달함
  - 최종적으로 `LLMConnector.compressMessages(...)`를 호출함
- `server/utils/helpers/chat/index.js`
  - `messageArrayCompressor()`는 `tokenBuffer = 600`을 확보하고 필요 시 system, history, user를 순차 압축함
- `server/utils/AiProviders/openAi/index.js`
  - `#appendContext()`가 컨텍스트를 `[CONTEXT i]` 블록으로 system prompt 뒤에 붙임

```js
this.limits = {
  history: this.promptWindowLimit() * 0.15,
  system: this.promptWindowLimit() * 0.15,
  user: this.promptWindowLimit() * 0.7,
};
```

### 제품 적용 포인트

- 검색 파라미터와 최종 프롬프트 압축을 별도 계층으로 둬야 함
- 워크스페이스 단위 설정은 운영자가 제어하는 coarse-grained 안전장치로 두고 런타임 압축기는 모델별 fine-grained 안전장치로 두는 편이 나음
- 압축 전에 context를 system prompt에 어떻게 붙일지 포맷을 고정해야 provider를 바꿔도 동작이 흔들리지 않음

### 해석과 시사점

- 질문에서 기대하는 워크스페이스 전역 하드 리밋은 이 프로젝트에서 단일 값 하나로 구현돼 있지 않음
- 실제 구조는 검색량 제한용 워크스페이스 필드와 모델 창 크기 기반 압축기를 결합한 하이브리드 방식임
- 따라서 벤치마킹 포인트는 단일 상수 도입보다 검색 단계와 프롬프트 조립 단계를 나눠 각각 제한값을 두는 설계에 있음

## 4. Query mode 숏서킷으로 무근거 응답을 LLM 호출 전에 차단

### 채택 기술 구조

- 워크스페이스가 `query` 모드일 때는 일반 채팅과 다르게 검색된 컨텍스트가 없으면 답하지 않는 정책이 강제됨
- 숏서킷은 두 번 작동함
- 첫 번째는 워크스페이스 namespace 자체가 없거나 임베딩 수가 0개일 때임
- 두 번째는 pinned docs, parsed files, 벡터 검색 결과, history backfill까지 모두 반영했는데도 `contextTexts.length === 0`일 때임
- 두 경우 모두 외부 LLM 호출을 생략하고 `queryRefusalResponse` 또는 기본 문구를 즉시 반환함

### 코드 근거 예시

- `server/utils/chats/stream.js`
  - `(!hasVectorizedSpace || embeddingsCount === 0) && chatMode === "query"`
  - `chatMode === "query" && contextTexts.length === 0`
- 같은 패턴이 `apiChatHandler.js`, `embed.js`, `openaiCompatible.js`에도 반복됨

```js
if (chatMode === "query" && contextTexts.length === 0) {
  const textResponse =
    workspace?.queryRefusalResponse ??
    "There is no relevant information in this workspace to answer your query.";
  // LLM 호출 없이 즉시 반환
}
```

### 제품 적용 포인트

- 검색형 모드와 일반 대화형 모드를 분리해야 함
- 검색형 모드에서는 검색 실패 후 모델 일반 지식으로라도 답하는 흐름을 허용하지 않는 편이 문서형 지식 베이스에 더 적합함
- refusal 메시지는 운영자가 조정 가능한 설정값으로 두는 편이 좋음

### 해석과 시사점

- 이 설계는 환각 억제를 프롬프트 엔지니어링에만 맡기지 않음
- 검색 결과가 비어 있을 때 LLM을 아예 호출하지 않는 정책 레벨 통제가 들어가 있음
- 엔터프라이즈 지식 베이스에서는 이 방식이 품질보다 신뢰성을 우선한다는 점에서 특히 유효함

## 5. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 청크 헤더 메타데이터는 `title`, `published`, `source` 중심이라 문서 버전, 페이지 번호, 섹션 경로 같은 정밀 citation 모델은 아님
- `source`는 `link://`와 `youtube://` 계열에 한정되므로 모든 문서에 원본 URL이 실리는 것은 아님
- `fillSourceWindow()`는 모델 입력용 컨텍스트를 backfill하지만 그 source가 항상 그대로 UI citation에 노출되지는 않음
- `messageArrayCompressor()`의 `cannonball` 압축은 의미 보존형 요약이 아니라 중간 토큰 절삭이므로 긴 문서의 중심부 정보가 손실될 수 있음
- `query` 모드는 안전하지만 모델이 일반 상식으로 답할 수 있는 질문도 워크스페이스 근거가 없으면 거절함

### 제품 해석

- AnythingLLM의 접근은 정밀한 citation 렌더러보다 운영 안정성과 일관된 거절 정책을 우선함
- 따라서 벤치마킹할 때는 모든 상황에서 가장 풍부한 citation을 노출하는가보다 근거 없는 답변을 얼마나 일찍 차단하는가를 중심 기준으로 보는 편이 맞음

## 사내 지식 베이스 구축 시 벤치마킹 인사이트

- 청크 생성 시점에 출처 메타데이터를 주입하고 벡터 저장 시에도 같은 메타데이터를 함께 보존하는 이중 구조를 채택해야 함
- follow-up 질문 품질을 위해 현재 검색 결과가 부족할 때 과거 source를 backfill하는 계층을 두되 UI citation 노출 정책과는 분리해야 함
- 검색 제한값과 프롬프트 압축기는 하나로 합치지 말고 별도 계층으로 운영해야 함
- 검색형 질의 모드에서는 무근거 상태를 탐지했을 때 LLM 호출 자체를 막는 숏서킷을 두는 편이 신뢰성에 유리함
- 고정된 최대 토큰 상수 하나를 두는 방식보다 워크스페이스 설정값과 모델별 `promptWindowLimit()` 기반 압축기를 결합하는 하이브리드 구조가 실제 운영에 더 강함
