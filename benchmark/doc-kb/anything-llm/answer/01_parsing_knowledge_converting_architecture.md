# 다종 문서 파싱 및 지식 변환 파이프라인 분석

## 개요

AnythingLLM의 문서 수집 파이프라인은 "모든 포맷을 하나의 범용 파서로 처리한다"는 방식이 아니다. 포맷별 전용 변환기를 `collector` 서비스 안에 분리해 두고, 결과를 공통 JSON 문서 계약으로 정규화한 뒤 `server`에서 다시 청킹과 임베딩으로 넘기는 2단 구조에 가깝다. 벤치마킹할 지점은 파서 종류 자체보다, 이종 입력을 같은 지식 객체로 수렴시키는 변환 계약과 서비스 경계 설계다.

처음 보는 사람이 이 문서에서 먼저 이해해야 할 전제는 아래와 같다.

- `collector`는 파일, 링크, raw text를 포맷별 converter로 파싱하는 수집 서비스
- `server`는 `collector` 출력물을 읽어 청킹, 임베딩, 워크스페이스 연결을 수행하는 검색 서비스
- AnythingLLM의 공통 원본 계약은 원본 바이너리 자체가 아니라 `collector`가 만든 문서 JSON
- 파일, 링크, raw text는 입력 경로는 다르지만 최종적으로 같은 문서 계약으로 수렴
- 지식 변환은 파싱에서 끝나지 않고 `TextSplitter`와 vector DB 적재까지 이어짐

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| `collector` | 파일, 링크, raw text를 파싱해 공통 문서 JSON으로 바꾸는 서비스 |
| converter | 확장자나 입력 종류별 전용 변환기 모듈 |
| 문서 JSON | `title`, `pageContent`, `chunkSource`, `token_count_estimate` 같은 공통 필드를 가진 중간 산출물 |
| `parseOnly` | 워크스페이스 적재 없이 미리보기용 결과만 만드는 처리 모드 |
| `TextSplitter` | 문서 JSON을 청크로 나누고 메타데이터 헤더를 붙이는 서버 계층 |
| vector DB 적재 | 청크를 임베딩해 검색 가능한 상태로 저장하는 단계 |

처음 읽을 때는 아래 흐름으로 이해하면 된다.

1. 사용자가 파일, 링크, raw text를 업로드하거나 입력함
2. `collector`가 입력 종류와 확장자에 맞는 converter를 선택해 본문과 메타데이터를 추출함
3. 추출 결과를 공통 문서 JSON으로 저장함
4. `server`가 이 JSON을 읽어 `TextSplitter`로 청킹하고 메타데이터 헤더를 붙임
5. vector DB provider가 청크를 임베딩해 저장하고, 이후 워크스페이스 검색과 답변 생성에 재사용함

예를 들어 사용자가 PDF 하나를 업로드하면 파이프라인은 아래처럼 흘러간다.

```text
manual.pdf
-> collector/processSingleFile
-> asPDF converter
-> 공통 문서 JSON 생성
-> server/TextSplitter 청킹
-> vector DB 임베딩 적재
```

중간 산출물의 형태는 대략 아래와 같다. 실제 값은 입력 경로와 converter 종류에 따라 달라진다.

```json
{
  "title": "manual.pdf",
  "docSource": "manual.pdf",
  "chunkSource": "manual.pdf",
  "pageContent": "PDF에서 추출된 전체 텍스트 ...",
  "token_count_estimate": 1820
}
```

즉 이 문서의 핵심 질문은 "어떤 파서를 쓰는가"보다 "여러 입력을 어떻게 같은 검색용 문서 객체로 바꾸는가"다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 포맷별 전용 변환기를 매핑하는 디스패처 구조

### 채택 기술 구조

AnythingLLM은 업로드된 파일을 확장자 기준으로 분기해 각 포맷에 맞는 변환기로 처리한다. 핵심은 `collector/processSingleFile/index.js`가 단일 파서가 아니라 "파일 타입 라우터" 역할을 한다는 점이다.

- 텍스트 계열인 `txt`, `md`, `csv`, `json`, `html`은 `asTxt` 계열로 단순 텍스트를 추출함
- PDF는 `asPDF`에서 전용 `PDFLoader`를 사용하고, 텍스트가 비면 OCR fallback을 수행함
- DOCX는 `langchain/document_loaders/fs/docx`의 `DocxLoader`로 처리함
- PPTX, ODT, ODP는 `officeparser` 기반 `asOfficeMime`으로 처리함
- XLSX는 `node-xlsx`로 시트를 파싱한 뒤 CSV 유사 문자열로 변환함
- EPUB, MBOX, 오디오, 이미지는 각각 전용 converter로 처리함
- 확장자가 미리 등록되지 않았더라도 MIME과 버퍼를 검사해 텍스트 파일로 볼 수 있으면 `.txt` 경로로 우회 처리함

즉 이 시스템은 "다종 문서를 지원하는 단일 파서"보다 "포맷별 전용 변환기를 공통 진입점 뒤에 매단 디스패처"에 가깝다.

### 코드 근거 예시

- `collector/utils/constants.js`
  - `SUPPORTED_FILETYPE_CONVERTERS`가 확장자별 converter를 매핑함
  - `ACCEPTED_MIMES`가 업로드 가능 타입을 명시함
- `collector/processSingleFile/index.js`
  - 경로를 검증함
  - 예약 파일을 차단함
  - 지원 확장자를 판별함
  - 미지원 확장자의 텍스트 fallback을 처리함
  - 최종 converter를 동적으로 로드함
- `collector/processSingleFile/convert/asDocx.js`
  - `DocxLoader` 기반 DOCX 처리
- `collector/processSingleFile/convert/asOfficeMime.js`
  - `officeparser.parseOfficeAsync()` 기반 Office 계열 처리
- `collector/processSingleFile/convert/asXlsx.js`
  - `node-xlsx`로 시트별 데이터를 파싱함

### 제품 적용 포인트

- 파서 종류가 계속 늘어날 수 있는 제품이라면 단일 파서 추상화보다 `확장자 -> converter 모듈` 매핑 테이블을 먼저 설계하는 편이 유지보수에 유리함
- 신규 포맷을 붙일 때 서버 전체를 건드리지 않고 `collector` 변환기만 추가하도록 책임을 나누는 편이 효과적임
- 미지원 확장자를 바로 실패시키기보다 텍스트로 읽을 수 있으면 텍스트 파서로 우회하는 전략이 운영 탄력성을 높임

### 해석과 시사점

- 라이브러리 선택 자체보다 포맷별 파서를 `collector` 내부 모듈로 격리한 구조가 더 중요한 설계 포인트임
- 이 분리 덕분에 문서 수집 범위가 넓어져도 `server`의 임베딩 및 검색 계층은 거의 수정하지 않아도 됨
- 반면 포맷별 변환 품질은 각 converter 구현에 크게 의존하므로, 특정 포맷 품질 이슈가 생기면 공통 파이프라인보다 해당 converter를 직접 보는 편이 맞음

## 2. 파싱 결과를 공통 JSON 문서 계약으로 정규화하는 구조

### 채택 기술 구조

AnythingLLM에서 더 중요한 설계는 파싱 결과를 어떤 "공통 문서 객체"로 바꾸느냐다. 각 converter는 최종적으로 거의 같은 필드를 갖는 JSON 문서를 만들고, 이 문서를 파일 시스템에 저장한다. 이 단계에서 문서는 이미 검색용 객체로 변환되며, 이후 서버는 포맷 원본이 아니라 이 JSON 계약을 기준으로 동작한다.

공통 필드 예시는 다음과 같다.

- `id`
- `url`
- `title`
- `docAuthor`
- `description`
- `docSource`
- `chunkSource`
- `published`
- `wordCount`
- `pageContent`
- `token_count_estimate`

이 JSON은 `collector/utils/files.writeToServerDocuments()`를 통해 `server/storage/documents` 또는 `server/storage/direct-uploads`에 저장된다. 즉 `collector`의 출력은 DB row가 아니라 표준화된 문서 JSON 파일이다.

### 코드 근거 예시

- `collector/processSingleFile/convert/asTxt.js`
- `collector/processSingleFile/convert/asPDF/index.js`
- `collector/processSingleFile/convert/asDocx.js`
- `collector/processSingleFile/convert/asXlsx.js`
  - 모든 converter가 공통 필드 구조를 조립해 저장함
- `collector/processRawText/index.js`
  - raw text도 같은 문서 계약으로 생성함
- `collector/utils/files/index.js`
  - `writeToServerDocuments()`가 저장 위치를 결정함
  - `parseOnly`면 `direct-uploads`, 아니면 `documents/custom-documents`에 저장함
- `server/utils/files/index.js`
  - 서버가 이 JSON을 다시 읽어 메타데이터와 본문을 소비함
  - `REQUIRED_FILE_OBJECT_FIELDS`로 필요한 메타 필드를 정의함

### 제품 적용 포인트

- 파서가 어떤 라이브러리를 쓰는지보다 수집 결과를 어떤 공통 DTO로 바꿀지 먼저 고정해야 함
- 수집기와 검색 서버 사이를 느슨하게 결합하려면 DB 직접 적재보다 파일 기반 문서 계약을 두는 방식이 운영상 단순함
- `pageContent`와 `token_count_estimate`를 파싱 시점에 함께 만들어 두면 이후 임베딩, pinned docs, 문서 선택기, 비용 추정 로직이 같은 계약을 재사용할 수 있음

### 해석과 시사점

- 포맷 복잡도를 `collector` 안에서 흡수하고 이후 계층에서는 문서 JSON만 보면 된다는 점이 이 구조의 가장 큰 장점임
- 검색 서버가 DOCX나 PDF의 원본 형식을 몰라도 되므로 계층 분리가 선명함
- 반면 표, 레이아웃, 슬라이드 구조 같은 풍부한 원본 문맥은 대부분 평탄한 `pageContent` 문자열로 사라짐

## 3. 링크와 외부 소스도 같은 문서 계약으로 흡수하는 구조

### 채택 기술 구조

AnythingLLM은 파일 업로드만 처리하지 않는다. 링크, 유튜브, 웹사이트 depth crawl, GitHub, GitLab, Confluence, Obsidian Vault, PaperlessNgx 같은 외부 소스도 `collector` 쪽에서 같은 문서 계약으로 흡수한다.

일반 링크 처리 흐름은 다음과 같다.

- `processLink()`가 URL 유효성을 검사함
- `scrapeGenericUrl()`이 링크를 `web`, `file`, `youtube`로 분기함
- 웹 페이지는 `PuppeteerWebBaseLoader`로 본문을 수집함
- Puppeteer가 실패하면 일반 `fetch`로 fallback 함
- 결과를 다시 공통 JSON 문서 계약으로 저장함

즉 외부 소스와 로컬 파일은 서로 다른 저장 형식을 쓰지 않고, 최종적으로 같은 문서 구조로 수렴한다.

### 코드 근거 예시

- `collector/processLink/index.js`
  - 링크 진입점
- `collector/processLink/convert/generic.js`
  - `PuppeteerWebBaseLoader`
  - `fetch` fallback
  - `chunkSource: link://...` 주입
- `collector/utils/extensions/WebsiteDepth/index.js`
  - 깊이 기반 웹사이트 수집
- `collector/utils/extensions/RepoLoader/*`
  - GitHub, GitLab 저장소 흡수
- `collector/utils/extensions/Confluence/*`
- `collector/utils/extensions/YoutubeTranscript/*`

### 제품 적용 포인트

- 파일 파이프라인과 링크 파이프라인을 별도 지식 모델로 나누지 말고 같은 문서 계약으로 수렴시키는 편이 이후 검색 계층을 단순하게 만듦
- 웹 수집은 브라우저 렌더링 기반 loader와 가벼운 fallback을 함께 두는 편이 실전 운영에 유리함
- 외부 커넥터는 검색 서버가 아니라 `collector` 확장 모듈에 붙여야 책임이 명확해짐

### 해석과 시사점

- AnythingLLM은 문서 파서와 외부 커넥터를 같은 수집기 레이어에 둠
- 이 선택 덕분에 소스가 파일이든 URL이든 이후 파이프라인은 거의 같은 흐름을 따름
- 우리 제품도 사내 위키, 레포, 포털까지 흡수하려면 파서와 커넥터를 같은 ingest boundary에 묶는 편이 유리함

## 4. 메타데이터 헤더를 붙인 청킹과 임베딩 진입 구조

### 채택 기술 구조

AnythingLLM에서 "지식 변환"은 `collector`에서 끝나지 않는다. `collector`가 문서 JSON을 만들고 나면, 실제 임베딩 직전에는 `server/utils/TextSplitter`가 문서를 다시 가공한다. 여기서 중요한 점은 두 가지다.

- 메타데이터 헤더를 각 청크 앞에 prepend 함
- 임베딩 모델의 최대 청크 길이를 넘지 않도록 chunk size를 동적으로 제한함

메타데이터 헤더는 모든 메타를 그대로 붙이지 않고, 현재 구현 기준으로는 주로 아래 값만 뽑아낸다.

- `title` -> `sourceDocument`
- `published`
- `chunkSource` -> `source`

이 값은 `<document_metadata>...</document_metadata>` 형식 문자열로 만들어져 각 청크 앞에 붙는다. 이후 vector DB provider는 이 청크 배열을 임베딩하고 저장한다.

### 코드 근거 예시

- `server/utils/TextSplitter/index.js`
  - `buildHeaderMeta()`
  - `stringifyHeader()`
  - `determineMaxChunkSize()`
- `server/utils/vectorDbProviders/lance/index.js`
- `server/utils/vectorDbProviders/pinecone/index.js`
- `server/utils/vectorDbProviders/pgvector/index.js`
  - 공통적으로 `TextSplitter`를 생성한 뒤 `splitText(pageContent)`로 청크를 만듦
- `server/utils/vectorDbProviders/*`
  - 임베딩 후 메타데이터와 함께 vector DB에 저장함

### 제품 적용 포인트

- 메타데이터 주입 시점을 파서 단계가 아니라 임베딩 직전 청킹 단계에 두면 원문 보존과 검색용 가공을 분리할 수 있음
- chunk size를 관리자 설정에만 맡기지 말고 embedder의 최대 길이로 한 번 더 clamp 해야 함
- source metadata는 검색과 답변 단계에서 재활용하기 쉬운 키만 남기는 편이 좋음

### 해석과 시사점

- 현재 구현은 파싱된 원문을 그대로 저장하고, 검색용 메타데이터 주입은 뒤 단계에서 수행함
- 이 분리는 원문 계약과 검색 계약이 섞이지 않게 해 준다는 점에서 좋은 선택임
- 다만 메타데이터 헤더가 현재는 `link://`와 `youtube://` 중심 source 추출에 최적화돼 있어, 모든 문서 타입에서 풍부한 citation 맥락을 자동 보장하는 구조로 보기는 어려움

## 5. 포맷별 특수 처리에서 드러나는 실제 설계 선택

### 채택 기술 구조

AnythingLLM의 수집 파이프라인은 모든 포맷에 동일하게 동작하지 않는다. 대표적인 특수 처리는 다음과 같다.

- PDF
  - `splitPages: true`로 페이지 단위 로딩을 시도함
  - 텍스트가 비면 OCR로 fallback 함
- XLSX
  - 일반 저장 시 시트별로 개별 문서를 생성함
  - `parseOnly` 시에는 여러 시트를 하나로 합쳐 미리보기용 단일 문서로 반환함
- 오디오
  - local whisper 또는 OpenAI whisper provider를 선택해 텍스트로 변환함
- 이미지
  - `OCRLoader` 기반으로 문자를 추출함
- raw text
  - 외부에서 들어온 텍스트도 별도 예외 처리 없이 같은 문서 계약으로 변환함

### 코드 근거 예시

- `collector/processSingleFile/convert/asPDF/index.js`
  - OCR fallback 존재
- `collector/processSingleFile/convert/asXlsx.js`
  - `parseOnly` 분기와 시트별 문서 생성
- `collector/processSingleFile/convert/asAudio.js`
  - `LocalWhisper`, `OpenAiWhisper` 분기
- `collector/processSingleFile/convert/asImage.js`
  - `OCRLoader.ocrImage()`
- `collector/processRawText/index.js`
  - raw text를 표준 문서 JSON으로 변환함

### 제품 적용 포인트

- 표 구조가 중요한 포맷은 `파일 하나 = 문서 하나`로 두지 말고 시트나 섹션 단위 분해 여부를 포맷별로 다르게 설계해야 함
- OCR과 음성 전사는 예외 기능이 아니라 `collector`의 정규 converter 계층에 편입하는 편이 자연스러움
- `parseOnly` 같은 미리보기 모드는 실제 저장 경로와 결과 granularity를 바꿀 수 있어야 함

### 해석과 시사점

- 이 시스템은 모든 문서를 균일하게 다루기보다 포맷별 특성에 따라 granularity를 다르게 가져가는 쪽에 가깝다
- PDF, 스프레드시트, 위키 문서를 같은 방식으로 자르면 오히려 품질이 떨어질 수 있음
- 따라서 공통 계약은 유지하되 파서별 분해 전략은 다르게 가져가는 편이 맞음

## 6. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 공통 문서 계약이 단순한 문자열 중심이라 표 구조, 레이아웃, 슬라이드 hierarchy 같은 원본 의미가 평탄화됨
- 링크 수집은 Puppeteer fallback 덕분에 유연하지만, HTML 정제 품질은 사이트 구조에 따라 편차가 클 수 있음
- `processSingleFile`, `processLink`, `processRawText`는 요청-응답형으로 실행되므로 무거운 문서는 `collector` 지연 시간이 길어질 수 있음
- 메타데이터 헤더는 유용하지만 현재 구현 기준으로는 모든 문서 타입의 출처를 같은 품질로 보강하지 못함
- 미지원 포맷을 텍스트로 우회 처리하는 전략은 운영 탄력성을 높이지만 구조 손실 가능성도 큼

### 제품 해석

- AnythingLLM의 파이프라인은 정교한 의미 보존 파서보다 운영 가능한 범용 ingest 시스템에 더 가깝다
- 정확한 레이아웃 재현보다 다양한 입력을 최대한 실패 없이 공통 지식 객체로 바꾸는 데 우선순위를 둠
- 사내 지식 베이스 구축 관점에서는 실용적인 선택이지만, 정밀한 표 해석이나 문단 의미 보존이 중요한 도메인이라면 converter별 후처리 계층을 추가로 설계할 필요가 있음

## 적용 인사이트

우리 제품이 AnythingLLM에서 먼저 벤치마킹해야 할 지점은 파서 라이브러리 목록이 아니라 수집 파이프라인의 경계 설계다. 구체적으로는 `포맷별 전용 converter`, `공통 문서 JSON 계약`, `링크와 파일의 동일 ingest 경로`, `임베딩 직전 메타데이터 헤더 주입`을 한 세트로 가져가야 한다.

- 파서 교체 가능성을 열어 두려면 `확장자 -> converter` 매핑 레이어를 별도 서비스 경계 안에 둬야 함
- 검색 서버는 원본 포맷을 몰라도 되도록 `collector` 출력 계약을 먼저 표준화해야 함
- 웹, 레포, 위키, raw text까지 모두 같은 문서 계약으로 수렴시키면 이후 검색과 권한 계층이 단순해짐
- 메타데이터 주입은 수집 시점보다 임베딩 직전 청킹 단계에 두는 편이 원문 보존과 검색 최적화를 함께 만족시키기 쉬움
- 스프레드시트, PDF, 오디오처럼 granularity가 다른 입력은 공통 계약은 유지하되 포맷별 분해 전략을 다르게 설계해야 함
