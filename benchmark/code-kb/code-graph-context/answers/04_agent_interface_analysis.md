# CodeGraphContext 지능형 에이전트 도구 인터페이스 분석

## 도입 개요

이 문서는 CodeGraphContext가 로컬 코드 그래프를 에이전트가 실제로 호출 가능한 도구 집합으로 어떻게 노출하는지 현재 구현 기준으로 분석한 문서이다. 특히 stdio 기반 MCP 서버 루프, 작업 의미가 드러나는 도구 스키마, JSON 응답 래핑 방식, 장기 작업 제어, 안전한 fallback 질의 도구를 중심으로 실제 제품 설계에 참고할 수 있는 인터페이스 설계 포인트를 정리한다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. stdio 기반 MCP 서버 루프와 프로토콜 최소 구현

### 채택 기술 구조

- CodeGraphContext의 에이전트 인터페이스는 IDE 플러그인 내부 API가 아니라 표준 입력과 표준 출력을 사용하는 JSON-RPC 기반 MCP 서버로 노출됨
- 서버는 `initialize`, `tools/list`, `tools/call`, `notifications/initialized` 정도의 최소 메서드만 구현해 도구 호출 중심의 단순한 표면을 유지함
- `initialize` 응답에는 `protocolVersion`, `serverInfo`, `capabilities`가 포함되며 `capabilities`는 현재 `tools.listTools`만 노출함
- 흥미로운 점은 `serverInfo` 안에 `systemPrompt`를 함께 실어 클라이언트가 연결 직후 도구 사용 원칙을 같이 전달받게 만든다는 점임
- 메인 루프는 `stdin.readline`을 executor에서 읽고, 실제 도구 실행은 `asyncio.to_thread`로 넘겨 이벤트 루프가 동기 질의 때문에 막히지 않도록 처리함
- 서버 시작 시점에 `CodeWatcher`를 함께 기동해 이후 watch 계열 도구가 같은 프로세스 안에서 바로 동작할 수 있게 준비함

### 코드 근거 예시

```python
if method == 'initialize':
    response = {
        "jsonrpc": "2.0", "id": request_id,
        "result": {
            "protocolVersion": "2025-03-26",
            "serverInfo": {
                "name": "CodeGraphContext", "version": "0.1.0",
                "systemPrompt": LLM_SYSTEM_PROMPT
            },
            "capabilities": {"tools": {"listTools": True}},
        }
    }
elif method == 'tools/list':
    response = {
        "jsonrpc": "2.0", "id": request_id,
        "result": {"tools": list(self.tools.values())}
    }
elif method == 'tools/call':
    tool_name = params.get('name')
    args = params.get('arguments', {})
    result = await self.handle_tool_call(tool_name, args)
```

```python
line = await loop.run_in_executor(None, sys.stdin.readline)
...
return await asyncio.to_thread(handler, **args)
```

### 제품 적용 포인트

- `src/codegraphcontext/server.py`는 MCP 프로토콜 진입점, 도구 라우팅, 오류 응답 포맷을 한 파일에 모은 기준 구현임
- `src/codegraphcontext/cli/main.py`의 `cgc mcp start`는 이 서버를 실제 사용자 도구 체인에 연결하는 엔트리포인트임
- `src/codegraphcontext/prompts.py`는 프로토콜 밖 문서가 아니라 서버 핸드셰이크 안으로 프롬프트를 주입하는 구조를 보여줌

### 해석과 시사점

- 이 구조는 특정 클라이언트 SDK에 묶이지 않으면서도 에이전트가 바로 호출 가능한 도구 서버를 만들려는 실용적 설계임
- 우리 팀이 에이전트 도구 서버를 만들 때도 transport 계층은 단순하게 유지하고, 초반에는 `tools/list`와 `tools/call` 중심의 최소 구현으로 시작하는 편이 운영 부담이 낮음
- `systemPrompt`를 초기 핸드셰이크에 넣는 방식은 단순 문서 링크보다 즉시성 있는 사용 가이드를 제공한다는 점에서 참고할 만함

## 2. 작업 의미가 드러나는 도구 표면과 스키마 설계

### 채택 기술 구조

- CodeGraphContext의 도구 표면은 범용 검색 하나에 모든 의미를 몰아넣지 않고 인덱싱, 검색, 관계 분석, 작업 모니터링, 관리, watch, 번들 로딩으로 역할을 나눔
- 각 도구는 `inputSchema`를 직접 정의하고 `required`, `default`, `enum`을 함께 넣어 에이전트가 추론 가능한 호출 계약을 가짐
- 특히 `analyze_code_relationships`는 `query_type` enum에 `find_callers`, `find_all_callees`, `class_hierarchy`, `call_chain`, `variable_scope` 같은 분석 단위를 넣어 단순 검색보다 높은 수준의 의도를 직접 표현하게 만듦
- `add_code_to_graph`, `add_package_to_graph`, `watch_directory` 같은 도구는 코드 검색 도구가 아니라 컨텍스트 자체를 확장하고 유지하는 운영 도구로 설계돼 있음
- 서버 클래스는 실제 비즈니스 로직을 직접 구현하지 않고 핸들러에 DB 매니저, GraphBuilder, CodeFinder, JobManager를 주입하는 wrapper 계층으로 동작함

### 코드 근거 예시

```python
"analyze_code_relationships": {
    "name": "analyze_code_relationships",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": [
                    "find_callers", "find_callees", "find_all_callers",
                    "find_all_callees", "find_importers", "who_modifies",
                    "class_hierarchy", "overrides", "dead_code",
                    "call_chain", "module_deps", "variable_scope",
                    "find_complexity", "find_functions_by_argument",
                    "find_functions_by_decorator"
                ]
            },
            "target": {"type": "string"},
            "context": {"type": "string"}
        },
        "required": ["query_type", "target"]
    }
}
```

```python
def analyze_code_relationships_tool(self, **args) -> Dict[str, Any]:
    return analysis_handlers.analyze_code_relationships(self.code_finder, **args)
```

### 제품 적용 포인트

- `src/codegraphcontext/tool_definitions.py`는 에이전트가 볼 수 있는 도구 계약 자체를 정의하는 핵심 파일임
- `src/codegraphcontext/server.py`의 wrapper 메서드들은 프로토콜 계층과 비즈니스 계층을 느슨하게 분리하는 참고 구현임
- `src/codegraphcontext/tools/handlers/` 하위 모듈은 도구별 책임을 분리해 MCP 표면을 유지하면서 기능을 확장하는 구조를 보여줌

### 해석과 시사점

- 이 프로젝트의 강점은 도구 이름과 스키마가 작업 의미를 직접 드러낸다는 점임
- 우리 팀이 에이전트용 도구를 설계할 때도 범용 `search` 하나에 기대기보다 호출 분석, 계층 분석, 인덱싱, 상태 조회를 분리한 도구 집합이 에이전트 성공률을 높일 가능성이 큼
- 엄격한 API 게이트웨이 없이도 `enum`과 기본값 설계만 잘해도 에이전트가 잘못된 호출을 줄일 수 있다는 점이 실전 노하우임

## 3. JSON 결과 래핑 방식과 실제 응답 DTO의 성격

### 채택 기술 구조

- `tools/call`의 성공 응답은 구조화된 JSON 객체를 그대로 넘기지 않고 `content[0].type = "text"` 안에 `json.dumps(result, indent=2)` 문자열로 감싸 반환함
- 따라서 MCP 클라이언트는 프로토콜 레벨에서는 텍스트 응답을 받고, 실제 의미 있는 payload는 그 안의 JSON 문자열을 다시 해석하는 이중 구조를 다루게 됨
- 응답 DTO는 하나의 고정 스키마로 통일돼 있지 않고 도구와 질의 유형별로 달라짐
- 예를 들어 `find_code`는 `ranked_results`, `search_type`, `relevance_score` 중심이고, `find_callers`는 `caller_file_path`, `caller_line_number` 중심이며, 복잡도 분석은 `path`, `line_number`, `complexity`를 반환함
- 즉 이 인터페이스의 실질적 강점은 모든 응답이 같은 필드를 준다는 데 있지 않고, 작업별로 필요한 위치 정보와 요약 정보를 함께 준다는 데 있음
- `analyze_code_relationships`는 대부분 `summary`를 같이 반환해 에이전트가 결과를 빠르게 요약하거나 후속 질의를 선택하기 쉽게 만듦

### 코드 근거 예시

```python
response = {
    "jsonrpc": "2.0", "id": request_id,
    "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
}
```

```python
return {
    "query": user_query_normalized,
    "functions_by_name": ...,
    "classes_by_name": ...,
    "variables_by_name": ...,
    "content_matches": ...,
    "ranked_results": all_results[:15],
    "total_matches": len(all_results)
}
```

```python
return {
    "query_type": "find_callers", "target": target, "context": context, "results": results,
    "summary": f"Found {len(results)} functions that call '{target}'"
}
```

### 제품 적용 포인트

- `src/codegraphcontext/server.py`는 텍스트 콘텐츠 래핑이라는 프로토콜 표현 방식을 보여줌
- `src/codegraphcontext/tools/code_finder.py`는 실제 도메인 응답 DTO가 질의 유형에 따라 어떻게 달라지는지 확인하는 핵심 위치임
- `src/codegraphcontext/tools/handlers/analysis_handlers.py`와 `management_handlers.py`는 내부 결과에 `success`, `summary`, 사람 친화적 시간 문자열을 덧붙이는 얇은 응답 조립 계층임

### 해석과 시사점

- 이 구조는 다양한 클라이언트 호환성 측면에서는 단순하지만, 응답을 다시 JSON으로 파싱해야 한다는 비용을 클라이언트에 넘기는 선택이기도 함
- 우리 팀이 에이전트 도구를 만든다면 프로토콜 레벨 콘텐츠 표현과 실제 비즈니스 DTO를 의도적으로 분리할지 먼저 정하는 편이 좋음
- 또 하나의 중요한 교훈은 위치 정보가 중요하더라도 모든 도구에 억지로 같은 필드를 강제하기보다 작업별 DTO를 명시적으로 정의하는 편이 더 정확하다는 점임

## 4. 장기 작업 제어와 컨텍스트 운영 도구의 결합

### 채택 기술 구조

- CodeGraphContext의 에이전트 인터페이스는 조회 전용이 아니라 컨텍스트를 생성하고 유지하는 운영 명령까지 포함함
- 인덱싱 계열 도구는 바로 완료를 기다리지 않고 `job_id`를 반환한 뒤 `check_job_status`와 `list_jobs`로 후속 상태 조회를 하게 만듦
- `JobInfo`에는 `status`, `total_files`, `processed_files`, `current_file`, `estimated_duration`, `errors`, `path`, `is_dependency`가 담겨 에이전트가 장기 작업을 추적할 수 있음
- 상태 조회 응답은 내부 수치만 반환하지 않고 `estimated_time_remaining_human`, `elapsed_time_human`, `actual_duration_human` 같은 사람이 읽기 쉬운 필드를 추가함
- `watch_directory`는 단순히 watcher만 거는 것이 아니라 경로가 아직 인덱싱되지 않았으면 초기 스캔 job을 먼저 시작한 뒤 watch 상태로 넘어가는 복합 운영 도구임
- `load_bundle`과 `search_registry_bundles`는 장시간 인덱싱을 우회해 미리 만들어진 그래프 스냅샷을 불러오는 운영 경로를 에이전트 도구로 직접 노출함

### 코드 근거 예시

```python
job_id = job_manager.create_job(str(path_obj), is_dependency)
job_manager.update_job(job_id, total_files=total_files, estimated_duration=estimated_time)
...
return {
    "success": True, "job_id": job_id,
    "message": f"Background processing started for {str(path_obj)}",
    "instructions": f"Use 'check_job_status' with job_id '{job_id}' to monitor progress"
}
```

```python
if job.status == JobStatus.RUNNING:
    if job.estimated_time_remaining:
        job_dict["estimated_time_remaining_human"] = ...
    if job.start_time:
        job_dict["elapsed_time_human"] = ...
```

```python
if is_already_indexed:
    code_watcher.watch_directory(path_str, perform_initial_scan=False)
else:
    scan_job_result = add_code_func(path=path_str, is_dependency=False)
    code_watcher.watch_directory(path_str, perform_initial_scan=True)
```

### 제품 적용 포인트

- `src/codegraphcontext/core/jobs.py`는 에이전트가 다룰 장기 작업 메타데이터 모델의 기준 구현임
- `src/codegraphcontext/tools/handlers/indexing_handlers.py`와 `management_handlers.py`는 비동기 작업 생성과 사용자 친화적 상태 응답을 연결하는 핵심 계층임
- `src/codegraphcontext/tools/handlers/watcher_handlers.py`는 조회 도구와 운영 도구를 같은 MCP 표면에 묶는 방식을 보여줌

### 해석과 시사점

- 이 프로젝트의 숨은 강점은 검색 도구뿐 아니라 컨텍스트 lifecycle 자체를 에이전트가 조작하게 했다는 점임
- 우리 팀이 지식 베이스 도구를 만들 때도 `search`만 제공하면 실제 작업 흐름이 끊기기 쉬우므로 인덱싱, 재인덱싱, 감시, 스냅샷 로딩까지 한 인터페이스 안에서 다루는 편이 좋음
- 장기 작업에 대한 상태 API와 사람이 읽기 쉬운 시간 표현을 같이 두면 에이전트뿐 아니라 사람 운영자도 같은 응답을 재사용할 수 있음

## 5. 안전장치가 있는 fallback 질의와 오류 전달 방식

### 채택 기술 구조

- `execute_cypher_query`는 다른 도구가 답하지 못하는 경우를 위한 fallback이지만 쓰기 작업을 막는 안전장치를 포함함
- 금지 키워드를 검사할 때 문자열 리터럴을 먼저 제거한 뒤 `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`, `CALL apoc`를 막아 단순 문자열 포함으로 인한 오탐을 줄임
- 도구 실행 중 핸들러가 `{"error": ...}`를 반환하면 서버는 JSON-RPC 레벨에서 `code = -32000`인 오류로 감싸고 원래 payload를 `data`에 실어 보냄
- 미지원 메서드는 `-32601`, 예기치 않은 서버 예외는 `-32603`으로 구분해 프로토콜 오류와 비즈니스 오류를 분리함
- 서버 초기화 단계에서 DB 매니저 생성과 드라이버 연결을 먼저 수행해 설정 오류를 도구 호출 시점이 아니라 서버 시작 시점에 드러내는 fail-fast 전략을 사용함

### 코드 근거 예시

```python
for keyword in forbidden_keywords:
    if re.search(r'\b' + keyword + r'\b', query_without_strings, re.IGNORECASE):
        return {
            "error": "This tool only supports read-only queries. Prohibited keywords like CREATE, MERGE, DELETE, SET, etc., are not allowed."
        }
```

```python
if "error" in result:
    response = {
        "jsonrpc": "2.0", "id": request_id,
        "error": {"code": -32000, "message": "Tool execution error", "data": result}
    }
```

```python
try:
    self.db_manager = get_database_manager()
    self.db_manager.get_driver()
except ValueError as e:
    raise ValueError(f"Database configuration error: {e}")
```

### 제품 적용 포인트

- `src/codegraphcontext/tools/handlers/query_handlers.py`는 read-only fallback 도구의 안전장치 구현을 보여줌
- `src/codegraphcontext/server.py`는 도구 오류와 프로토콜 오류를 다른 계층에서 어떻게 표준화하는지 보여주는 핵심 파일임
- `src/codegraphcontext/core/__init__.py`와 각 DB 매니저는 에이전트 인터페이스 품질이 결국 초기화와 연결 검증 품질에도 의존함을 보여줌

### 해석과 시사점

- 이 프로젝트의 기술적 노하우는 강력한 fallback 도구를 주되 쓰기 권한을 억제하고 오류를 기계적으로 분류해 에이전트가 후속 행동을 고르기 쉽게 만든 점임
- 우리 팀도 범용 질의 도구를 열어둘 때는 읽기 전용 제약과 구조화된 오류 코드를 같이 설계해야 안전성과 자동화 가능성을 동시에 확보할 수 있음
- fail-fast 초기화는 에이전트가 잘못된 환경 위에서 계속 헛도는 상황을 줄이는 데 효과적임

## 6. 한계와 trade-off

### 현재 구현 기준에서 주의할 점

- 현재 `tools/call` 성공 응답은 구조화된 객체가 아니라 JSON 문자열을 담은 텍스트 콘텐츠라서 클라이언트가 한 번 더 파싱해야 함
- 위치 정보가 중요한 것은 맞지만, 모든 도구가 `file_absolute_path`, `start_line`, `end_line`를 공통 최상위 필드로 보장하는 구조는 아님
- 실제 응답은 `path`, `line_number`, `caller_file_path`, `method_line_number`처럼 질의별 필드명이 달라 DTO 일관성은 제한적임
- `initialize`의 `serverInfo.version`은 현재 패키지 버전과 동기화되지 않고 하드코딩된 `0.1.0`을 반환함
- capabilities는 현재 tools 위주라 resources, prompts, streaming 같은 더 넓은 MCP 기능을 활용하는 구조는 아님
- job 상태는 메모리 기반이라 서버 재시작 시 추적 정보가 사라지고 단일 프로세스 전제를 강하게 가짐

### 제품 해석

- 이 설계는 완전한 범용 MCP 플랫폼보다 로컬 코드 분석용 도구 서버를 빠르게 안정적으로 제공하는 데 초점을 둔 선택임
- 즉 CodeGraphContext의 에이전트 인터페이스는 `작업 의미가 드러나는 도구 표면 + 텍스트 래핑 JSON 응답 + job 기반 운영 도구 + 안전한 fallback` 조합으로 이해하는 편이 정확함

# 사내 지식 베이스 구축 시 벤치마킹 인사이트

### transport는 단순하게 두고 도구 의미를 풍부하게 설계

- stdio 기반 JSON-RPC처럼 단순한 transport만으로도 충분히 강한 에이전트 도구 서버를 만들 수 있음
- 차별점은 프로토콜 복잡도보다 도구 이름, 입력 스키마, 후속 호출 흐름에 담긴 작업 의미에서 나옴

### 검색 도구와 운영 도구를 분리하지 말고 함께 설계

- 실제 에이전트는 검색만 하지 않고 인덱싱 시작, 상태 추적, 감시 등록, 번들 로딩까지 수행함
- 우리 팀도 지식 베이스를 에이전트에 붙일 때는 조회 API와 운영 API를 같은 도구 집합 안에서 설계하는 편이 작업 완결성이 높음

### DTO는 획일성보다 작업 적합성을 우선

- 모든 결과에 똑같은 필드를 억지로 넣기보다 핵심 위치 정보와 작업별 전용 필드를 명시적으로 조합하는 편이 정확함
- 대신 어떤 도구가 어떤 위치 필드를 보장하는지는 계약 문서로 분명히 적어야 에이전트 편집 로직이 흔들리지 않음

### fallback 질의 도구에는 읽기 전용 제약과 오류 코드를 같이 둠

- 강력한 범용 질의 도구는 필요하지만, 쓰기 금지와 구조화된 오류 응답이 없으면 에이전트 자동화에 위험함
- 문자열 리터럴 제거 뒤 금지 키워드를 검사하는 방식은 단순하지만 실용적인 안전장치로 참고할 만함

### 초기 핸드셰이크에서 사용 원칙까지 같이 전달

- `systemPrompt`를 초기화 응답에 포함하는 방식은 클라이언트 문서 의존도를 줄이고 도구 사용 습관을 일관되게 만들 수 있음
- 우리 팀이 여러 클라이언트를 지원한다면 기능 목록뿐 아니라 사용 원칙도 핸드셰이크 단계에서 같이 주입하는 방식을 검토할 만함
