# 4. MCP 도구와 AI 협업 인터페이스 분석

## 개요

Basic Memory의 MCP 계층은 "똑똑한 거대 에이전트 하나"를 구현하려는 방향보다, 저장된 지식을 읽고 쓰고 연결하는 작은 도구 세트를 조합하는 방향에 가깝다. 이 제품에서 AI는 앱 내부 블랙박스가 아니라, Markdown 파일과 지식 그래프 위에서 작업하는 협업 주체다. 그래서 MCP 인터페이스도 에이전트의 자율성을 크게 만드는 쪽보다, 도구 호출을 투명하고 재조합 가능하게 만드는 쪽으로 설계돼 있다.

처음 보는 사람이 이 문서를 읽을 때 먼저 잡아야 할 제품 정의는 아래와 같다.

- Basic Memory는 Markdown 파일을 원본 지식 저장소로 두고, MCP를 통해 AI가 그 저장소를 읽고 쓰고 연결하게 만드는 local-first 지식 베이스 제품임

이 문서에서 먼저 알아야 할 전제는 아래와 같다.

- 이 제품에서 AI는 앱 내부에 갇힌 기능이 아니라 저장된 지식을 다루는 협업 주체임
- MCP는 "한 번에 다 해주는 거대 에이전트"보다 "작은 도구를 조합하는 인터페이스"에 가깝게 설계됨
- 대화의 목표는 raw chat transcript 축적보다 note와 graph 형태의 지식 자산 생성에 있음
- MCP tool은 직접 도메인 로직을 모두 수행하지 않고, typed client와 API 경계를 통해 서비스 계층에 연결됨

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| MCP tool | LLM이 직접 호출하는 작업 단위. 검색, 읽기, 쓰기, 문맥 확장 같은 기능을 나눠 가짐 |
| typed client | MCP tool이 API를 호출할 때 쓰는 타입 검증 포함 클라이언트 계층 |
| API router | 외부 요청을 서비스 계층으로 연결하고 request/response contract를 관리하는 계층 |
| service | 파일 저장, 파싱, 링크 해석, 인덱싱 같은 핵심 도메인 로직 계층 |
| atomic tool | 한 번의 의도가 비교적 분명한 작은 도구 단위 |
| composable tool | 다른 도구와 순차적으로 조합해 더 큰 작업 흐름을 만들 수 있는 도구 |
| conversation-to-knowledge | 대화 내용을 raw 로그가 아니라 note, observation, relation 같은 지식 구조로 남기는 방식 |

예를 들어 사용자가 "지난번 논의한 search 설계를 찾아서 이어서 정리해줘"라고 요청하면 대략 아래 흐름이 일어난다.

1. AI가 `search_notes` 또는 `recent_activity`로 시작점을 찾음
2. 필요하면 `read_note`나 `build_context`로 기존 지식을 읽고 연결 관계를 확인함
3. 수정이 필요하면 `edit_note` 또는 `write_note`로 결과를 Markdown note에 반영함
4. 이 과정에서 MCP tool은 typed client를 통해 API를 호출하고, 실제 저장과 인덱싱은 service 계층이 담당함

즉 이 문서의 주제는 "AI가 얼마나 자율적인가"보다 "AI가 사람과 같은 지식 저장소를 어떻게 안전하게 다루게 만드는가"에 가깝다.

이번 섹션에서 벤치마킹할 지점은 세 가지다.

- 왜 단일 거대 에이전트 대신 atomic하고 composable한 도구 세트를 택했는가
- 왜 MCP tool → typed client → API → service 구조로 계층을 나눴는가
- AI 대화를 일회성 로그가 아니라 재사용 가능한 지식으로 남기게 만드는 제품 설계는 무엇인가

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 단일 거대 에이전트보다 작은 MCP 도구 조합을 택한 이유

### 채택 기술 구조

Basic Memory의 MCP는 "한 번 호출하면 알아서 다 해주는 super-agent"보다 역할이 잘린 작은 도구 묶음으로 노출된다. 중요한 기준은 기능 분류보다 작업 의도다. 즉 이 제품은 "질문을 넣으면 답을 만든다"보다 "지식 저장소에 어떤 조작을 할 것인가"를 작은 도구 단위로 나눈다.

`mcp/tools/__init__.py` 기준 주요 도구는 다음처럼 역할이 분리돼 있다.

- 도구 구성
  - `write_note`: 새 지식 생성과 전체 overwrite 경로
  - `edit_note`: append, prepend, replace_section, find_replace 같은 점진 수정
  - `search_notes`: 탐색 시작점 찾기
  - `read_note`: 특정 노트의 원문과 구조 확인
  - `build_context`: 특정 `memory://` 기준 그래프 문맥 확장
  - `recent_activity`: 최근 변경 흐름 요약과 탐색 출발점 제공
- 사용 방식: 상위 LLM은 검색 후 읽기, 읽은 뒤 수정, 최근 활동 후 문맥 확장 같은 연쇄를 상황에 맞게 조합할 수 있음
- prompt 계층: 별도 거대 로직보다 기존 도구 orchestration에 가까움
  - `continue_conversation` prompt는 `search_notes` 또는 `recent_activity`를 먼저 호출함
  - 다음 단계로 `read_note`나 `build_context` 사용을 유도함

### 코드 근거 예시

- `src/basic_memory/mcp/tools/__init__.py`
  - MCP 서버에 등록되는 도구 세트가 작은 기능별 단위로 나뉘어 있음
- `src/basic_memory/mcp/tools/write_note.py`
  - 노트 생성과 전체 overwrite 경로를 담당함
- `src/basic_memory/mcp/tools/edit_note.py`
  - append, prepend, replace_section, find_replace 같은 증분 수정 연산을 별도 tool로 제공함
- `src/basic_memory/mcp/tools/search.py`
  - 검색만 전담하고, 읽기나 수정은 다른 tool로 넘김
- `src/basic_memory/mcp/tools/build_context.py`
  - 특정 `memory://` URI 기준 문맥 확장만 수행함
- `src/basic_memory/mcp/tools/recent_activity.py`
  - 최근 변경 탐색과 프로젝트 discovery를 담당함
- `src/basic_memory/mcp/prompts/continue_conversation.py`
  - `search_notes`, `recent_activity` 결과를 바탕으로 다음 tool 호출을 유도함
- `src/basic_memory/mcp/prompts/search.py`
  - search 후 `read_note`, `build_context`, `recent_activity`를 다음 단계로 제안함

### 제품 적용 포인트

- MCP 도구 설계는 CRUD 기준보다 "사용자가 지금 무엇을 하려는가" 기준으로 자르는 편이 조합성이 좋아짐
- 검색, 읽기, 쓰기, 문맥 확장을 한 도구에 우겨 넣지 않으면 실패 원인과 재시도 전략이 명확해짐
- prompt 계층은 새 비즈니스 로직을 만드는 곳이 아니라, 기존 도구들을 어떻게 순서 있게 쓰는지 안내하는 orchestration 계층으로 두는 편이 안정적임

### 해석과 시사점

- Basic Memory의 MCP 철학은 agent autonomy보다 tool composability에 더 가깝다
- 이 구조 덕분에 상위 LLM 클라이언트는 상황에 따라 더 유연한 판단을 할 수 있다
- 반대로 사용자 입장에서는 어떤 상황에 어떤 tool을 써야 하는지 학습이 조금 더 필요하다

## 2. MCP tool → typed client → API → service 구조로 경계를 나눈 이유

### 채택 기술 구조

이 프로젝트는 MCP tool이 직접 도메인 service를 호출하지 않는다. 대신 MCP tool은 typed client를 통해 HTTP API를 호출하고, API router가 다시 service를 호출한다. 겉으로 보면 한 단계 돌아가는 구조지만, 실제로는 재사용과 routing, contract 분리를 동시에 해결하기 위한 경계다.

호출 경계는 다음 순서로 분리된다.

- 호출 경계
  - MCP tool
  - typed client
  - HTTP API router
  - service
- 이 분리로 얻는 효과는 세 가지다.
  - entrypoint 재사용: MCP는 typed client로 API를 호출하고, API는 request/response를 표준화하며, service는 파일 쓰기와 파싱, 인덱싱, 링크 해석을 담당함. CLI는 다시 MCP tool을 JSON 출력으로 재사용함
  - routing 분리: MCP tool은 `get_project_client()`만 사용하면 되고, typed client는 `/v2/projects/{project_id}/...` 경로만 책임지며, local ASGI인지 remote cloud HTTP인지는 client 생성 시점에 결정됨
  - contract와 domain logic 분리: API는 external_id UUID, pagination, response model, HTTP error를 담당하고, service는 entity 생성, permalink 해석, relation resolution, file sync를 담당함

결과적으로 MCP tool은 사용자 경험과 입력 해석에 집중하고, service는 저장소 정합성과 도메인 규칙에 집중한다. `cli/commands/tool.py`가 별도 코드 경로 없이 MCP tool을 `output_format="json"`으로 호출해 그대로 출력하는 점도 이 설계를 잘 보여 준다.

### 코드 근거 예시

- `src/basic_memory/mcp/tools/write_note.py`
  - `get_project_client()`로 올바른 client를 받고 `KnowledgeClient`를 사용함
- `src/basic_memory/mcp/tools/read_note.py`
  - `KnowledgeClient`, `ResourceClient`, `search_notes`를 조합해 식별자 해석과 읽기를 수행함
- `src/basic_memory/mcp/tools/search.py`
  - `SearchClient`로 API 검색을 호출함
- `src/basic_memory/mcp/tools/build_context.py`
  - `MemoryClient`로 memory API를 호출함
- `src/basic_memory/mcp/clients/knowledge.py`
  - knowledge API 경로와 Pydantic 응답 검증을 캡슐화함
- `src/basic_memory/mcp/clients/search.py`
  - search API path construction과 `SearchResponse` 검증을 담당함
- `src/basic_memory/mcp/clients/memory.py`
  - context API path construction과 `GraphContext` 검증을 담당함
- `src/basic_memory/api/v2/routers/knowledge_router.py`
  - create, update, patch, move, delete를 HTTP endpoint로 노출함
  - fast path와 indexing/vector sync scheduling을 제어함
- `src/basic_memory/services/entity_service.py`
  - 파일 쓰기, Markdown 파싱, entity/observation/relation 갱신 같은 핵심 도메인 로직을 담당함
- `src/basic_memory/cli/commands/tool.py`
  - MCP tool을 JSON으로 호출하고 결과를 그대로 출력함
- `src/basic_memory/mcp/container.py`, `src/basic_memory/api/container.py`, `src/basic_memory/cli/container.py`
  - 각 entrypoint가 설정을 한 번만 읽는 composition root 구조를 가짐

### 제품 적용 포인트

- MCP tool이 직접 서비스 로직을 호출하게 두면 local/cloud routing, auth, contract versioning이 뒤엉키기 쉬움
- typed client를 두면 API path, 응답 검증, 에러 처리 규칙을 각 tool에서 중복하지 않아도 됨
- CLI, MCP, API가 같은 코어를 재사용하게 하려면 "service 직접 공유"만큼 "contract 경계 공유"도 중요함

### 해석과 시사점

- Basic Memory의 계층 분리는 단순한 추상화 과잉이 아니라 routing과 재사용을 위한 장치다
- 특히 per-project cloud routing이 붙는 순간, tool과 service 사이에 client/API 경계가 있는 편이 훨씬 유리해진다
- 반대로 순수 로컬 단일 앱만 생각하면 이 구조는 다소 우회적으로 보일 수 있다

## 3. AI 대화를 일회성 채팅 로그가 아니라 재사용 가능한 지식으로 남기는 설계

### 채택 기술 구조

Basic Memory의 협업 모델은 채팅 내용을 transcript DB에 쌓는 방식이 아니다. 대신 대화에서 남길 가치가 있는 내용을 Markdown note와 지식 그래프로 승격시키는 구조를 택한다. 핵심은 "대화 저장"보다 "지식 생성"에 있다.

이 설계는 세 층에서 드러난다.

- 협업 구조
  - 저장 단위: 채팅 메시지보다 note가 기본 단위다. `write_note`는 제목, 디렉터리, 내용, tags, note type을 받아 Markdown 파일을 만들고, observation과 relation 문법으로 대화 중 나온 사실과 연결을 구조화함
  - 수정 방식: transcript append보다 incremental knowledge editing에 가깝다. `edit_note`는 append, prepend, replace_section, find_replace를 제공하고, 새 세션이 이전 내용을 덮기보다 기존 노트에 정제된 내용을 덧붙이는 흐름을 지원함
  - 재사용 방식: `search_notes`로 관련 노트를 찾고, `build_context`로 `memory://permalink` 주변 그래프를 확장하며, `recent_activity`로 최근에 달라진 지식을 확인함

이 구조는 "AI가 기억한다"보다 "AI가 사람이 소유하는 지식 저장소를 함께 가꾼다"는 모델에 가깝다. `ai-assistant-guide-extended.md`도 recording 시 permission과 transparency를 요구하고, conversation을 decision, discovery, action plan, connected topic 같은 note로 저장하라고 권장한다. 즉 transcript raw dump보다 관찰값, 결정, 관계, 실행 항목으로 재구성된 note를 선호한다.

### 코드 근거 예시

- `src/basic_memory/mcp/tools/write_note.py`
  - observation, relation 문법을 포함한 Markdown note 생성을 MCP 수준에서 직접 지원함
  - 생성 후 observation 수와 relation 해석 결과를 요약으로 돌려줌
- `src/basic_memory/mcp/tools/edit_note.py`
  - append/prepend auto-create
  - find_replace/replace_section 같은 점진 수정 경로를 제공함
- `src/basic_memory/mcp/tools/read_note.py`
  - exact lookup 실패 시 title search, text search로 fallback하며 기존 지식을 다시 찾게 함
- `src/basic_memory/mcp/tools/recent_activity.py`
  - project-specific mode와 cross-project discovery mode를 제공해 최근 대화/지식 흐름을 다시 진입하게 함
- `src/basic_memory/services/entity_service.py`
  - note 내용을 파싱해 entity, observation, relation으로 저장함
  - unresolved relation도 forward reference로 보존함
- `docs/ai-assistant-guide-extended.md`
  - Recording Conversations 섹션에서 저장 전 동의, 저장 후 확인, 장기 가치 중심 기록을 강조함
  - conversation summary, decision record, connected topics를 note 형태로 남기는 예시를 제공함
- `src/basic_memory/mcp/prompts/continue_conversation.py`
  - 이전 대화를 이어갈 때 먼저 `search_notes`나 `recent_activity`를 호출하고, 이후 `read_note`와 `build_context`로 이어 가도록 설계함

### 제품 적용 포인트

- AI 협업 제품에서 기억을 남기려면 transcript 저장보다 "어떤 형식의 지식 자산으로 바꿀 것인가"를 먼저 설계해야 함
- 새 내용을 항상 새 문서로 쓰기보다 기존 note에 증분 편집하는 경로를 별도 tool로 두는 편이 장기 유지에 유리함
- conversation capture는 자동 저장보다 permission, transparency, 구조화 규칙을 함께 설계해야 사용자 신뢰가 생김

### 해석과 시사점

- Basic Memory는 AI 메모리 제품이라기보다 인간과 AI가 공동 편집하는 지식 저장소에 가깝다
- 이 구조의 강점은 세션이 끝나도 가치 있는 정보가 Markdown note와 graph relation으로 남는다는 점이다
- 반대로 raw transcript 보존이나 대화 turn-level replay 자체는 핵심 제품 가치로 다루지 않는다

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- atomic tool 세트는 유연하지만, 상위 LLM이 적절한 tool sequence를 고를 수 있어야 효과가 난다
- tool → client → API → service 구조는 강하지만, 순수 로컬 단일 프로세스 관점에서는 레이어가 많아 보일 수 있다
- 대화 저장은 지식 자산화에 최적화돼 있지만, raw chat history를 그대로 복원하는 제품과는 성격이 다르다
- prompt 계층이 도구 조합을 잘 안내하더라도, 실제 기록 품질은 AI가 observation과 relation을 얼마나 잘 쓰는지에 여전히 영향을 받는다

### 제품 해석

- Basic Memory의 MCP는 "에이전트를 크게 만드는 시스템"보다 "도구 체인을 잘 설계한 시스템"에 가깝다
- 이 제품의 협업 모델은 AI autonomy보다 AI accountability와 human-readable artifacts를 더 중시한다
- 따라서 벤치마킹 초점도 agent planning sophistication보다 `tool granularity`, `contract boundary`, `conversation-to-knowledge workflow`에 두는 편이 맞다

# 적용 인사이트

우리 제품이 Basic Memory에서 가장 먼저 벤치마킹해야 할 것은 MCP를 단순 integration layer로 보지 않고, 인간과 AI가 같은 지식 저장소를 다루기 위한 협업 인터페이스로 설계하는 관점이다. 구체적으로는 `작은 도구 세트`, `typed client와 API 경계`, `증분 편집 중심의 기록 흐름`, `대화를 note와 graph로 승격시키는 저장 규칙`을 한 세트로 가져가는 것이 핵심이다.

- super-agent 하나보다 검색, 읽기, 쓰기, 문맥 확장을 분리한 tool 세트가 더 투명하고 재조합 가능함
- MCP tool은 UX와 입력 해석에 집중하고, typed client와 API는 contract와 routing을 흡수하게 두는 편이 유지보수에 유리함
- CLI까지 같은 MCP tool을 재사용하면 entrypoint별 중복 구현을 크게 줄일 수 있음
- AI 대화를 장기 자산으로 만들려면 transcript 저장보다 decision, discovery, action item, relation을 note 구조로 남기는 편이 실용적임
- 협업형 memory 제품의 차별점은 "AI가 기억한다"보다 "AI가 사람이 소유하는 지식을 함께 정리한다"는 점에 있어야 함
