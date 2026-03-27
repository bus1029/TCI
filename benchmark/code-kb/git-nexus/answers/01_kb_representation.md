# 1. GitNexus 지식 모델링 및 다중 언어 대응 아키텍처 분석

## 도입 개요
GitNexus의 지식 표현은 "모든 것을 하나의 범용 노드로 뭉치는 방식"이 아니라, 공통 그래프 계약 위에 언어별 심벌 레이블을 올리고 관계는 하나의 공통 릴레이션으로 묶는 하이브리드 구조에 가깝습니다. 파일과 폴더로 물리 구조를 먼저 만들고, 그 위에 Tree-sitter 기반 파싱 결과를 `Function`, `Class`, `Struct`, `Trait` 같은 심벌 노드로 얹은 뒤, 커뮤니티와 프로세스 같은 파생 지식까지 같은 그래프 안에 흡수합니다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 파일 구조와 심벌 구조를 분리한 2층 지식 단위 설계

### 채택 기술 구조
- 지식의 최소 단위를 처음부터 심벌 하나로만 보지 않고, 먼저 `File`과 `Folder`로 저장소의 물리 구조 생성 후 파싱 단계에서 심벌 노드 추가하는 2층 구조 사용
- 파싱 결과는 단일 "범용 심벌 테이블"로 수렴하지 않고 `Function`, `Class`, `Interface`, `Method`와 `Struct`, `Enum`, `Trait`, `Impl`, `TypeAlias`, `Const` 같은 언어별 레이블 유지
- 런타임 계약은 공통 구조 사용
  - 인메모리 그래프의 모든 노드는 `GraphNode { id, label, properties }` 형식 따름
  - `properties`는 `name`, `filePath`, `startLine`, `endLine`, `language`, `isExported` 같은 공통 속성 공유
- GitNexus의 "다중 언어 정규화"는 완전한 단일 물리 스키마보다 공통 DTO와 공통 질의 패턴 위에 다중 레이블을 유지하는 방식에 가까움
- 현재 네이티브 파서 기준 지원 언어는 `JavaScript`, `TypeScript`, `TSX`, `Python`, `Java`, `C`, `C++`, `C#`, `Go`, `Rust`, `PHP`, `Kotlin`, 선택적 `Swift`임

### 코드 근거 예시
- `gitnexus/src/core/ingestion/structure-processor.ts`
  - 저장소 경로 순회 후 `File`과 `Folder` 노드 먼저 생성
  - `CONTAINS` 관계 생성
- `gitnexus/src/core/ingestion/parsing-processor.ts`
  - 기본 레이블을 `CodeElement`로 두고 실제 capture에 따라 `Function`, `Class`, `Interface`, `Method`, `Struct`, `Trait` 등 구체 레이블로 치환함
- `gitnexus/src/core/graph/types.ts`
  - 공통 인메모리 계약인 `GraphNode`, `NodeLabel`, `NodeProperties` 정의
- `gitnexus/src/core/kuzu/schema.ts`
  - 물리 저장은 `File`, `Function`, `Class`, `Interface`, `Method`, `CodeElement`, `Struct`, `Enum` 등 별도 node table로 선언됨

### 제품 적용 포인트
- 다중 언어를 다룰 때는 "저장 계층은 레이블별 분리, 애플리케이션 계층은 공통 노드 계약으로 통일" 방식이 현실적임
- 파일 트리와 심벌 트리를 동시에 보존하면 검색, 영향 분석, 코드 브라우징, UI 파일 패널을 같은 그래프에서 처리하기 쉬움
- 언어별 특수 심벌을 억지로 범용 타입 하나에 접어 넣기보다 공통 속성만 맞추고 레이블 유지하는 편이 추후 질의 표현력 측면에서 유리함

### 해석과 시사점
- GitNexus의 강점은 "범용 스키마 하나"보다 "공통 계약 위에 풍부한 레이블을 얹는 방식"에 있음
- 이 구조는 언어별 특징을 잃지 않으면서도 에이전트와 UI에는 일관된 그래프 인터페이스 제공 가능
- 반대로 완전히 추상화된 단일 타입 모델은 아니므로 질의와 적재 계층에서는 레이블 확장 관리 계속 필요

## 2. 노드는 분리하고 관계는 단일 `CodeRelation`으로 통합하는 하이브리드 스키마

### 채택 기술 구조
- GitNexus는 노드 테이블은 타입별로 분리하지만, 관계는 하나의 `CodeRelation` 릴레이션 테이블로 통합함
- 관계의 종류는 별도 릴레이션 테이블을 늘리는 대신 `type` 속성으로 구분함
- 현재 핵심 관계 타입은 `CONTAINS`, `DEFINES`, `IMPORTS`, `CALLS`, `EXTENDS`, `IMPLEMENTS`, `MEMBER_OF`, `STEP_IN_PROCESS`임
- 관계 메타데이터도 함께 저장함
  - `confidence`는 해석 신뢰도 표현
  - `reason`은 해석 근거 표현
  - `step`은 프로세스 내 순서 표현
- 이 설계 덕분에 MCP 도구와 Cypher 질의는 "관계 하나 + type 필터"라는 단순한 표면 유지 가능

### 코드 근거 예시
- `gitnexus/src/core/kuzu/schema.ts`
  - `REL_TABLE_NAME = 'CodeRelation'`
  - `REL_TYPES`에 지원 관계 타입 정의
  - `CREATE REL TABLE CodeRelation (...)` 스키마에 `type`, `confidence`, `reason`, `step` 속성 사용
- `gitnexus/src/mcp/tools.ts`
  - Cypher 예시도 모두 `[:CodeRelation {type: 'CALLS'}]` 형태 전제로 설명함
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - 관계 적재 시 `CodeRelation` CSV를 `FROM`/`TO` 레이블 쌍별로 다시 나눠 `COPY` 수행
  - 논리적으로는 관계가 하나지만 Kuzu 적재 단계에서는 레이블 쌍 제약을 만족시키기 위한 물리적 분할 필요

### 제품 적용 포인트
- 관계 종류가 계속 늘어나는 시스템이라면 릴레이션을 여러 개로 찢기보다 공통 관계 + 타입 속성 모델이 운영과 질의 측면에서 단순함
- 저장소 엔진이 FROM/TO 레이블 제약을 강하게 요구하면 GitNexus처럼 적재 단계에서만 pair 분할을 두는 방식이 실용적임
- `confidence`, `reason` 같은 해석 메타데이터를 관계에 붙여두면 이후 영향 분석이나 LLM 응답에서 "확실한 연결"과 "추정 연결" 구분 쉬워짐

### 해석과 시사점
- GitNexus는 "모든 것을 단일 테이블로" 저장하는 구조가 아니라 "노드는 다형적으로 유지하고 관계 인터페이스만 단순화"한 구조임
- 이 선택은 LLM 도구 표면을 단순하게 만들지만 레이블 종류가 늘어날수록 관계 스키마의 `FROM ... TO ...` 선언이 커지는 trade-off 동반

## 3. 결정적 ID와 심벌 인덱스로 멱등성과 해석 가능성을 확보

### 채택 기술 구조
- GitNexus의 ID 생성은 UUID 기반이 아니라 `generateId(label, name) => \`${label}:${name}\`` 형태의 결정적 문자열 조합을 사용함
- 이 규칙은 파일, 폴더, 심벌, 관계에 모두 적용됨
- 실제 심벌 노드 ID는 단순히 이름만 쓰지 않고 대체로 `label:filePath:symbolName` 꼴로 생성됨
- 관계 ID도 `CALLS`, `DEFINES`, `IMPORTS` 같은 관계 타입과 source/target 조합으로 결정적으로 만들어짐
- 추가로 심벌 해석을 위해 파일 단위 exact index와 프로젝트 전역 fuzzy index를 함께 유지하는 `SymbolTable` 사용

### 코드 근거 예시
- `gitnexus/src/lib/utils.ts`
  - `generateId(label, name)`는 단순 문자열 결합 함수
- `gitnexus/src/core/ingestion/structure-processor.ts`
  - 파일과 폴더는 경로 기반 `File:path`, `Folder:path` 식 ID 생성
- `gitnexus/src/core/ingestion/parsing-processor.ts`
  - 파싱된 심벌은 `generateId(nodeLabel, \`${file.path}:${nodeName}\`)` 형태로 생성됨
- `gitnexus/src/core/ingestion/symbol-table.ts`
  - `fileIndex: Map<filePath, Map<symbolName, nodeId>>`
  - `globalIndex: Map<symbolName, SymbolDefinition[]>`
  - exact lookup과 fuzzy lookup 동시 제공
- `gitnexus/src/core/kuzu/kuzu-adapter.ts`
  - `comm_`, `proc_` 접두어를 별도 노드 타입 판별 규칙으로 사용함

### 제품 적용 포인트
- 인덱싱 파이프라인 재실행 시 동일 노드 재사용을 노린다면 사람 읽을 수 있는 결정적 ID가 디버깅과 점진 갱신에 유리함
- 파일 범위 exact index와 프로젝트 범위 fuzzy index를 분리하면 import가 완전하지 않은 언어나 프레임워크 매직이 섞인 코드에서도 점진적 해석 가능
- 단순한 ID 규칙을 쓰더라도 심벌은 이름만이 아니라 최소한 파일 경로 같은 문맥을 함께 포함해야 충돌 위험 줄어듦

### 해석과 시사점
- GitNexus는 무결성을 DB 제약보다 인메모리 규칙과 ID 설계에서 먼저 확보하려는 성향이 강함
- 이 방식은 빠르고 예측 가능하지만 함수 오버로드나 익명 구조처럼 "이름 + 파일 경로"만으로 충분히 구분되지 않는 언어 구조에서는 충돌 가능성을 완전히 제거하지 못함
- 특히 상속과 구현 관계처럼 외부 심벌을 참조하는 일부 흐름은 파일 경로 없는 이름 기반 ID를 쓰는 코드가 있어 fuzzy 해석 여지 남음

## 4. AST 사실만 저장하지 않고 커뮤니티와 프로세스를 같은 그래프에 승격

### 채택 기술 구조
- GitNexus의 지식 베이스는 단순 AST 저장소가 아님
- 파싱과 관계 분석이 끝난 뒤 그래프 위에서 `Community`, `Process`라는 파생 노드를 추가 생성함
- `Community`는 밀접하게 연결된 심벌 묶음을 기능 영역처럼 표현하고 `Process`는 진입점에서 종단점까지의 실행 흐름을 요약함
- 이 파생 노드들은 별도 보조 문서가 아니라 같은 그래프 스키마 안에 정식 노드로 저장되며 원래 심벌들과 `MEMBER_OF`, `STEP_IN_PROCESS` 관계로 연결됨

### 코드 근거 예시
- `gitnexus/src/core/ingestion/community-processor.ts`
  - 커뮤니티 노드는 `comm_${number}` 형식 ID를 가짐
  - `heuristicLabel`, `cohesion`, `symbolCount`를 계산해 저장함
- `gitnexus/src/core/ingestion/process-processor.ts`
  - 프로세스 노드는 `proc_${idx}_${entryName}` 형식 ID를 가짐
  - `processType`, `stepCount`, `communities`, `entryPointId`, `terminalId`를 저장함
- `gitnexus/src/core/graph/types.ts`
  - `NodeProperties` 안에 `heuristicLabel`, `cohesion`, `processType`, `stepCount`, `communities`, `entryPointScore` 같은 상위 메타데이터 필드 포함
- `gitnexus/src/core/kuzu/schema.ts`
  - `Community`, `Process`가 별도 node table로 선언돼 있음

### 제품 적용 포인트
- 코드 조각 자체뿐 아니라 "기능 영역"과 "실행 흐름"을 노드로 승격하면 검색 결과를 프로세스 단위로 묶거나 영향 분석을 아키텍처 수준에서 설명하기 쉬워짐
- 이런 파생 지식을 같은 저장소에 넣어두면 에이전트 도구, 웹 시각화, 문서 생성기가 동일한 질의 계층 재사용 가능

### 해석과 시사점
- GitNexus의 지식 모델은 AST 중심 지식 베이스 위에 아키텍처 추론 레이어를 올린 형태임
- 이 점이 "파일/심벌 검색 도구"와 GitNexus를 구분하는 핵심 강점임
- 다만 `Community`, `Process`는 정적 컴파일러 사실이라기보다 후처리 추론 결과이므로 이를 소비하는 쪽에서는 확정 사실과 해석 레이어 구분 필요

## 5. 워커와 웹을 고려한 직렬화 가능한 그래프 계약

### 채택 기술 구조
- 인메모리 그래프는 `Map` 기반으로 관리되어 노드와 관계 추가 시 중복 삽입 기본 방지
- 대규모 그래프를 다룰 때 불필요한 배열 복사를 줄이기 위해 `iterNodes()`, `iterRelationships()`, `forEachNode()`, `forEachRelationship()` 같은 zero-copy 성격 접근자 제공
- 워커 통신이나 웹 메인 스레드 전송에서는 `Map`과 함수가 직접 전달되지 않으므로 파이프라인 결과를 배열 기반 `SerializablePipelineResult`로 한 번 직렬화한 뒤 다시 복원함

### 코드 근거 예시
- `gitnexus/src/core/graph/graph.ts`
  - 내부 저장은 `Map<string, GraphNode>`, `Map<string, GraphRelationship>`
  - 외부에는 iterator와 count getter를 함께 노출함
- `gitnexus/src/types/pipeline.ts`
  - `serializePipelineResult()`는 iterator 결과를 배열로 변환해 `postMessage` 가능한 형태로 바꿈
  - `deserializePipelineResult()`는 다시 `KnowledgeGraph`로 복원함

### 제품 적용 포인트
- 대형 그래프를 다루는 제품이라면 런타임 내부 표현과 IPC 전송 표현 분리하는 편이 안전함
- 저장 계층과 별개로 "워커 친화적인 DTO"를 설계해두면 브라우저 버전과 서버 버전이 같은 논리 모델 공유하기 쉬워짐

### 해석과 시사점
- GitNexus는 지식 모델을 DB 스키마만으로 정의하지 않고 인메모리 그래프 계약과 워커 직렬화 규격까지 포함한 운영 모델로 봄
- 이는 웹과 CLI가 같은 개념 공유하는 데 유리하지만 구현 복잡도는 그만큼 늘어남

## 6. 한계와 trade-off

### 현재 구현 기준에서 주의할 점
- 공통 모델은 존재하지만 물리 저장까지 완전히 단일 스키마로 통합된 것은 아님
- `CodeElement`는 존재하지만 실제 파싱 결과는 가능한 한 구체 레이블로 저장되므로 범용 상위 타입 하나만으로 전부 처리된다고 보기는 어려움
- 관계는 단일 `CodeRelation` 인터페이스로 단순화돼 있지만 Kuzu 적재 단계에서는 레이블 쌍별 분할 필요
- 결정적 ID는 디버깅과 멱등성에 유리하지만 오버로드나 이름 충돌 같은 언어 특수 케이스에는 완전한 해법 아님
- 지원 언어는 꽤 넓지만 파서가 설치되지 않은 언어는 파싱 단계에서 건너뜀

### 제품 해석
- GitNexus의 KB 표현 전략은 "완전한 범용 추상화"보다 "실제 개발 도구에 바로 쓰기 좋은 구조적 타협"에 가까움
- 저장소와 에이전트 도구가 이해하기 쉬운 단순한 인터페이스를 유지하면서도 내부적으로는 언어별 차이와 후처리 추론 레이어를 수용하는 쪽에 무게가 실려 있음

# 적용 인사이트
- 파일 구조와 심벌 구조 분리 후 공통 노드 계약 두는 방식 검토 필요
- 관계는 가능한 한 단일 인터페이스 유지하고 신뢰도와 생성 이유 같은 메타데이터 동반 저장 필요
- 정적 구문 사실만 저장하지 말고 커뮤니티와 실행 흐름 같은 파생 지식까지 같은 그래프에 승격하는 방식 검토 가치 높음
- 결정적 문자열 ID는 빠르지만 오버로드와 이름 충돌에 약하므로 서명 기반 키나 AST 위치 기반 키 병행 검토 필요
- "공통 계약 + 다중 레이블" 전략은 확장성이 높지만 저장 계층 스키마 유지 비용 동반하므로 실제 지원 범위 먼저 정한 뒤 도입하는 편이 안전함
