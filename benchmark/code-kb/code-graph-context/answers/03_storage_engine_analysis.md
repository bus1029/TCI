# CodeGraphContext 저장소 및 백엔드 추상화 아키텍처 분석

## 도입 개요

이 문서는 CodeGraphContext가 코드 그래프를 어떤 저장소 계층 위에 유지하고, 여러 그래프 백엔드를 어떻게 같은 애플리케이션 흐름 안에서 전환하는지 현재 구현 기준으로 분석한 문서이다. 특히 로컬 우선 보안 경계, 임베디드 DB 실행 방식, 백엔드 선택 팩토리, Neo4j 호환 래퍼 구조를 중심으로 실제 제품 설계에 참고할 수 있는 저장소 전략을 정리한다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 로컬 우선 저장 경계와 오프라인 처리 성향

### 채택 기술 구조

- CodeGraphContext의 기본 코드 파싱과 그래프 적재 경로는 로컬 프로세스 안에서 동작함
- 소스 분석은 `tree-sitter` 기반 파서와 언어별 추출기로 처리되고, 결과는 로컬 또는 사용자가 지정한 그래프 백엔드에 바로 적재됨
- KùzuDB와 FalkorDB Lite를 사용할 경우 저장소도 홈 디렉터리 하위 파일과 소켓 경로를 기준으로 구성돼 외부 DB 서버 없이 동작 가능함
- `source`, `docstring`, `path`, `line_number` 같은 코드 메타데이터는 백엔드 노드 컬럼에 직접 저장되며 별도 외부 색인 서비스에 의존하지 않음
- 다만 이 프로젝트 전체가 절대적으로 오프라인 전용인 것은 아님
- 번들 레지스트리 다운로드와 원격 FalkorDB, Neo4j 연결 기능이 별도로 존재하므로 오프라인 보안 경계는 로컬 백엔드를 선택하고 원격 기능을 사용하지 않을 때 가장 강하게 성립함

### 코드 근거 예시

```python
self.db_path = os.getenv(
    'KUZUDB_PATH',
    config_db_path or str(Path.home() / '.codegraphcontext' / 'kuzudb')
)
```

```python
self.db_path = os.getenv(
    'FALKORDB_PATH',
    config_db_path or str(Path.home() / '.codegraphcontext' / 'falkordb.db')
)
self.socket_path = os.getenv(
    'FALKORDB_SOCKET_PATH',
    config_socket_path or str(Path.home() / '.codegraphcontext' / 'falkordb.sock')
)
```

### 제품 적용 포인트

- `src/codegraphcontext/core/database_kuzu.py`와 `src/codegraphcontext/core/database_falkordb.py`는 로컬 파일 시스템 기반 저장 경계를 어떻게 잡는지 보여줌
- `src/codegraphcontext/tools/` 하위 파서는 코드 분석 경로가 외부 API 호출 없이 로컬 파싱 위주로 구성된다는 점을 확인하는 기준 위치임
- 반대로 `src/codegraphcontext/core/bundle_registry.py`와 원격 DB 매니저는 네트워크 기능이 별도 존재한다는 점을 보여주는 예외 경로임

### 해석과 시사점

- 이 프로젝트의 강점은 분석 파이프라인의 기본 경로를 로컬 처리와 로컬 저장에 붙여 놓았다는 점임
- 우리 팀이 보안 민감한 지식 베이스를 만든다면 오프라인 기본 경로와 원격 확장 경로를 명확히 분리하는 설계가 유리함
- 동시에 문서에서는 `완전 오프라인 제품`처럼 과장하지 않고 어떤 기능에서 네트워크가 다시 등장하는지 경계를 같이 적는 편이 정확함

## 2. 백엔드 선택 팩토리와 공통 드라이버 표면

### 채택 기술 구조

- CodeGraphContext는 단일 DB 구현체에 하드코딩되지 않고 `get_database_manager()` 팩토리로 백엔드를 선택함
- 선택 우선순위는 `CGC_RUNTIME_DB_TYPE`, `DEFAULT_DATABASE`, `DATABASE_TYPE` 같은 명시적 설정을 먼저 보고, 그다음 사용 가능한 임베디드 백엔드를 자동 선택하는 방식임
- 현재 코드 기준 자동 선택 순서는 FalkorDB Lite 가능 시 우선, 그다음 KùzuDB, 그다음 원격 FalkorDB, 마지막으로 Neo4j임
- 문서상 흔히 `KùzuDB 기본`처럼 이해되기 쉽지만 실제 구현은 환경 조건이 맞으면 FalkorDB Lite를 먼저 시도함
- 공통 계층은 전통적인 의미의 추상 베이스 클래스라기보다 각 매니저가 `get_driver()`, `close_driver()`, `is_connected()`, `get_backend_type()`를 제공하고, 반환 드라이버를 Neo4j 유사 표면으로 맞추는 래퍼 패턴에 가까움
- 이 공통 표면 덕분에 상위 계층은 백엔드 종류와 상관없이 `with driver.session() as session: session.run(...)` 패턴을 유지할 수 있음

### 코드 근거 예시

```python
db_type = os.getenv('CGC_RUNTIME_DB_TYPE')
if not db_type:
    db_type = os.getenv('DEFAULT_DATABASE')
if not db_type:
    db_type = os.getenv('DATABASE_TYPE')
```

```python
if _is_falkordb_available():
    ...
    return mgr

if _is_kuzudb_available():
    ...
    return KuzuDBManager()
```

### 제품 적용 포인트

- `src/codegraphcontext/core/__init__.py`는 설정 기반 선택과 자동 감지를 한곳에 모은 팩토리 구현임
- `src/codegraphcontext/core/database.py`, `database_falkordb.py`, `database_kuzu.py`, `database_falkordb_remote.py`는 동일한 상위 호출 패턴을 유지하기 위해 드라이버 래퍼를 두는 구조를 보여줌
- 저장소 계층을 교체 가능하게 만들고 싶다면 각 백엔드가 같은 추상 메서드 집합을 강제하지 않더라도 최소 실행 표면을 맞추는 방식만으로도 충분히 운영 가능하다는 사례임

### 해석과 시사점

- 이 프로젝트의 저장소 추상화는 엄격한 인터페이스 상속보다 실제 호출 호환성을 우선한 실용적 설계임
- 우리 팀이 여러 DB를 지원할 때도 상위 계층이 실제로 호출하는 최소 API만 고정하면 초기 복잡도를 낮출 수 있음
- 다만 문서에서는 이를 `공용 인터페이스`라고 부를 수는 있어도 `추상 클래스 기반 설계`라고 과장해 쓰지 않는 편이 정확함

## 3. 임베디드 백엔드 실행 방식의 차별화

### 채택 기술 구조

- KùzuDB와 FalkorDB Lite는 둘 다 임베디드 성격을 가지지만 실행 방식은 다름
- KùzuDB는 프로세스 내부에서 `kuzu.Database`와 `kuzu.Connection`을 직접 열어 단순한 파일 기반 로컬 저장소로 동작함
- 반면 FalkorDB Lite는 메인 프로세스 안에 직접 붙지 않고 worker subprocess를 띄운 뒤 Unix socket으로 통신함
- FalkorDB Lite 경로는 소켓 존재 여부와 `GRAPH.QUERY` 동작 여부를 검사해 stale socket이나 반쯤 죽은 프로세스를 정리하고 다시 띄우는 방어 로직까지 포함함
- 즉 둘 다 서버리스에 가깝지만 KùzuDB는 direct embedded, FalkorDB Lite는 local subprocess + socket 분리형이라는 차이가 있음
- 이 차이는 안정성, 배포 방식, 플랫폼 지원 범위에서 그대로 드러남

### 코드 근거 예시

```python
import kuzu
self._db = kuzu.Database(self.db_path)
self._conn = kuzu.Connection(self._db)
```

```python
env['FALKORDB_PATH'] = self.db_path
env['FALKORDB_SOCKET_PATH'] = self.socket_path
...
self._process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
```

### 제품 적용 포인트

- `src/codegraphcontext/core/database_kuzu.py`는 가장 단순한 형태의 embedded graph DB 연결 패턴을 보여줌
- `src/codegraphcontext/core/database_falkordb.py`는 로컬 임베디드라고 해도 프로세스 격리를 통해 런타임 충돌과 환경 오염을 줄일 수 있음을 보여줌
- Unix socket 검사, stale socket 정리, subprocess health check 같은 요소는 로컬 전용 DB를 안정적으로 배포할 때 참고할 만한 운영 노하우임

### 해석과 시사점

- 저장소를 로컬에 둔다고 해서 구현이 항상 단순한 것은 아님
- 오히려 임베디드 DB를 어떻게 메인 프로세스와 결합하거나 격리할지가 운영 안정성에 큰 영향을 줌
- 우리 팀이 로컬 저장소를 채택한다면 direct embedded 방식과 subprocess 격리 방식 중 어떤 제약이 더 중요한지 먼저 정리하는 편이 좋음

## 4. 백엔드별 쿼리 호환성과 번역 레이어

### 채택 기술 구조

- CodeGraphContext는 상위 계층 쿼리를 완전히 백엔드별로 갈라 쓰지 않고, 하위 래퍼에서 일부 Neo4j 스타일 쿼리를 번역하는 전략을 사용함
- Neo4j는 기본 드라이버를 거의 그대로 사용하되 database name 주입용 래퍼를 둠
- FalkorDB 세션 래퍼는 제약 조건과 인덱스 생성 구문을 RedisGraph/FalkorDB 문법에 맞게 변환함
- Kùzu 세션 래퍼는 `SET n += $props`를 컬럼별 할당으로 풀고, 복합 식별자를 `uid`로 주입하며, 라벨과 쿼리 일부를 Kùzu 호환 형태로 바꿈
- 즉 이 프로젝트는 애플리케이션 전체를 백엔드별로 분기시키기보다 번역 레이어를 통해 상위 쿼리의 재사용률을 높이는 쪽을 선택함

### 코드 근거 예시

```python
if "CREATE CONSTRAINT" in q_upper:
    ...
    query = re.sub(r'\s+FOR\s+', ' ON ', query, flags=re.IGNORECASE)
    query = re.sub(r'\s+REQUIRE\s+', ' ASSERT ', query, flags=re.IGNORECASE)
```

```python
if "SET" in query and "+=" in query:
    ...
    set_clauses.append(f"{node_var}.{k} = ${clean_k}")
```

### 제품 적용 포인트

- `src/codegraphcontext/core/database_falkordb.py`의 `_translate_schema_query()`는 스키마 관련 Cypher 차이를 래퍼에서 흡수하는 구현 예시임
- `src/codegraphcontext/core/database_kuzu.py`의 `_translate_query()`는 속성 필터링, `uid` 주입, 일부 문법 변환을 한 레이어에서 처리하는 핵심 구현임
- 여러 백엔드를 지원할 때 상위 비즈니스 로직을 최대한 유지하고 싶다면 쿼리 번역기를 두는 방식이 현실적인 절충안이 될 수 있음

### 해석과 시사점

- 이 구조의 장점은 상위 코드 재사용성이 높다는 점임
- 반면 번역 레이어가 커질수록 백엔드 차이에서 오는 숨은 제약과 edge case가 하위 계층에 누적됨
- 우리 팀이 비슷한 전략을 쓴다면 모든 쿼리를 번역하려 하기보다 생성, 스키마, 검색처럼 차이가 큰 구간부터 부분 번역으로 시작하는 편이 현실적임

## 5. 원격 확장 경로와 운영 지향 백엔드

### 채택 기술 구조

- 로컬 임베디드 경로 외에도 CodeGraphContext는 원격 FalkorDB와 Neo4j를 지원함
- 원격 FalkorDB는 TCP와 선택적 SSL/TLS, username/password, graph name 설정을 받아 외부 서버에 접속함
- Neo4j는 URI, 사용자명, 비밀번호, optional database name을 받아 표준 드라이버로 연결함
- Neo4j 쪽은 URI 형식 검증, 소켓 연결 확인, 인증 실패 구분, routing 오류 가이드처럼 운영 환경에서 필요한 검증 메시지를 비교적 상세하게 제공함
- 따라서 이 프로젝트의 저장소 전략은 로컬 우선이지만, 운영 규모나 조직 환경에 따라 원격 서버형 DB로 확장될 수 있는 구조를 이미 내장하고 있음

### 코드 근거 예시

```python
kwargs = {
    'host': self.host,
    'port': self.port,
}
if self.ssl:
    kwargs['ssl'] = True
```

```python
uri_pattern = r'^(neo4j|neo4j\+s|neo4j\+ssc|bolt|bolt\+s|bolt\+ssc)://[^:]+(:\d+)?$'
```

### 제품 적용 포인트

- `src/codegraphcontext/core/database_falkordb_remote.py`는 임베디드와 원격 FalkorDB를 분리된 매니저로 관리하는 구조를 보여줌
- `src/codegraphcontext/core/database.py`는 단순 연결 코드보다 운영 친화적 validation과 test_connection 메시지에 더 많은 공을 들인 구현임
- 로컬 기본 제품이라도 엔터프라이즈 확장을 고려한다면 접속 검증과 에러 메시지 체계를 초기에 같이 설계하는 편이 좋음

### 해석과 시사점

- 저장소 전략을 로컬 전용으로 고정하면 초기 배포는 쉬워지지만 조직 규모가 커질수록 중앙 서버 요구가 다시 생기기 쉽다
- CodeGraphContext처럼 임베디드 경로와 원격 경로를 동시에 두면 제품 포지션을 넓힐 수 있음
- 다만 백엔드가 늘어날수록 쿼리 호환성과 운영 테스트 범위도 함께 커진다는 점을 감안해야 함

## 6. 한계와 trade-off

### 현재 구현 기준에서 주의할 점

- 문서나 설명에서 KùzuDB를 기본 백엔드처럼 말하기 쉽지만 실제 자동 선택은 환경에 따라 FalkorDB Lite를 먼저 시도함
- 공통 계층은 엄격한 추상 클래스보다 래퍼와 호출 호환성에 의존하므로 백엔드 차이가 완전히 숨겨지는 구조는 아님
- FalkorDB Lite는 Unix 계열과 Python 3.12 이상 제약이 있고 Windows에서는 직접 지원하지 않음
- 오프라인 처리 성향은 강하지만 번들 레지스트리 다운로드나 원격 DB 연결 같은 네트워크 기능은 별도로 존재함

### 제품 해석

- 이 설계는 단일 정답 저장소를 강제하기보다 사용 환경에 따라 임베디드와 서버형 백엔드를 오갈 수 있게 만든 실용적 타협안임
- 즉 CodeGraphContext의 저장소 아키텍처는 `완전 단순한 로컬 DB 제품`이라기보다 `로컬 우선 + 선택적 원격 확장 + 래퍼 기반 호환성` 전략으로 이해하는 편이 정확함

# 사내 지식 베이스 구축 시 벤치마킹 인사이트

### 로컬 기본 경로와 원격 확장 경로를 분리

- 보안과 초기 사용성을 잡으려면 로컬 임베디드 경로를 먼저 제공하고, 원격 서버형 저장소는 별도 설정으로 열어두는 전략이 유리함
- 문서와 제품 설명에서도 어떤 기능이 완전 로컬이고 어떤 기능이 네트워크를 쓰는지 경계를 명확히 적는 편이 좋음

### 공통 호출 표면만 먼저 맞춤

- 여러 백엔드를 동시에 지원할 때는 완전한 추상 계층보다 상위 로직이 실제로 사용하는 최소 API를 먼저 통일하는 편이 구현 속도와 유지보수 측면에서 현실적임
- 단 이 방식은 번역 레이어 품질이 곧 제품 안정성이 되므로 쿼리 차이가 큰 구간은 집중 관리가 필요함

### 임베디드 DB도 운영 관점으로 설계

- 로컬 DB라고 해서 파일 하나 열면 끝나는 문제가 아니며, subprocess 격리, socket health check, stale resource 정리 같은 운영 장치가 필요할 수 있음
- 팀 내 지식 베이스 제품도 로컬 전용 배포를 목표로 한다면 초기부터 lifecycle 관리 코드를 같이 설계하는 편이 좋음

### 검증과 에러 메시지를 저장소 전략의 일부로 봄

- DB 연결 실패는 단순 예외가 아니라 제품 신뢰도에 직접 영향을 주므로 validate와 test_connection 단계에서 구체적인 피드백을 주는 편이 좋음
- 특히 온보딩 비용을 줄이려면 잘못된 URI, 인증 실패, 포트 미개방 같은 오류를 구분해 안내하는 구조가 효과적임
