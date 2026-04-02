# Node / 경계 / 서비스 표 가이드

## 목적

Node 선정, 서비스 배치, 상위 경계처럼 구조 뼈대를 잡는 산출물을 한 묶음의 표 문서로 설명한다.

## 언제 이 문서를 보는가

- 무엇을 Node로 넣을지 정할 때
- 서비스별 위치를 배정할 때
- `public / private / external / data` 경계를 나눌 때
- Execution Environment를 top-level Node와 분리해 적을 때

## 이 문서에서 별도 메모로 두지 않는 항목

- `Node를 어디까지 쪼갤지에 대한 기준 메모`
- `사용자에게 보이는 서비스 / 내부 서비스 구분 메모`

위 항목들은 각각 별도 문서로 분리하지 않고, `포함할 Node / 제외할 Node 목록`의 이유 컬럼과 `서비스 Node 매핑 초안`의 기준 섹션 또는 컬럼에 흡수하는 편이 더 효율적이다.

## 1. 포함할 Node / 제외할 Node 목록

### 이 산출물이 하는 일

메인 그림에 어떤 Node를 넣고 어떤 Node를 빼는지 확정한다.

### 권장 형태

- 짧은 목록 문서
- 포함 목록과 제외 목록을 분리

### 예시 형태

```md
## 포함할 Node
| Node | 이유 | 경계 | 비고 |
|---|---|---|---|
| Web Application | 사용자 진입점 | public | 필수 |
| IDE Plugin | public client node | public | Web Application 경유 |
| Knowledge Base | 중앙 지식 허브 | data | 내부 Artifact 구분 |

## 제외할 Node
| Node | 제외 이유 | 대체 표현 | 비고 |
|---|---|---|---|
| Browser Runtime | 메인 그림 추상화보다 낮음 | 사용자 액터 | 상세 그림 후보 |
| Execution Environment | top-level Node로 세지 않음 | Node 내부 nested EE | 범위 포함 가능 |
```

### 완료 기준

- 포함과 제외가 분리되어 있다
- 각 항목에 이유가 있다

## 2. 서비스 Node 매핑 초안

### 이 산출물이 하는 일

C2 컨테이너를 Deployment Diagram Node로 매핑한다. 이 표 안에 Node 분해 기준과 사용자 노출 여부도 함께 담는다.

### 권장 형태

- 표 문서

### 예시 형태

```md
## 매핑 기준
- C2 컨테이너 1개를 Deployment Node 1개로 본다
- Execution Environment는 범위에 포함하되 top-level Node로 승격하지 않는다
- 내부 컴포넌트는 Node로 승격하지 않는다

| C2 컨테이너 | Deployment Node | 상위 경계 | 사용자 노출 여부 | 이유 |
|---|---|---|---|---|
| Web Application | Web Application Node | public | 예 | 단일 진입점 |
| IDE Plugin | IDE Plugin Node | public | 예 | public client node |
| Data Collection | Data Collection Node | private | 아니오 | 내부 수집 계층 |
```

### 완료 기준

- 모든 C2 컨테이너가 빠짐없이 등장한다

## 3. 서비스별 제공 위치 표

### 이 산출물이 하는 일

각 서비스가 어느 Node와 어느 경계에서 제공되는지 보여준다.

### 권장 형태

- 서비스 기준 표

### 예시 형태

```md
| 서비스 | 제공 Node | 상위 경계 | 접근 주체 | 비고 |
|---|---|---|---|---|
| Web UI | Web Application Node | public | 사용자 | 메인 진입 |
| 분석 서비스 | Analysis Engine Node | private | 내부 서비스 | 직접 접근 없음 |
```

### 완료 기준

- 서비스와 Node가 분리되어 있다

## 4. 상위 경계 초안

### 이 산출물이 하는 일

메인 그림의 큰 구역인 `public / private / external / data`를 배치한다.

### 권장 형태

- 경계별 섹션 문서

### 예시 형태

```md
## public
- 포함 Node: Web Application, IDE Plugin

## private
- 포함 Node: Data Collection, Data Processing, Analysis Engine, Interactive Assistant, Workflow & Integration

## data
- 포함 Node: Knowledge Base

## external
- 포함 Node: C1 외부 시스템 전체
```

### 완료 기준

- 4개 경계가 모두 정의돼 있다

## 5. 우리 시스템 / 외부 서비스 구분표

### 이 산출물이 하는 일

각 대상이 우리 통제 범위 안인지 밖인지 명확히 한다.

### 권장 형태

- 소유 경계 표

### 예시 형태

```md
| 대상 | 구분 | 통제 수준 | 비고 |
|---|---|---|---|
| Web Application Node | 우리 시스템 | 직접 통제 | public |
| IDE Plugin Node | 우리 시스템 | 직접 통제 | public client |
| Code Repository | 외부 서비스 | 연동만 가능 | external |
```

### 완료 기준

- 우리 시스템과 외부 서비스가 혼재되지 않는다
