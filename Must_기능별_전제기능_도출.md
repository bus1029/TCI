# Must Have 기능별 전제 기능 도출

> Must Have 11개 기능 각각을 top-down으로 분해하여, **"이 기능이 동작하려면 반드시 선행되어야 하는 하위 기능/구성요소"**를 도출한 결과입니다.
> 경쟁 제품(CAST Imaging, Swimm, CodeScene, Sourcegraph) 및 최신 기술 자료(2025~2026)를 참고하였습니다.

---

## 전체 요약

| # | Must Have 기능 | 전제 기능 수 | 핵심 전제 기능 (Top 3) |
|---|---|---|---|
| 1 | Source Code Ingestion | 5 | Git 커넥터, 스냅샷 저장소, 언어/프레임워크 감지 |
| 2 | Data Sources | 5 | 커넥터 프레임워크, 정규화 파이프라인, 인증 관리 |
| 3 | Static Structure Analysis | 5 | 다중 언어 파서, 심볼 추출기, 관계 매핑 엔진 |
| 4 | 비즈니스 규칙 추출 | 5 | 제어 흐름 분석, LLM 추론, 규칙 구조화 |
| 5 | Knowledge Base Construction | 5 | 그래프 DB, 스키마 설계, 인덱싱/검색 |
| 6 | Change Impact Analysis | 5 | Diff 엔진, 의존성 그래프, 영향 전파 계산 |
| 7 | Ask Swimm (AI 질의응답) | 6 | 컨텍스트 검색(RAG), LLM 오케스트레이션, 채팅 인터페이스 |
| 8 | Ask Kodesage (AI 질의응답) | 5 | 컨텍스트 검색(RAG), LLM 오케스트레이션, 피드백 루프 |
| 9 | 배포/엔터프라이즈 플랜 | 5 | 컨테이너 오케스트레이션, 설치 자동화, 리소스 관리 |
| 10 | Enterprise Operation | 4 | 분석 스케줄러, 모니터링, 장애 복구 |
| 11 | CI/CD 연동 | 5 | 웹훅 수신, 이벤트 매핑, 결과 리포팅 |

---

## 1. Source Code Ingestion

> 분석 대상 코드 자산을 수집해 분석 가능한 스냅샷으로 만든다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 1-1 | **Git 커넥터** | Git SSH/HTTPS 프로토콜로 레포지토리를 clone/fetch. 브랜치·태그·커밋 단위 접근 지원 | CAST Imaging: Git 기반 레포 연결, Swimm: 코드베이스 연결 |
| 1-2 | **증분 동기화 (Incremental Sync)** | 전체 clone이 아닌 변경분만 fetch하여 대규모 레포에서도 효율적으로 동기화 | Sourcegraph: incremental indexing, AWS CodePipeline: 이벤트 기반 변경분 수집 |
| 1-3 | **스냅샷 저장소** | 특정 시점의 코드 상태를 불변 스냅샷으로 저장. 분석 재현성 보장 및 시점 간 비교 지원 | CAST Imaging: 스냅샷 기반 분석, SonarQube: 분석 시점별 데이터 보관 |
| 1-4 | **언어/프레임워크 자동 감지** | 레포 내 파일 확장자·설정 파일·패키지 매니저를 기반으로 사용 언어·프레임워크를 자동 식별 | CAST Imaging: 150+ 기술 지원, Swimm: 자동 언어 감지 |
| 1-5 | **분석 대상 필터링** | 제외 경로(node_modules, vendor, build 등), 포함 경로를 설정해 불필요한 코드 제외 | SonarQube: source/exclusion 설정, CodeScene: 분석 범위 설정 |

### 선후관계

```
Git 커넥터 → 증분 동기화 → 스냅샷 저장소
                                ↓
              언어/프레임워크 감지 + 분석 대상 필터링
```

---

## 2. Data Sources

> 코드/문서/티켓/위키 등 데이터 소스를 등록하고 연동 상태를 관리한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 2-1 | **커넥터 프레임워크** | 다양한 외부 시스템(Git, Jira, Confluence, Notion 등)에 대한 커넥터를 플러그인 방식으로 관리하는 프레임워크 | Airbyte: 소스 커넥터 아키텍처, Databricks Lakeflow Connect: 플러그인형 커넥터 |
| 2-2 | **인증 정보 관리** | 각 데이터 소스별 OAuth, API 토큰, SSH 키 등 인증 정보를 안전하게 저장·관리 | OpenSearch Data Prepper: AWS Secrets Manager 연동, Airbyte: credential vault |
| 2-3 | **데이터 정규화 파이프라인** | 소스별로 다른 형식(XHTML, JSON, Markdown 등)의 데이터를 내부 통합 포맷으로 변환 | Databricks: Confluence 콘텐츠 XHTML→내부 포맷 변환, Airbyte: stream 기반 정규화 |
| 2-4 | **연동 상태 모니터링** | 각 소스의 연결 상태(정상/오류/동기화 중), 마지막 동기화 시각, 오류 로그를 추적 | Airbyte: sync status dashboard, Databricks: 파이프라인 상태 모니터링 |
| 2-5 | **증분/전체 동기화 정책** | 소스별로 증분 동기화(변경분만) 또는 전체 스냅샷 동기화를 선택하는 정책 관리 | Databricks: 페이지는 증분, 라벨은 스냅샷 방식 지원 |

### 선후관계

```
커넥터 프레임워크 → 인증 정보 관리 → 데이터 정규화 파이프라인
                                            ↓
                     연동 상태 모니터링 + 증분/전체 동기화 정책
```

---

## 3. Static Structure Analysis

> 코드 기반 정적 구조를 식별하고 구조 메타데이터/관계를 생성한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 3-1 | **다중 언어 파서 (Multi-language Parser)** | 언어별 AST(추상 구문 트리)를 생성하는 파서. 언어 추가가 플러그인 형태로 확장 가능해야 함 | **Tree-sitter**: 40+ 언어 지원, 순수 C 구현, 구문 오류에도 견고. Ant Group YASA: Unified AST로 Java/JS/Python/Go 통합 분석 |
| 3-2 | **심볼 추출기 (Symbol Extractor)** | AST에서 클래스, 함수, 변수, 인터페이스 등 심볼을 추출하고 메타데이터(타입, 접근제어자, 위치 등)를 수집 | **Sourcegraph SCIP**: 심볼 정의/참조/구현을 표준 프로토콜로 추출. CodexGraph: MODULE, CLASS, FUNCTION, METHOD, FIELD, GLOBAL_VARIABLE 노드 |
| 3-3 | **관계 매핑 엔진** | 추출된 심볼 간의 관계(호출, 상속, 구현, 포함, 임포트 등)를 식별하고 매핑 | CodexGraph: CONTAINS, HAS_METHOD, INHERITS, USES, CALLS 엣지 추출 (intra-file + cross-file 분석) |
| 3-4 | **컴포넌트/레이어 식별기** | 심볼과 관계 데이터를 바탕으로 상위 수준의 컴포넌트(모듈, 패키지, 레이어, 서비스)를 자동 식별 | CAST Imaging: 레이어 자동 식별, CodeScene: Architectural Components 정의 |
| 3-5 | **구조 메타데이터 저장소** | 추출된 심볼, 관계, 컴포넌트 정보를 저장하고 탐색 가능하게 하는 저장소 | CAST Imaging: PostgreSQL + Neo4j (ETL로 그래프 변환), CodexGraph: Neo4j 그래프 DB |

### 선후관계

```
다중 언어 파서(3-1) → 심볼 추출기(3-2) → 관계 매핑 엔진(3-3)
                                                    ↓
                         컴포넌트/레이어 식별기(3-4) → 구조 메타데이터 저장소(3-5)
```

### 기술 선택 참고

| 요소 | 추천 기술 | 근거 |
|---|---|---|
| 파서 | **Tree-sitter** | 40+ 언어, 증분 파싱, 구문 오류 내성, 산업 표준 (Sourcegraph, GitHub, Neovim 등 채택) |
| 심볼 프로토콜 | **SCIP (Sourcegraph)** | 언어 무관 심볼 인덱싱 표준, cross-repo 지원, 활발한 생태계 |
| 그래프 저장소 | **Neo4j** | CAST Imaging 채택, CodexGraph 채택, property graph 모델로 코드 관계 표현에 최적 |

---

## 4. 비즈니스 규칙 추출 (Create Specs)

> 코드에서 비즈니스 규칙을 추출해 비기술자도 이해 가능한 자연어 스펙으로 제공한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 4-1 | **제어 흐름 분석 (CFG 생성)** | 조건문·분기·루프 등 제어 흐름을 파악해 "어떤 조건에서 어떤 동작이 일어나는가"를 구조화 | SpecGen: 코드에서 formal specification 추출 시 제어 흐름 분석 필수 |
| 4-2 | **도메인 로직 패턴 인식** | 할인 계산, 상태 전이, 유효성 검증 등 비즈니스 규칙에 해당하는 코드 패턴을 식별 | ExIde 프레임워크: rule-based process 추출, DeepRule: 비즈니스 규칙 시맨틱 파싱 |
| 4-3 | **LLM 기반 자연어 변환** | 식별된 규칙을 비기술자가 이해할 수 있는 자연어 설명으로 변환 | Swimm: 코드 → 자연어 설명 생성 (정적 분석 + LLM 3단계 파이프라인) |
| 4-4 | **규칙 구조화 / 카탈로그** | 추출된 규칙을 분류(도메인, 모듈, 유형별)하고 검색·탐색 가능하게 카탈로그화 | CAST Imaging: 트랜잭션 기반 비즈니스 로직 카탈로그 |
| 4-5 | **정적 구조 분석 결과 (3번 기능의 산출물)** | 비즈니스 규칙 추출은 심볼/관계/컴포넌트 정보가 이미 있어야 효과적으로 수행 가능 | Swimm: 정적 분석으로 관련 흐름과 컴포넌트를 먼저 식별한 후 규칙 추출 |

### 선후관계

```
[3. Static Structure Analysis 완료] → 제어 흐름 분석(4-1)
                                          ↓
                                   도메인 로직 패턴 인식(4-2)
                                          ↓
                                   LLM 기반 자연어 변환(4-3)
                                          ↓
                                   규칙 구조화/카탈로그(4-4)
```

---

## 5. Knowledge Base Construction

> 분석 결과를 구조화해 지식 모델/그래프를 구성하고 재탐색 가능하게 만든다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 5-1 | **그래프 데이터베이스** | 심볼·관계·규칙 등 분석 산출물을 노드/엣지로 저장하는 그래프 DB | CAST Imaging: Neo4j, CodexGraph: Neo4j property graph, RIG: JSON 기반 LLM-friendly 구조 |
| 5-2 | **지식 그래프 스키마 설계** | 코드 엔티티(함수, 클래스, 모듈, 규칙, 문서 등)와 관계를 정의하는 온톨로지/스키마 | CodexGraph: MODULE→CLASS→FUNCTION 계층 + CALLS/INHERITS/USES 관계 정의 |
| 5-3 | **ETL 파이프라인** | 분석 엔진(파서, 심볼 추출기 등)의 산출물을 그래프 DB로 변환·적재하는 파이프라인 | CAST Imaging: PostgreSQL → ETL → Neo4j 파이프라인 명시 |
| 5-4 | **인덱싱 / 검색 엔진** | 그래프 데이터를 키워드·시맨틱 검색할 수 있도록 인덱싱. RAG의 retrieval 계층 역할 | AST-Derived Graph-RAG: 결정론적 AST 그래프가 multi-hop 질의에서 LLM 추출 그래프 대비 높은 정확도 |
| 5-5 | **버전 관리 / 스냅샷** | 분석 시점별 지식 그래프 상태를 보존해 시점 간 비교·이력 추적 가능 | CAST Imaging: 스냅샷 기반 분석 결과 관리 |

### 선후관계

```
그래프 DB(5-1) + 스키마 설계(5-2)
           ↓
     ETL 파이프라인(5-3) ← [3. Static Structure Analysis] + [4. 비즈니스 규칙 추출]의 산출물
           ↓
     인덱싱/검색 엔진(5-4) + 버전 관리(5-5)
```

### 기술 선택 참고

| 요소 | 추천 기술 | 근거 |
|---|---|---|
| 그래프 DB | **Neo4j** | CAST Imaging/CodexGraph 채택, property graph로 코드 관계 표현에 최적 |
| 보조 저장소 | **PostgreSQL** | 관계형 메타데이터(프로젝트 설정, 사용자 등) 저장. CAST Imaging도 PostgreSQL + Neo4j 조합 사용 |
| 검색 엔진 | **벡터 DB (Qdrant/Pinecone 등) + 키워드 검색** | RAG용 시맨틱 검색. AST-Derived Graph와 벡터 임베딩 하이브리드가 최신 트렌드 |

---

## 6. Change Impact Analysis

> 변경 Diff를 기준으로 영향 범위를 구조/트랜잭션 관점에서 추적한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 6-1 | **Diff 계산 엔진** | 커밋/PR 간 코드 변경을 파일·함수·심볼 수준으로 계산 | Goodchanges: AST 수준 diff로 변경된 export 심볼 식별. Augment Code: 파일 단위 실시간 인덱싱 |
| 6-2 | **의존성 그래프 (5번 지식 베이스의 산출물)** | 변경된 심볼로부터 영향을 받는 심볼·모듈을 탐색하려면 의존성 그래프가 이미 구축되어 있어야 함 | Augment Code: living dependency graph로 blast radius 계산 |
| 6-3 | **영향 전파 계산기 (Blast Radius)** | 변경 기점에서 의존 그래프를 따라 영향이 미치는 범위를 계산하는 알고리즘 | Augment Code: critical request path 추적, Goodchanges: 워크스페이스 의존 그래프 전파 |
| 6-4 | **트랜잭션/흐름 연계** | 단순 심볼 의존이 아닌 비즈니스 트랜잭션(API 요청→서비스→DB) 관점에서 영향 연결 | CAST Imaging: 트랜잭션 연계 영향 분석 |
| 6-5 | **영향 결과 시각화/리포팅** | 영향 범위를 목록·그래프·요약 형태로 사용자에게 전달 | Augment Code: 인터랙티브 dependency map + permalink 공유 |

### 선후관계

```
[1. Source Code Ingestion] → Diff 계산 엔진(6-1)
[5. Knowledge Base]       → 의존성 그래프(6-2)
                                    ↓
                          영향 전파 계산기(6-3) + 트랜잭션 연계(6-4)
                                    ↓
                          영향 결과 시각화/리포팅(6-5)
```

---

## 7. Ask Swimm (AI 질의응답)

> 코드 분석과 기존 문서를 바탕으로 자연어 질의에 컨텍스트 답변(다이어그램 포함)을 제공한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 7-1 | **컨텍스트 검색 엔진 (RAG Retrieval)** | 질문과 관련된 코드·문서·메타데이터를 검색해 LLM에 전달할 컨텍스트를 구성 | Swimm: 정적 분석 기반 결정론적 retrieval → LLM 생성 3단계. CODERAG-BENCH: 고품질 컨텍스트가 GPT-4o 성능 27.4% 향상 |
| 7-2 | **LLM 오케스트레이션** | 프롬프트 구성, LLM 호출, 응답 후처리를 관리. 모델 교체 가능한 추상화 필요 | Swimm: LLM-agnostic 설계 (내부/승인 모델 교체 가능) |
| 7-3 | **할루시네이션 방지 체계** | 코드 기반 사실(ground truth)과 LLM 답변을 검증하여 잘못된 정보 생성을 억제 | Swimm: 결정론적 정적 분석으로 hallucination 방지. AST-Derived Graph-RAG: LLM 추출 그래프 대비 hallucination 리스크 감소 |
| 7-4 | **다이어그램 생성기** | 답변에 포함될 구조/흐름 다이어그램을 자동 생성 (Mermaid, PlantUML 등) | Swimm: 다이어그램 포함 답변 제공 |
| 7-5 | **채팅 인터페이스 / 세션 관리** | 대화형 UI, 대화 이력 관리, 후속 질문 컨텍스트 유지 | Swimm: Ask Swimm 채팅, Kodesage: 프롬프트 질의 + 대화 이력 |
| 7-6 | **답변→문서 변환 (지식 축적)** | 유용한 답변을 문서로 저장하여 지식 베이스에 축적 | Swimm: 답변을 문서화해 팀 지식으로 축적 |

### 선후관계

```
[5. Knowledge Base] → 컨텍스트 검색(7-1) → LLM 오케스트레이션(7-2)
                                                    ↓
                                           할루시네이션 방지(7-3)
                                                    ↓
                                     다이어그램 생성(7-4) + 채팅 인터페이스(7-5)
                                                    ↓
                                           답변→문서 변환(7-6)
```

---

## 8. Ask Kodesage (AI 질의응답)

> 레거시 자산에 대한 자연어 질의를 답변하고 컨텍스트/평가 기능을 제공한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 8-1 | **컨텍스트 검색 엔진 (RAG Retrieval)** | 7-1과 동일. 레거시 코드에 특화된 검색 가중치/필터링 필요 | Kodesage: 컨텍스트/우선순위/태깅/강제 설정 |
| 8-2 | **LLM 오케스트레이션** | 7-2와 동일 | — |
| 8-3 | **답변 평가(피드백) 시스템** | 사용자가 답변에 Good/Bad/코멘트를 남기고, 이를 품질 개선에 반영하는 피드백 루프 | Kodesage: 답변 평가(Good/Bad/코멘트) 기능 명시 |
| 8-4 | **컨텍스트 설정 / 태깅** | 사용자가 질의 범위(레포, 모듈, 태그)를 지정하고 우선순위를 설정하는 기능 | Kodesage: 컨텍스트/우선순위/태깅/강제 설정 |
| 8-5 | **채팅 인터페이스 / 세션 관리** | 7-5와 동일 | — |

### 7번(Ask Swimm)과의 공통/차이

| 구분 | Ask Swimm | Ask Kodesage | 공통 |
|---|---|---|---|
| 고유 | 다이어그램 생성, 답변→문서 변환 | 답변 평가 시스템, 컨텍스트 태깅/강제 설정 | 컨텍스트 검색, LLM 오케스트레이션, 채팅 인터페이스 |

---

## 9. 배포/엔터프라이즈 플랜

> 클라우드/온프렘 배포 옵션과 엔터프라이즈 지원을 제공한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 9-1 | **컨테이너화 / 오케스트레이션** | 모든 서비스를 Docker 컨테이너로 패키징하고 Kubernetes 등으로 오케스트레이션 | CAST Imaging: 컨테이너 기반 배포, SonarQube: Docker/K8s 지원, Qodana: installer CLI |
| 9-2 | **설치 자동화 (Installer/CLI)** | 온프렘 고객을 위한 자동화된 설치 도구(CLI, Ansible, Helm Chart 등) | CAST Imaging: CLI 자동화, Qodana Self-Hosted Lite: installer CLI 제공 |
| 9-3 | **리소스 사이징 / 스케일링** | 분석 대상 규모(LOC)에 따라 필요 리소스(CPU/메모리/스토리지)를 산정하고 스케일링 정책 제공 | SonarQube: LOC별 reference architecture (10M LOC: 4vCPU, 8GB RAM), Compute Engine 워커 수 조절 |
| 9-4 | **데이터 격리 / 멀티테넌시** | SaaS 환경에서 고객 간 데이터 격리 보장, 또는 온프렘에서의 단일 테넌트 배포 | Swimm: 100% in-network 로컬 모드, CAST Imaging: 에어갭 배포 지원 |
| 9-5 | **라이선스 / 플랜 관리** | 기능별 접근 제어(Free/Pro/Enterprise), 사용량 기반 과금, 라이선스 키 검증 | SonarQube: Community/Developer/Enterprise/Data Center 에디션별 기능 차등 |

### 선후관계

```
컨테이너화(9-1) → 설치 자동화(9-2)
      ↓
리소스 사이징(9-3) + 데이터 격리(9-4)
      ↓
라이선스/플랜 관리(9-5)
```

---

## 10. Enterprise Operation

> 엔터프라이즈 환경에서 안정적으로 운영/대규모 분석을 수행하도록 지원한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 10-1 | **분석 스케줄러 / 작업 큐** | 대규모 분석 작업을 스케줄링하고, 우선순위 기반으로 큐잉·실행·재시도 | CAST Imaging: CLI 기반 분석 자동화 (fast-scan → deep analysis → publish), SonarQube: Compute Engine 워커 |
| 10-2 | **시스템 모니터링 / 헬스체크** | 서비스 상태, 리소스 사용량, 분석 진행률을 실시간 모니터링 | SonarQube: Prometheus 기반 모니터링 |
| 10-3 | **장애 복구 / 데이터 백업** | 분석 중단 시 재개, 정기 백업, 복구 절차 | SonarQube: DB 백업/복구, CAST Imaging: 스냅샷 보관 |
| 10-4 | **감사 로그 / 접근 추적** | 누가 언제 어떤 분석을 실행했는지, 어떤 데이터에 접근했는지 추적 | Swimm: SOC2/ISO 인증을 위한 감사 로그, CAST Imaging: Auth Service |

### 선후관계

```
분석 스케줄러(10-1) → 시스템 모니터링(10-2)
                            ↓
              장애 복구(10-3) + 감사 로그(10-4)
```

---

## 11. CI/CD 연동

> CI/CD 이벤트와 결합해 분석/자동화를 연결한다.

### 전제 기능

| # | 전제 기능 | 설명 | 근거/참고 |
|---|---|---|---|
| 11-1 | **웹훅 수신 엔드포인트** | GitHub/GitLab/Jenkins 등에서 발생하는 PR/Push/Pipeline 이벤트를 수신하는 API | SonarQube: GitHub App 웹훅, GitLab CI 연동. AWS CodePipeline: Git 웹훅 기반 이벤트 수신 |
| 11-2 | **이벤트 매핑 / 라우팅** | 수신된 이벤트를 내부 분석 작업(전체 분석/Diff 분석/리포트 생성)으로 매핑하는 규칙 엔진 | CodeScene: PR/MR 이벤트 → 분석 트리거 매핑 |
| 11-3 | **분석 트리거 / 실행** | 매핑된 분석 작업을 자동으로 실행. 10번(Enterprise Operation)의 작업 큐와 연계 | SonarQube: CI 파이프라인 내 SonarScanner 실행, CAST Imaging: CLI 자동화 |
| 11-4 | **결과 리포팅 (PR 코멘트/Status Check)** | 분석 결과를 PR 코멘트, Commit Status, Quality Gate로 리포팅 | SonarQube: GitHub PR decoration, Quality Gate 상태 리포팅. CodeScene: PR 코멘트 |
| 11-5 | **플랫폼별 플러그인/앱** | GitHub App, GitLab Integration, Jenkins Plugin 등 각 플랫폼 고유의 연동 방식 지원 | CodeScene: Jenkins 플러그인, SonarQube: GitHub App + GitLab Integration |

### 선후관계

```
웹훅 수신(11-1) → 이벤트 매핑(11-2) → 분석 트리거(11-3)
                                              ↓
                            결과 리포팅(11-4) + 플랫폼별 플러그인(11-5)
```

---

## Must Have 기능 간 의존 관계

Must Have 기능들은 서로 독립적이지 않으며, 아래와 같은 선후 의존이 존재합니다.

```
[1. Source Code Ingestion] ──→ [3. Static Structure Analysis]
[2. Data Sources]          ──→         ↓
                               [4. 비즈니스 규칙 추출]
                                       ↓
                               [5. Knowledge Base Construction]
                                       ↓
                            ┌──────────┼──────────┐
                            ↓          ↓          ↓
                     [6. Change    [7. Ask     [8. Ask
                      Impact]      Swimm]     Kodesage]
                            ↓
                     [11. CI/CD 연동]

[9. 배포/엔터프라이즈] ──→ [10. Enterprise Operation]
```

### 구현 우선순위 제안 (시니어 개발자 관점)

| Phase | 기능 | 이유 |
|---|---|---|
| **Phase 1 (기반)** | 1. Source Code Ingestion + 2. Data Sources | 모든 분석의 입력. 이것 없이는 아무것도 시작 불가 |
| **Phase 2 (분석 코어)** | 3. Static Structure Analysis | 정적 분석은 4, 5, 6번의 공통 전제 조건 |
| **Phase 3 (지식 구축)** | 5. Knowledge Base Construction + 4. 비즈니스 규칙 추출 | 분석 결과를 저장·탐색 가능하게 만들어야 이후 기능이 의미 있음 |
| **Phase 4 (사용자 가치)** | 7. Ask Swimm + 8. Ask Kodesage | 지식 베이스 위에서 동작하는 최종 사용자 가치. 여기서 제품 차별화 |
| **Phase 5 (변경 분석)** | 6. Change Impact Analysis + 11. CI/CD 연동 | 일상 워크플로우에 녹아드는 기능. Phase 2~3의 산출물 필요 |
| **Phase 6 (엔터프라이즈)** | 9. 배포/엔터프라이즈 + 10. Enterprise Operation | 제품이 동작하는 상태에서 안정적으로 운영하기 위한 기능 |
