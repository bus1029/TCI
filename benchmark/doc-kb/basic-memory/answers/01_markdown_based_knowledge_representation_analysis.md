# Markdown 기반 지식 표현 방식 분석

## 개요

Basic Memory의 핵심 선택은 "문서를 얼마나 많이 수집할 것인가"보다 "사람과 AI가 같은 지식을 어떤 형태로 오래 유지할 것인가"에 가깝다. 이 프로젝트는 PDF, DOCX, 위키 커넥터를 광범위하게 흡수하는 범용 ingest 시스템이 아니라, 일반 Markdown 파일을 원본 계약으로 삼고 그 안의 frontmatter, observation, relation을 지식 그래프로 변환하는 local-first 구조를 택했다.

처음 보는 사람이 이 문서에서 먼저 이해해야 할 전제는 아래와 같다.

- 원본 데이터는 데이터베이스가 아니라 Markdown 파일
- 데이터베이스는 검색, 링크 해석, 그래프 탐색을 위한 인덱스
- AI는 MCP 도구를 통해 이 파일과 인덱스를 읽고 씀

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| Project | 하나의 지식 베이스 단위. 고유한 루트 디렉터리와 설정을 가짐 |
| Entity | Markdown 파일 하나가 인덱싱되어 만들어지는 지식 그래프의 노드 |
| Observation | `- [category] content` 형식으로 적는 구조화된 사실 |
| Relation | `- relation_type [[Target]]` 또는 본문의 `[[Target]]`에서 추출되는 연결 |
| Permalink | 파일 경로와 별개로 유지되는 논리 식별자 |
| `memory://` URL | MCP 도구와 컨텍스트 구성에 쓰이는 엔티티 주소 체계 |

예를 들어 Basic Memory의 출발점은 아래 같은 평범한 Markdown 파일이다.

```markdown
---
title: Coffee Brewing Methods
type: note
tags: [coffee, brewing]
permalink: coffee-brewing-methods
---

# Coffee Brewing Methods

- [method] Pour over provides more flavor clarity than French press
- [technique] Water temperature at 205°F extracts optimal compounds #brewing
- relates_to [[Coffee Bean Origins]]
```

이 파일이 저장되면 시스템은 파일 자체를 원본 문서로 보관하고, frontmatter, observation, relation을 파싱한 뒤, 이를 `Entity`, `Observation`, `Relation` 형태로 DB에 인덱싱하고, 마지막으로 검색과 컨텍스트 구성에서 다시 활용한다.

벤치마킹할 지점은 세 가지다.

- 사람이 직접 읽고 수정 가능한 파일을 source of truth로 두는 방식
- 최소 문법으로 Observation, Relation, Permalink를 추출하는 방식
- 파일 경로와 분리된 논리 식별자를 두고 이동이나 이름 변경에도 링크를 버티게 하는 방식

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 사람이 직접 수정 가능한 Markdown 파일을 원본 계약으로 유지하는 구조

### 채택 기술 구조

- 기본 원칙
    - Basic Memory는 노트 하나를 "앱 내부 레코드"가 아니라 "파일 시스템 위의 Markdown 문서"로 봄
    - `docs/NOTE-FORMAT.md`는 모든 문서가 plain Markdown 파일이며, 파일 변경이 데이터베이스의 지식 그래프를 갱신한다고 명시함
    - 즉 데이터베이스는 원본 저장소가 아니라 검색과 그래프 탐색을 위한 인덱스 계층임
- 내부 계층 분리
    - `EntityParser`는 파일을 읽어 frontmatter, 본문, observation, relation을 `EntityMarkdown`으로 파싱함
    - `MarkdownProcessor`는 frontmatter와 본문, 구조화된 section을 다시 직렬화하는 역할만 맡음
    - `Entity` 모델은 하나의 Markdown 파일을 하나의 지식 노드로 저장하고, `file_path`, `permalink`, `checksum`, `entity_metadata`, `content_type`를 함께 관리함
    - `SyncService`는 파일을 다시 파싱해 DB 엔티티와 관계를 갱신하고 checksum을 반영함
    - `SearchService`는 같은 엔티티에서 entity, observation, relation 검색 row를 생성함
- 구조적 의미
    - 파일 포맷, 파싱, DB 모델, 검색 인덱싱이 계층적으로 나뉘어 있음
    - 사용자는 Markdown만 보면 되고, 내부 시스템은 그 파일에서 여러 파생 구조를 만듦
    - 노트 수정의 출발점이 앱 화면이 아니라 파일 자체라는 점이 local-first 성격을 강화함
- 제품 관점 해석
    - 사람이 직접 읽을 수 있는 파일 계약을 두면 앱 밖에서도 지식을 소유할 수 있음
    - Git, diff, 로컬 편집기, 백업 도구와 자연스럽게 연결됨
    - AI 세션이 끝나도 지식이 앱 외부의 Markdown 파일로 지속됨

### 코드 근거 예시

- `docs/NOTE-FORMAT.md`
    - 파일이 source of truth라고 명시함
    - frontmatter, observations, relations의 기본 계약을 설명함
- `src/basic_memory/markdown/entity_parser.py`
    - BOM 제거
    - YAML frontmatter 파싱
    - title 기본값을 파일명 stem으로 보정
    - type 기본값을 `note`로 보정
    - tags를 정규화함
- `src/basic_memory/markdown/markdown_processor.py`
    - frontmatter와 본문을 다시 직렬화함
    - structured section을 표준 형식으로 씀
    - 파일 쓰기는 atomic write로 처리함
- `src/basic_memory/models/knowledge.py`
    - `Entity`가 `file_path`, `permalink`, `checksum`, `content_type`, `entity_metadata`를 저장함
- `src/basic_memory/sync/sync_service.py`
    - Markdown 재파싱 후 `upsert_entity_from_markdown()`를 호출함
    - 최종 checksum과 file metadata를 다시 반영함
- `src/basic_memory/services/search_service.py`
    - 엔티티 하나에서 entity, observation, relation 검색 row를 각각 생성함

### 제품 적용 포인트

- 지식 베이스를 장기 자산으로 보려면 앱 전용 DB 레코드보다 사람이 직접 읽을 수 있는 파일 계약이 유리함
- 파서, 직렬화기, 도메인 모델, 검색 인덱서를 분리하면 저장 포맷을 유지한 채 내부 구현을 바꾸기 쉬움
- Git, diff, 로컬 편집기, 백업 전략과 자연스럽게 연결되려면 "문서 = 파일" 모델이 강력함
- local-first 제품에서는 DB보다 파일 복구와 파일 소유권을 더 중요한 운영 원칙으로 둬야 함

### 해석과 시사점

- Basic Memory의 강점은 다종 문서 수집력보다 파일 소유권과 장기 지속성에 있음
- 이 구조 덕분에 AI 세션이 끝나도 지식이 앱 밖의 Markdown 파일로 남음
- 반대로 범용 문서 수집기 관점에서는 입력 표면이 좁다

## 2. Observation, Relation, Permalink를 최소 문법으로 추출하는 파싱 구조

### 채택 기술 구조

- 기본 원칙
    - Basic Memory는 복잡한 전용 에디터 없이 일반 Markdown 문법 위에 아주 얇은 의미 계층만 추가함
    - Observation과 Relation은 별도 데이터 입력 화면이 아니라 Markdown 패턴으로 표현됨
    - 이 덕분에 사용자는 평소 쓰던 문서 작성 습관을 크게 바꾸지 않아도 됨
- observation 문법
    - Observation은 `[category] content #tag1 #tag2 (context)` 형식으로 적는 구조화된 사실임
    - `observation_plugin`은 이 패턴을 읽어 observation으로 추출함
    - 체크박스, Markdown 링크, bare wiki link는 observation에서 제외함
    - 카테고리가 없더라도 해시태그가 있으면 observation으로 인정함
- relation 문법
    - Relation은 `relation_type [[Target Entity]] (context)` 형식의 explicit relation으로 표현함
    - 본문 안의 `[[Target Entity]]`도 implicit relation으로 해석함
    - `relation_plugin`은 list item 안의 explicit relation과 prose 안의 wiki link를 모두 파싱함
- frontmatter 정규화
    - `EntityParser`는 YAML이 날짜, 숫자, 불리언을 파이썬 기본 타입으로 바꿔버리는 문제를 막기 위해 값을 다시 정규화함
    - 이 덕분에 note author는 평범한 YAML을 쓰고, downstream 코드는 일관된 타입을 받음
- 구조적 의미
    - `## Observations`, `## Relations` 같은 헤더는 관례일 뿐 필수는 아님
    - 문서 어디에서든 문법 패턴이 보이면 추출하는 방향을 택함
    - Markdown의 최소 문법이 곧 저장 모델의 출발점이 됨

### 코드 근거 예시

- `docs/NOTE-FORMAT.md`
    - observation 문법
    - explicit relation, inline relation 문법
    - permalink와 `memory://` URL의 의미를 설명함
- `src/basic_memory/markdown/plugins.py`
    - `is_observation()`, `parse_observation()`
    - `is_explicit_relation()`, `parse_relation()`
    - `parse_inline_relations()`
- `src/basic_memory/markdown/entity_parser.py`
    - markdown-it 토큰에서 observation, relation을 수집함
    - frontmatter 값을 안전한 타입으로 정규화함
- `src/basic_memory/markdown/schemas.py`
    - `Observation`, `Relation`, `EntityFrontmatter`, `EntityMarkdown`의 최소 계약을 정의함
- `src/basic_memory/markdown/utils.py`
    - `entity_model_from_markdown()`이 Markdown 결과를 `Entity`와 `Observation` DB 모델로 바꿔 줌

### 제품 적용 포인트

- 문서형 지식 베이스라면 무거운 전용 편집기보다 "일반 Markdown + 얇은 의미 문법"이 채택 비용이 낮음
- explicit relation과 inline relation을 함께 지원하면 문서 작성 습관을 강하게 바꾸지 않고도 그래프를 만들 수 있음
- frontmatter 정규화 계층을 별도로 두면 YAML 사용 편의성과 런타임 안정성을 함께 얻을 수 있음
- 사용자가 문법을 일관되게 쓸수록 검색과 그래프 품질도 좋아지므로, 제품 문서화와 템플릿이 중요함

### 해석과 시사점

- Basic Memory는 AST나 엔터프라이즈 문서 구조를 해석하는 시스템이 아니라, Markdown 작성 규칙으로 지식 그래프를 만드는 시스템에 가까움
- 이 설계는 회의록, 설계 노트, 조사 메모처럼 사람이 작성하는 문서에 잘 맞음
- 반대로 PDF 표 구조, 슬라이드 계층, 코드 심벌 구조 같은 풍부한 원문 의미는 다루지 않음

## 3. 경로와 분리된 안정 식별자와 이동 보호 구조

### 채택 기술 구조

- 식별자 기본 구조
    - Basic Memory는 파일 경로와 논리 식별자를 분리함
    - `Entity`는 실제 파일 위치인 `file_path`와 별도의 식별자 `permalink`를 함께 가짐
    - 여기에 API 안정 식별자인 `external_id` UUID도 따로 둠
    - 즉 하나의 노트는 물리 위치, 논리 주소, API 참조의 세 축으로 식별됨
- permalink 생성 방식
    - `generate_permalink()`는 단순 slugify가 아님
    - 경로를 POSIX 스타일로 정규화하고, 실확장자를 제거하고, 공백과 underscore를 hyphen으로 바꾸고, camelCase와 CJK 경계도 정리함
    - `build_canonical_permalink()`는 설정에 따라 프로젝트 slug를 prefix로 붙여 canonical permalink를 만들 수 있음
- permalink 결정 우선순위
    - `EntityService.resolve_permalink()`는 frontmatter 명시값, 기존 DB permalink, 새 경로 기반 permalink 순으로 우선순위를 둠
    - 충돌 시 숫자 suffix를 붙여 유일성을 확보함
    - 즉 파일 이동이나 이름 변경이 일어나도 기존 링크를 최대한 지키려는 쪽으로 설계됨
- 링크 해석 방식
    - `LinkResolver`는 exact permalink, exact title, exact file path, `.md` path, fuzzy search 순으로 시도함
    - source path가 주어지면 같은 폴더나 가까운 경로를 우선하는 context-aware resolution도 수행함
    - canonical permalink와 legacy permalink를 함께 후보로 보아 이전 링크가 깨지지 않게 함
- 이동 처리 방식
    - `move_entity()`와 `SyncService.handle_move()`는 파일을 실제로 rename한 뒤 DB의 `file_path`를 갱신함
    - 설정이 켜져 있으면 frontmatter의 permalink도 새 경로 기준으로 다시 씀
    - 그 다음 checksum을 다시 계산해 DB에 반영하고, 검색 인덱스를 다시 맞춤
    - 파일 이동을 단순 rename이 아니라 식별자와 인덱스의 일관성 유지 작업으로 다룸

### 코드 근거 예시

- `src/basic_memory/utils.py`
    - `generate_permalink()`
    - `build_canonical_permalink()`
    - `detect_potential_file_conflicts()`
- `src/basic_memory/models/knowledge.py`
    - `Entity`의 project별 `file_path`, `permalink` unique index
    - `external_id` UUID
    - observation, relation의 synthetic permalink 생성
- `src/basic_memory/repository/entity_repository.py`
    - `get_by_permalink()`, `get_by_file_path()`
    - `get_file_path_for_permalink()`, `get_permalink_for_file_path()`
    - permalink conflict 시 numeric suffix 부여
- `src/basic_memory/services/entity_service.py`
    - `resolve_permalink()`
    - `create_entity()`
    - `move_entity()`
- `src/basic_memory/services/link_resolver.py`
    - permalink, title, path, fuzzy search 순의 해석
    - source path 기반 nearest match 선택
    - canonical permalink와 legacy permalink를 함께 처리
- `src/basic_memory/services/file_service.py`
    - `move_file()`
    - `update_frontmatter()`
- `src/basic_memory/markdown/utils.py`
    - frontmatter에 permalink가 없으면 기존 permalink를 보존함

### 제품 적용 포인트

- 파일 저장소 기반 제품이라면 경로와 논리 식별자를 분리해야 폴더 정리와 링크 안정성을 함께 가져갈 수 있음
- permalink 생성 규칙은 slugify 한 줄로 끝내지 말고 Unicode, 경로, 프로젝트 prefix, 충돌 suffix까지 함께 설계해야 함
- 이동 시 DB만 바꾸거나 파일만 바꾸면 안 되고, frontmatter, checksum, 검색 인덱스까지 같은 트랜잭션 감각으로 다뤄야 함
- 링크 해석은 exact match만으로 끝내지 말고 canonical permalink, legacy permalink, source-context 기반 해석을 함께 설계하는 편이 실무적으로 강함

### 해석과 시사점

- Basic Memory의 식별자 설계는 "로컬 파일은 자주 옮겨진다"는 현실을 잘 반영함
- 특히 permalink와 file path를 분리한 점, canonical과 legacy 후보를 함께 해석하는 점이 실무적으로 강함
- 반대로 permalink를 이동 시 갱신할지 유지할지는 설정과 운영 원칙에 따라 달라질 수 있으므로, 제품 차원에서 팀 규칙을 같이 정해야 함

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 이 구조의 입력 표면은 사실상 Markdown 중심임
- 지식 그래프 품질은 문서 작성자가 observation과 relation 문법을 얼마나 일관되게 쓰는지에 영향을 받음
- `MarkdownProcessor`는 structured section을 표준 형식으로 다시 쓰는 계층이라, 완전한 원문 round-trip 보존 레이어로 보기는 어려움
- permalink 안정성은 강하지만, 이동 시 permalink를 갱신할지 유지할지는 설정과 운영 관례를 함께 정해야 함
- 링크 해석은 exact permalink, title, path, fuzzy search를 조합하는 구조라서 완전 불변의 hard reference 시스템과는 다름

### 제품 해석

- Basic Memory는 "모든 문서를 다 파싱하는 수집 플랫폼"보다 "Markdown 기반 지식을 오래 유지하고 다시 찾게 만드는 인프라"에 가까움
- 이 제품의 강점은 지식 표현을 인간 친화적으로 유지한 채 검색과 그래프를 얹는 데 있음
- 따라서 벤치마킹의 초점도 파서 종류보다 `저장 계약`, `최소 문법`, `식별자 설계`에 맞추는 편이 맞음

# 적용 인사이트

우리 제품이 Basic Memory에서 가장 먼저 벤치마킹해야 할 것은 Markdown을 단순 입력 포맷이 아니라 장기 지식 계약으로 취급하는 태도다. 구체적으로는 `파일 원본 계약`, `얇은 의미 문법`, `경로와 분리된 permalink`, `이동 시 frontmatter와 checksum까지 함께 갱신하는 흐름`을 한 세트로 가져가는 것이 핵심이다.

- 사용자와 AI가 같은 저장소를 함께 써야 한다면 사람이 직접 편집 가능한 파일 포맷을 원본으로 두는 편이 유리함
- 그래프를 만들기 위해 거대한 DSL을 도입하기보다 observation과 wiki link 같은 최소 문법을 먼저 설계하는 편이 실용적임
- 파일 정리와 폴더 개편이 잦은 환경이라면 `file_path`와 `permalink`를 반드시 분리해야 함
- 링크 안정성을 높이려면 exact match뿐 아니라 canonical permalink, legacy permalink, source-context 기반 resolution까지 같이 설계해야 함
- 이 제품의 차별점은 다종 문서 ingest가 아니라 "사람이 읽는 Markdown을 그대로 장기 기억 인프라로 바꾸는 방식"에 있음