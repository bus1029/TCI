# 6. 구조 품질과 스키마 진화 분석

## 개요

Basic Memory의 스키마 시스템은 자유로운 Markdown을 대체하는 별도 저장 포맷이 아니다. 이 프로젝트는 먼저 사람이 읽고 쓰는 Markdown 문법을 유지하고, 그 위에 `schema infer`, `schema validate`, `schema diff`를 얹어 구조 품질을 점진적으로 끌어올린다. 핵심은 처음부터 엄격한 입력 폼을 강제하는 것이 아니라, 실제 사용 패턴이 쌓인 뒤 그 패턴을 스키마로 결정화하는 방식이다.

처음 보는 사람이 이 문서를 읽을 때 먼저 잡아야 할 제품 정의는 아래와 같다.

- Basic Memory는 Markdown 파일을 원본 지식 저장소로 두고, 그 위에 검색, 그래프, sync를 얹는 local-first 지식 베이스 제품이며, 스키마 시스템은 그 저장 방식을 바꾸지 않고 구조 품질을 점검하고 진화시키는 보조 계층임

이 문서에서 먼저 알아야 할 전제는 아래와 같다.

- 이 제품의 기본 입력은 자유로운 Markdown note이며, 스키마는 그 note를 대체하지 않음
- 구조 품질은 입력 단계에서 모두 강제하는 것이 아니라, 실제 사용 패턴을 관찰하고 나중에 점검하는 방식으로 다룸
- Basic Memory가 말하는 품질은 note 포맷, 파일과 인덱스 정합성, 검색 품질, 스키마 검증까지 포함한 운영 품질에 가까움
- 즉 이 문서의 주제는 "엄격한 타입 시스템"보다 "유연한 저장소를 어떻게 점점 더 정돈된 시스템으로 만드는가"에 있음

이번 섹션에서 벤치마킹할 지점은 두 가지다.

- 왜 자유로운 Markdown 위에 inference, validation, drift 분석을 추가했는가
- 지식 베이스를 단순 저장소가 아니라 점점 더 정돈된 시스템으로 만들기 위해 어떤 품질 장치를 묶었는가

이 문서에서 반복해서 나오는 세 용어는 먼저 이렇게 이해하면 된다.

- `schema infer`
  - 같은 `type`의 note들을 분석해 "이 타입의 note는 보통 어떤 observation과 relation을 가지는가"를 추론하는 기능
  - 즉 사람이 schema를 처음부터 설계하지 않아도, 실제 usage에서 공통 구조를 뽑아 schema 초안을 만들게 해 줌
- `schema validate`
  - 특정 note 또는 note 집합이 현재 schema와 얼마나 맞는지 점검하는 기능
  - 필수 observation 누락, enum 값 불일치, relation 누락 같은 구조 품질 문제를 경고 또는 에러로 보여 줌
- `schema diff`
  - 현재 schema와 실제 note usage가 시간이 지나며 얼마나 달라졌는지 비교하는 기능
  - 새로 자주 쓰이기 시작한 필드, 거의 안 쓰게 된 필드, single-value에서 array로 바뀐 필드를 찾아 schema drift를 알려 줌

이 문서를 읽기 전에 알아두면 좋은 기본 용어도 함께 정리하면 다음과 같다.

- `frontmatter`
  - Markdown 파일 맨 위의 YAML 메타데이터 블록
  - `title`, `type`, `tags`, `permalink`, `schema` 같은 값을 담음
- `observation`
  - `- [category] content` 형식으로 적는 구조화된 사실
  - schema의 일반 필드는 보통 이 observation category에 대응됨
- `relation`
  - `- relation_type [[Target]]` 형식의 연결 정보
  - schema의 entity reference field는 보통 이 relation type에 대응됨
- `schema note`
  - 별도 설정 파일이 아니라, `type: schema`를 가진 일반 Markdown note
  - 이 note 안의 frontmatter에 스키마 정의가 들어 있음
- `Picoschema`
  - schema note의 frontmatter 안에서 쓰는 간단한 스키마 표기법
  - 예를 들어 `name: string`, `role?: string`, `works_at?: Organization`처럼 필드 구조를 짧게 표현함

예를 들어 팀이 `type: Person` note를 오랫동안 자유롭게 쌓아 왔다고 가정하면, Basic Memory의 품질 루프는 대략 아래처럼 동작한다.

1. 사람과 AI가 먼저 Markdown note를 자유롭게 작성함
2. `schema infer`가 여러 `Person` note를 보고 자주 나오는 observation과 relation 패턴을 스키마 후보로 제안함
3. `schema validate`가 개별 note가 그 구조와 얼마나 맞는지 점검함
4. 시간이 지나 note 사용 패턴이 바뀌면 `schema diff`가 drift를 알려 줌
5. 이 과정과 별개로 formatting, sync, doctor, search fallback이 전체 품질 루프를 받쳐 줌

즉 이 문서의 핵심은 "스키마 엔진 하나"가 아니라 "Markdown 저장소가 무질서해지지 않도록 여러 품질 장치를 어떻게 연결하는가"에 가깝다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 자유로운 Markdown 위에 schema inference, validation, drift 분석을 얹은 이유

### 채택 기술 구조

- 기본 철학
  - 스키마는 새 데이터 모델이 아니라 기존 note 문법 위에 덧붙는 품질 계층임
  - `type: schema`인 일반 note가 스키마 정의를 담고, 실제 note는 그대로 observation과 relation 문법을 사용함
  - 즉 입력 자유도는 유지하고, 구조 품질만 추가로 측정함
- 스키마 해석 방식
  - `resolve_schema()`는 `inline schema -> explicit reference -> implicit by type -> no schema` 순서로 적용함
  - `inline schema`는 현재 note frontmatter 안에 schema dict를 직접 쓰는 방식임
  - `explicit reference`는 `schema: Person`처럼 다른 schema note를 명시적으로 가리키는 방식임
  - `implicit by type`는 note의 `type: person`을 보고 같은 entity를 설명하는 schema note를 자동으로 찾는 방식임
  - note마다 스키마를 강제로 붙이지 않고, 있을 때만 해석함
  - 스키마가 없으면 note는 여전히 유효한 Markdown note로 남음
- 검증 방식
  - `validate_note()`는 schema field를 기존 note 구조에 직접 대응시킴
  - scalar field는 `[category]` observation으로, entity ref field는 `relation [[Target]]`으로 검증함
  - schema에 없는 observation과 relation은 에러가 아니라 `unmatched_*` 정보로 남김
  - 기본 모드는 `warn`이고, `strict`일 때만 에러로 승격함
- 추론 방식
  - `infer_schema()`는 note를 먼저 자유롭게 쌓고, 나중에 빈도 분석으로 스키마를 제안함
  - 기본 기준은 `95% 이상 required`, `25% 이상 optional`, 그 이하는 제외임
  - relation은 target note type까지 추적해서 `works_at?: Organization` 같은 필드 제안으로 이어짐
- drift 분석 방식
  - `diff_schema()`는 현재 schema와 실제 note usage를 비교함
  - 새로 자주 등장한 필드, 거의 쓰이지 않는 필드, single/array cardinality 변화를 따로 감지함
  - 즉 스키마를 정답으로 고정하지 않고, 운영 중 변화하는 사용 패턴과 계속 비교함
- 구조적 의미
  - Basic Memory는 "엄격한 구조를 먼저 설계하고 입력을 맞추게 하는 제품"보다 "유연하게 축적한 뒤 공통 패턴을 추출하는 제품"에 가깝다
  - 이 때문에 스키마는 제약 시스템이라기보다 품질 피드백 시스템 역할이 더 크다

### 코드 근거 예시

- `src/basic_memory/schema/__init__.py`
  - 스키마 시스템을 "type: schema note" 기반 계층으로 정의함
- `src/basic_memory/schema/parser.py`
  - Picoschema를 `SchemaField`, `SchemaDefinition`으로 파싱함
  - `settings.frontmatter`까지 같은 문법으로 검증 규칙에 포함함
- `src/basic_memory/schema/resolver.py`
  - inline, explicit ref, implicit type 기반 우선순위 해석을 구현함
- `src/basic_memory/schema/validator.py`
  - 스키마 필드를 observation과 relation에 직접 매핑함
  - `warn` 기본값과 `strict` 승격 규칙, `unmatched_observations`, `unmatched_relations` 수집을 구현함
- `src/basic_memory/schema/inference.py`
  - "Write freely -> patterns emerge -> crystallize into schema" 흐름을 코드 주석과 로직으로 직접 드러냄
  - 빈도 기반 required, optional, excluded 분류와 array 추론을 구현함
- `src/basic_memory/schema/diff.py`
  - new field, dropped field, cardinality change를 별도 drift 신호로 계산함
- `src/basic_memory/api/v2/routers/schema_router.py`
  - schema validation, inference, drift를 별도 API로 노출함
  - schema file을 DB metadata 대신 파일에서 직접 읽어 최신 설정을 우선 적용함
- `src/basic_memory/mcp/tools/schema.py`
  - MCP 사용자가 raw JSON 대신 바로 읽을 수 있는 validation, inference, drift 리포트를 받게 함
- `docs/NOTE-FORMAT.md`
  - 스키마가 새 문법을 만들지 않고 기존 note 문법에 대응된다는 제품 규칙을 설명함

### 제품 적용 포인트

- 자유로운 입력을 포기하지 않고 구조 품질을 높이려면 스키마를 저장 포맷이 아니라 품질 계층으로 두는 편이 현실적임
- 스키마는 "모든 필드를 정의하는 완전한 계약"보다 "중요 필드를 점검하는 부분 계약"으로 두는 편이 운영 저항이 낮음
- inference를 먼저 두고 validation을 나중에 두면 초기 도입 장벽이 크게 낮아짐
- drift 분석은 스키마 변경 요청을 감으로 처리하지 않고 실제 usage 변화로 판단하게 해 줌
- metadata까지 검증해야 한다면 본문 규칙과 별도 시스템을 만들기보다 `settings.frontmatter`처럼 같은 문법으로 묶는 편이 일관적임

### 해석과 시사점

- Basic Memory가 스키마를 도입한 이유는 Markdown의 자유도를 줄이기 위해서가 아니라, 장기 운영에서 구조가 흐트러지는 지점을 관찰 가능하게 만들기 위해서임
- 이 시스템의 강점은 schema-first 제품처럼 입력을 막는 데 있지 않고, usage-first 제품처럼 실제 note 집합에서 공통 구조를 끌어낸 뒤 점진적으로 엄격도를 올릴 수 있다는 점에 있음

## 2. 지식 베이스를 점점 더 정돈된 시스템으로 만들기 위한 품질 장치

### 채택 기술 구조

- 기본 품질 층
  - `docs/NOTE-FORMAT.md`가 frontmatter, observation, relation, permalink의 최소 규칙을 정의함
  - 즉 Basic Memory는 완전 자유 텍스트가 아니라 "사람이 읽을 수 있는 최소 구조화 Markdown"을 기본 단위로 삼음
- 쓰기 품질 장치
  - `MarkdownProcessor.write_file()`은 atomic write, checksum 검증, structured section 직렬화를 담당함
  - 여기서 atomic write는 임시 파일에 먼저 쓴 뒤 최종 파일로 교체해 중간 저장 실패 시 파일 손상을 줄이는 방식임
  - checksum은 파일 내용의 해시값으로, 실제 내용이 바뀌었는지 판단하는 기준으로 사용됨
  - `file_utils.dump_frontmatter()`와 built-in `mdformat` 경로는 YAML frontmatter와 Markdown 모양을 일관되게 유지함
  - `bm format`은 프로젝트 전체의 `.md`, `.json`, `.canvas` 파일에 같은 formatter 정책을 적용함
- 파일 ↔ DB 정합성 장치
  - `SyncService`는 checksum, mtime, size, move detection, deletion detection, watermark 기반 incremental scan을 묶어 파일과 DB를 맞춤
  - watermark는 "마지막으로 어디까지 스캔했는가"를 나타내는 기준 시점과 파일 개수 정보임
  - incremental scan은 전체 파일을 다시 읽지 않고, 마지막 스캔 이후 바뀐 파일만 다시 확인하는 방식임
  - 변경이 있으면 relation resolution과 vector embedding sync까지 이어서 처리함
  - relation resolution은 아직 대상이 없던 링크를 다시 확인해 실제 relation으로 연결하는 과정임
  - vector embedding은 semantic search를 위해 note 내용을 벡터 표현으로 바꾸는 단계임
  - 즉 note 품질만 보는 것이 아니라 인덱스와 그래프까지 함께 최신 상태로 유지함
- 운영 검증 장치
  - `bm doctor`는 DB -> file 생성, file -> DB sync, search 확인, status clean 확인까지 실제 왕복 루프를 점검함
  - 이 명령은 단위 기능 테스트가 아니라 "이 제품의 핵심 계약이 실제로 살아 있는가"를 확인하는 운영용 체크에 가깝다
- 검색 품질 장치
  - `SearchService`는 strict FTS 결과가 비면 relaxed OR fallback을 한 번 더 시도함
  - FTS는 Full-Text Search로, 일반 키워드 검색 인덱스를 뜻함
  - relaxed OR fallback은 검색어가 너무 빡빡해 결과가 0건일 때, 일부 조건을 느슨하게 바꿔 한 번 더 찾는 방식임
  - vector 품질을 위해 전체 content를 chunk 파이프라인에 넘기고, sync 후 batch vector sync도 수행함
  - 즉 검색은 단순 인덱스 구축만이 아니라 실제 retrieval 품질 보정을 포함함
- 스키마 품질 장치
  - validation은 note별 품질 점검
  - inference는 패턴 추출
  - drift는 구조 변화 감지
  - 세 기능이 별개가 아니라 "축적 -> 점검 -> 진화" 루프로 연결됨
- 외부 인터페이스 품질 장치
  - CLI, API, MCP가 같은 schema core를 재사용함
  - MCP 도구는 실패 시 `No Notes Found`, `No Schema Found`, `No Schema Pattern Found` 같은 안내를 반환해 사용자가 바로 다음 행동을 알 수 있게 함
  - 품질 장치는 내부 엔진에만 있지 않고 사용자 인터페이스까지 이어짐

### 코드 근거 예시

- `docs/NOTE-FORMAT.md`
  - note 구조와 schema-to-note mapping을 명시함
- `src/basic_memory/markdown/markdown_processor.py`
  - atomic write, checksum dirty check, structured observation/relation formatting을 수행함
- `src/basic_memory/file_utils.py`
  - `format_markdown_builtin()`과 `format_file()`로 Markdown formatting 경로를 제공함
- `src/basic_memory/cli/commands/format.py`
  - 프로젝트 전체 파일 포맷 정리를 별도 운영 명령으로 제공함
- `src/basic_memory/sync/sync_service.py`
  - watermark 기반 incremental scan
  - checksum 기반 modified 판단
  - checksum 기반 move detection
  - relation resolution
  - batch vector sync
- `src/basic_memory/cli/commands/doctor.py`
  - file ↔ DB 루프와 search/status 검증을 실제 동작으로 확인함
- `src/basic_memory/services/search_service.py`
  - strict FTS 실패 시 relaxed fallback을 적용함
  - vector embedding 품질을 위해 full content를 검색 인덱싱 파이프라인에 유지함
- `src/basic_memory/api/v2/routers/schema_router.py`
  - schema file을 직접 읽어 watcher 지연으로 인한 stale metadata 문제를 줄임
  - stale metadata는 파일은 이미 바뀌었지만 DB 인덱스에는 아직 이전 값이 남아 있는 상태를 뜻함
- `tests/mcp/test_tool_schema.py`
  - `write_note -> sync -> schema_validate` 흐름과 no-schema, no-notes, drift detection 가이드를 end-to-end로 검증함

### 제품 적용 포인트

- 지식 베이스 품질은 스키마 하나로 해결되지 않음
- 최소 포맷 규칙, 안정적 직렬화, 파일 ↔ 인덱스 sync, 운영 검증, 검색 품질 보정, 스키마 피드백이 함께 있어야 장기 운영이 가능함
- 품질 장치는 작성 시점과 검색 시점, 운영 시점에 각각 있어야 함
- 포맷터와 스키마 검증은 성격이 다르므로 분리하되, 둘 다 사람이 읽는 Markdown을 기준으로 움직이게 하는 편이 좋음
- 사용자가 다음 행동을 알 수 있도록 validation 실패나 no-schema 상황을 안내형 인터페이스로 돌려주는 것이 중요함

### 해석과 시사점

- Basic Memory의 구조 품질 전략은 "강한 중앙 통제"보다 "여러 개의 약한 품질 장치를 연결하는 방식"에 가까움
- note 문법은 느슨하게 유지하되 formatting이 형태를 안정화하고, sync가 파일과 인덱스를 맞추고, doctor가 운영 루프를 검증하고, search가 retrieval 품질을 보정하고, schema가 구조 변화를 가시화함
- 이 조합 덕분에 자유로운 Markdown 저장소가 시간이 지나도 완전히 무질서한 상태로 붕괴하지 않게 설계돼 있음

## 3. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- schema validation은 강한 타입 시스템이라기보다 presence, enum, cardinality 중심의 경량 점검에 가깝다
- `validator.py`는 schema에 없는 observation과 relation을 허용하므로, 엄격한 표준화보다 유연성을 우선한다
- `docs/NOTE-FORMAT.md`는 `strict`가 sync를 막는다고 설명하지만, 현재 코드 기준 schema validation은 `schema_router`, `CLI`, `MCP tool` 경로에 있고 `sync_service.py` 내부에서 자동 실행되는 흐름은 보이지 않는다
- 즉 현재 구현은 "sync-time enforcement"보다 "on-demand quality analysis" 성격이 더 강하다
- 여기서 sync-time enforcement는 파일 동기화 시점에 자동으로 schema 규칙을 강제하는 방식을 뜻하고, on-demand quality analysis는 사용자가 validate나 diff를 실행할 때 점검하는 방식을 뜻함
- inference는 빈도 기반이라 note type이 너무 넓거나 혼합돼 있으면 유의미한 schema를 못 만들 수 있다
- drift 분석도 구조 변화는 잘 잡지만, 필드 의미 변화 같은 의미론적 drift까지는 직접 다루지 않는다

### 제품 해석

- Basic Memory의 품질 전략은 schema-first 강제 입력 시스템이 아니라 운영 중 품질 신호를 계속 수집하는 관측 시스템에 가깝다
- 이 제품의 강점은 자유도를 유지하면서도 품질 저하를 늦추는 데 있다
- 반대로 정말 강한 구조 통제가 필요한 도메인이라면 현재 방식만으로는 부족할 수 있고, 입력 단계의 제약이나 workflow gate가 추가로 필요할 수 있다

# 적용 인사이트

우리 제품이 Basic Memory에서 가장 먼저 벤치마킹해야 할 것은 "유연한 입력과 구조 품질을 양자택일로 보지 않는 설계"다. 구체적으로는 `최소 Markdown 규칙`, `usage-first schema inference`, `warn 기본값의 validation`, `drift analysis`, `file ↔ index doctor`, `search fallback`을 하나의 품질 루프로 묶는 방식이 핵심이다.

- 스키마는 초기에 강제하지 말고 실제 사용 패턴이 생긴 뒤 도입하는 편이 채택 저항이 낮음
- validation은 전면 차단보다 `warn -> strict`로 올려 가는 단계형 전략이 실무적임
- 포맷 정리, sync 검증, 검색 품질 보정은 스키마와 별개가 아니라 같은 품질 체인의 일부로 설계해야 함
- 스키마 정의를 별도 전용 테이블이 아니라 일반 note로 두면 사용자 소유권과 제품 단순성을 함께 가져가기 쉬움
- 품질 장치는 내부 엔진에만 두지 말고 CLI, MCP, API에서 모두 같은 피드백을 제공해야 팀이 실제로 활용할 수 있음
