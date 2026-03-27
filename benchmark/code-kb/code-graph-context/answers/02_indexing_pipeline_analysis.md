# CodeGraphContext 인덱싱 파이프라인 아키텍처 분석

## 도입 개요

이 문서는 CodeGraphContext가 대규모 코드베이스 인덱싱과 파일 변경 감시를 어떻게 처리하는지 현재 구현 기준으로 분석한 문서이다. 특히 watcher 기반 갱신 루프, 백그라운드 작업 추적, 인덱싱 범위 제어, `.cgc` 번들 export/import 흐름을 중심으로 실제 운영에 참고할 수 있는 파이프라인 설계 포인트를 정리한다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 파일 변경 감지와 전체 리링크를 동반한 증분 갱신

### 채택 기술 구조

- `watchdog` 기반 `Observer`와 `FileSystemEventHandler`로 파일 생성, 수정, 삭제, 이동 이벤트를 수신함
- 이벤트는 경로별 `threading.Timer`로 디바운스 처리해 IDE 자동 저장이나 연속 저장에서 과도한 갱신을 줄임
- 변경 처리의 핵심은 완전한 파일 단위 삭제 후 재삽입과 저장소 전역 재링크의 결합임
- 즉 변경된 파일 노드는 `update_file_in_graph()`로 개별 교체하지만, 이후 전체 파일을 다시 파싱해 `CALLS`와 `INHERITS`를 저장소 단위로 다시 계산함
- 따라서 이 구조는 순수한 의미의 국소 증분 갱신이라기보다 단일 파일 교체와 저장소 전역 관계 재계산을 조합한 하이브리드 방식임
- 이 선택은 교차 파일 호출 관계와 상속 관계가 파일 하나 수정으로 쉽게 깨질 수 있다는 점을 반영한 구현임

### 코드 근거 예시

```python
def _debounce(self, event_path, action):
    if event_path in self.timers:
        self.timers[event_path].cancel()
    timer = threading.Timer(self.debounce_interval, action)
    timer.start()
    self.timers[event_path] = timer
```

```python
self.graph_builder.update_file_in_graph(
    modified_path, self.repo_path, self.imports_map
)

self.graph_builder._create_all_function_calls(self.all_file_data, self.imports_map)
self.graph_builder._create_all_inheritance_links(self.all_file_data, self.imports_map)
```

### 제품 적용 포인트

- `src/codegraphcontext/core/watcher.py`는 watcher가 단순 이벤트 전달자가 아니라 저장소 상태 캐시와 재링크 오케스트레이션을 함께 담당하는 구조를 보여줌
- `src/codegraphcontext/tools/graph_builder.py`의 `update_file_in_graph()`는 파일 단위 교체 경계를 정의하는 기준 구현임
- 같은 파일의 `_create_all_function_calls()`와 `_create_all_inheritance_links()`는 전역 관계 무결성을 후처리 단계로 분리한 구현 포인트임

### 해석과 시사점

- 실시간성만 극대화하면 잘못된 호출 관계가 쉽게 남기 때문에 CodeGraphContext는 정확성을 우선하는 쪽으로 설계됨
- 우리 팀이 증분 인덱싱을 설계한다면 노드 갱신과 엣지 재계산을 같은 단계로 보지 말고 분리된 파이프라인으로 다루는 편이 안전함
- 특히 교차 파일 해석이 필요한 관계는 파일 단위 증분만으로 끝내지 않고 전역 리링크 규칙을 따로 두는 편이 운영상 유리함

## 2. 비동기 작업 추적과 진행률 피드백 구조

### 채택 기술 구조

- 인덱싱은 즉시 완료되는 동기 명령이 아니라 job 기반 백그라운드 작업으로 실행됨
- `JobInfo`는 `status`, `total_files`, `processed_files`, `current_file`, `estimated_duration`, `actual_duration`, `errors`를 담는 작업 메타데이터 구조체임
- `JobStatus`는 `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`로 상태를 강제함
- 인덱싱 시작 전 `estimate_processing_time()`으로 대상 파일 수와 예상 시간을 계산해 job에 선반영함
- 실제 인덱싱 루프에서는 현재 파일과 처리 수를 계속 갱신하고, 조회 시점에는 `estimated_time_remaining`과 경과 시간을 사람이 읽기 쉬운 문자열로 다시 가공함
- 작업 정보는 메모리 기반이지만 `threading.Lock`으로 보호돼 비동기 갱신 충돌을 줄임

### 코드 근거 예시

```python
@property
def estimated_time_remaining(self) -> Optional[float]:
    if self.status != JobStatus.RUNNING or self.processed_files == 0:
        return None
    elapsed = (datetime.now() - self.start_time).total_seconds()
    avg_time_per_file = elapsed / self.processed_files
    remaining_files = self.total_files - self.processed_files
    return remaining_files * avg_time_per_file
```

```python
job_id = job_manager.create_job(str(path_obj), is_dependency)
job_manager.update_job(job_id, total_files=total_files, estimated_duration=estimated_time)
...
self.job_manager.update_job(job_id, current_file=str(file))
self.job_manager.update_job(job_id, processed_files=processed_count)
```

### 제품 적용 포인트

- `src/codegraphcontext/core/jobs.py`는 작업 메타데이터를 Enum과 dataclass로 분리한 단순하고 확장 가능한 구조를 보여줌
- `src/codegraphcontext/tools/handlers/indexing_handlers.py`는 작업 생성과 예상 시간 산출을 API 응답에 연결하는 예시임
- `src/codegraphcontext/tools/handlers/management_handlers.py`는 내부 수치를 그대로 노출하지 않고 `estimated_time_remaining_human`, `elapsed_time_human` 같은 사용자 친화 포맷으로 재가공함

### 해석과 시사점

- 인덱싱 파이프라인에서 중요한 것은 실제 처리 속도뿐 아니라 사용자가 현재 무슨 일이 일어나는지 알 수 있게 만드는 것임
- 우리 팀이 긴 인덱싱 작업을 설계한다면 상태 Enum, 진행률, 현재 처리 대상, 남은 시간 추정은 초기에 같이 설계하는 편이 좋음
- 단 메모리 기반 job 저장은 서버 재시작 시 상태가 사라지므로 장기 작업이나 다중 인스턴스 환경에서는 영속화 계층이 추가로 필요함

## 3. 인덱싱 범위 제어와 파이프라인 전환 전략

### 채택 기술 구조

- 인덱싱 전 대상 파일을 고정하지 않고 `IGNORE_DIRS`와 `.cgcignore`를 함께 적용해 실제 처리 범위를 줄임
- `IGNORE_DIRS`는 공통적으로 제외할 디렉터리 이름 목록이고 `.cgcignore`는 저장소 로컬 규칙을 gitwildmatch 방식으로 해석함
- 이 구조는 대규모 레포에서 불필요한 빌드 산출물, 캐시, 벤더 디렉터리를 초기에 제거하는 데 유리함
- 또 하나의 특징은 Tree-sitter 파이프라인이 유일한 경로가 아니라는 점임
- `SCIP_INDEXER=true`이고 언어별 `scip-<lang>` 도구가 있으면 SCIP 기반 인덱싱 경로를 우선 시도하고, 그렇지 않으면 기존 Tree-sitter 경로로 폴백함
- SCIP 경로에서도 source, complexity, decorators, imports 같은 일부 속성은 Tree-sitter로 보완해 두 파이프라인을 완전히 배타적으로 나누지 않음

### 코드 근거 예시

```python
candidate = curr / ".cgcignore"
...
spec = pathspec.PathSpec.from_lines('gitwildmatch', ignore_patterns)
```

```python
scip_enabled = (get_config_value("SCIP_INDEXER") or "false").lower() == "true"
if detected_lang and is_scip_available(detected_lang):
    await self._build_graph_from_scip(path, is_dependency, job_id, detected_lang)
    return
```

### 제품 적용 포인트

- `src/codegraphcontext/tools/graph_builder.py`의 `.cgcignore` 탐색과 `IGNORE_DIRS` 필터링은 인덱싱 비용을 제어하는 첫 번째 방어선임
- 같은 파일의 `_build_graph_from_scip()`는 정확도 우선 경로를 feature flag로 선택하고, 실패 시 기본 경로로 되돌리는 전환 전략을 보여줌
- `src/codegraphcontext/cli/config_manager.py`는 파이프라인 동작을 코드 수정 없이 설정으로 제어하게 만든 운영 포인트임

### 해석과 시사점

- 대규모 코드 인덱싱은 파서 성능만이 아니라 어떤 파일을 아예 처리하지 않을지 결정하는 정책이 성능에 큰 영향을 줌
- 우리 팀이 인덱서를 만들 때도 ignore 규칙과 파이프라인 전환 flag를 초기에 넣어두면 운영 실험과 정확도 튜닝이 쉬워짐
- 특히 정확도 높은 대체 인덱서가 있을 때 기존 파이프라인을 버리기보다 보완 경로로 결합하는 방식은 점진적 도입에 유리함

## 4. 그래프 스냅샷 번들링과 재로딩 파이프라인

### 채택 기술 구조

- `.cgc` 번들은 단순 압축 파일이 아니라 메타데이터, 스키마, 노드, 엣지, 통계, README를 포함한 그래프 스냅샷 형식임
- export 시 현재 그래프에서 metadata, schema, nodes, edges를 추출해 JSON과 JSONL로 저장한 뒤 ZIP 아카이브로 묶음
- import 시 번들을 압축 해제하고 필수 파일을 검증한 다음 노드와 엣지를 순차적으로 적재함
- 노드 import에서는 이전 그래프의 ID와 현재 DB의 신규 ID를 매핑해, 이후 엣지 import 시 관계 연결을 복원함
- duplicate repository를 방지하는 검사와 전체 그래프 삭제 옵션을 같이 두어 운영 실수를 줄이려 함
- 다만 schema import는 아직 fully implemented 상태가 아니고 현재는 애플리케이션이 스키마를 미리 만든다는 전제를 둠

### 코드 근거 예시

```python
with zipfile.ZipFile(bundle_path, 'r') as zip_ref:
    zip_ref.extractall(temp_path)

is_valid, validation_msg = self._validate_bundle(temp_path)
...
node_count = self._import_nodes(temp_path / "nodes.jsonl")
edge_count = self._import_edges(temp_path / "edges.jsonl")
```

```python
query = f"CREATE (n:{label_str}) SET n = $props RETURN {id_function}(n) as new_id"
...
id_mapping[old_id] = record['new_id']
```

### 제품 적용 포인트

- `src/codegraphcontext/core/cgc_bundle.py`는 그래프 결과를 재사용 가능한 아티팩트로 취급하는 전형적인 export/import 파이프라인 예시임
- 같은 파일의 `_validate_bundle()`과 duplicate repository 검사 로직은 단순 파일 적재보다 운영 안전장치를 우선한 구현 포인트임
- `_import_schema()`가 placeholder라는 점은 이 문서에서 명시해야 할 실제 제약 사항임

### 해석과 시사점

- 장시간 인덱싱 결과를 번들로 고정하면 팀 간 공유, 데모 환경 준비, 반복 로컬 세팅 비용 절감에 유리함
- 우리 팀이 지식 베이스를 만든다면 인덱싱 결과를 DB 내부 상태로만 두지 말고 이식 가능한 스냅샷 형식으로 분리하는 편이 좋음
- 단 schema import가 완전하지 않으면 애플리케이션 버전과 런타임 스키마에 대한 호환성 전략을 같이 설계해야 함

## 5. 한계와 trade-off

### 현재 구현 기준에서 주의할 점

- watcher 경로는 변경 파일만 교체하지만 이후 저장소 전체 파일을 다시 파싱하고 관계를 다시 연결하므로 완전한 미세 증분 갱신은 아님
- job 상태는 메모리에 저장되므로 프로세스 재시작이나 다중 서버 환경에는 적합하지 않음
- `.cgc` 번들 import는 노드와 엣지는 적재하지만 schema import는 아직 실질적으로 구현되지 않음
- SCIP 경로는 feature flag와 외부 바이너리 설치에 의존하므로 기본 경로보다 운영 복잡도가 높음

### 제품 해석

- 이 설계는 초정밀 증분 처리나 완전 영속 작업 큐보다 단일 프로세스 환경에서의 실용성과 구현 단순성을 우선한 선택임
- 즉 CodeGraphContext의 인덱싱 파이프라인은 로컬 개발 환경과 에이전트 보조 도구에 최적화된 구조로 보는 편이 정확함

# 사내 지식 베이스 구축 시 벤치마킹 인사이트

### 디바운스와 전역 리링크를 분리해 설계

- 파일 감지와 심벌 갱신과 관계 재연결을 하나의 단계로 뭉치지 말고 분리된 단계로 설계하는 편이 무결성 확보에 유리함
- 특히 교차 파일 의존성이 많은 시스템이라면 파일 단위 갱신 뒤 전역 리링크 규칙을 별도로 두는 편이 안전함

### 긴 인덱싱 작업은 job 기반 메타데이터로 감쌈

- 상태 Enum, 진행률, 현재 처리 파일, 예상 시간, 실패 원인을 한 구조체에 담아두면 CLI와 API와 에이전트 도구가 같은 메타데이터를 재사용할 수 있음
- 남은 시간 추정은 완벽하지 않아도 사용자가 체감하는 안정성에 큰 영향을 줌

### 인덱싱 범위 제어를 파서 최적화만큼 중요하게 봄

- ignore 디렉터리, 저장소 로컬 ignore 규칙, 언어별 파이프라인 전환 flag는 대규모 레포에서 필수에 가까운 운영 장치임
- 성능 개선은 더 빠른 파서만이 아니라 아예 처리하지 않을 파일을 줄이는 정책에서 많이 나옴

### 결과를 이식 가능한 아티팩트로 분리

- 장시간 인덱싱 결과를 번들로 내보낼 수 있게 하면 팀 공유와 초기 세팅 시간을 크게 줄일 수 있음
- 단 번들 포맷을 도입할 때는 schema 호환성, ID 매핑, duplicate import 방지까지 같이 설계해야 함
