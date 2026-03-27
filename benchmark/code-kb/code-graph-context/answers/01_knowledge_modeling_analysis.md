# CodeGraphContext 지식 모델링 및 다중 언어 대응 아키텍처 분석

## 도입 개요

이 문서는 CodeGraphContext가 로컬 소스 코드를 어떤 단위로 분해하고 어떤 공통 스키마로 그래프에 적재하는지 현재 구현 기준으로 분석한 문서이다. 특히 다중 언어 파서가 반환하는 심벌 구조가 그래프 빌더에서 어떻게 공통 라벨 체계로 수렴하는지, 그리고 KùzuDB에서 복합 식별자와 다형성 관계를 어떻게 처리하는지에 초점을 둔다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 심벌 중심 지식 모델과 다중 언어 정규화

### 채택 기술 구조

- CodeGraphContext는 텍스트 청크가 아니라 함수, 클래스, 변수, 인터페이스 같은 코드 심벌을 지식의 기본 단위로 저장함
- 언어별 파서는 다르지만 반환 구조는 `functions`, `classes`, `variables`, `imports`, `function_calls` 같은 공통 키를 중심으로 맞춰짐
- GraphBuilder는 이 표준 반환 구조를 `Function`, `Class`, `Variable`, `Trait`, `Interface`, `Struct`, `Enum` 같은 공통 라벨군으로 매핑함
- 중요한 점은 공통 라벨 체계가 곧 단일 물리 테이블을 뜻하는 것은 아니라는 점임
- 실제 KùzuDB 스키마에서는 `Function`, `Class`, `Variable` 등이 각각 별도 NODE TABLE로 선언됨
- 다만 여러 노드 테이블이 `path`, `line_number`, `end_line`, `source`, `docstring`, `lang`, `is_dependency` 같은 공통 좌표와 메타데이터를 공유해 질의 방식과 후속 처리 패턴을 통일함
- `Function`에는 `context`, `context_type`, `class_context`, `decorators`, `args`, `cyclomatic_complexity`까지 함께 저장해 단순 이름 검색을 넘어 구조 분석에 필요한 문맥을 남김
- `Variable`은 현재 스키마상 `end_line`이 없고 `Parameter`는 `function_line_number`를 별도 키로 저장하므로 심벌 타입별 메타데이터는 완전히 동일하지 않음

### 코드 근거 예시

```python
item_mappings = [
    (file_data.get('functions', []), 'Function'),
    (file_data.get('classes', []), 'Class'),
    (file_data.get('traits', []), 'Trait'),
    (file_data.get('variables', []), 'Variable'),
    (file_data.get('interfaces', []), 'Interface'),
]
```

```sql
CREATE NODE TABLE Function (
  uid STRING,
  name STRING,
  path STRING,
  line_number INT64,
  end_line INT64,
  source STRING,
  docstring STRING,
  lang STRING,
  cyclomatic_complexity INT64,
  context STRING,
  context_type STRING,
  class_context STRING,
  is_dependency BOOLEAN,
  decorators STRING[],
  args STRING[],
  PRIMARY KEY (uid)
)
```

### 제품 적용 포인트

- `src/codegraphcontext/tools/graph_builder.py`의 `item_mappings`는 다중 언어 결과를 공통 라벨로 수렴시키는 중심 지점임
- `src/codegraphcontext/core/database_kuzu.py`는 공통 메타데이터가 실제 스키마에 어떻게 반영되는지 보여줌
- `src/codegraphcontext/tools/languages/` 하위 구현은 언어별 AST 차이를 흡수하면서도 공통 반환 계약을 유지하는 참고 사례임
- `src/codegraphcontext/tools/languages/python.py`의 노트북 변환 경로는 문서형 코드 자산도 별도 저장소 없이 같은 지식 모델로 흡수하는 구현 사례임

### 해석과 시사점

- 이 프로젝트의 정규화는 모든 언어를 하나의 테이블에 넣는 방식이 아니라 언어별 파싱 결과를 공통 심벌 계약으로 수렴시키는 방식에 가까움
- 따라서 새 언어를 추가할 때 핵심 비용은 DB 전체 재설계보다 파서가 기존 반환 계약을 잘 따르도록 맞추는 데 있음
- 반대로 언어별 표현력이 완전히 같지는 않기 때문에 특정 언어에서만 나오는 심벌은 별도 라벨과 스키마 확장이 계속 필요함

## 2. 복합 식별자 우회와 다형성 관계 스키마

### 채택 기술 구조

- Function, Class, Variable 같은 심벌은 실질적으로 `name + path + line_number` 조합으로 식별됨
- KùzuDB 스키마에서는 이를 직접 복합 기본키로 두지 않고 `uid` 단일 키로 우회함
- 현재 구현은 `INSERT OR IGNORE` 기반이 아니라 `MERGE + uid 주입` 방식으로 동작함
- GraphBuilder는 먼저 `MERGE (n:Label {name, path, line_number})` 형태로 노드를 찾거나 만들고 `SET n += $props`로 속성을 채움
- Kuzu 래퍼는 이 쿼리를 번역하면서 `name`, `path`, `line_number`를 조합해 `uid`를 자동 주입함
- 동시에 허용된 컬럼만 남기도록 속성 필터링을 수행해 스키마 불일치와 쓰기 오류를 줄임
- 관계 모델은 노드보다 더 적극적으로 다형성을 활용함
- 예를 들어 `CALLS`는 `Function -> Function`, `Function -> Class`, `File -> Function`, `Class -> Class` 같은 여러 조합을 하나의 REL TABLE에 담음
- 호출 엣지에는 `line_number`, `args`, `full_call_name`을 함께 저장해 단순 연결 그래프를 넘는 실행 맥락을 남김
- 다만 KùzuDB가 다형성 `MERGE`를 자연스럽게 지원하지 않는 제약이 있어 실제 생성 로직은 가능한 조합을 순서대로 시도하는 우회 전략을 사용함

### 코드 근거 예시

```sql
CREATE REL TABLE CALLS (
  FROM Function TO Function,
  FROM Function TO Class,
  FROM File TO Function,
  FROM File TO Class,
  FROM Class TO Function,
  FROM Class TO Class,
  line_number INT64,
  args STRING[],
  full_call_name STRING
)
```

```python
MERGE (n:Function {name: $name, path: $path, line_number: $line_number})
SET n += $props
```

```python
if label in self.uid_map:
    pk_parts = self.uid_map[label]
    ...
    new_block = f"{{{props_str}, uid: ${uid_param}}}"
```

### 제품 적용 포인트

- `src/codegraphcontext/core/database_kuzu.py`의 `uid_map`과 `_translate_query()`는 복합 식별자를 단일 키로 흡수하는 실전 패턴임
- `src/codegraphcontext/tools/graph_builder.py`의 노드 생성부는 공통 좌표 기반 `MERGE`와 속성 갱신 패턴의 기준 구현임
- 같은 파일의 `CALLS` 생성부는 다형성 관계를 유지하면서도 백엔드 제약을 우회하는 구현 사례임

### 해석과 시사점

- 노드 모델은 공통 좌표 메타데이터로 정규화하고 관계 모델은 하나의 관계 타입에 여러 엔드포인트 조합을 허용하는 방식으로 확장성을 확보함
- 대신 쿼리 엔진 제약이 있는 백엔드에서는 관계 생성 로직이 복잡해지고 생성 순서와 폴백 쿼리 관리 비용이 늘어남
- 즉 이 구조는 스키마 단순화와 런타임 생성 복잡도를 맞바꾼 설계라고 볼 수 있음
- 관계 타입 수를 억제하면서 관계 속성을 풍부하게 두는 방식은 쿼리 표면을 단순하게 유지하는 대신 관계 생성 계층의 책임을 키우는 선택임

## 3. 심벌 문맥 보존과 구조 질의용 보조 관계 설계

### 채택 기술 구조

- 이 프로젝트의 강점은 함수 이름과 라인 번호만 저장하는 수준에서 멈추지 않는다는 점임
- Python을 포함한 여러 언어 파서는 함수와 변수에 대해 `context`, `context_type`, `class_context`를 함께 반환함
- GraphBuilder는 함수에 대해 `HAS_PARAMETER`, 클래스 메서드에 대해 `Class -[:CONTAINS]-> Function`, 중첩 함수에 대해 `Function -[:CONTAINS]-> Function` 관계까지 생성해 심벌의 상위 문맥을 그래프에 올림
- 이 구조 덕분에 단순 이름 검색을 넘어 메서드 소속, 중첩 함수, 파라미터 기반 검색 같은 구조 질의가 가능해짐

### 코드 근거 예시

```python
func_data = {
    "name": name,
    "line_number": node.start_point[0] + 1,
    "end_line": func_node.end_point[0] + 1,
    "args": args,
    "context": context,
    "context_type": context_type,
    "class_context": class_context,
}
```

```python
MERGE (p:Parameter {name: $arg_name, path: $path, function_line_number: $line_number})
MERGE (fn)-[:HAS_PARAMETER]->(p)
```

### 제품 적용 포인트

- `src/codegraphcontext/tools/languages/` 하위 파서는 심벌 자체뿐 아니라 상위 문맥까지 함께 반환하는 설계를 참고할 만함
- `src/codegraphcontext/tools/graph_builder.py`는 문맥 메타데이터를 보조 관계로 승격해 질의 가능성을 넓히는 구현 사례임

### 해석과 시사점

- 심벌의 이름과 위치만이 아니라 상위 문맥과 파라미터 관계까지 같이 저장하는 점은 에이전트 검색 품질을 높이는 실질적 강점임
- 우리 팀이 지식 베이스를 만든다면 핵심 심벌 외에도 `HAS_PARAMETER`, `CONTAINS` 같은 보조 관계를 초기에 같이 설계하는 편이 좋음

## 4. import와 이질적 코드 자산 흡수 전략

### 채택 기술 구조

- `IMPORTS`는 파일과 모듈의 단순 연결로 끝나지 않고 `alias`, `imported_name`, `full_import_name`, `line_number`를 관계 속성으로 분리해 저장함
- 이 구조는 동일 모듈을 여러 별칭으로 가져오거나 특정 심벌만 import하는 언어 차이를 흡수하는 데 유리함
- Python 파서는 `.ipynb`를 `nbconvert`로 임시 `.py`로 변환한 뒤 같은 파이프라인으로 파싱하고 저장 경로는 원래 노트북 경로를 유지함
- 즉 import 문법 차이와 노트북 같은 이질적 코드 자산을 별도 저장소 없이 공통 지식 모델 안으로 흡수하는 전략을 택함

### 제품 적용 포인트

- `src/codegraphcontext/tools/graph_builder.py`의 `IMPORTS` 생성 로직은 alias 기반 리팩터링이나 모듈 의존성 분석에 유리한 모델링 패턴임
- `src/codegraphcontext/tools/languages/python.py`의 노트북 변환 경로는 문서형 코드 자산도 별도 저장소 없이 같은 지식 모델로 흡수하는 구현 사례임

### 해석과 시사점

- import는 텍스트 한 줄로 저장하기보다 모듈 엔터티와 관계 속성으로 분리하는 편이 후속 분석과 코드 수정에 유리함
- 노트북을 별도 ingestion 체인으로 분리하지 않고 공통 심벌 모델로 흡수하는 방식은 사내 분석 자산 범위를 넓히는 데 참고할 만함

## 5. 한계와 trade-off

### 현재 구현 기준에서 주의할 점

- 공통 심벌 모델이 존재해도 언어별 표현력은 완전히 같지 않음
- 예를 들어 `.h` 파일은 현재 C가 아니라 C++ 파서로 우선 매핑됨
- 모든 심벌 타입이 같은 메타데이터를 가지는 것도 아님
- 따라서 완전한 언어 불변 스키마로 해석하면 과장이고 실제로는 공통 축을 최대화한 다중 언어 스키마로 보는 편이 정확함

### 제품 해석

- 이 설계는 LLM 친화적인 공통 모델과 언어 특수성을 동시에 가져가려는 절충안임
- 초기 제품에서는 모든 언어 세부 구조를 다 담으려 하기보다 공통 조회 가치가 높은 좌표와 관계부터 고정하는 편이 현실적임

# 사내 지식 베이스 구축 시 벤치마킹 인사이트

### 공통 심벌 계약을 먼저 고정

- 새 언어를 붙일 때 저장소 스키마를 자주 흔들지 않으려면 파서가 따를 공통 반환 계약을 먼저 정의하는 편이 유리함
- `functions`, `classes`, `variables`, `imports`, `function_calls` 같은 공통 키를 우선 정하고 언어별 확장은 그 위에 얹는 구조가 안정적임

### 좌표 메타데이터와 문맥 메타데이터를 같이 저장

- 에이전트가 실제 파일 수정까지 이어지려면 `path`, `line_number`, `end_line` 같은 좌표 메타데이터를 공통 계약으로 먼저 고정해야 함
- 여기에 `context`, `context_type`, `class_context` 같은 문맥 메타데이터를 함께 넣어야 검색 결과를 실제 편집이나 관계 분석으로 연결하기 쉬워짐

### 복합 식별자는 쿼리 번역 레이어에서 흡수

- 심벌 식별이 이름, 파일, 위치 조합이라면 DB 기본키를 그대로 노출하기보다 `uid` 생성 레이어를 두는 편이 운영과 이식성에 유리함
- 특히 여러 그래프 엔진을 지원할 계획이라면 쿼리 번역 계층에서 키 생성과 속성 필터링을 함께 처리하는 전략이 효과적임

### 관계 타입은 적게 두고 관계 속성은 풍부하게 설계

- 호출 관계를 여러 테이블로 잘게 쪼개기보다 `CALLS` 같은 대표 관계 타입에 `line_number`, `args`, `full_call_name`을 실어주는 방식이 에이전트 분석과 후속 질의에 유리함
- 다만 엔진 제약 때문에 생성 로직이 복잡해질 수 있으므로 스키마 단순화 이득과 런타임 복잡도를 함께 평가해야 함

### import와 parameter 같은 보조 구조도 그래프에 올림

- 대다수 팀은 함수와 클래스만 올리고 끝내지만 실제 에이전트 품질은 import alias, parameter, nested context 같은 보조 구조에서 차이가 많이 남
- 우리 팀이 지식 베이스를 만든다면 핵심 심벌 외에도 `HAS_PARAMETER`, `IMPORTS`, `CONTAINS` 같은 보조 관계를 초기에 같이 설계하는 편이 좋음
