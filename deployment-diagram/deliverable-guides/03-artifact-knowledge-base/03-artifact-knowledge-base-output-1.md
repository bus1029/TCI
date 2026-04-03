# Artifact / Knowledge Base 산출물 #1

출처: [https://www.notion.so/336c21d54f4280a99829da3ac916970f](https://www.notion.so/336c21d54f4280a99829da3ac916970f)

## 범위와 가정

- 이 초안은 `1. Artifact 이름 및 Node 매핑표`만 작성한다.
- 기본 대상은 TCI 내부 7개 Node다.
- 다만 메인 Deployment Diagram 정합성을 위해 Foundation Services의 대표 Artifact 2개도 함께 정의한다.
- 외부 연동 채널과 데이터 소스는 TCI가 직접 배포하는 Artifact 범위에서 제외한다.
- 모든 내부 Node에는 `웹 애플리케이션 1개`가 배포된다고 가정한다.
- 따라서 현재 표의 Artifact 이름은 기술 구현체라기보다 `Node별 대표 배포 웹 애플리케이션`을 뜻한다.

## 1. Artifact 이름 및 Node 매핑표

| Artifact 이름 | 담당 Node | 역할 | 표시 수준 | 비고 |
| --- | --- | --- | --- | --- |
| Web Application Web App Artifact | Web Application | 사용자 진입, 인증/인가, 세션 관리, API 라우팅 | 메인 그림 표시 | public |
| IDE Plugin Artifact | IDE Plugin | 로컬 코드 변경 스냅샷 수집, 분석 컨텍스트 조회 | 메인 그림 표시 | public |
| Interactive Assistant Web App Artifact | Interactive Assistant | 대화형 질의응답, 코드베이스 설명, 구조·규칙 설명 | 메인 그림 표시 | private |
| Analysis Engine Web App Artifact | Analysis Engine | 구조 분석, 영향도 분석, 테스트 영향 분석, 규칙 추출 | 메인 그림 표시 | private |
| Workflow & Integration Web App Artifact | Workflow & Integration | PR 자동화, 외부 연동, 리포트 생성, 워크플로우 실행 | 메인 그림 표시 | private |
| Graph Artifact | Knowledge Base | 구조 지식, 의존성, 규칙, CPG 계열 데이터 저장 | 내부 Artifact | data. Graph DB Runtime Environment에 배포 |
| Vector Artifact | Knowledge Base | 임베딩 및 유사도 검색 데이터 저장 | 내부 Artifact | data. Vector DB Runtime Environment에 배포 |
| Object Artifact | Knowledge Base | 원본 문서, 스냅샷, 산출물 파일 저장 | 내부 Artifact | data. Object Storage Runtime Environment에 배포 |
| Data Processing Web App Artifact | Data Processing | CPG 생성, 임베딩 생성, 규칙 패턴 식별, KB 적재 | 메인 그림 표시 | private |
| Data Collection Web App Artifact | Data Collection | 개발 자산 수집, 증분 동기화, 업로드 처리 | 메인 그림 표시 | private |
| LLM Provider Artifact | Public LLM Provider / Local LLM | 대화 추론, 임베딩 API 제공 | 메인 그림 표시 | external. LLM Inference Runtime에 배포되는 외부 Foundation Artifact |
| Platform Service Artifact | Platform & Infra | 인증/인가, 로그, 모니터링, 운영 공통 기능 제공 | 메인 그림 표시 | external. Platform Service Runtime에 배포되는 외부 Foundation Artifact |

## 초안 메모

- 이 표는 `Node당 대표 Artifact 1개`라는 단순화 버전이다.
- 다만 `Knowledge Base`는 예외적으로 `Node당 대표 Artifact 1개` 원칙을 따르지 않는다.
- `Knowledge Base`는 저장 계층 성격이 강하므로 단일 웹 애플리케이션 Artifact로 두지 않고, `Graph Artifact`, `Vector Artifact`, `Object Artifact`로 분해한다.
- 인덱싱 관련 저장 계층은 별도 Runtime/Artifact로 분리하지 않고, 이번 단계에서는 위 3개 계층 설명 안에 흡수한다.
- `Web App Artifact`라는 이름은 현재 사용자의 가정을 반영한 임시 명칭이다. 최종본에서는 `Service Artifact` 또는 기술 실체에 더 가까운 이름으로 정리할 수 있다.
- Foundation Services는 TCI 내부 배포 대상은 아니지만, 메인 Deployment Diagram에 실제로 표시되는 Artifact이므로 이 문서에서 함께 관리한다.

## 2. 기존 01 문서 Artifact 명칭 정리

`01-node-boundary-service-output-1.md`에서 사용하던 EE 관점의 Artifact 명칭은 이 문서 기준으로 아래처럼 정리한다.

| 01 문서의 기존 명칭 | 이 문서의 기준 명칭 | 비고 |
|---|---|---|
| User Access Artifact | Web Application Web App Artifact | Web Application 대표 Artifact |
| Conversational QA Artifact | Interactive Assistant Web App Artifact | Interactive Assistant 대표 Artifact |
| Analysis Service Artifact | Analysis Engine Web App Artifact | Analysis Engine 대표 Artifact |
| Automation & Integration Artifact | Workflow & Integration Web App Artifact | Workflow & Integration 대표 Artifact |
| Collection Agent Artifact | Data Collection Web App Artifact | Data Collection 대표 Artifact |
| Data Pipeline Artifact | Data Processing Web App Artifact | Data Processing 대표 Artifact |
| Graph DB | Graph Artifact | Knowledge Base 내부 Artifact |
| Vector DB | Vector Artifact | Knowledge Base 내부 Artifact |
| Object Storage | Object Artifact | Knowledge Base 내부 Artifact |
| LLM Provider Artifact | LLM Provider Artifact | Foundation Service Artifact. 명칭 유지 |
| Platform Service Artifact | Platform Service Artifact | Foundation Service Artifact. 명칭 유지 |

## 3. Knowledge Base 표현 결정표

### 기본 원칙

- 메인 그림에서는 `Knowledge Base`를 단일 상위 Node로 유지한다.
- 다만 `Knowledge Base`는 일반 서비스 Node와 달리 단일 웹 애플리케이션 Artifact로 표현하지 않는다.
- `Knowledge Base Node`는 물리 서버 1대를 뜻하는 것이 아니라, 데이터 계층의 논리적 상위 경계로 해석한다.
- `Knowledge Base Node` 내부에는 3개의 별도 `Runtime Environment`가 존재한다고 가정한다.
- 각 `Runtime Environment`에는 1개의 전용 DB Artifact가 배포된다고 가정한다.
- 따라서 Knowledge Base의 표현 수준은 `Knowledge Base Node -> Runtime Environment -> DB Artifact`로 잡는다.

### 표현 결정표

| 논리 요소 | Runtime Environment | DB Artifact | 메인 그림 표시 | 표현 방식 이유 | 비고 |
|---|---|---|---|---|---|
| Graph Store | Graph DB Runtime Environment | Graph Artifact | 예 | 구조 지식, 의존성, 규칙, CPG 계열 데이터를 담당하는 핵심 저장 계층이므로 독립 표현 가치가 높다 | 그래프 계열 DB 인스턴스 가정 |
| Vector Store | Vector DB Runtime Environment | Vector Artifact | 예 | 임베딩 및 유사도 검색 계층은 Graph/Object와 성격과 접근 패턴이 다르므로 별도 Runtime으로 분리하는 편이 자연스럽다 | 벡터 DB 인스턴스 가정 |
| Object Store | Object Storage Runtime Environment | Object Artifact | 예 | 원본 문서, 스냅샷, 산출물 파일 보관 계층은 DB형 저장소와 운영 특성이 달라 별도 Runtime으로 두는 편이 명확하다 | 오브젝트 스토리지 인스턴스 가정 |

### 추가 메모

- 이 결정표는 `Knowledge Base`를 단일 Node로 유지하면서도 내부 저장 계층의 이질성을 드러내기 위한 절충안이다.
- 즉, 메인 다이어그램의 상위 경계는 단순하게 유지하고, `Knowledge Base` 내부에서만 세부 저장 구조를 한 단계 더 드러낸다.
- 이 방식은 `각 DB가 실제로는 별도 인스턴스/별도 런타임에서 동작한다`는 가정을 표현하기에 적합하다.
- 인덱싱 관련 기능은 별도 Search Runtime/Artifact로 승격하지 않고, Vector 또는 Graph 계층의 내부 책임으로 본다.
- 반대로 `Query Facade`, `Schema Manager`, `Retention Manager` 같은 논리 컴포넌트는 이번 단계에서 `Runtime Environment`나 `Artifact`로 승격하지 않는다.
