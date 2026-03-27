# Basic Memory 한눈에 이해하기

## 이 문서의 목표

이 문서는 Basic Memory를 처음 접하는 사람이 짧은 시간 안에 아래 내용을 이해하도록 돕기 위해 작성했다.

- Basic Memory가 어떤 프로젝트인지
- 왜 일반적인 채팅 히스토리나 단순 RAG만으로는 부족한 문제를 풀려고 하는지
- 이 프로젝트가 내세우는 강점이 무엇인지
- 핵심 개념이 무엇인지
- 저장소 안에서 어떤 부분이 실제 제품 가치의 중심인지

대상 독자는 AI 기술을 막 배우기 시작한 사람까지 포함한다. 그래서 LLM, MCP, 지식 그래프 같은 용어도 가능한 한 전제지식 없이 이해할 수 있게 설명한다.

## 한 줄 설명

Basic Memory는 사람이 쓰는 Markdown 메모를 원본 데이터로 유지하면서, 그 내용을 지식 그래프로 인덱싱해 LLM이 읽고 쓰게 만드는 local-first 메모리 시스템이다.

더 정확히 말하면, 평범한 Markdown 파일 안의 사실과 링크를 구조화해서 검색 가능한 지식 베이스로 만들고, MCP를 통해 Claude Desktop, VS Code, Codex 같은 AI 도구가 그 지식을 계속 이어서 활용하게 해 주는 프로젝트다.

## 왜 이런 프로젝트가 필요한가

많은 사람이 AI와 대화할 때 겪는 가장 큰 문제는 기억이 이어지지 않는다는 점이다.

- 오늘 AI와 나눈 대화가 내일 새 대화에서 바로 이어지지 않는다
- 채팅 히스토리는 남아 있어도 구조화된 지식으로 쓰기 어렵다
- RAG는 보통 문서를 읽게만 하고, AI가 다시 그 지식 저장소에 써 넣는 흐름은 약하다
- 벡터 DB나 지식 그래프는 강력하지만 초심자에게는 설정과 운영이 무겁다

Basic Memory는 이 문제를 비교적 단순한 방식으로 푼다.

- 저장은 Markdown 파일에 한다
- 검색과 링크 해석은 데이터베이스가 맡는다
- AI는 MCP라는 표준 인터페이스로 같은 파일과 같은 지식 베이스를 읽고 쓴다

여기서 중요한 점은 "새로운 폐쇄형 메모리 시스템"을 만드는 것이 아니라, 사람이 직접 열어보고 수정할 수 있는 파일 기반 기억 시스템을 만든다는 것이다.

## Basic Memory가 푸는 문제

예를 들어 어떤 개발자가 몇 주 동안 AI와 프로젝트를 같이 진행한다고 가정해 보자.

- 첫째 날에는 프로젝트 구조를 정리했다
- 다음 주에는 검색 기능 설계를 논의했다
- 그 다음에는 테스트 전략과 클라우드 라우팅 방식을 정리했다

이 정보가 전부 채팅창에만 남아 있으면 아래 같은 질문에 답하기가 점점 어려워진다.

- 지난주에 어떤 설계 결정을 내렸는가
- 검색 기능과 관련된 노트는 무엇이 있는가
- 이 결정과 연결된 다른 문서는 무엇인가
- 지금 대화에 가져와야 할 관련 맥락은 어디까지인가

Basic Memory는 이 문제를 Markdown 노트와 지식 그래프로 풀려고 한다.

- 노트 하나하나를 엔티티로 다룬다
- 노트 안의 사실을 observation으로 분리한다
- `[[링크]]`를 relation으로 저장한다
- 검색과 최근 활동, 그래프 탐색으로 관련 문맥을 다시 조립한다

즉 이 프로젝트는 "AI가 과거 대화를 기억하게 하는 메모장"이 아니라, "사람과 AI가 함께 쓰는 구조화된 지식 베이스"에 더 가깝다.

## 이 프로젝트의 강점

### 1. 사람이 읽을 수 있는 Markdown을 원본으로 유지한다

Basic Memory의 가장 큰 장점은 파일이 원본이라는 점이다.

- 메모가 모두 평범한 Markdown 파일로 남는다
- Git으로 버전 관리를 할 수 있다
- Obsidian 같은 기존 도구로도 열어볼 수 있다
- 특정 AI 제품에 데이터가 잠기지 않는다

초심자 입장에서 이 점이 중요하다. 시스템이 어떻게 동작하는지 몰라도, 최소한 파일은 직접 볼 수 있고 필요하면 손으로 고칠 수 있기 때문이다.

### 2. 사람과 AI가 같은 지식 저장소를 함께 쓴다

많은 시스템은 사람이 보는 데이터와 AI가 보는 데이터가 다르다. 예를 들어 사람은 문서를 수정하고, AI는 별도의 검색 인덱스나 벡터 DB만 읽는 식이다.

Basic Memory는 이 간극을 줄인다.

- 사람은 Markdown 파일을 수정한다
- AI도 같은 노트를 읽고 쓴다
- DB는 별도의 진실 저장소가 아니라 검색과 탐색을 위한 인덱스 역할을 한다

이 구조 덕분에 "AI가 알고 있는 것"과 "사람이 파일에서 보는 것"이 크게 어긋나지 않는다.

### 3. 단순 메모를 구조화된 지식 그래프로 바꾼다

Basic Memory는 파일을 그냥 저장만 하지 않는다. 노트 안에서 구조를 읽어낸다.

- Frontmatter는 메타데이터로 저장한다
- `[category] 내용`은 observation으로 저장한다
- `relation_type [[Target]]`이나 본문 안 `[[Target]]`은 relation으로 저장한다

이 덕분에 메모가 늘어나도 단순한 텍스트 더미가 아니라, 검색 가능하고 연결 가능한 지식 그래프로 쌓인다.

### 4. 검색만이 아니라 문맥 조립까지 지원한다

Basic Memory의 가치는 단순 문자열 검색에만 있지 않다.

- permalink exact lookup
- full-text search
- semantic vector search
- relation traversal
- recent activity 조회
- `memory://` URL 기반 context build

즉 "관련 문서 몇 개 찾기"에서 끝나지 않고, 지금 대화에 필요한 주변 문맥까지 조립하는 데 초점을 둔다.

### 5. 로컬 우선을 유지하면서도 확장 가능하다

Basic Memory는 기본적으로 로컬 도구다. 하지만 나중에 필요하면 클라우드 기능도 붙일 수 있다.

- 기본 사용은 로컬 파일 + 로컬 DB
- 프로젝트별로 local mode와 cloud mode를 다르게 줄 수 있다
- CLI, API, MCP 세 진입점이 같은 코어 로직을 재사용한다
- 선택적으로 양방향 동기화와 클라우드 프로젝트 관리도 가능하다

즉 처음에는 가볍게 시작하고, 나중에는 팀 워크플로와 여러 환경으로 확장할 수 있다.

## 핵심 개념

Basic Memory를 이해할 때 가장 중요한 개념은 다섯 가지다.

| 개념 | 의미 | 왜 중요한가 |
| --- | --- | --- |
| Project | 하나의 지식 베이스 단위 | 어떤 파일 집합과 설정을 기준으로 동작하는지 결정 |
| Entity | Markdown 파일 하나에 대응하는 지식 그래프의 노드 | 검색과 링크 해석의 기본 단위 |
| Observation | 엔티티에 속한 구조화된 사실 | 메모를 검색 가능한 원자 단위로 쪼개 줌 |
| Relation | 엔티티 사이의 연결 | 노트들을 그래프로 묶어 문맥 탐색을 가능하게 함 |
| Permalink와 `memory://` URL | 엔티티를 안정적으로 가리키는 식별 방식 | 파일 이동이나 제목 변경 이후에도 참조를 유지하는 데 중요 |

### Project

Project는 Basic Memory에서 가장 큰 작업 단위다.

쉽게 말해 "하나의 메모리 공간"이라고 보면 된다.

- 각 프로젝트는 고유한 루트 디렉터리를 가진다
- 어떤 프로젝트를 기본 프로젝트로 쓸지 정할 수 있다
- 프로젝트마다 local mode 또는 cloud mode를 따로 가질 수 있다

초심자 관점에서는 폴더 하나를 그냥 여는 것과 비슷해 보일 수 있다. 하지만 Basic Memory에서는 그 폴더가 검색 인덱스, 동기화, MCP 라우팅의 기준점이 된다.

### Entity

Entity는 Markdown 파일 하나가 데이터베이스에 인덱싱될 때 만들어지는 핵심 객체다.

예시

- `Coffee Brewing Methods.md`
- `Project Architecture.md`
- `JWT Authentication.md`

파일 하나가 단순 파일로만 끝나는 것이 아니라, 아래 같은 속성을 가진 엔티티로 관리된다.

- 제목
- 파일 경로
- permalink
- 체크섬
- 메타데이터
- 본문에서 추출한 observation과 relation

즉 Entity는 "파일의 그래프 표현"이라고 이해하면 가장 쉽다.

### Observation

Observation은 엔티티에 속한 구조화된 사실이다.

예시

- `[decision] 검색 인덱스는 SQLite FTS5를 사용한다`
- `[constraint] 파일이 원본 데이터다`
- `[fact] 프로젝트는 Python 3.12 이상을 요구한다`

중요한 점은 observation이 그냥 메모 문장이 아니라 분류된 사실이라는 것이다. 이 구조 덕분에 Basic Memory는 노트 내용을 더 잘 검색하고, 나중에 스키마 검증도 할 수 있다.

### Relation

Relation은 엔티티와 엔티티 사이의 연결이다.

예시

- `depends_on [[Database Schema]]`
- `relates_to [[Semantic Search]]`
- `part_of [[Q1 Planning]]`

본문 안의 `[[WikiLink]]`도 relation으로 잡힌다. 그래서 Basic Memory는 단순 파일 모음이 아니라, 서로 연결된 지식 그래프로 동작한다.

AI가 과거 맥락을 따라가며 읽을 수 있는 이유도 바로 이 relation 계층 때문이다.

### Permalink와 `memory://` URL

Permalink는 엔티티를 안정적으로 식별하기 위한 고정 ID에 가깝다.

- 파일명이 바뀌어도 permalink는 유지할 수 있다
- 파일이 이동해도 permalink 기반 참조는 비교적 안정적이다

`memory://` URL은 이 permalink나 제목, 경로를 기반으로 엔티티를 가리키는 방식이다.

예시

- `memory://coffee-brewing-methods`
- `memory://Project Architecture`
- `memory://research/*`

이 주소 체계 덕분에 MCP 도구나 컨텍스트 빌더가 특정 노트와 그 주변 그래프를 안정적으로 찾아갈 수 있다.

## Basic Memory는 어떻게 동작하나

가장 중요한 흐름은 `노트 생성/갱신`과 `검색/문맥 구성` 두 가지다.

### 1. 노트 생성과 갱신

새 정보가 들어오면 대체로 아래 순서로 처리된다.

1. 사람이나 LLM이 `write_note` 또는 `edit_note` 같은 도구를 호출한다
2. MCP 계층이 올바른 프로젝트 client를 고른다
3. API router가 요청을 받는다
4. `EntityService`가 파일 저장과 인덱싱 작업을 조율한다
5. `FileService`가 Markdown 파일을 쓴다
6. `EntityParser`가 frontmatter, observation, relation을 파싱한다
7. repository 계층이 `Entity`, `Observation`, `Relation`을 갱신한다
8. `SearchService`가 검색 인덱스와 의미 기반 검색용 데이터까지 동기화한다

핵심은 "파일 저장"과 "지식 그래프 갱신"이 따로 놀지 않게 묶여 있다는 점이다.

또 파일이 직접 수정되더라도 watcher와 sync 계층이 이를 감지해서 DB 인덱스를 다시 맞춘다. 그래서 사람 편집과 AI 편집이 같은 시스템 안에서 공존할 수 있다.

### 2. 검색과 문맥 구성

질문이 들어오면 Basic Memory는 여러 방법을 조합해 관련 정보를 찾는다.

- 제목이나 permalink로 직접 찾기
- full-text search로 관련 노트 찾기
- semantic vector search로 의미상 비슷한 노트 찾기
- relation traversal로 연결된 노트 확장하기
- recent activity로 최근 바뀐 맥락 가져오기

이 과정의 핵심 서비스가 `SearchService`와 `ContextService`다.

결과도 단순 검색 결과 목록으로만 끝나지 않는다.

- 현재 노트
- 관련 observation
- 연결된 relation
- 주변 엔티티
- 최근 활동

이런 재료를 묶어 LLM이 다음 답변에 쓸 수 있는 컨텍스트를 만든다. 그래서 Basic Memory는 단순 검색기라기보다 "대화용 문맥 생성기"에 가깝다.

## 일반적인 RAG와 어떻게 다른가

| 항목 | 일반적인 RAG | Basic Memory |
| --- | --- | --- |
| 기본 단위 | 문서 청크 | Markdown 노트, entity, observation, relation |
| 원본 데이터 | 보통 문서와 인덱스가 분리 | Markdown 파일이 원본 |
| AI의 쓰기 경로 | 읽기 중심인 경우가 많음 | AI도 같은 노트에 직접 쓰기 가능 |
| 관계 표현 | 약하거나 후처리 의존 | `[[링크]]`와 relation으로 명시적 표현 |
| 검색 방식 | 주로 키워드 또는 벡터 검색 | FTS, vector, hybrid, graph traversal 조합 |
| 문맥 구성 | 관련 청크 반환 중심 | 관련 노트와 그래프 맥락까지 조립 |
| 사용자 통제 | 외부 서비스나 전용 DB 의존 가능 | 로컬 파일 기반이라 통제권이 큼 |

Basic Memory는 RAG를 완전히 대체하는 모든 것이라기보다, "사람과 AI가 함께 쓰는 장기 메모리" 문제에 더 잘 맞는 접근이라고 보는 편이 정확하다.

## 저장소는 어떻게 구성돼 있나

처음 보는 사람은 저장소를 세 부분으로 나눠 이해하면 된다.

### `src/basic_memory/services`, `repository`, `markdown`

여기가 프로젝트의 실제 제품 가치가 가장 많이 들어 있는 중심부다.

- `services/`는 생성, 수정, 검색, 문맥 구성 같은 비즈니스 로직을 담당한다
- `repository/`는 DB 접근과 검색 backend 구현을 담당한다
- `markdown/`은 Markdown에서 observation과 relation을 추출하는 파서를 담고 있다

Basic Memory가 "파일 기반 메모리 시스템"으로 동작하는 핵심 이유는 이 세 계층에 들어 있다.

### `src/basic_memory/cli`, `api`, `mcp`

여기는 같은 코어 기능을 서로 다른 방식으로 노출하는 진입점이다.

- `cli/`는 로컬 명령줄 인터페이스다
- `api/`는 FastAPI 기반 HTTP 계층이다
- `mcp/`는 Claude Desktop, VS Code, Codex 같은 AI 클라이언트를 위한 MCP 서버다

이 셋은 서로 다른 제품처럼 보일 수 있지만, 실제로는 같은 서비스 계층을 재사용하는 얇은 어댑터에 가깝다.

### `src/basic_memory/sync`, `schema`, `importers`, `tests`

여기는 제품을 실전에서 쓰게 만드는 지원 계층이다.

- `sync/`는 파일 변경 감지와 DB 인덱스 동기화를 담당한다
- `schema/`는 노트 구조 추론, 검증, diff를 담당한다
- `importers/`는 Claude, ChatGPT 같은 외부 대화 데이터를 가져온다
- `tests/`와 `test-int/`는 SQLite와 Postgres를 포함한 검증 체계를 담고 있다

즉 Basic Memory는 단순한 MCP 서버가 아니라, 파일 동기화와 검색 인프라, 스키마 시스템까지 묶은 꽤 완성도 높은 플랫폼형 저장소다.

## 누가 이 프로젝트를 좋아할 가능성이 큰가

아래 같은 문제를 가진 사람이나 팀이라면 Basic Memory가 특히 잘 맞을 수 있다.

- AI와의 대화를 일회성으로 끝내지 않고 축적하고 싶은 사람
- Markdown과 Git 중심 워크플로를 선호하는 사람
- Obsidian 같은 기존 노트 환경을 그대로 활용하고 싶은 사람
- 설계 결정, 회의 기록, 연구 메모를 AI와 함께 정리하고 싶은 개발팀
- 여러 MCP 클라이언트에서 같은 지식을 재사용하고 싶은 사람
- 로컬 우선을 유지하면서 나중에 클라우드 확장도 고려하는 팀

## 반대로 주의할 점

Basic Memory는 강력하지만, 모든 상황에 가장 단순한 해법은 아니다.

- 단순 FAQ 검색만 필요하다면 더 가벼운 RAG가 충분할 수 있다
- Markdown 구조와 observation, relation 형식을 이해해야 제대로 활용할 수 있다
- 파일과 DB가 분리되어 있으므로 sync와 인덱스 개념을 알아야 한다
- semantic search와 cloud 기능까지 쓰면 운영 복잡도가 올라간다
- 초반에는 "노트를 어떻게 쓰면 좋은가"에 대한 규칙을 팀 안에서 맞추는 비용이 있다

즉 Basic Memory는 단순 검색 툴보다 더 많은 가치를 주지만, 그만큼 지식 구조화와 운영 방식도 함께 받아들여야 한다.

## 이 프로젝트를 한 문장으로 다시 말하면

Basic Memory는 사람이 직접 관리하는 Markdown 지식을 AI가 계속 읽고 쓰고 탐색할 수 있게 만드는 local-first 메모리 인프라다.

## 더 읽으면 좋은 문서

코드를 바로 보고 싶다면 아래 순서가 가장 빠르다.

- [`src/basic_memory/config.py`]
- [`src/basic_memory/services/entity_service.py`]
- [`src/basic_memory/services/search_service.py`]
- [`src/basic_memory/services/context_service.py`]
- [`src/basic_memory/mcp/server.py`]
- [`src/basic_memory/mcp/tools/`]